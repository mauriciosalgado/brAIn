"""Local Git state, note-change plans, and raw committed-file reads. No working-tree reads."""

import subprocess

from rag import config
from rag.notes import is_note

_NOTES_DIR = config.NOTES_DIR.relative_to(config.ROOT).as_posix()  # as git paths: "notes"


class GitError(RuntimeError):
    """A git command failed, or the requested commit, branch or file does not exist."""


def _run_git(*args: str, input_text: str | None = None, errors: str = "replace") -> str:
    """Run `git <args>` in the repository and return its stdout as text. `input_text` is sent to
    stdin. Undecodable bytes are replaced unless `errors="strict"`, which raises ValueError.
    A failing command raises GitError with git's own message."""
    try:
        result = subprocess.run(
            ["git", "-C", str(config.ROOT), *args],
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
            errors=errors,
            input=input_text,
        )
    except FileNotFoundError as error:
        raise GitError("git is not installed") from error
    except subprocess.CalledProcessError as error:
        raise GitError(error.stderr.strip() or "git failed") from error
    return result.stdout


def _split_nul_output(output: str) -> list[str]:
    """Split Git's NUL-terminated fields without breaking filenames containing newlines."""
    return output.split("\0")[:-1]  # -z output ends with a separator


def remote_branch_tip(remote: str, branch: str) -> str:
    """The last fetched or pushed commit of a remote branch."""
    try:
        return _run_git("show-ref", "--verify", "--hash", f"refs/remotes/{remote}/{branch}").strip()
    except GitError as error:
        raise GitError(
            f"No '{remote}/{branch}' remote-tracking branch in {config.ROOT} ({error}). "
            "Check remote and branch in brain.toml (or BRAIN_BRANCH), then fetch the remote. "
            "Local commits are not indexed until pushed."
        ) from error


def notes_changed_between(since: str, until: str) -> tuple[list[str], list[str]]:
    """Diff two existing commits into changed and removed note paths.

    A rename is a removal plus an addition. Missing commits and other Git errors propagate.
    """
    output = _run_git("diff", "--name-status", "--no-renames", "-z", since, until, "--", _NOTES_DIR)
    fields = _split_nul_output(output)  # status, path, status, path, ...
    changed, removed = [], []
    for status, path in zip(fields[::2], fields[1::2], strict=True):
        if not is_note(path):
            continue
        if status == "D":
            removed.append(path)
        else:
            changed.append(path)
    return changed, removed


def list_committed_notes(commit: str) -> list[str]:
    """The paths of all notes (see `notes.is_note`) in a commit."""
    paths = _split_nul_output(
        _run_git("ls-tree", "-r", "-z", "--name-only", commit, "--", _NOTES_DIR)
    )
    return [path for path in paths if is_note(path)]


def plan_index(
    since: str | None, head: str, indexed_paths: set[str]
) -> tuple[list[str], list[str]]:
    """Choose the note updates needed to reach `head`, without touching the database.

    Use a commit diff when history exists, or all current notes when `since` is absent or gone.
    A full plan also removes `indexed_paths` no longer present in Git. The same commit needs no
    updates; unexpected Git errors propagate rather than becoming full plans.
    """
    if since == head:
        return [], []
    if since:
        # --batch-check prints "<sha> missing" for an unknown object, which is not an error
        object_type = _run_git(
            "cat-file", "--batch-check=%(objecttype)", input_text=f"{since}\n"
        ).strip()
        if object_type == "commit":
            return notes_changed_between(since, head)
        if object_type != f"{since} missing":
            raise GitError(f"{since} is not a commit")
    current = sorted(list_committed_notes(head))
    return current, sorted(indexed_paths - set(current))


def committed_file_size(commit: str, path: str) -> int:
    """The size in bytes of `path` as committed in `commit`, without reading its contents."""
    return int(_run_git("cat-file", "-s", f"{commit}:{path}"))


def read_committed_file(commit: str, path: str) -> str:
    """The text of `path` as committed in `commit`, not as edited in the working tree.
    Line endings become `\\n`, a leading byte order mark is removed, and invalid UTF-8 raises
    ValueError."""
    text = _run_git("cat-file", "blob", f"{commit}:{path}", errors="strict")
    return text.removeprefix("\ufeff")
