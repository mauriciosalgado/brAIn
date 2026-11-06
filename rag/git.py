"""Everything brAIn needs from git.

The index follows one branch (`config.BRANCH`), whichever branch is checked out: the notes git
reports as added, modified or deleted there since the last sync are indexed, re-indexed or
removed. Notes are read from that commit, never from the working tree, so work in progress and
other branches never reach the index.
"""

import subprocess
from collections.abc import Iterator

from rag import config


class GitError(RuntimeError):
    pass


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(config.ROOT), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except FileNotFoundError as error:
        raise GitError("git is not installed") from error
    except subprocess.CalledProcessError as error:
        raise GitError(error.stderr.strip() or "git failed") from error
    return result.stdout


def main_commit() -> str:
    """The tip of the branch the index follows."""
    try:
        return _git(
            "rev-parse", "--verify", "--quiet", f"refs/heads/{config.BRANCH}^{{commit}}"
        ).strip()
    except GitError as error:
        raise GitError(
            f"No '{config.BRANCH}' branch with commits in {config.ROOT} ({error}). "
            "Set BRAIN_BRANCH to the branch your team merges notes into."
        ) from error


def _notes_dir() -> str:
    return config.NOTES_DIR.relative_to(config.ROOT).as_posix()


def _split(output: str) -> list[str]:
    return output.split("\0")[:-1]  # -z output ends with a separator


def changed_notes(since: str, until: str) -> tuple[list[str], list[str]]:
    """The paths under notes/ to (re)index and to remove to go from commit `since` to `until`.
    Paths are relative to the repository. A rename is a removal of the old path plus an addition
    of the new one."""
    output = _git("diff", "--name-status", "--no-renames", "-z", since, until, "--", _notes_dir())
    fields = _split(output)  # status, path, status, path, ...
    to_index, to_remove = [], []
    for status, path in zip(fields[::2], fields[1::2], strict=True):
        (to_remove if status == "D" else to_index).append(path)
    return to_index, to_remove


def list_notes(commit: str) -> list[str]:
    """Every file under notes/ in `commit`."""
    return _split(_git("ls-tree", "-r", "-z", "--name-only", commit, "--", _notes_dir()))


def read_notes(commit: str, paths: list[str]) -> Iterator[tuple[str, bytes]]:
    """Yield (path, content) as the notes are in `commit`, not in the working tree."""
    if not paths:
        return
    command = ["git", "-C", str(config.ROOT), "cat-file", "--batch"]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
        for path in paths:  # one request, one answer: "<id> blob <size>", content, newline
            process.stdin.write(f"{commit}:{path}\n".encode())
            process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3 or header[1] != b"blob":
                raise GitError(f"{path} is not in commit {commit[:7]}")
            size = int(header[2])
            yield path, process.stdout.read(size + 1)[:size]  # +1 for the newline after it
