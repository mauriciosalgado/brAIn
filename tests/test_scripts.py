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


def fake_old_git(directory: Path) -> None:
    executable = directory / "git"
    executable.write_text(
        '#!/bin/sh\nif [ "$1" = cat-file ]; then exit 129; fi\nexec /usr/bin/git "$@"\n'
    )
    executable.chmod(0o755)


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
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
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


def test_setup_can_be_run_again(clone, tmp_path):
    path = fake_uv(tmp_path / "bin", tmp_path / "uv.log")
    for _ in range(2):
        assert run(clone / "setup.sh", path=path).returncode == 0
    assert git(clone, "config", "--local", "core.hooksPath") == ".githooks"


@pytest.mark.parametrize("scope", ["local", "global"])
def test_setup_enables_required_hooks_even_when_another_path_is_configured(clone, tmp_path, scope):
    if scope == "local":
        git(clone, "config", "--local", "core.hooksPath", "my-hooks")
    else:
        (clone / ".gitconfig").write_text("[core]\n\thooksPath = my-hooks\n")
    result = run(clone / "setup.sh", path=fake_uv(tmp_path / "bin", tmp_path / "uv.log"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(clone, "config", "--local", "core.hooksPath") == ".githooks"
    assert "Replacing core.hooksPath 'my-hooks'" in result.stdout
    assert "other hooks will no longer run" in result.stdout
    assert "All good" in result.stdout


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


def test_setup_stops_before_installing_when_git_lacks_required_batch_support(clone, tmp_path):
    log = tmp_path / "uv.log"
    path = fake_uv(tmp_path / "bin", log)
    fake_old_git(tmp_path / "bin")
    result = run(clone / "setup.sh", path=path)
    assert result.returncode == 1 and "Git 2.42+" in result.stdout
    assert not log.exists()


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
    assert "✓ git 2.42+ installed" in result.stdout and "Fix the issues above" in result.stdout


def test_doctor_reports_unsupported_git_without_stopping_other_checks(clone, tmp_path):
    healthy_clone(clone)
    path = fake_uv(tmp_path / "bin", tmp_path / "uv.log")
    fake_old_git(tmp_path / "bin")
    result = run(clone / "doctor.sh", path=path)
    assert result.returncode == 1 and "✗ git 2.42+ installed" in result.stdout
    assert result.stdout.count("✗") == 1 and result.stdout.count("✓") == 8


@pytest.mark.parametrize("scope", ["local", "global"])
def test_doctor_is_happy_when_everything_is_in_place(clone, tmp_path, scope):
    if scope == "local":
        healthy_clone(clone)
    else:
        (clone / ".gitconfig").write_text("[core]\n\thooksPath = .githooks\n")
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


# ---- the hooks themselves -------------------------------------------------------------------


@pytest.mark.parametrize("update", ["merge", "rebase"])
def test_git_updates_trigger_sync_without_a_client(clone, tmp_path, update):
    log = tmp_path / "uv.log"
    path = fake_uv(tmp_path / "bin", log)
    result = run(clone / "setup.sh", path=path)
    assert result.returncode == 0, result.stdout + result.stderr
    log.unlink()
    git(clone, "config", "user.name", "Test")
    git(clone, "config", "user.email", "test@example.com")
    git(clone, "config", "commit.gpgsign", "false")
    git(clone, "add", ".")
    git(clone, "commit", "-q", "-m", "baseline")
    branch = git(clone, "branch", "--show-current")
    git(clone, "checkout", "-q", "-b", "incoming")
    (clone / "notes").mkdir()
    (clone / "notes" / "new.md").write_text("# New note\n\nPulled content.\n")
    git(clone, "add", "notes")
    git(clone, "commit", "-q", "-m", "new note")
    git(clone, "checkout", "-q", branch)
    if update == "rebase":
        (clone / "local.txt").write_text("local change\n")
        git(clone, "add", "local.txt")
        git(clone, "commit", "-q", "-m", "local change")
    assert not log.exists()
    subprocess.run(
        ["git", update, "incoming"],
        cwd=clone,
        env={"PATH": path, "HOME": str(clone)},
        capture_output=True,
        text=True,
        check=True,
    )
    wait_for(log)
    assert log.read_text().strip() == f"{clone.resolve()}: run rag sync"
    assert (clone / "notes" / "new.md").read_text() == "# New note\n\nPulled content.\n"


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


@pytest.mark.skipif(
    any(shutil.which("uv", path=p) for p in ("/opt/homebrew/bin", "/usr/local/bin")),
    reason="uv is installed in a location the hook falls back to",
)
def test_hook_without_uv_never_breaks_git(clone, tmp_path):
    result = run_hook(clone, "post-merge", SYSTEM_PATH, tmp_path / "nohome")
    assert result.returncode == 0 and "uv not found" in result.stderr
