"""The shell scripts are run for real, in a throwaway git repository, with a fake `uv`."""

import shutil
import subprocess
import time
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
SYSTEM_PATH = "/usr/bin:/bin"
HOOKS = ("post-merge", "post-rewrite")


@pytest.fixture
def clone(tmp_path):
    """A git repository holding copies of the scripts."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for name in ("setup.sh", "doctor.sh"):
        shutil.copy2(PROJECT / name, repo / name)
    shutil.copytree(PROJECT / ".githooks", repo / ".githooks")
    return repo


def fake_uv(directory: Path, log: Path, behaviour: str = "") -> str:
    """A `uv` that records its calls and then runs `behaviour` (shell). Returns a PATH using it."""
    directory.mkdir(parents=True, exist_ok=True)
    uv = directory / "uv"
    uv.write_text(f'#!/bin/sh\necho "$PWD: $*" >> "{log}"\n{behaviour}\n')
    uv.chmod(0o755)
    return f"{directory}:{SYSTEM_PATH}"


def run(script: Path, *args: str, path: str = SYSTEM_PATH, home: Path | None = None):
    return subprocess.run(
        [str(script), *args],
        cwd=script.parent,
        env={"PATH": path, "HOME": str(home or script.parent)},
        capture_output=True,
        text=True,
        check=False,
    )


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def wait_for(path: Path) -> None:
    for _ in range(50):  # hooks sync in the background
        if path.exists():
            return
        time.sleep(0.1)


# ---- setup.sh -------------------------------------------------------------------------------


def test_setup_does_everything_in_order_and_ends_with_the_doctor(clone, tmp_path):
    log = tmp_path / "uv.log"
    result = run(clone / "setup.sh", path=fake_uv(tmp_path / "bin", log))
    assert result.returncode == 0, result.stdout + result.stderr
    calls = [line.split(": ", 1)[1] for line in log.read_text().splitlines()]
    assert calls[0] == "sync"
    assert calls[1] == "run rag model"  # fetched or repaired even when there is nothing to index
    assert calls[2] == "run rag sync"
    assert "sync --check" in calls[3]  # the doctor ran after the index was built
    assert git(clone, "config", "--local", "core.hooksPath") == ".githooks"
    assert "All good" in result.stdout


def test_setup_restores_the_executable_bit_of_the_hooks(clone, tmp_path):
    for hook in (clone / ".githooks").iterdir():
        hook.chmod(0o644)  # what a zip download or some file systems do
    assert (
        run(clone / "setup.sh", path=fake_uv(tmp_path / "bin", tmp_path / "uv.log")).returncode == 0
    )
    assert all((clone / ".githooks" / h).stat().st_mode & 0o111 for h in (*HOOKS, "sync-notes"))


def test_setup_can_be_run_again(clone, tmp_path):
    path = fake_uv(tmp_path / "bin", tmp_path / "uv.log")
    for _ in range(2):
        assert run(clone / "setup.sh", path=path).returncode == 0
    assert git(clone, "config", "--local", "core.hooksPath") == ".githooks"


def test_setup_does_not_override_another_hooks_path(clone, tmp_path):
    git(clone, "config", "--local", "core.hooksPath", "my-hooks")
    result = run(clone / "setup.sh", path=fake_uv(tmp_path / "bin", tmp_path / "uv.log"))
    assert git(clone, "config", "--local", "core.hooksPath") == "my-hooks"
    assert "left alone" in result.stdout


def test_setup_stops_when_a_step_fails(clone, tmp_path):
    path = fake_uv(
        tmp_path / "bin",
        tmp_path / "uv.log",
        'case "$*" in "run rag sync") exit 1;; esac',
    )
    result = run(clone / "setup.sh", path=path)
    assert result.returncode == 1 and "All good" not in result.stdout


def test_setup_without_uv_explains_how_to_get_it(clone):
    result = run(clone / "setup.sh")
    assert result.returncode == 1 and "✗ missing: uv" in result.stdout


def test_setup_outside_a_git_clone_fails(tmp_path):
    lone = tmp_path / "lone"
    lone.mkdir()
    shutil.copy2(PROJECT / "setup.sh", lone / "setup.sh")
    assert (
        run(lone / "setup.sh", path=fake_uv(tmp_path / "bin", tmp_path / "uv.log")).returncode != 0
    )


# ---- doctor.sh ------------------------------------------------------------------------------


def healthy_clone(clone: Path) -> None:
    git(clone, "config", "--local", "core.hooksPath", ".githooks")


def test_doctor_reports_everything_wrong_on_a_fresh_clone(clone):
    result = run(clone / "doctor.sh")
    assert result.returncode == 1
    for problem in (
        "✗ uv installed",
        "✗ embedding model works offline",
        "✗ git hooks enabled",
    ):
        assert problem in result.stdout
    assert "✓ git installed" in result.stdout and "Fix the issues above" in result.stdout


def test_doctor_is_happy_when_everything_is_in_place(clone, tmp_path):
    healthy_clone(clone)
    result = run(clone / "doctor.sh", path=fake_uv(tmp_path / "bin", tmp_path / "uv.log"))
    assert result.returncode == 0, result.stdout
    assert (
        "✗" not in result.stdout and result.stdout.count("✓") == 9 and "All good" in result.stdout
    )


@pytest.mark.parametrize(
    ("failing_call", "expected"),
    [
        ("sync --check", "✗ dependencies match uv.lock"),
        ("import rag.mcp.server", "✗ MCP server loads"),
        ("model_works", "✗ embedding model works offline"),
        ("rag status", "✗ index up to date"),
    ],
)
def test_doctor_flags_each_failing_check_and_only_that_one(clone, tmp_path, failing_call, expected):
    healthy_clone(clone)
    path = fake_uv(
        tmp_path / "bin",
        tmp_path / "uv.log",
        f'case "$*" in *"{failing_call}"*) exit 1;; esac',
    )
    result = run(clone / "doctor.sh", path=path)
    assert result.returncode == 1
    assert expected in result.stdout and result.stdout.count("✗") == 1


def test_doctor_checks_the_model_through_the_code_that_never_downloads(clone, tmp_path):
    healthy_clone(clone)
    log = tmp_path / "uv.log"
    run(clone / "doctor.sh", path=fake_uv(tmp_path / "bin", log))
    assert "embeddings.model_works()" in log.read_text()


@pytest.mark.parametrize("broken", ["missing", "not-executable"])
def test_doctor_flags_hooks_that_git_would_not_run(clone, tmp_path, broken):
    healthy_clone(clone)
    hook = clone / ".githooks" / "post-merge"
    if broken == "missing":
        hook.unlink()
    else:
        hook.chmod(0o644)
    result = run(clone / "doctor.sh", path=fake_uv(tmp_path / "bin", tmp_path / "uv.log"))
    assert "✗ git hooks enabled" in result.stdout and result.returncode == 1


def test_doctor_changes_nothing(clone, tmp_path):
    healthy_clone(clone)
    before = sorted(p.name for p in clone.rglob("*") if ".git/" not in str(p))
    run(clone / "doctor.sh", path=fake_uv(tmp_path / "bin", tmp_path / "uv.log"))
    assert sorted(p.name for p in clone.rglob("*") if ".git/" not in str(p)) == before


# ---- the hooks themselves -------------------------------------------------------------------


def run_hook(clone: Path, name: str, path: str, home: Path, *args: str, cwd: Path | None = None):
    return subprocess.run(
        [str(clone / ".githooks" / name), *args],
        cwd=cwd or clone,
        env={"PATH": path, "HOME": str(home)},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("name", HOOKS)
def test_every_hook_runs_sync_from_the_repository_root(clone, tmp_path, name):
    log = tmp_path / "uv.log"
    path = fake_uv(tmp_path / "bin", log)
    (clone / "notes").mkdir()
    result = run_hook(clone, name, path, tmp_path, cwd=clone / "notes")
    assert result.returncode == 0, result.stderr
    wait_for(log)
    assert log.read_text().strip() == f"{clone.resolve()}: run rag sync"


def test_hook_finds_uv_in_the_users_local_bin_when_git_has_a_minimal_path(clone, tmp_path):
    home = tmp_path / "home"
    log = tmp_path / "uv.log"
    fake_uv(home / ".local" / "bin", log)
    assert run_hook(clone, "post-merge", SYSTEM_PATH, home).returncode == 0
    wait_for(log)
    assert "run rag sync" in log.read_text()


def test_the_callers_uv_wins_over_the_fallback_locations(clone, tmp_path):
    home = tmp_path / "home"
    fake_uv(home / ".local" / "bin", tmp_path / "fallback.log")
    mine = fake_uv(tmp_path / "mine", tmp_path / "mine.log")
    run_hook(clone, "post-merge", mine, home)
    wait_for(tmp_path / "mine.log")
    assert (tmp_path / "mine.log").exists() and not (tmp_path / "fallback.log").exists()


@pytest.mark.skipif(
    any(shutil.which("uv", path=p) for p in ("/opt/homebrew/bin", "/usr/local/bin")),
    reason="uv is installed in a location the hook falls back to",
)
def test_hook_without_uv_never_breaks_git(clone, tmp_path):
    result = run_hook(clone, "post-merge", SYSTEM_PATH, tmp_path / "nohome")
    assert result.returncode == 0 and "uv not found" in result.stderr


def test_hook_outside_a_repository_does_nothing(tmp_path):
    shutil.copytree(PROJECT / ".githooks", tmp_path / ".githooks")
    result = subprocess.run(
        [str(tmp_path / ".githooks" / "post-merge")],
        cwd=tmp_path,
        env={"PATH": SYSTEM_PATH, "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
