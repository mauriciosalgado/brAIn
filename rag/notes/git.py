"""Plain git: the tip of a branch, what changed between commits, and the files in a commit.

Files are read from a commit, never from the working tree. It knows nothing about notes.
"""

import subprocess
from collections.abc import Iterator

from rag import config


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
    return _run("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}").strip()


def changed_files(since: str, until: str, folder: str) -> tuple[list[str], list[str]]:
    """The files under `folder` to add or update, and to remove, to go from commit `since` to
    `until`. Paths are relative to the repository. A rename is a removal plus an addition."""
    output = _run("diff", "--name-status", "--no-renames", "-z", since, until, "--", folder)
    fields = _split(output)  # status, path, status, path, ...
    changed, removed = [], []
    for status, path in zip(fields[::2], fields[1::2], strict=True):
        (removed if status == "D" else changed).append(path)
    return changed, removed


def list_files(commit: str, folder: str) -> list[str]:
    """Every file under `folder` in `commit`."""
    return _split(_run("ls-tree", "-r", "-z", "--name-only", commit, "--", folder))


def read_files(commit: str, paths: list[str]) -> Iterator[tuple[str, bytes]]:
    """Yield (path, content) of each file as it is in `commit`."""
    if not paths:
        return
    command = ["git", "-C", str(config.ROOT), "cat-file", "--batch"]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
        assert process.stdin and process.stdout
        for path in paths:  # one request, one answer: "<id> blob <size>", content, newline
            process.stdin.write(f"{commit}:{path}\n".encode())
            process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3 or header[1] != b"blob":
                raise GitError(f"{path} is not in commit {commit[:7]}")
            size = int(header[2])
            yield path, process.stdout.read(size + 1)[:size]  # +1 for the newline after it
