"""Storage and locked-retrieval guarantees."""

import pytest
from lancedb.query import LanceVectorQueryBuilder

from rag import config
from rag.index import store
from rag.index.chunker import Chunk
from rag.index.store import EmbeddedNote, Store, open_index


def note(source: str, vector_value: float = 0.1, chunks: int = 1) -> EmbeddedNote:
    made = [Chunk(f"text {i} of {source}", "Title", i) for i in range(chunks)]
    return EmbeddedNote(source, made, [[vector_value] * config.EMBEDDING_SIZE] * chunks)


def test_the_index_survives_being_opened_again(vault):
    Store().replace_notes([note("notes/a.md")])
    Store().set_indexed_commit("abc123")
    again = Store()
    assert again.sources() == {"notes/a.md"} and again.indexed_commit() == "abc123"


def test_retrieval_does_not_create_a_missing_index(vault):
    with pytest.raises(RuntimeError, match="uv run rag sync"), open_index():
        pass
    assert not config.DB_DIR.exists()


@pytest.mark.parametrize("unusable", ["incomplete", "incompatible", "missing-table"])
def test_retrieval_refuses_unusable_indexes_without_rebuilding(vault, monkeypatch, unusable):
    index = Store()
    index.replace_notes([note("notes/a.md")])
    if unusable != "incomplete":
        index.set_indexed_commit("abc123")
    marker = (config.DB_DIR / "indexed").read_bytes()
    version = index._table.version
    if unusable == "incompatible":
        monkeypatch.setattr(store, "FINGERPRINT", "other settings")
    elif unusable == "missing-table":
        index._db.drop_table(store.TABLE)
    with pytest.raises(RuntimeError, match="uv run rag sync"), open_index():
        pass
    assert (config.DB_DIR / "indexed").read_bytes() == marker
    if unusable == "missing-table":
        assert store.TABLE not in index._db.list_tables().tables
    else:
        assert index._table.version == version
        assert index.count() == 1


@pytest.mark.parametrize("notes", [0, 25])
def test_sources_reads_every_unique_path_without_counting_chunks(vault, monkeypatch, notes):
    index = Store()
    expected = {f"notes/n{i}.md" for i in range(notes)}
    if expected:
        index.replace_notes([note(source, chunks=3) for source in sorted(expected)])
    monkeypatch.setattr(index, "count", lambda: pytest.fail("source scans must not count chunks"))
    assert index.sources() == expected


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


def test_search_preserves_results_without_materializing_vectors(vault, monkeypatch):
    index = Store()
    notes = [note(f"notes/n{i}.md") for i in range(24)]
    for i, item in enumerate(notes):
        item.vectors[0][i] = float(i + 1)
    index.replace_notes(notes)
    vector = [1.0] + [0.0] * (config.EMBEDDING_SIZE - 1)
    expected = index._table.search(vector).distance_type("cosine").limit(5).to_list()
    materialized = []
    original = LanceVectorQueryBuilder.to_list

    def capture(query):
        rows = original(query)
        materialized.extend(rows)
        return rows

    monkeypatch.setattr(LanceVectorQueryBuilder, "to_list", capture)
    assert index.search(vector, 5) == [
        {
            "text": row["text"],
            "source": row["source"],
            "header_path": row["header_path"],
            "score": 1 - row["_distance"],
        }
        for row in expected
    ]
    assert materialized
    assert all(set(row) == {"text", "source", "header_path", "_distance"} for row in materialized)
