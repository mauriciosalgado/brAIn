"""What rag/git.py reads from git: which notes changed, and their content as committed."""

import pytest

from rag import config, git


def test_read_notes_returns_the_committed_content_not_the_working_copy(vault, commit):
    (vault / "a.md").write_text("committed")
    commit()
    (vault / "a.md").write_text("edited afterwards")
    head = git.main_commit()
    assert list(git.read_notes(head, ["notes/a.md"])) == [("notes/a.md", b"committed")]


def test_every_note_is_read_in_order_whatever_its_size(vault, commit):
    (vault / "big.md").write_bytes(b"x" * 300_000)
    (vault / "small.md").write_text("small note\n")
    (vault / "empty.md").write_text("")
    commit()
    paths = ["notes/big.md", "notes/small.md", "notes/empty.md"]
    notes = dict(git.read_notes(git.main_commit(), paths))
    assert notes == {
        "notes/big.md": b"x" * 300_000,
        "notes/small.md": b"small note\n",
        "notes/empty.md": b"",
    }


def test_content_that_looks_like_git_protocol_is_read_as_content(vault, commit):
    tricky = b"abc blob 5\nxyz\n\n\r\n\x00\xff"
    (vault / "tricky.md").write_bytes(tricky)
    (vault / "after.md").write_text("after")
    commit()
    notes = dict(git.read_notes(git.main_commit(), ["notes/tricky.md", "notes/after.md"]))
    assert notes == {"notes/tricky.md": tricky, "notes/after.md": b"after"}


def test_a_path_that_is_not_in_the_commit_is_an_error(vault, commit):
    (vault / "a.md").write_text("a")
    commit()
    with pytest.raises(git.GitError, match="not in commit"):
        list(git.read_notes(git.main_commit(), ["notes/missing.md"]))


def test_paths_with_spaces_and_unicode_are_read(vault, commit):
    (vault / "my note ü.md").write_text("content")
    commit()
    head = git.main_commit()
    assert git.list_notes(head) == ["notes/my note ü.md"]
    assert list(git.read_notes(head, ["notes/my note ü.md"])) == [
        ("notes/my note ü.md", b"content")
    ]


def test_changed_notes_splits_what_to_index_from_what_to_remove(vault, commit, vault_git):
    (vault / "keep.md").write_text("keep")
    (vault / "edit.md").write_text("one")
    (vault / "gone.md").write_text("gone")
    first = commit()
    (vault / "edit.md").write_text("two")
    (vault / "new.md").write_text("new")
    vault_git("rm", "-q", "notes/gone.md")
    vault_git("mv", "notes/keep.md", "notes/kept.md")
    second = commit()
    to_index, to_remove = git.changed_notes(first, second)
    assert sorted(to_index) == ["notes/edit.md", "notes/kept.md", "notes/new.md"]
    assert sorted(to_remove) == ["notes/gone.md", "notes/keep.md"]


def test_only_files_under_notes_count(vault, commit):
    (vault / "a.md").write_text("a")
    (vault.parent / "README.md").write_text("readme")
    commit()
    assert git.list_notes(git.main_commit()) == ["notes/a.md"]


def test_the_branch_is_main_unless_told_otherwise(vault, commit, vault_git, monkeypatch):
    (vault / "a.md").write_text("a")
    main = commit()
    assert git.main_commit() == main
    vault_git("checkout", "-q", "-b", "feature")
    (vault / "b.md").write_text("b")
    commit()
    assert git.main_commit() == main  # the checked-out branch does not matter
    monkeypatch.setattr(config, "BRANCH", "release")
    with pytest.raises(git.GitError, match="No 'release' branch"):
        git.main_commit()


def test_outside_a_repository_the_error_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "NOTES_DIR", tmp_path / "notes")
    with pytest.raises(git.GitError, match="BRAIN_BRANCH"):
        git.main_commit()
