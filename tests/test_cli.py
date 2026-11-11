import subprocess
import sys

import pytest
from samples import AWS

from rag import cli
from rag.index import embeddings, indexer


def run_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr("sys.argv", ["rag", *args])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    captured = capsys.readouterr()
    return exit_info.value.code, captured.out, captured.err


@pytest.mark.parametrize("question", [("how", "to", "rotate", "keys"), ("how to rotate keys",)])
def test_sync_status_and_query(vault, publish, monkeypatch, capsys, question):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    code, out, _ = run_cli(monkeypatch, capsys, "status")
    assert code == 1 and "1 to update" in out and "index at nothing" in out
    code, out, _ = run_cli(monkeypatch, capsys, "sync")
    assert code == 0 and out.startswith("RAG: 1 indexed (")
    code, out, _ = run_cli(monkeypatch, capsys, "status")
    assert code == 0 and "0 to update" in out
    code, out, _ = run_cli(monkeypatch, capsys, "query", *question)
    assert code == 0 and "notes/aws-keys.md" in out and "Score:" in out
    assert "Section: AWS Keys" in out and "Covers:" not in out
    (vault / "aws-keys.md").write_text(AWS.replace("ninety", "sixty"))
    publish()
    code, out, _ = run_cli(monkeypatch, capsys, "query", *question)
    assert code == 0 and "ninety" in out and "sixty" not in out
    run_cli(monkeypatch, capsys, "sync")
    code, out, _ = run_cli(monkeypatch, capsys, "query", *question)
    assert code == 0 and "sixty" in out and "ninety" not in out
    (vault / "aws-keys.md").unlink()
    publish()
    code, out, _ = run_cli(monkeypatch, capsys, "sync")
    assert code == 0 and out == "RAG: 0 indexed (0 chunks), 1 removed\n"


def test_problems_are_messages_not_tracebacks(vault, publish, monkeypatch, capsys, caplog):
    code, _, err = run_cli(monkeypatch, capsys, "query", "anything")
    assert code == 1 and "Run 'uv run rag sync' first" in err and "Traceback" not in err
    code, _, err = run_cli(monkeypatch, capsys, "nonsense")
    assert code == 2 and "usage: rag" in err
    (vault / "bad.md").write_bytes(b"# Bad\n\nbroken \xff\xfe bytes " * 5)
    publish()
    code, _, _ = run_cli(monkeypatch, capsys, "sync")
    assert code == 1 and "skipped notes/bad.md" in caplog.text


def test_reset_deletes_the_index_and_sync_rebuilds_it(vault, publish, monkeypatch, capsys):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    run_cli(monkeypatch, capsys, "sync")
    code, out, _ = run_cli(monkeypatch, capsys, "reset")
    assert code == 0 and "rag sync" in out
    code, _, err = run_cli(monkeypatch, capsys, "query", "rotate keys")
    assert code == 1 and "Run 'uv run rag sync' first" in err
    code, out, _ = run_cli(monkeypatch, capsys, "sync")
    assert code == 0 and out.startswith("RAG: 1 indexed (")
    assert run_cli(monkeypatch, capsys, "reset")[0] == 0
    assert run_cli(monkeypatch, capsys, "reset")[0] == 0  # nothing to delete is not an error


def test_model_prepares_the_model(vault, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(embeddings, "ensure_model", lambda: calls.append("ensured"))
    code, out, _ = run_cli(monkeypatch, capsys, "model")
    assert code == 0 and calls == ["ensured"] and "ready" in out


def test_io_failures_are_messages_not_tracebacks(monkeypatch, capsys):
    def full_disk():
        raise OSError("disk full")

    monkeypatch.setattr(indexer, "sync", full_disk)
    code, _, err = run_cli(monkeypatch, capsys, "sync")
    assert code == 1 and "rag: disk full" in err and "Traceback" not in err


def test_status_requires_the_current_commit_even_when_no_notes_changed(
    vault, publish, monkeypatch, capsys
):
    (vault / "aws-keys.md").write_text(AWS)
    indexed = publish()
    indexer.sync()
    (vault.parent / "README.md").write_text("Only documentation changed.\n")
    head = publish()
    code, out, _ = run_cli(monkeypatch, capsys, "status")
    assert code == 1 and "0 to update" in out
    assert f"index at {indexed[:7]}, origin/main at {head[:7]}" in out
    monkeypatch.setattr(
        embeddings, "embed_documents", lambda _: pytest.fail("unchanged notes were embedded")
    )
    indexer.sync()
    code, out, _ = run_cli(monkeypatch, capsys, "status")
    assert code == 0 and f"index at {head[:7]}, origin/main at {head[:7]}" in out


def test_help_does_not_load_settings_or_the_indexing_stack():
    code = (
        "import sys\n"
        "from rag import cli\n"
        "sys.argv = ['rag', '-h']\n"
        "try:\n"
        "    cli.main()\n"
        "except SystemExit as error:\n"
        "    assert error.code == 0\n"
        "assert not {'rag.config', 'rag.index.indexer', 'rag.index.embeddings', "
        "'fastembed', 'lancedb'} & sys.modules.keys()\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    assert "usage: rag" in result.stdout
