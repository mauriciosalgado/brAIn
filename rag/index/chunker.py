"""Split Markdown into independent sections with a shared description string."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt

from rag.config import DOCUMENT_CONTEXT_CHARS, MAX_CHUNK_SIZE, SKIP_HEADINGS

_PARSER = MarkdownIt("commonmark").enable("table")

# Frontmatter opens the file and looks like `key: value` (or a comment), so a note that merely
# starts with a `---` rule is not mistaken for one.
_FRONTMATTER = re.compile(
    r"\A---[ \t]*\n(?=[^\n]*:|[ \t]*#).*?\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.DOTALL
)
_SKIPPED_HEADINGS = {heading.lower() for heading in SKIP_HEADINGS}
_TAG_LINE = re.compile(r"^ {0,3}Tags:\s*(#.*)", re.IGNORECASE)
_BREAKS = ("\n\n", "\n", " ")  # where a long text may be cut, best first
_LONGEST_PATH_NAME = 100  # a setext "heading" can be a whole paragraph


@dataclass
class Chunk:
    text: str
    header_path: str  # the headings above the chunk, for example "Title > Section"
    chunk_index: int  # its position in the note
    context: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def embedding_text(self) -> str:
        """What gets embedded: the chunk with its section path, so headings are searchable."""
        context = f"Context: {self.context}\n\n" if self.context else ""
        return f"Section: {self.header_path}\n\n{context}{self.text}"


@dataclass
class Heading:
    level: int
    name: str
    line: int  # where it starts


@dataclass
class Section:
    """The lines [start, end) under one heading path."""

    path: str
    start: int
    end: int


def chunk_markdown(text: str, source: str) -> list[Chunk]:
    """The chunks of a note, in reading order. `source` is the note's path."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = _blank_out_frontmatter(text).split("\n")
    headings = _headings(lines)
    title = _note_title(headings, source)

    sections = _sections(headings, lines, title)
    context = _document_context(lines, headings, sections)
    tags = _take_tags(lines, headings, sections)
    chunks = []
    for section in sections:
        body = _trim("\n".join(lines[section.start : section.end]))
        if not _has_content(body):
            continue
        for part in _chunk_section(body):
            if _has_content(part):
                chunks.append(
                    Chunk(
                        text=part,
                        header_path=section.path,
                        chunk_index=len(chunks),
                        context=context,
                        tags=tags,
                    )
                )
    return chunks


def _document_context(lines: list[str], headings: list[Heading], sections: list[Section]) -> str:
    """First prose paragraph below # Title, before Links/Tags; no generated or Summary fallback."""
    if not headings or headings[0].level != 1:
        return ""
    intro = next((s for s in sections if s.start == headings[0].line), None)
    if intro is None:
        return ""
    own = lines[intro.start : intro.end]
    for token in _PARSER.parse("\n".join(own)):
        if token.type == "paragraph_open" and token.level == 0 and token.map:
            start, end = token.map
            for line in range(start, end):
                if re.match(r"^ {0,3}(?:links|tags):", own[line], re.IGNORECASE):
                    end = line
                    break
            paragraph = "\n".join(own[start:end]).strip()
            if len(paragraph) <= DOCUMENT_CONTEXT_CHARS:
                return paragraph
            return paragraph[:DOCUMENT_CONTEXT_CHARS].rsplit(" ", 1)[0]
    return ""


def _take_tags(lines: list[str], headings: list[Heading], sections: list[Section]) -> list[str]:
    """Extract introductory Tags: lines, leaving code, quotes, lists and later sections alone."""
    intro_end = headings[0].line if headings else len(lines)
    if headings and headings[0].level == 1:
        for section in sections:
            if section.start == headings[0].line:
                intro_end = section.end
                break

    tags: list[str] = []
    for token in _PARSER.parse("\n".join(lines[:intro_end])):
        if token.type != "paragraph_open" or token.level != 0 or token.map is None:
            continue
        for line in range(*token.map):
            match = _TAG_LINE.match(lines[line])
            if match is None:
                continue
            for value in re.findall(r"(?<!\S)#([^\s#]+)", match[1]):
                tag = value.lower()
                if tag not in tags:
                    tags.append(tag)
            lines[line] = ""
    return tags


def _chunk_section(text: str) -> list[str]:
    """Pack a section's Markdown blocks into chunk bodies, splitting oversized blocks first."""
    if len(text) <= MAX_CHUNK_SIZE:
        return [text]
    lines = text.split("\n")
    block_types: dict[int, str | None] = {0: None}
    for token in _PARSER.parse(text):
        if token.level == 0 and token.map is not None:
            block_types[token.map[0]] = token.type
    starts = sorted(block_types)
    pieces = []
    ends = [*starts[1:], len(lines)]
    for start, end in zip(starts, ends, strict=True):
        block = _trim("\n".join(lines[start:end]))
        if not block:
            continue
        pieces.extend(_split_block(block, block_types[start]))
    packed: list[str] = []
    for piece in pieces:
        if packed and len(packed[-1]) + 2 + len(piece) <= MAX_CHUNK_SIZE:
            packed[-1] += "\n\n" + piece
        else:
            packed.append(piece)
    return packed


