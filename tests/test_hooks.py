import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "reference-transaction"


@pytest.fixture
def hook_environment(tmp_path_factory, monkeypatch):
    root = tmp_path_factory.mktemp("hook")
    package = root / "rag"
    package.mkdir()
    (package / "__init__.py").touch()
    shutil.copyfile(ROOT / "rag" / "config.py", package / "config.py")
    uv = root / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        'if [ "$1 $2 $3" = "run --no-sync python" ]; then\n'
        "  shift 3\n"
        f'  exec {shlex.quote(sys.executable)} "$@"\n'
        "fi\n"
        '[ "$*" = "run --no-sync rag sync" ] || exit 2\n'
        'echo synced >> "$HOOK_LOG"\n'
        'echo "RAG: sync ran"\n'
        'exit "${SYNC_EXIT:-0}"\n'
    )
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{root}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("PYTHONPATH", str(root))
    monkeypatch.setenv("HOOK_LOG", str(root / "sync.log"))
    monkeypatch.delenv("BRAIN_BRANCH", raising=False)
    return root


@pytest.mark.parametrize(
    ("phase", "refs", "syncs"),
    [
        ("preparing", "old new refs/remotes/origin/main\n", 0),
        ("prepared", "old new refs/remotes/origin/main\n", 0),
        ("aborted", "old new refs/remotes/origin/main\n", 0),
        ("committed", "old new refs/heads/main\n", 0),
        ("committed", "old new refs/remotes/origin/feature\n", 0),
        ("committed", "old new refs/remotes/other/main\n", 0),
        ("committed", "old new refs/tags/main\n", 0),
        ("committed", "same same refs/remotes/origin/main\n", 0),
        ("committed", "old new HEAD\n", 0),
        ("committed", "old new refs/remotes/origin/main\n", 1),
        (
            "committed",
            "old new HEAD\nold new refs/remotes/origin/main\nold new refs/remotes/origin/main\n",
            1,
        ),
    ],
)
def test_hook_filters_phase_and_refs(hook_environment, phase, refs, syncs):
    result = subprocess.run(
        [str(HOOK), phase],
        cwd=hook_environment,
        input=refs,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == ("\nRAG: sync ran\n" if syncs else "")


def test_local_updates_do_not_even_start_python(hook_environment):
    (hook_environment / "uv").write_text("#!/bin/sh\nexit 99\n")
    subprocess.run(
        [str(HOOK), "committed"],
        input="old new HEAD\nold new refs/heads/main\nold new refs/tags/v1\n",
        text=True,
        check=True,
    )


@pytest.mark.parametrize("remote", ["origin", "upstream"])
@pytest.mark.parametrize("branch", ["trunk", "release/notes"])
@pytest.mark.parametrize("override", [False, True])
def test_hook_uses_configured_target(hook_environment, monkeypatch, branch, remote, override):
    (hook_environment / "brain.toml").write_text(f'branch = "{branch}"\nremote = "{remote}"\n')
    if override:
        monkeypatch.setenv("BRAIN_BRANCH", "override/notes")
        branch = "override/notes"
    target = f"refs/remotes/{remote}/{branch}"
    for ref, expected in [
        (f"refs/heads/{branch}", ""),
        (f"{target}-extra", ""),
        (target, "\nRAG: sync ran\n"),
    ]:
        result = subprocess.run(
            [str(HOOK), "committed"],
            cwd=hook_environment,
            input=f"old new {ref}\n",
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout == expected


def test_hook_reports_configuration_and_sync_errors(hook_environment, monkeypatch):
    monkeypatch.setenv("SYNC_EXIT", "1")
    result = subprocess.run(
        [str(HOOK), "committed"],
        cwd=hook_environment,
        input="old new refs/remotes/origin/main\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1 and result.stdout == "\nRAG: sync ran\n"
    (hook_environment / "brain.toml").write_text("not valid TOML")
    result = subprocess.run(
        [str(HOOK), "committed"],
        cwd=hook_environment,
        input="old new refs/remotes/origin/main\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1 and "not valid TOML" in result.stderr
    assert result.stdout == ""
