"""The local index on its own: the guarantees rag/db.py gives to the sync code."""

import pytest

import rag
from rag import config, db
from rag.chunker import Chunk
from rag.db import EmbeddedNote, Index


def note(source: str, vector_value: float = 0.1, chunks: int = 1) -> EmbeddedNote:
    made = [Chunk(f"text {i} of {source}", "Title", i) for i in range(chunks)]
    return EmbeddedNote(source, made, [[vector_value] * config.EMBEDDING_SIZE] * chunks)


def chunks_of(index: Index, source: str) -> list[str]:
    rows = (
        index._table.search()
        .where("source = '" + source.replace("'", "''") + "'")
        .limit(100)
        .to_list()
    )
    return sorted(row["text"] for row in rows)


def test_opening_the_index_again_keeps_everything(vault):
    Index().replace_notes([note("notes/a.md")])
    Index().set_indexed_commit("abc123")
    again = Index()
    assert again.sources() == {"notes/a.md"} and again.indexed_commit() == "abc123"


def test_a_lost_table_forgets_which_commit_it_matched(vault):
    index = Index()
    index.replace_notes([note("notes/a.md")])
    index.set_indexed_commit("abc123")
    index._db.drop_table(db.TABLE)
    assert Index().indexed_commit() is None and Index().count() == 0


def test_many_notes_can_be_deleted_at_once(vault):
    index = Index()
    index.replace_notes([note(f"notes/n{i}.md") for i in range(300)])
    index.delete_notes([f"notes/n{i}.md" for i in range(299)])
    assert index.sources() == {"notes/n299.md"}


def test_deleting_nothing_does_nothing(vault):
    index = Index()
    index.replace_notes([note("notes/a.md")])
    index.delete_notes([])
    assert index.sources() == {"notes/a.md"}


@pytest.mark.parametrize("path", ["notes/it's.md", "notes/a'b'c.md", "notes/x' OR '1'='1.md"])
def test_paths_with_quotes_are_stored_and_deleted_exactly(vault, path):
    index = Index()
    index.replace_notes([note(path), note("notes/other.md")])
    index.delete_notes([path])
    assert index.sources() == {"notes/other.md"}


def test_replacing_a_note_leaves_no_old_chunks(vault):
    index = Index()
    index.replace_notes([note("notes/a.md")])
    index.replace_notes([note("notes/a.md", 0.2), note("notes/b.md")])
    assert index.count() == 2 and index.sources() == {"notes/a.md", "notes/b.md"}


def test_no_hits_means_no_results():
    assert rag._close_to_best([]) == []


def test_a_note_that_shrinks_or_grows_keeps_exactly_its_new_chunks(vault):
    index = Index()
    index.replace_notes([note("notes/a.md", chunks=5), note("notes/b.md", chunks=2)])
    index.replace_notes([note("notes/a.md", chunks=2), note("notes/b.md", chunks=4)])
    assert chunks_of(index, "notes/a.md") == ["text 0 of notes/a.md", "text 1 of notes/a.md"]
    assert len(chunks_of(index, "notes/b.md")) == 4 and index.count() == 6


def test_replacing_notes_leaves_the_other_notes_alone(vault):
    index = Index()
    index.replace_notes([note("notes/a.md", chunks=3), note("notes/b.md", chunks=3)])
    index.replace_notes([note("notes/a.md", 0.5, chunks=1)])
    assert len(chunks_of(index, "notes/b.md")) == 3 and len(chunks_of(index, "notes/a.md")) == 1


def test_replacing_a_batch_is_one_write_so_a_search_never_sees_half_of_it(vault):
    index = Index()
    index.replace_notes([note(f"notes/n{i}.md", chunks=3) for i in range(20)])
    before = index._table.version
    index.replace_notes([note(f"notes/n{i}.md", chunks=2) for i in range(10, 30)])
    assert index._table.version == before + 1
    assert index.count() == 10 * 3 + 20 * 2


@pytest.mark.parametrize("path", ["notes/it's.md", "notes/x' OR '1'='1.md", "notes/a b ü.md"])
def test_paths_with_quotes_and_spaces_can_be_replaced_too(vault, path):
    index = Index()
    index.replace_notes([note(path, chunks=3), note("notes/other.md")])
    index.replace_notes([note(path, chunks=1)])
    assert len(chunks_of(index, path)) == 1 and index.count() == 2
