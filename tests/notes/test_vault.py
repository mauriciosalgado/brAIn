"""Which files are notes, and what they say on the searched branch."""

import pytest

from rag import config
from rag.notes import git
from rag.notes import vault as notes


def test_only_markdown_notes_outside_hidden_and_skipped_folders_are_notes(
    vault, commit, monkeypatch
):
    monkeypatch.setattr(config, "SKIP_FOLDERS", ["archive"])
    for path in [
        "keep.md",
        "archive2/other.md",  # only the folder named "archive" is skipped
        "archive/old.md",
        ".trash/deleted.md",
        "sub/.hidden/x.md",
        "notes.txt",
        "../README.md",  # outside notes/
    ]:
        (vault / path).parent.mkdir(parents=True, exist_ok=True)
        (vault / path).write_text("text")
    head = commit()
    assert notes.list_notes(head) == ["notes/archive2/other.md", "notes/keep.md"]


def test_changed_notes_leave_out_what_is_not_a_note(vault, commit, vault_git):
    (vault / "a.md").write_text("a")
    first = commit()
    (vault / "a.md").write_text("changed")
    (vault / "b.md").write_text("new")
    (vault / "image.png").write_bytes(b"\x89PNG")
    (vault / ".trash").mkdir()
    (vault / ".trash" / "c.md").write_text("hidden")
    second = commit()
    assert sorted(notes.changed_notes(first, second)[0]) == ["notes/a.md", "notes/b.md"]
    vault_git("rm", "-q", "notes/a.md")
    assert notes.changed_notes(second, commit())[1] == ["notes/a.md"]


def test_the_tip_is_the_configured_branch_and_a_missing_one_says_how_to_fix_it(
    vault, commit, vault_git, monkeypatch
):
    (vault / "a.md").write_text("a")
    main = commit()
    vault_git("checkout", "-q", "-b", "feature")
    assert notes.branch_tip() == main
    monkeypatch.setattr(config, "BRANCH", "release")
    with pytest.raises(git.GitError, match=r"No 'release' branch.*brain\.toml"):
        notes.branch_tip()


def test_outside_a_repository_the_error_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    with pytest.raises(git.GitError, match="not a git repository"):
        notes.branch_tip()


def test_read_note_gives_the_committed_text_by_relative_or_absolute_path(vault, commit):
    (vault / "a.md").write_bytes(b"\xef\xbb\xbfcommitted")
    commit()
    (vault / "a.md").write_text("edited, not committed")
    assert notes.read_note("notes/a.md") == "committed"
    assert notes.read_note(str(vault / "a.md")) == "committed"


def test_read_note_refuses_what_is_not_a_note(vault, commit):
    (vault / "a.md").write_text("a")
    (vault / ".trash").mkdir()
    (vault / ".trash" / "gone.md").write_text("hidden")
    (vault.parent / "README.md").write_text("outside")
    commit()
    for path in ["README.md", "notes/.trash/gone.md", "notes/../README.md", "notes/missing.md"]:
        with pytest.raises(ValueError, match="No note at"):
            notes.read_note(path)
