"""Local Git state, note-change plans, and raw committed-file reads. No working-tree reads."""

import subprocess
from collections.abc import Iterator
from typing import IO

from rag import config
from rag.notes import is_note

_NOTES_DIR = config.NOTES_DIR.relative_to(config.ROOT).as_posix()


class GitError(RuntimeError):
    pass


def _run(*args: str, input_text: str | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(config.ROOT), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            input=input_text,
        )
    except FileNotFoundError as error:
        raise GitError("git is not installed") from error
    except subprocess.CalledProcessError as error:
        raise GitError(error.stderr.strip() or "git failed") from error
    return result.stdout


def _split(output: str) -> list[str]:
    return output.split("\0")[:-1]  # -z output ends with a separator


def remote_branch_tip(remote: str, branch: str) -> str:
    """The last fetched or pushed commit of a remote branch."""
    try:
        return _run("show-ref", "--verify", "--hash", f"refs/remotes/{remote}/{branch}").strip()
    except GitError as error:
        raise GitError(
            f"No '{remote}/{branch}' remote-tracking branch in {config.ROOT} ({error}). "
            "Check remote and branch in brain.toml (or BRAIN_BRANCH), then fetch the remote. "
            "Local commits are not indexed until pushed."
        ) from error


def changed_notes(since: str, until: str) -> tuple[list[str], list[str]]:
    """Notes to index and remove between commits. A rename is a removal plus an addition."""
    output = _run("diff", "--name-status", "--no-renames", "-z", since, until, "--", _NOTES_DIR)
    fields = _split(output)  # status, path, status, path, ...
    changed, removed = [], []
    for status, path in zip(fields[::2], fields[1::2], strict=True):
        if is_note(path):
            (removed if status == "D" else changed).append(path)
    return changed, removed


def list_notes(commit: str) -> list[str]:
    """Eligible note paths in a commit."""
    paths = _split(_run("ls-tree", "-r", "-z", "--name-only", commit, "--", _NOTES_DIR))
    return [path for path in paths if is_note(path)]


def plan_index(
    since: str | None, head: str, indexed_paths: set[str]
) -> tuple[list[str], list[str]]:
    """Plan replacements and removals from commits and known paths, without accessing the DB."""
    if since == head:
        return [], []
    if since:
        kind = _run("cat-file", "--batch-check=%(objecttype)", input_text=f"{since}\n").strip()
        if kind == "commit":
            return changed_notes(since, head)
        if kind != f"{since} missing":
            raise GitError(f"{since} is not a commit")
    current = sorted(list_notes(head))
    return current, sorted(indexed_paths - set(current))


def _blob_size(fields: list[bytes], commit: str, path: str) -> int:
    if len(fields) != 3 or fields[1] != b"blob" or not fields[2].isdigit():
        raise GitError(f"{path} is not in commit {commit[:7]}")
    return int(fields[2])


def file_sizes(commit: str, paths: list[str]) -> dict[str, int]:
    """Read committed blob sizes in one batch, without requesting their contents."""
    if not paths:
        return {}
    output = _run(
        "cat-file",
        "--batch-check",
        "-Z",
        input_text="".join(f"{commit}:{path}\0" for path in paths),
    )
    headers = _split(output)
    if len(headers) != len(paths):
        raise GitError("git cat-file returned an incomplete size listing")
    return {
        path: _blob_size(header.encode().split(), commit, path)
        for path, header in zip(paths, headers, strict=True)
    }


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
            size = _blob_size(_read_header(process.stdout), commit, path)
            content = process.stdout.read(size)
            if len(content) != size or process.stdout.read(1) != b"\0":
                raise GitError(f"Incomplete committed file: {path}")
            yield path, content
    if process.returncode:
        raise GitError("git cat-file failed")
