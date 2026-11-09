"""The guarantees rag/index/store.py gives to the sync code."""

import pytest

from rag import config
from rag.index import store
from rag.index.chunker import Chunk
from rag.index.store import EmbeddedNote, Store


def note(source: str, vector_value: float = 0.1, chunks: int = 1) -> EmbeddedNote:
    made = [Chunk(f"text {i} of {source}", "Title", i) for i in range(chunks)]
    return EmbeddedNote(source, made, [[vector_value] * config.EMBEDDING_SIZE] * chunks)


def test_the_index_survives_being_opened_again(vault):
    Store().replace_notes([note("notes/a.md")])
    Store().set_indexed_commit("abc123")
    again = Store()
    assert again.sources() == {"notes/a.md"} and again.indexed_commit() == "abc123"


def test_a_lost_table_forgets_which_commit_it_matched(vault):
    index = Store()
    index.replace_notes([note("notes/a.md")])
    index.set_indexed_commit("abc123")
    index._db.drop_table(store.TABLE)
    assert Store().indexed_commit() is None and Store().count() == 0


def test_opening_an_incompatible_index_preserves_it_until_explicit_rebuilding(vault, monkeypatch):
    index = Store()
    index.replace_notes([note("notes/a.md")])
    index.set_indexed_commit("abc123")
    marker = (config.DB_DIR / "indexed").read_bytes()
    monkeypatch.setattr(store, "FINGERPRINT", "changed settings")
    opened = Store()
    assert opened.count() == 1 and opened.indexed_commit() is None
    assert (config.DB_DIR / "indexed").read_bytes() == marker
    opened.rebuild_if_needed()
    assert opened.count() == 0 and opened.indexed_commit() is None
    assert (config.DB_DIR / "indexed").read_text().startswith("changed settings")


@pytest.mark.parametrize("path", ["notes/it's.md", "notes/x' OR '1'='1.md", "notes/a b ü.md"])
def test_paths_with_quotes_are_stored_replaced_and_deleted_exactly(vault, path):
    index = Store()
    index.replace_notes([note(path, chunks=3), note("notes/other.md")])
    index.replace_notes([note(path, chunks=1)])
    assert index.count() == 2
    index.delete_notes([path])
    assert index.sources() == {"notes/other.md"}


def test_replacing_notes_leaves_no_old_chunks_and_the_others_alone(vault):
    index = Store()
    index.replace_notes([note("notes/a.md", chunks=5), note("notes/b.md", chunks=3)])
    index.replace_notes([note("notes/a.md", chunks=2), note("notes/c.md")])
    assert index.count() == 2 + 3 + 1
    assert index.sources() == {"notes/a.md", "notes/b.md", "notes/c.md"}


def test_a_batch_is_one_write(vault):
    index = Store()
    index.replace_notes([note(f"notes/n{i}.md", chunks=3) for i in range(20)])
    before = index._table.version
    index.replace_notes([note(f"notes/n{i}.md", chunks=2) for i in range(10, 30)])
    assert index._table.version == before + 1
    assert index.count() == 10 * 3 + 20 * 2


def test_deleting_nothing_changes_nothing(vault):
    index = Store()
    index.replace_notes([note("notes/a.md")])
    index.delete_notes([])
    assert index.sources() == {"notes/a.md"}
