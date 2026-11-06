"""The local index on its own: the guarantees rag/db.py gives to the sync code."""

import pytest

import rag
from rag import config, db
from rag.chunker import Chunk
from rag.db import EmbeddedNote, Index


def note(source: str, vector_value: float = 0.1) -> EmbeddedNote:
    chunk = Chunk(f"text of {source}", "Title", 0)
    return EmbeddedNote(source, [chunk], [[vector_value] * config.EMBEDDING_SIZE])


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
