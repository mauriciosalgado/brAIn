"""The notes in the repository: which files are notes, and what they say on the searched branch.

The index follows one branch (`config.BRANCH`), whichever branch is checked out. Notes are read
from that branch's commits, never from the working tree, so work in progress and other branches
never reach the index.
"""

import contextlib
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from rag import config
from rag.notes import git

_NOTES_DIR = config.NOTES_DIR.relative_to(config.ROOT).as_posix()


def branch_tip() -> str:
    """The latest commit of the searched branch."""
    try:
        return git.branch_tip(config.BRANCH)
    except git.GitError as error:
        raise git.GitError(
            f"No '{config.BRANCH}' branch with commits in {config.ROOT} ({error}). "
            "Set branch in brain.toml (or BRAIN_BRANCH) to the branch your notes are on."
        ) from error


def _is_note(path: str) -> bool:
    """A Markdown file in notes/, not in a hidden folder (.trash) or one skipped in brain.toml."""
    relative = PurePosixPath(path).relative_to(_NOTES_DIR)
    hidden = any(part.startswith(".") for part in relative.parts)
    skipped = any(relative.is_relative_to(folder) for folder in config.SKIP_FOLDERS)
    return path.endswith(".md") and not hidden and not skipped


def list_notes(commit: str) -> list[str]:
    """Every note in `commit`."""
    return [path for path in git.list_files(commit, _NOTES_DIR) if _is_note(path)]


def changed_notes(since: str, until: str) -> tuple[list[str], list[str]]:
    """The notes to (re)index and to remove to go from commit `since` to `until`."""
    changed, removed = git.changed_files(since, until, _NOTES_DIR)
    return [p for p in changed if _is_note(p)], [p for p in removed if _is_note(p)]


def read_notes(commit: str, paths: list[str]) -> Iterator[tuple[str, bytes]]:
    """Yield (path, content) of each note as it is in `commit`."""
    return git.read_files(commit, paths)


def read_note(path: str) -> str:
    """The note at `path` (relative to the repository, or absolute) as it is on the branch."""
    with contextlib.suppress(ValueError):  # a path that is already relative
        path = Path(path).relative_to(config.ROOT).as_posix()
    commit = branch_tip()
    if path not in list_notes(commit):
        raise ValueError(f"No note at {path} on {config.BRANCH}. Use a path from search_notes.")
    ((_, content),) = read_notes(commit, [path])
    return content.decode("utf-8-sig", errors="replace")
