"""Turns a Markdown note into chunks, the pieces a search returns.

A chunk is the text under one heading, with its heading path ("Title > Section"). A Markdown
parser finds the headings, so a `#` in a code block or a quote is never one. A section that is too
long is split at paragraph, line or word breaks; one that is too short joins its neighbour.
Sections under a skipped heading are left out.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from markdown_it import MarkdownIt

from rag.config import MAX_CHUNK_SIZE, MIN_CHUNK_SIZE, SKIP_HEADINGS

_PARSER = MarkdownIt("commonmark")

# Frontmatter opens the file and looks like `key: value` (or a comment), so a note that merely
# starts with a `---` rule is not mistaken for one.
_FRONTMATTER = re.compile(
    r"\A---[ \t]*\n(?=[^\n]*:|[ \t]*#).*?\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.DOTALL
)
_SKIPPED_HEADINGS = {heading.lower() for heading in SKIP_HEADINGS}
_BREAKS = ("\n\n", "\n", " ")  # where a long text may be cut, best first
_LONGEST_PATH_NAME = 100  # a setext "heading" can be a whole paragraph


@dataclass
class Chunk:
    text: str
    header_path: str  # the headings above the chunk, for example "Title > Section"
    chunk_index: int  # its position in the note

    @property
    def embedding_text(self) -> str:
        """What gets embedded: the chunk with its section path, so headings are searchable."""
        return f"Section: {self.header_path}\n\n{self.text}"


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


class Piece(NamedTuple):
    """Text that may become a chunk, under one heading path."""

    path: str
    text: str
    whole_section: bool  # the text is all of its section, not a part of a section that was split


def chunk_markdown(text: str, source: str) -> list[Chunk]:
    """The chunks of a note, in reading order. `source` is the note's path."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = _blank_out_frontmatter(text).split("\n")
    headings = _headings(lines)
    title = _note_title(headings, source)

    pieces: list[Piece] = []
    for section in _sections(headings, lines, title):
        section_text = "\n".join(lines[section.start : section.end])
        if _content_length(section_text) > 0:  # a heading with nothing under it makes no chunk
            texts = _split(section_text, MAX_CHUNK_SIZE)
            pieces += [Piece(section.path, text, len(texts) == 1) for text in texts]

    return [Chunk(p.text, p.path, i) for i, p in enumerate(_merge_tiny(pieces))]


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

    names_above: dict[int, str] = {}  # heading level -> name
    skipped_level = None  # the level of the skipped heading we are inside, if any
    for i, heading in enumerate(headings):
        if skipped_level is not None and heading.level > skipped_level:
            continue  # a sub-heading of a skipped heading
        if heading.name.lower() in _SKIPPED_HEADINGS:
            skipped_level = heading.level
            continue
        skipped_level = None
        name = _shorten(heading.name)
        if not name and heading.level == 1:
            name = title  # an empty `#` heading takes the note's title
        names_above = {lv: above for lv, above in names_above.items() if lv < heading.level}
        names_above[heading.level] = name
        end = headings[i + 1].line if i + 1 < len(headings) else len(lines)
        path = _heading_path(names_above, title)
        sections.append(Section(path, heading.line, end))
    return sections


def _heading_path(names_above: dict[int, str], title: str) -> str:
    """The names joined by " > ". The note's title comes first unless it has its own `#`."""
    names = ([] if 1 in names_above else [title]) + [
        names_above[level] for level in sorted(names_above)
    ]
    return " > ".join(name for name in names if name)


def _split(text: str, limit: int, breaks: tuple[str, ...] = _BREAKS) -> list[str]:
    """Pieces of at most `limit` characters, cut at the first kind of break that works."""
    text = _trim(text)
    if len(text) <= limit:
        return [text] if text else []
    if not breaks:
        return [text[i : i + limit] for i in range(0, len(text), limit)]
    pieces: list[str] = []
    current = ""
    for part in text.split(breaks[0]):
        for fitting in _split(part, limit, breaks[1:]) if len(part) > limit else [part]:
            joined = current + breaks[0] + fitting if current else fitting
            if len(joined) <= limit:
                current = joined
            else:
                pieces.append(current)
                current = fitting
    return [piece.rstrip() for piece in [*pieces, current] if piece.strip()]


def _merge_tiny(pieces: list[Piece]) -> list[Piece]:
    """Join a tiny piece to the piece before it, or, for a tiny start (often a title and a line of
    tags), to the piece after, while the result still fits. A piece of a long section is only
    joined within its own section, so a chunk never sits under the wrong heading path."""
    merged: list[Piece] = []
    for piece in pieces:
        if len(merged) == 1 and _is_tiny(merged[0].text) and _fits(merged[0].text, piece.text):
            merged[0] = piece._replace(text=merged[0].text + "\n\n" + piece.text)
        elif (
            merged
            and _is_tiny(piece.text)
            and _fits(merged[-1].text, piece.text)
            and (piece.whole_section or merged[-1].path == piece.path)
        ):
            merged[-1] = merged[-1]._replace(text=merged[-1].text + "\n\n" + piece.text)
        else:
            merged.append(piece)
    return merged


def _trim(text: str) -> str:
    """Without blank lines at the start or whitespace at the end. The first line keeps its
    indentation, which can be what makes it code and not a heading."""
    return re.sub(r"\A(?:[ \t]*\n)+", "", text).rstrip()


def _content_length(text: str) -> int:
    """The content length without a leading Markdown heading or whitespace."""
    text = _trim(text)
    lines = text.split("\n")
    tokens = _PARSER.parse(text.split("\n\n", 1)[0])
    if tokens and tokens[0].type == "heading_open" and tokens[0].map:
        lines = lines[tokens[0].map[1] :]
    return len("".join(lines).strip())


def _is_tiny(text: str) -> bool:
    return _content_length(text) < MIN_CHUNK_SIZE


def _fits(first: str, second: str) -> bool:
    return len(first) + 2 + len(second) <= MAX_CHUNK_SIZE  # 2 for the blank line between them
