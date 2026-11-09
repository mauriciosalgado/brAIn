"""Local Git state, note-change plans, and raw committed-file reads. No working-tree reads."""

import subprocess
from collections.abc import Iterator
from pathlib import PurePosixPath
from typing import IO

from rag import config

_NOTES_DIR = config.NOTES_DIR.relative_to(config.ROOT).as_posix()


class GitError(RuntimeError):
    pass


def _run(*args: str) -> str:
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


def _split(output: str) -> list[str]:
    return output.split("\0")[:-1]  # -z output ends with a separator


def branch_tip(branch: str) -> str:
    """The latest commit of `branch`."""
    try:
        return _run("show-ref", "--verify", "--hash", f"refs/heads/{branch}").strip()
    except GitError as error:
        raise GitError(
            f"No '{branch}' branch with commits in {config.ROOT} ({error}). "
            "Set branch in brain.toml (or BRAIN_BRANCH) to the branch your notes are on."
        ) from error


def _is_note(path: str) -> bool:
    """A Markdown file outside hidden folders and the configured exclusions."""
    relative = PurePosixPath(path).relative_to(_NOTES_DIR)
    hidden = any(part.startswith(".") for part in relative.parts)
    skipped = any(relative.is_relative_to(folder) for folder in config.SKIP_FOLDERS)
    return path.endswith(".md") and not hidden and not skipped


def changed_notes(since: str, until: str) -> tuple[list[str], list[str]]:
    """Notes to index and remove between commits. A rename is a removal plus an addition."""
    output = _run("diff", "--name-status", "--no-renames", "-z", since, until, "--", _NOTES_DIR)
    fields = _split(output)  # status, path, status, path, ...
    changed, removed = [], []
    for status, path in zip(fields[::2], fields[1::2], strict=True):
        if _is_note(path):
            (removed if status == "D" else changed).append(path)
    return changed, removed


def list_notes(commit: str) -> list[str]:
    """Eligible note paths in a commit."""
    paths = _split(_run("ls-tree", "-r", "-z", "--name-only", commit, "--", _NOTES_DIR))
    return [path for path in paths if _is_note(path)]


def plan_index(
    since: str | None, head: str, indexed_paths: set[str]
) -> tuple[list[str], list[str]]:
    """Plan replacements and removals from commits and known paths, without accessing the DB."""
    if since == head:
        return [], []
    if since:
        try:
            return changed_notes(since, head)
        except GitError:  # the previous commit may be gone after a history rewrite
            pass
    current = sorted(list_notes(head))
    return current, sorted(indexed_paths - set(current))


def _read_header(stream: IO[bytes]) -> list[bytes]:
    header = bytearray()
    while byte := stream.read(1):
        if byte == b"\0":
            return bytes(header).split()
        header.extend(byte)
    raise GitError("git cat-file ended before returning a file header")


def read_files(commit: str, paths: list[str]) -> Iterator[tuple[str, bytes]]:
    """Yield paths and raw file bytes from a local commit, without decoding or note validation."""
    if not paths:
        return
    command = ["git", "-C", str(config.ROOT), "cat-file", "--batch", "-Z"]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
        assert process.stdin and process.stdout
        for path in paths:  # NUL framing keeps filenames separate from the blob contents.
            process.stdin.write(f"{commit}:{path}\0".encode())
            process.stdin.flush()
            header = _read_header(process.stdout)
            if len(header) != 3 or header[1] != b"blob" or not header[2].isdigit():
                raise GitError(f"{path} is not in commit {commit[:7]}")
            size = int(header[2])
            content = process.stdout.read(size)
            if len(content) != size or process.stdout.read(1) != b"\0":
                raise GitError(f"Incomplete committed file: {path}")
            yield path, content
    if process.returncode:
        raise GitError("git cat-file failed")
