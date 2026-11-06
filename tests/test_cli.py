import pytest
from samples import AWS

from rag import cli
from rag.index import embeddings


def run_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr("sys.argv", ["rag", *args])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    captured = capsys.readouterr()
    return exit_info.value.code, captured.out, captured.err


def test_sync_status_and_query(vault, commit, monkeypatch, capsys):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    code, out, _ = run_cli(monkeypatch, capsys, "status")
    assert code == 1 and "1 to update" in out and "index at nothing" in out
    code, out, _ = run_cli(monkeypatch, capsys, "sync")
    assert code == 0 and "1 indexed" in out
    code, out, _ = run_cli(monkeypatch, capsys, "status")
    assert code == 0 and "0 to update" in out
    code, out, _ = run_cli(monkeypatch, capsys, "query", "how", "to", "rotate", "keys")
    assert code == 0 and "notes/aws-keys.md" in out and "Score:" in out


def test_problems_are_messages_not_tracebacks(vault, commit, monkeypatch, capsys):
    code, _, err = run_cli(monkeypatch, capsys, "query", "anything")
    assert code == 1 and "No 'main' branch" in err and "Traceback" not in err
    code, _, err = run_cli(monkeypatch, capsys, "nonsense")
    assert code == 2 and "usage: rag" in err
    (vault / "bad.md").write_bytes(b"# Bad\n\nbroken \xff\xfe bytes " * 5)
    commit()
    code, _, err = run_cli(monkeypatch, capsys, "sync")
    assert code == 1 and "skipped notes/bad.md" in err


def test_model_prepares_the_model(vault, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(embeddings, "ensure_model", lambda: calls.append("ensured"))
    code, out, _ = run_cli(monkeypatch, capsys, "model")
    assert code == 0 and calls == ["ensured"] and "ready" in out
