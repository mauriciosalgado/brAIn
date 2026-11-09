"""Scripts run in private Git repositories; main updates exercise the real indexer."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import lancedb
import pytest
from samples import AWS, CAKE, numbered

from rag import config
from rag.index.store import TABLE

PROJECT = Path(__file__).resolve().parents[1]
SYSTEM_PATH = "/usr/bin:/bin"
REF_UPDATE = f"{'0' * 40} {'1' * 40} refs/remotes/origin/main\n"


@pytest.fixture
def clone(tmp_path):
    """A git repository holding copies of the scripts."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    for name in ("setup.sh", "doctor.sh"):
        shutil.copy2(PROJECT / name, repo / name)
    shutil.copytree(PROJECT / ".githooks", repo / ".githooks")
    return repo


def fake_uv(directory: Path, log: Path, behaviour: str = "") -> str:
    """A `uv` that records its calls and then runs `behaviour` (shell). Returns a PATH using it."""
    directory.mkdir(parents=True, exist_ok=True)
    uv = directory / "uv"
    uv.write_text(
        f'#!/bin/sh\necho "$PWD: $*" >> "{log}"\n'
        'case "$*" in\n'
        '  "run --no-sync python -c from rag.config import INDEX_REF; print(INDEX_REF)")\n'
        "    echo refs/remotes/origin/main; exit 0 ;;\n"
        "esac\n"
        f"{behaviour}\n"
    )
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
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


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
    hook = clone / ".githooks" / "reference-transaction"
    if broken == "missing":
        hook.unlink()
    else:
        hook.chmod(0o644)
    result = run(clone / "doctor.sh", path=fake_uv(tmp_path / "bin", tmp_path / "uv.log"))
    assert "✗ git hooks enabled" in result.stdout and result.returncode == 1


# ---- the hooks themselves -------------------------------------------------------------------