def _split_block(block: str, kind: str | None) -> list[str]:
    if len(block) <= MAX_CHUNK_SIZE:
        return [block]
    if kind == "fence":
        opening, *body = block.split("\n")
        marker = re.match(r"\s*(`{3,}|~{3,})", opening)
        assert marker is not None
        closing = marker[1]
        if body and re.fullmatch(rf"\s*{closing[0]}{{{len(closing)},}}\s*", body[-1]):
            body.pop()
        room = MAX_CHUNK_SIZE - len(opening) - len(closing) - 2
        if room > 0:
            return [f"{opening}\n{part}\n{closing}" for part in _split_text("\n".join(body), room)]
    elif kind == "table_open":
        lines = block.split("\n")
        header = "\n".join(lines[:2])
        room = MAX_CHUNK_SIZE - len(header) - 1
        if room > 0:
            rows = "\n".join(lines[2:])
            return [header + "\n" + part for part in _split_text(rows, room, ("\n", " "))]
    elif kind in ("bullet_list_open", "ordered_list_open"):
        lines = block.split("\n")
        starts = [
            t.map[0]
            for t in _PARSER.parse(block)
            if t.type == "list_item_open" and t.level == 1 and t.map
        ]
        parts = []
        ends = [*starts[1:], len(lines)]
        for start, end in zip(starts, ends, strict=True):
            parts.extend(_split_text("\n".join(lines[start:end]), MAX_CHUNK_SIZE))
        return parts
    return _split_text(block, MAX_CHUNK_SIZE)


def _blank_out_frontmatter(text: str) -> str:
    """Blank lines in place of the frontmatter, so line numbers stay the same."""
    match = _FRONTMATTER.match(text)
    if not match:
        return text
    return "\n" * match.group(0).count("\n") + text[match.end() :]


def _headings(lines: list[str]) -> list[Heading]:
    tokens = _PARSER.parse("\n".join(lines))
    return [
        Heading(int(token.tag[1]), _plain_text(tokens[i + 1]), token.map[0])
        for i, token in enumerate(tokens)
        if token.type == "heading_open" and token.map and not token.level  # level 0: top level
    ]


def _plain_text(inline) -> str:
    """The text of a heading without its markup. Line breaks become spaces."""
    parts = []
    for child in inline.children or []:
        if child.type in ("text", "code_inline", "image"):  # an image gives its alt text
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts).strip()


def _note_title(headings: list[Heading], source: str) -> str:
    """The first heading if it is a `#` heading, else the file name as words."""
    if headings and headings[0].level == 1 and headings[0].name:
        return _shorten(headings[0].name)
    return Path(source).stem.replace("-", " ").title()


def _shorten(name: str) -> str:
    if len(name) <= _LONGEST_PATH_NAME:
        return name
    return name[: _LONGEST_PATH_NAME - 1].rstrip() + "…"


def _sections(headings: list[Heading], lines: list[str], title: str) -> list[Section]:
    """One section per heading, plus the text before the first heading. A skipped heading and its
    sub-headings are left out."""
    sections: list[Section] = []
    if not headings or headings[0].line > 0:
        end = headings[0].line if headings else len(lines)
        sections.append(Section(title, 0, end))

    skipped_level = None  # the level of the skipped heading we are inside, if any
    stack: list[Heading] = []
    for i, heading in enumerate(headings):
        if skipped_level is not None and heading.level > skipped_level:
            continue  # a sub-heading of a skipped heading
        if heading.name.lower() in _SKIPPED_HEADINGS:
            skipped_level = heading.level
            continue
        skipped_level = None
        while stack and stack[-1].level >= heading.level:
            stack.pop()
        stack.append(heading)
        end = headings[i + 1].line if i + 1 < len(headings) else len(lines)
        path = _heading_path(stack, title)
        sections.append(Section(path, heading.line, end))
    return sections


def _heading_path(headings: list[Heading], title: str) -> str:
    """The names joined by " > ". The note's title comes first unless it has its own `#`."""
    names = [_shorten(heading.name) for heading in headings]
    if headings[0].level != 1:
        names.insert(0, title)
    elif not names[0]:
        names[0] = title
    return " > ".join(name for name in names if name)


def _split_text(text: str, limit: int, breaks: tuple[str, ...] = _BREAKS) -> list[str]:
    """Pieces of at most `limit` characters, cut at the first kind of break that works."""
    text = _trim(text)
    if len(text) <= limit:
        return [text] if text else []
    if not breaks:
        return [text[i : i + limit] for i in range(0, len(text), limit)]
    pieces: list[str] = []
    current = ""
    separator = breaks[0]
    for part in text.split(separator):
        fitting_parts = [part]
        if len(part) > limit:
            fitting_parts = _split_text(part, limit, breaks[1:])
        for fitting in fitting_parts:
            joined = current + separator + fitting if current else fitting
            if len(joined) <= limit:
                current = joined
            else:
                pieces.append(current)
                current = fitting
    pieces.append(current)
    return [piece.rstrip() for piece in pieces if piece.strip()]


def _trim(text: str) -> str:
    """Without blank lines at the start or whitespace at the end. The first line keeps its
    indentation, which can be what makes it code and not a heading."""
    return re.sub(r"\A(?:[ \t]*\n)+", "", text).rstrip()


def _has_content(text: str) -> bool:
    """Headings and thematic rules alone are not answer content."""
    text = _trim(text)
    lines = text.split("\n")
    for token in _PARSER.parse(text):
        if token.type in ("heading_open", "hr") and not token.level and token.map:
            start, end = token.map
            lines[start:end] = [""] * (end - start)
    return any(line.strip() for line in lines)
