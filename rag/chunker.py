"""Markdown -> chunks that follow the structure of the note.

Headings come from markdown-it-py's CommonMark parser, so `#` inside code fences, quotes or
HTML is never a heading. A chunk is one section (or a part of an oversized one), prefixed
with its heading path. Oversized sections are split at block boundaries: code fences stay
valid (re-fenced when cut) and tables repeat their header row. Tiny sections are merged into
a neighbour.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt

from rag.config import MAX_CHUNK_SIZE, MIN_CHUNK_SIZE, SKIP_HEADERS

_md = MarkdownIt("commonmark").enable("table")
# Frontmatter must open the file and look like `key: value` (or a comment), so a note that
# merely starts with a `---` rule is not mistaken for one.
_FRONTMATTER = re.compile(
    r"\A---[ \t]*\n(?=[^\n]*:|[ \t]*#).*?\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.DOTALL
)
_SKIP = {h.lower() for h in SKIP_HEADERS}
# A heading longer than this is really a paragraph (text followed by `---` is a heading): it stays
# in the text, is not repeated on every chunk, and only its start shows in paths.
_MAX_HEADER = MAX_CHUNK_SIZE // 4
_LABEL = 100


@dataclass
class Chunk:
    text: str
    header_path: str  # the headings above the chunk, for example "Title > Section"
    chunk_index: int  # its position in the note

    @property
    def embedding_text(self) -> str:
        """What gets embedded: the chunk with its section breadcrumb, so headings are searchable."""
        return f"Section: {self.header_path}\n\n{self.text}"


@dataclass
class Heading:
    level: int
    name: str
    line: int


@dataclass
class Block:
    """A top-level Markdown block as the line range [start, end). `kind` is "fence", "table"
    or "" for anything else."""

    start: int
    end: int
    kind: str = ""


@dataclass
class Fence:
    """A fenced code block at any depth (also inside lists and quotes)."""

    start: int
    end: int
    marker: str


@dataclass
class Section:
    """Lines [start, end) of the note under one header path.

    `header` is the heading line, repeated on every chunk of an oversized section.
    """

    path: str
    start: int
    end: int
    header: str = ""


def _strip_frontmatter(text: str) -> str:
    """Blank out the frontmatter, so line numbers stay stable."""
    match = _FRONTMATTER.match(text)
    if not match:
        return text
    return "\n" * match.group(0).count("\n") + text[match.end() :]


def _label(name: str) -> str:
    """A heading name as shown in a path: whole, or cut when it is a paragraph."""
    return name if len(name) <= _MAX_HEADER else name[: _LABEL - 1].rstrip() + "…"


def _heading_text(inline) -> str:
    """Plain text of a heading: markup is dropped, line breaks become spaces."""
    parts = []
    for child in inline.children or []:
        if child.type in (
            "text",
            "code_inline",
            "image",
        ):  # an image contributes its alt text
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts).strip()


def _scan(lines: list[str]) -> tuple[list[Heading], list[Block], dict[int, Fence]]:
    tokens = _md.parse("\n".join(lines))
    headings, blocks, fences, heading_lines = [], [], {}, set()
    for i, tok in enumerate(tokens):
        if not tok.map or tok.nesting < 0:
            continue
        if tok.type == "fence":
            fences[tok.map[0]] = Fence(tok.map[0], tok.map[1], tok.markup)
        if tok.level:
            continue
        if tok.type == "heading_open":
            name = _heading_text(tokens[i + 1])
            headings.append(Heading(int(tok.tag[1]), name, tok.map[0]))
            heading_lines.update(range(*tok.map))
            if len(name) > _MAX_HEADER:  # a paragraph: the path only shows its start
                blocks.append(Block(tok.map[0], tok.map[1]))
        else:
            kind = {"fence": "fence", "table_open": "table"}.get(tok.type, "")
            blocks.append(Block(tok.map[0], tok.map[1], kind))
    return headings, _with_gaps(blocks, lines, heading_lines), fences


def _with_gaps(blocks: list[Block], lines: list[str], heading_lines: set[int]) -> list[Block]:
    """Add blocks for text the parser emits no block for (e.g. `[1]: url` link definitions)."""
    filled, cursor = [], 0
    for block in blocks:
        filled += _text_runs(lines, cursor, block.start, heading_lines)
        filled.append(block)
        cursor = block.end
    return filled + _text_runs(lines, cursor, len(lines), heading_lines)


def _text_runs(lines: list[str], start: int, end: int, skip: set[int]) -> list[Block]:
    """Blocks for runs of non-blank, non-heading lines in [start, end)."""
    runs, run_start = [], None
    for i in range(start, end + 1):
        if i < end and i not in skip:
            run_start = i if run_start is None else run_start
        elif run_start is not None:
            if any(line.strip() for line in lines[run_start:i]):
                runs.append(Block(run_start, i))
            run_start = None
    return runs


def _sections(headings: list[Heading], lines: list[str], title: str) -> list[Section]:
    """One section per indexable heading, plus any text before the first heading.

    Sections under a skipped heading (References, Table of Contents) are left out.
    """
    sections = []
    first = headings[0].line if headings else len(lines)
    if first > 0:
        sections.append(Section(title, 0, first))

    path: dict[int, str] = {}  # heading level -> name, for the current position
    skipped_level = None
    for i, heading in enumerate(headings):
        end = headings[i + 1].line if i + 1 < len(headings) else len(lines)
        if skipped_level is not None and heading.level > skipped_level:
            continue
        skipped_level = heading.level if heading.name.lower() in _SKIP else None
        if skipped_level is not None:
            continue
        path = {level: name for level, name in path.items() if level < heading.level}
        path[heading.level] = _label(heading.name) or (title if heading.level == 1 else "")
        names = ([] if 1 in path else [title]) + [path[level] for level in sorted(path)]
        header = lines[heading.line] if len(heading.name) <= _MAX_HEADER else ""
        sections.append(Section(" > ".join(n for n in names if n), heading.line, end, header))
    return sections


def _trim(text: str) -> str:
    """Without leading blank lines and trailing whitespace; the first line keeps its indentation,
    which can be what makes it code."""
    return re.sub(r"\A(?:[ \t]*\n)+", "", text).rstrip()


def _body_len(text: str) -> int:
    """Length of a chunk's content, ignoring its heading line and whitespace."""
    lines = _trim(text).splitlines()
    if lines and re.match(r" {0,3}#{1,6}(?:\s|$)", lines[0]):
        lines = lines[1:]
    return len("".join(lines).strip())


