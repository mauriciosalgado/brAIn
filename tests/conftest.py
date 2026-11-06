"""Every test gets a time limit, so an infinite loop fails loudly instead of hanging the suite."""

import signal
import subprocess
from pathlib import Path

import pytest

from rag import config

LIMIT_SECONDS = 60
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


@pytest.fixture(autouse=True)
def _time_limit():
    def too_slow(*_):
        raise TimeoutError(f"test took more than {LIMIT_SECONDS} s")

    previous = signal.signal(signal.SIGALRM, too_slow)
    signal.alarm(LIMIT_SECONDS)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, previous)


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """A git repository with an empty notes/ folder and a private index, so tests never touch
    the real ones. The user's own git settings (signing, hooks) are ignored."""
    notes = tmp_path / "notes"
    notes.mkdir()
    rag_dir = tmp_path / ".rag"
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "NOTES_DIR", notes)
    monkeypatch.setattr(config, "RAG_DIR", rag_dir)
    monkeypatch.setattr(config, "DB_DIR", rag_dir / "lancedb")
    monkeypatch.setattr(config, "LOCK_PATH", rag_dir / "sync.lock")
    for name, value in GIT_ENV.items():
        monkeypatch.setenv(name, value)
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / ".gitignore").write_text(".rag/\n")  # as in the real repository
    return notes


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.fixture
def commit(vault):
    """Commits everything in the vault, as a teammate's push or your own commit would."""

    def run(message: str = "notes") -> str:
        git(vault.parent, "add", "-A")
        git(vault.parent, "commit", "-q", "--allow-empty", "-m", message)
        return git(vault.parent, "rev-parse", "HEAD")

    return run


@pytest.fixture
def vault_git(vault):
    """Runs a git command in the vault's repository."""
    return lambda *args: git(vault.parent, *args)
