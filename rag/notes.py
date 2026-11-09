"""Note eligibility and whole-note reading, independent of search and synchronization."""

from pathlib import Path, PurePosixPath

from rag import config


def is_note(path: str) -> bool:
    """Whether a repository-relative path is an eligible Markdown note."""
    note = PurePosixPath(path)
    folder = PurePosixPath(config.NOTES_DIR.relative_to(config.ROOT).as_posix())
    if not note.is_relative_to(folder):
        return False
    relative = note.relative_to(folder)
    return (
        note.suffix == ".md"
        and not any(part.startswith(".") for part in relative.parts)
        and not any(relative.is_relative_to(skipped) for skipped in config.SKIP_FOLDERS)
    )


def read_note(path: str) -> str:
    """Read the current working-tree note. This is the only note-reading backend."""
    note = Path(path)
    if not note.is_absolute():
        note = config.ROOT / note
    message = f"No note at {path}. Use a path from search_notes."
    # Both the requested path and the file it really points to (after symlinks) must be notes.
    if not note.is_relative_to(config.NOTES_DIR) or not is_note(
        note.relative_to(config.ROOT).as_posix()
    ):
        raise ValueError(message)
    note = note.resolve()
    if (
        not note.is_relative_to(config.NOTES_DIR.resolve())
        or not is_note(note.relative_to(config.ROOT.resolve()).as_posix())
        or not note.is_file()
    ):
        raise ValueError(message)
    return note.read_bytes().decode("utf-8-sig", errors="replace")
