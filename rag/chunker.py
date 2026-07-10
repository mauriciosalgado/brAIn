import re
import logging
from dataclasses import dataclass
from pathlib import Path
from rag.config import MAX_CHUNK_SIZE, MIN_CHUNK_SIZE, SKIP_HEADERS

logger = logging.getLogger(__name__)


@dataclass()
class Chunk:
    id: str
    text: str
    source: str
    header_path: str
    chunk_index: int


def _header_level(header: str) -> int:
    """Return the header level (number of #)"""
    return len(header.split()[0])  # Count leading #


def _build_header_path(title: str, header_stack: dict[int, str]):
    """Build header path like 'Title > H2 > H3'"""
    parts = [header_stack[level] for level in sorted(header_stack)]
    if title:
        return " > ".join([title] + parts)
    return " > ".join(parts)


def _content_length(chunk_text: str) -> int:
    """Calculate content length, excluding whitespace"""
    lines = chunk_text.strip().splitlines()
    if lines and re.match(r"^#{2,6}\s+", lines[0]):
        # If first line is a header, exclude it from content length
        lines = lines[1:]
    return len("".join(lines).strip())


def _extract_preamble(text: str, matches: list[re.Match]) -> str:
    """Extract note description, between H1 and first H2"""
    if len(matches) < 2:
        return ""

    raw = text[matches[0].end() : matches[1].start()]
    lines = []
    for line in raw.strip().splitlines():
        if re.match(r"^(Tags:|Links:|---|<!--)", line):
            break
        lines.append(line)
    preamble = "\n".join(lines).strip()
    return preamble


def _build_chunks(
    text: str, preamble: str, matches: list[re.Match], source: str, title: str
) -> list[Chunk]:
    """Build chunks based on header matches. Uses a stack to track current header path."""

    chunks = []
    header_stack = {}

    for i in range(1, len(matches)):
        match = matches[i]
        header = match.group(1).strip()
        header_name = header.lstrip("#").strip()

        if header_name in SKIP_HEADERS:
            continue

        header_level = _header_level(header)
        header_stack = {k: v for k, v in header_stack.items() if k < header_level}
        header_stack[header_level] = header.lstrip("#").strip()

        start = match.start()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        chunk = text[start:end].strip()

        # Warn if chunk is too large
        if len(chunk) > MAX_CHUNK_SIZE:
            logger.warning(f"Large chunk ({len(chunk)} chars) in {source}: {header}")

        chunks.append(
            Chunk(
                id=f"{source}#{i}",
                text=chunk,
                source=source,
                header_path=_build_header_path(title, header_stack),
                chunk_index=i,
            )
        )

    return chunks


def _merge_small_chunks(chunks: list[Chunk], source: str) -> list[Chunk]:
    """Merge chunks smaller than MIN_CHUNK_SIZE into previous chunk"""
    merged = []

    for chunk in chunks:
        content_is_small = _content_length(chunk.text) < MIN_CHUNK_SIZE
        has_previous_chunk = len(merged) > 0

        if content_is_small and has_previous_chunk:
            merged[-1].text += "\n\n" + chunk.text
        else:
            merged.append(chunk)

    for i, chunk in enumerate(merged):
        chunk.id = f"{source}#{i}"
        chunk.chunk_index = i

    return merged


def _chunk_markdown(text: str, filepath: Path) -> tuple[str, list[Chunk]]:
    """Chunk markdown text based on headers. Returns preamble and list of chunks."""
    source = str(filepath)

    # Pattern: line starts with 1-6 #, followed by space
    header_pattern = re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE)

    # Find all header positions in file buffer
    matches = list(header_pattern.finditer(text))

    if not matches:
        # No headers, return the whole text as one chunk
        return "", [
            Chunk(id="0", text=text, source=source, header_path="", chunk_index=0)
        ]

    # Extract title from first header if it exists
    title = matches[0].group(1).lstrip("#").strip()
    preamble = _extract_preamble(text, matches)
    chunks = _build_chunks(
        text=text, preamble="", matches=matches, source=source, title=title
    )
    chunks = _merge_small_chunks(chunks, source)

    return preamble, chunks


def get_chunks(filepath: str | Path) -> tuple[str, list[Chunk]]:
    if isinstance(filepath, str):
        filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    text = filepath.read_text()
    preamble, chunks = _chunk_markdown(text, filepath)

    return preamble, chunks
