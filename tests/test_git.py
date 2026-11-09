"""Committed-note reads and local Git change plans, independent of the database."""

from unittest.mock import Mock

import pytest

from rag import config, git


def tip(vault_git) -> str:
    return vault_git("rev-parse", "HEAD")


def test_files_are_read_as_committed_not_as_edited(vault, commit, vault_git):
    (vault / "a.md").write_text("committed")
    commit()
    (vault / "a.md").write_text("edited afterwards")
    assert git.read_committed_file(tip(vault_git), "notes/a.md") == "committed"


def test_every_file_is_read_whatever_its_name_and_content(vault, commit, vault_git):
    contents = {
        "notes/big.md": "x" * 300_000,
        "notes/tricky.md": "abc blob 5\nxyz\n\n\x00 end",
        "notes/empty.md": "",
        "notes/my note ü.md": "unicode name ü",
        "notes/line\nbreak.md": "newline filename",
    }
    for path, content in contents.items():
        (vault.parent / path).write_text(content, encoding="utf-8")
    commit()
    head = tip(vault_git)
    for path, content in contents.items():
        assert git.committed_file_size(head, path) == len(content.encode())
        assert git.read_committed_file(head, path) == content


def test_a_byte_order_mark_is_removed_and_line_endings_are_normalized(vault, commit, vault_git):
    (vault / "bom.md").write_bytes(b"\xef\xbb\xbftext")
    (vault / "crlf.md").write_bytes(b"one\r\ntwo\rthree")
    commit()
    head = tip(vault_git)
    assert git.read_committed_file(head, "notes/bom.md") == "text"
    assert git.read_committed_file(head, "notes/crlf.md") == "one\ntwo\nthree"
    assert git.committed_file_size(head, "notes/crlf.md") == len(b"one\r\ntwo\rthree")


def test_invalid_utf8_is_an_error(vault, commit, vault_git):
    (vault / "bad.md").write_bytes(b"not UTF-8: \xff")
    commit()
    with pytest.raises(ValueError, match="utf-8"):
        git.read_committed_file(tip(vault_git), "notes/bad.md")


@pytest.mark.parametrize("reader", [git.committed_file_size, git.read_committed_file])
def test_a_path_that_is_not_in_the_commit_is_an_error(vault, commit, vault_git, reader):
    (vault / "a.md").write_text("a")
    commit()
    with pytest.raises(git.GitError, match=r"notes/missing\.md"):
        reader(tip(vault_git), "notes/missing.md")


def test_list_committed_notes_stays_inside_the_folder(vault, commit, vault_git):
    (vault / "a.md").write_text("a")
    (vault.parent / "README.md").write_text("readme")
    commit()
    assert git.list_committed_notes(tip(vault_git)) == ["notes/a.md"]


def test_notes_changed_between_splits_what_to_update_from_what_to_remove(vault, commit, vault_git):
    (vault / "keep.md").write_text("keep")
    (vault / "edit.md").write_text("one")
    (vault / "gone.md").write_text("gone")
    first = commit()
    (vault / "edit.md").write_text("two")
    (vault / "new.md").write_text("new")
    vault_git("rm", "-q", "notes/gone.md")
    vault_git("mv", "notes/keep.md", "notes/kept.md")  # a rename: a removal plus an addition
    second = commit()
    changed, removed = git.notes_changed_between(first, second)
    assert sorted(changed) == ["notes/edit.md", "notes/kept.md", "notes/new.md"]
    assert sorted(removed) == ["notes/gone.md", "notes/keep.md"]


def test_the_tip_is_that_of_the_named_remote_branch_whatever_is_checked_out(
    vault, publish, vault_git
):
    (vault / "a.md").write_text("a")
    main = publish()
    vault_git("checkout", "-q", "-b", "feature")
    (vault / "b.md").write_text("b")
    publish()
    assert git.remote_branch_tip("origin", "main") == main
    with pytest.raises(git.GitError):
        git.remote_branch_tip("origin", "release")