def _cut(text: str, limit: int) -> list[str]:
    """Cut text into pieces of at most `limit` characters, at spaces where possible."""
    if limit < 1:
        raise ValueError(f"cannot cut text into pieces of {limit} characters")
    pieces = []
    while len(text) > limit:
        cut = text.rfind(" ", 0, limit)
        cut = cut if cut > 0 else limit
        pieces.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return pieces + ([text] if text else [])


def _pack(units: list[str], limit: int, sep: str) -> list[str]:
    """Greedily join units with `sep` up to `limit`; an over-long unit is cut first."""
    packed, current = [], ""
    for piece in (p for unit in units for p in _cut(unit, limit)):
        candidate = f"{current}{sep}{piece}" if current else piece
        if current and len(candidate) > limit:
            packed.append(current)
            current = piece
        else:
            current = candidate
    return packed + ([current] if current else [])


def _fence_units(lines: list[str], marker: str, room: int) -> list[str]:
    """A code block as one unit, or as re-fenced pieces if it is longer than `room`."""
    text = "\n".join(lines).rstrip()
    if len(text) <= room:
        return [text]
    opener = lines[0]
    prefix = opener[: opener.index(marker)]  # indentation, or `> ` inside a quote
    if len(prefix) > room // 8:  # absurdly deep indentation
        prefix = ""
    closer = prefix + marker
    long_info = []
    if len(opener) > room // 4:  # a very long info string is really text: it goes before the fence
        long_info = [opener[len(prefix) + len(marker) :].strip()]
        opener = closer
    has_closer = len(lines) > 1 and re.fullmatch(
        f"{re.escape(marker[0])}{{{len(marker)},}}", lines[-1].strip(" >\t")
    )
    body = lines[1:-1] if has_closer else lines[1:]
    budget = room - len(opener) - len(closer) - 2
    return [t for t in long_info if t] + [
        f"{opener}\n{piece}\n{closer}" for piece in _pack(body, budget, "\n")
    ]


