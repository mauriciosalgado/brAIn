import pytest

from rag import config, notes


def test_read_respects_skipped_folders(vault, monkeypatch):
    monkeypatch.setattr(config, "SKIP_FOLDERS", ["archive"])
    (vault / "archive").mkdir()
    (vault / "archive" / "old.md").write_text("ignored")
    with pytest.raises(ValueError, match="No note at"):
        notes.read_note("notes/archive/old.md")


def test_read_rejects_symlinks_outside_the_notes_folder(vault):
    outside = vault.parent / "outside.md"
    outside.write_text("outside the knowledge base")
    (vault / "linked.md").symlink_to(outside)
    with pytest.raises(ValueError, match="No note at"):
        notes.read_note("notes/linked.md")


def test_skipped_symlink_paths_cannot_bypass_note_filtering(vault, monkeypatch):
    monkeypatch.setattr(config, "SKIP_FOLDERS", ["archive"])
    (vault / "current.md").write_text("current note")
    (vault / "archive").mkdir()
    (vault / "archive" / "linked.md").symlink_to(vault / "current.md")
    with pytest.raises(ValueError, match="No note at"):
        notes.read_note("notes/archive/linked.md")


def test_symlinks_to_skipped_notes_are_refused(vault, monkeypatch):
    monkeypatch.setattr(config, "SKIP_FOLDERS", ["archive"])
    (vault / "archive").mkdir()
    (vault / "archive" / "old.md").write_text("ignored")
    (vault / "linked.md").symlink_to(vault / "archive" / "old.md")
    with pytest.raises(ValueError, match="No note at"):
        notes.read_note("notes/linked.md")