@pytest.fixture(params=[("origin", "main"), ("upstream", "trunk"), ("origin", "release/notes")])
def real_index_env(clone, request):
    """Private application, remote, and index using the installed environment and cached model."""
    remote, branch = request.param
    shutil.copytree(PROJECT / "rag", clone / "rag", ignore=shutil.ignore_patterns("__pycache__"))
    (clone / "brain.toml").write_text(f'remote = "{remote}"\nbranch = "{branch}"\n')
    (clone / ".gitignore").write_text(".rag/\n__pycache__/\n")
    (clone / ".rag").mkdir()
    (clone / ".rag" / "models").symlink_to(config.MODEL_CACHE_DIR, target_is_directory=True)
    env = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}:{os.environ['PATH']}",
        "VIRTUAL_ENV": sys.prefix,
        "PYTHONPATH": str(clone),
        "BRAIN_BRANCH": branch,
        "TEST_REMOTE": remote,
        "UV_NO_PROJECT": "true",
        "UV_NO_SYNC": "true",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_MERGE_AUTOEDIT": "no",
    }
    git(clone, "config", "core.hooksPath", "/dev/null")
    git(clone, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    git(clone, "config", "user.name", "Test")
    git(clone, "config", "user.email", "test@example.com")
    git(clone, "config", "commit.gpgsign", "false")
    notes = clone / "notes"
    notes.mkdir()
    (notes / "keep.md").write_text(AWS)
    (notes / "change.md").write_text(CAKE)
    (notes / "removed.md").write_text(numbered(2))
    git(clone, "add", ".")
    git(clone, "commit", "-q", "-m", "baseline")
    baseline = git(clone, "rev-parse", branch)
    published = clone.parent / "published.git"
    subprocess.run(["git", "init", "-q", "--bare", str(published)], env=env, check=True)
    git(clone, "remote", "add", remote, str(published))
    subprocess.run(["git", "push", "-q", "-u", remote, branch], cwd=clone, env=env, check=True)
    status = subprocess.run(
        ["uv", "run", "rag", "status"],
        cwd=clone,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert status.returncode == 1, status.stdout + status.stderr
    assert f"index at nothing, {remote}/{branch} at {baseline[:7]}" in status.stdout
    subprocess.run(
        ["uv", "run", "rag", "sync"],
        cwd=clone,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    marker = clone / ".rag" / "lancedb" / "indexed"
    assert marker.read_text().partition("\n")[2] == baseline
    return env


@pytest.mark.parametrize(
    "update",
    [
        "commit",
        "merge",
        "rebase",
        "reset",
        "update-ref",
        "fetch",
        "pull-ff",
        "pull-merge",
        "pull-rebase",
    ],
)
def test_git_updates_trigger_sync_without_a_client(clone, real_index_env, update):
    env = real_index_env
    remote, branch = env["TEST_REMOTE"], env["BRAIN_BRANCH"]
    baseline = git(clone, "rev-parse", branch)
    notes = clone / "notes"
    marker = clone / ".rag" / "lancedb" / "indexed"
    if update != "commit":
        git(clone, "checkout", "-q", "-b", "incoming")
    (notes / "change.md").write_text(CAKE.replace("forty", "fifty"))
    (notes / "removed.md").unlink()
    (notes / "new.md").write_text(numbered(1))
    git(clone, "add", "-A")
    if update != "commit":
        git(clone, "commit", "-q", "-m", "note changes")
        git(clone, "checkout", "-q", branch)
    if update in ("rebase", "pull-merge", "pull-rebase"):
        (clone / "local.txt").write_text("local change\n")
        git(clone, "add", "local.txt")
        git(clone, "commit", "-q", "-m", "local change")
    if update in ("update-ref", "fetch"):
        git(clone, "checkout", "-q", "incoming")
    assert marker.read_text().partition("\n")[2] == baseline
    if update in ("fetch", "pull-ff", "pull-merge", "pull-rebase"):
        peer = clone.parent / "peer"
        subprocess.run(
            ["git", "clone", "-q", "--no-checkout", str(clone), str(peer)], env=env, check=True
        )
        git(peer, "remote", "set-url", "origin", str(clone.parent / "published.git"))
        subprocess.run(
            ["git", "push", "-q", "origin", f"{git(clone, 'rev-parse', 'incoming')}:{branch}"],
            cwd=peer,
            env=env,
            check=True,
        )
    git(clone, "config", "core.hooksPath", ".githooks")
    args = {
        "commit": ["commit", "-q", "-m", "new note"],
        "merge": ["merge", "incoming"],
        "rebase": ["rebase", "incoming"],
        "reset": ["reset", "--soft", "incoming"],
        "update-ref": ["update-ref", f"refs/heads/{branch}", "incoming"],
        "fetch": ["fetch", remote],
        "pull-ff": ["pull", "--ff-only", remote, branch],
        "pull-merge": ["pull", "--no-rebase", "--no-ff", remote, branch],
        "pull-rebase": ["pull", "--rebase", remote, branch],
    }[update]
    result = subprocess.run(
        ["git", *args],
        cwd=clone / ".githooks",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    output = result.stdout + result.stderr
    if update not in ("fetch", "pull-ff", "pull-merge", "pull-rebase"):
        assert " indexed (" not in output
        assert marker.read_text().partition("\n")[2] == baseline
        result = subprocess.run(
            ["git", "push", remote, branch],
            cwd=clone,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout + result.stderr
    assert output.count("RAG: ") == 1
    assert "\nRAG: 2 indexed (" in output and "1 removed" in output
    head = git(clone, "rev-parse", f"refs/remotes/{remote}/{branch}")
    assert head != baseline
    assert marker.read_text().partition("\n")[2] == head
    status = subprocess.run(
        ["uv", "run", "rag", "status"],
        cwd=clone,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert f"index at {head[:7]}, {remote}/{branch} at {head[:7]}" in status.stdout
    table = lancedb.connect(clone / ".rag" / "lancedb").open_table(TABLE)
    rows = table.search().select(["source", "text"]).limit(None).to_list()
    assert {row["source"] for row in rows} == {
        "notes/keep.md",
        "notes/change.md",
        "notes/new.md",
    }
    changed = "\n".join(row["text"] for row in rows if row["source"] == "notes/change.md")
    assert "fifty" in changed and "forty" not in changed


@pytest.mark.parametrize("outcome", ["dry-run", "rejected"])
def test_unsuccessful_publication_does_not_sync(clone, real_index_env, outcome):
    env = real_index_env
    remote, branch = env["TEST_REMOTE"], env["BRAIN_BRANCH"]
    marker = clone / ".rag" / "lancedb" / "indexed"
    before = marker.read_bytes()
    git(clone, "config", "core.hooksPath", ".githooks")
    (clone / "notes" / "draft.md").write_text(CAKE)
    git(clone, "add", "-A")
    git(clone, "commit", "-qm", "unpublished draft")
    args = ["git", "push", remote, branch]
    if outcome == "dry-run":
        args.append("--dry-run")
    else:
        reject = clone.parent / "published.git" / "hooks" / "pre-receive"
        reject.write_text("#!/bin/sh\nexit 1\n")
        reject.chmod(0o755)
    result = subprocess.run(args, cwd=clone, env=env, capture_output=True, text=True, check=False)
    assert result.returncode == (0 if outcome == "dry-run" else 1)
    assert " indexed (" not in result.stdout + result.stderr
    assert marker.read_bytes() == before
    result = subprocess.run(
        ["uv", "run", "rag", "query", "how long to bake cake"],
        cwd=clone,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "notes/draft.md" not in result.stdout
    assert marker.read_bytes() == before


def run_hook(
    clone: Path,
    path: str,
    home: Path,
    *args: str,
    input: str | None = None,
):
    return subprocess.run(
        [str(clone / ".githooks" / "reference-transaction"), *args],
        cwd=clone,
        env={"PATH": path, "HOME": str(home)},
        capture_output=True,
        text=True,
        input=input,
        check=False,
    )


@pytest.mark.parametrize("updates", [REF_UPDATE, REF_UPDATE * 2])
def test_reference_hook_runs_sync_once_from_the_repository_root(clone, tmp_path, updates):
    log = tmp_path / "uv.log"
    output = "RAG: 1 indexed (1 chunks), 0 removed"
    path = fake_uv(tmp_path / "bin", log, f'echo "{output}"')
    result = run_hook(clone, path, tmp_path, "committed", input=updates)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"\n{output}\n"
    assert log.read_text().splitlines() == [
        f"{clone.resolve()}: run --no-sync python -c "
        "from rag.config import INDEX_REF; print(INDEX_REF)",
        f"{clone.resolve()}: run --no-sync rag sync",
    ]


@pytest.mark.parametrize("state", ["preparing", "prepared", "aborted"])
def test_uncommitted_reference_transactions_do_not_sync(clone, tmp_path, state):
    log = tmp_path / "uv.log"
    path = fake_uv(tmp_path / "bin", log)
    result = run_hook(clone, path, tmp_path, state, input=REF_UPDATE)
    assert result.returncode == 0 and not log.exists()


@pytest.mark.parametrize("ref", ["HEAD", "refs/heads/main", "refs/tags/v1"])
def test_nonbranch_reference_updates_do_not_sync(clone, tmp_path, ref):
    log = tmp_path / "uv.log"
    path = fake_uv(tmp_path / "bin", log)
    result = run_hook(
        clone,
        path,
        tmp_path,
        "committed",
        input=REF_UPDATE.replace("refs/remotes/origin/main", ref),
    )
    assert result.returncode == 0 and not log.exists()


def test_hook_finds_uv_in_the_users_local_bin_when_git_has_a_minimal_path(clone, tmp_path):
    home = tmp_path / "home"
    log = tmp_path / "uv.log"
    fake_uv(home / ".local" / "bin", log)
    assert run_hook(clone, SYSTEM_PATH, home, "committed", input=REF_UPDATE).returncode == 0
    assert "run --no-sync rag sync" in log.read_text()


def test_sync_failure_is_reported_without_aborting_the_push(clone, tmp_path):
    healthy_clone(clone)
    path = fake_uv(tmp_path / "bin", tmp_path / "uv.log", 'echo "rag: disk full" >&2; exit 1')
    git(clone, "add", ".")
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "initial",
        ],
        cwd=clone,
        env={"PATH": path, "HOME": str(clone)},
        capture_output=True,
        text=True,
        check=True,
    )
    assert "rag: disk full" not in result.stderr
    published = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(published)], check=True)
    git(clone, "remote", "add", "origin", str(published))
    result = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=clone,
        env={"PATH": path, "HOME": str(clone)},
        capture_output=True,
        text=True,
        check=True,
    )
    assert git(clone, "--git-dir", str(published), "rev-parse", "refs/heads/main") == git(
        clone, "rev-parse", "main"
    )
    assert "rag: disk full" in result.stderr