def _table_units(lines: list[str], room: int) -> list[str]:
    """A table as one unit, or as pieces that each repeat the header row."""
    text = "\n".join(lines)
    if len(text) <= room:
        return [text]
    header = "\n".join(lines[:2])
    if len(header) > room // 4:  # too wide to repeat on every piece
        return _pack(lines, room, "\n")
    return [f"{header}\n{rows}" for rows in _pack(lines[2:], room - len(header) - 1, "\n")]


def _block_units(lines: list[str], block: Block, fences: dict[int, Fence], room: int) -> list[str]:
    """The block as units of at most `room` characters: whole if it fits, else by line,
    keeping any code block inside it (for example in a list) together."""
    block_lines = lines[block.start : block.end]
    if len("\n".join(block_lines)) <= room:
        return ["\n".join(block_lines)]
    if block.kind == "fence":
        return _fence_units(block_lines, fences[block.start].marker, room)
    if block.kind == "table":
        return _table_units(block_lines, room)
    units, i = [], block.start
    while i < block.end:
        fence = fences.get(i)
        if fence and fence.end <= block.end:
            units += _fence_units(lines[fence.start : fence.end], fence.marker, room)
            i = fence.end
        else:
            units.append(lines[i])
            i += 1
    return _pack(units, room, "\n")


def _split(
    lines: list[str], section: Section, blocks: list[Block], fences: dict[int, Fence]
) -> list[str]:
    """Split one section into chunks of at most MAX_CHUNK_SIZE characters."""
    text = _trim("\n".join(lines[section.start : section.end]))
    if len(text) <= MAX_CHUNK_SIZE:
        return [text]
    prefix = f"{section.header}\n\n" if section.header else ""
    room = MAX_CHUNK_SIZE - len(prefix)
    units = []
    for block in blocks:
        if block.start >= section.start and block.end <= section.end:
            units += _block_units(lines, block, fences, room)
    return [prefix + piece for piece in _pack(units, room, "\n\n")]


def _tiny(text: str) -> bool:
    return _body_len(text) < MIN_CHUNK_SIZE


def _fits(first: str, second: str) -> bool:
    return len(first) + 2 + len(second) <= MAX_CHUNK_SIZE


def _merge_small(pieces: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Fold tiny pieces into a neighbour while the result still fits: into the previous piece, or,
    for a tiny start (often just a title and a tags line), into the piece that follows it."""
    merged: list[tuple[str, str]] = []
    for path, text in pieces:
        if merged and len(merged) == 1 and _tiny(merged[0][1]) and _fits(merged[0][1], text):
            merged[0] = (path, merged[0][1] + "\n\n" + text)
        elif merged and _tiny(text) and _fits(merged[-1][1], text):
            merged[-1] = (merged[-1][0], merged[-1][1] + "\n\n" + text)
        else:
            merged.append((path, text))
    return merged


def _title(headings: list[Heading], source: str) -> str:
    """The first heading if it is an H1, else the filename as words."""
    if headings and headings[0].level == 1 and headings[0].name:
        return _label(headings[0].name)
    return Path(source).stem.replace("-", " ").title()


def chunk_markdown(text: str, source: str) -> list[Chunk]:
    """The chunks of a note, in reading order. `source` is the note's path."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = _strip_frontmatter(text).split("\n")
    headings, blocks, fences = _scan(lines)
    title = _title(headings, source)

    pieces = []
    for section in _sections(headings, lines, title):
        if _body_len("\n".join(lines[section.start : section.end])) > 0:
            pieces += [(section.path, p) for p in _split(lines, section, blocks, fences)]

    return [Chunk(chunk_text, path, i) for i, (path, chunk_text) in enumerate(_merge_small(pieces))]