def test_a_branch_name_is_not_a_revision_expression(vault, publish):
    publish()
    with pytest.raises(git.GitError, match="No 'origin/main~0' remote-tracking branch"):
        git.remote_branch_tip("origin", "main~0")


def test_only_markdown_notes_outside_hidden_and_skipped_folders_are_notes(
    vault, commit, monkeypatch
):
    monkeypatch.setattr(config, "SKIP_FOLDERS", ["archive"])
    for path in [
        "keep.md",
        "archive2/other.md",
        "archive/old.md",
        ".trash/deleted.md",
        "sub/.hidden/x.md",
        "notes.txt",
        "../README.md",
    ]:
        (vault / path).parent.mkdir(parents=True, exist_ok=True)
        (vault / path).write_text("text")
    head = commit()
    assert git.list_committed_notes(head) == ["notes/archive2/other.md", "notes/keep.md"]


def test_notes_changed_between_leaves_out_what_is_not_a_note(vault, commit, vault_git):
    (vault / "a.md").write_text("a")
    first = commit()
    (vault / "a.md").write_text("changed")
    (vault / "b.md").write_text("new")
    (vault / "image.png").write_bytes(b"\x89PNG")
    (vault / ".trash").mkdir()
    (vault / ".trash" / "c.md").write_text("hidden")
    second = commit()
    assert sorted(git.notes_changed_between(first, second)[0]) == ["notes/a.md", "notes/b.md"]
    vault_git("rm", "-q", "notes/a.md")
    assert git.notes_changed_between(second, commit())[1] == ["notes/a.md"]


@pytest.mark.parametrize("previous", [None, "0" * 40])
def test_missing_history_plans_all_current_notes_and_removes_obsolete_paths(
    vault, commit, previous
):
    (vault / "current.md").write_text("current")
    (vault / "new.md").write_text("new")
    head = commit()
    writes, removes = git.plan_index(previous, head, {"notes/current.md", "notes/obsolete.md"})
    assert writes == ["notes/current.md", "notes/new.md"]
    assert removes == ["notes/obsolete.md"]
    assert not config.DB_DIR.exists()


def test_unexpected_diff_errors_do_not_become_rebuild_plans(vault, commit, monkeypatch):
    (vault / "a.md").write_text("before")
    previous = commit()
    (vault / "a.md").write_text("after")
    head = commit()
    monkeypatch.setattr(
        git, "notes_changed_between", Mock(side_effect=git.GitError("unexpected diff failure"))
    )
    monkeypatch.setattr(git, "list_committed_notes", lambda _: pytest.fail("unexpected rebuild"))
    with pytest.raises(git.GitError, match="unexpected diff failure"):
        git.plan_index(previous, head, {"notes/a.md"})


def test_history_lookup_errors_do_not_become_rebuild_plans(monkeypatch):
    monkeypatch.setattr(git, "_run_git", Mock(side_effect=git.GitError("history lookup failed")))
    monkeypatch.setattr(git, "list_committed_notes", lambda _: pytest.fail("unexpected rebuild"))
    with pytest.raises(git.GitError, match="history lookup failed"):
        git.plan_index("previous", "head", {"notes/a.md"})


def test_the_tip_is_the_configured_branch_and_a_missing_one_says_how_to_fix_it(
    vault, publish, vault_git, monkeypatch
):
    (vault / "a.md").write_text("a")
    main = publish()
    vault_git("checkout", "-q", "-b", "feature")
    assert git.remote_branch_tip(config.REMOTE, config.BRANCH) == main
    monkeypatch.setattr(config, "BRANCH", "release")
    with pytest.raises(
        git.GitError, match=r"No 'origin/release' remote-tracking branch.*brain\.toml"
    ):
        git.remote_branch_tip(config.REMOTE, config.BRANCH)


def test_outside_a_repository_the_error_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    with pytest.raises(git.GitError, match="not a git repository"):
        git.remote_branch_tip(config.REMOTE, config.BRANCH)
