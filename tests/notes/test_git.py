"""Plain git: files as they are in a commit, and what changed between two."""

import pytest

from rag.notes import git


def tip(vault_git) -> str:
    return vault_git("rev-parse", "HEAD")


def test_files_are_read_as_committed_not_as_edited(vault, commit, vault_git):
    (vault / "a.md").write_text("committed")
    commit()
    (vault / "a.md").write_text("edited afterwards")
    assert list(git.read_files(tip(vault_git), ["notes/a.md"])) == [("notes/a.md", b"committed")]


def test_every_file_is_read_in_order_whatever_its_content(vault, commit, vault_git):
    tricky = b"abc blob 5\nxyz\n\n\r\n\x00\xff"  # looks like git's own protocol
    contents = {
        "notes/big.md": b"x" * 300_000,
        "notes/tricky.md": tricky,
        "notes/empty.md": b"",
        "notes/my note ü.md": b"unicode name",
    }
    for path, content in contents.items():
        (vault.parent / path).write_bytes(content)
    commit()
    assert dict(git.read_files(tip(vault_git), list(contents))) == contents


def test_a_path_that_is_not_in_the_commit_is_an_error(vault, commit, vault_git):
    (vault / "a.md").write_text("a")
    commit()
    with pytest.raises(git.GitError, match="not in commit"):
        list(git.read_files(tip(vault_git), ["notes/missing.md"]))


def test_list_files_stays_inside_the_folder(vault, commit, vault_git):
    (vault / "a.md").write_text("a")
    (vault.parent / "README.md").write_text("readme")
    commit()
    assert git.list_files(tip(vault_git), "notes") == ["notes/a.md"]


def test_changed_files_splits_what_to_update_from_what_to_remove(vault, commit, vault_git):
    (vault / "keep.md").write_text("keep")
    (vault / "edit.md").write_text("one")
    (vault / "gone.md").write_text("gone")
    first = commit()
    (vault / "edit.md").write_text("two")
    (vault / "new.md").write_text("new")
    vault_git("rm", "-q", "notes/gone.md")
    vault_git("mv", "notes/keep.md", "notes/kept.md")  # a rename: a removal plus an addition
    second = commit()
    changed, removed = git.changed_files(first, second, "notes")
    assert sorted(changed) == ["notes/edit.md", "notes/kept.md", "notes/new.md"]
    assert sorted(removed) == ["notes/gone.md", "notes/keep.md"]


def test_the_tip_is_that_of_the_named_branch_whatever_is_checked_out(vault, commit, vault_git):
    (vault / "a.md").write_text("a")
    main = commit()
    vault_git("checkout", "-q", "-b", "feature")
    (vault / "b.md").write_text("b")
    commit()
    assert git.branch_tip("main") == main
    with pytest.raises(git.GitError):
        git.branch_tip("release")
