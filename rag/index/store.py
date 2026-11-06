"""The local index: a LanceDB table on disk, one per developer, rebuilt from the notes.

The table holds every chunk with its vector. Next to it, a small marker file records the settings
the index was built with and the git commit it matches. The commit is written last, so an
interrupted sync is simply repeated.
"""

import hashlib
import os
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import NamedTuple

import lancedb
import pyarrow as pa
from filelock import FileLock
from lancedb.index import IvfHnswSq

from rag import config
from rag.notes import chunker

TABLE = "chunks"
SCHEMA = pa.schema(
    [
        ("source", pa.string()),
        ("chunk_index", pa.int32()),
        ("header_path", pa.string()),
        ("text", pa.string()),
        ("vector", pa.list_(pa.float32(), config.EMBEDDING_SIZE)),
    ]
)
VECTOR_INDEX = "vector_idx"

# Everything that decides what is stored. When it changes, the index is rebuilt from the notes.
FINGERPRINT = hashlib.sha256(
    repr(
        (
            config.MODEL,
            config.EMBEDDING_SIZE,
            config.MAX_CHUNK_SIZE,
            config.MIN_CHUNK_SIZE,
            tuple(config.SKIP_HEADINGS),
            tuple(config.SKIP_FOLDERS),
            Path(chunker.__file__).read_bytes(),
        )
    ).encode()
).hexdigest()


@contextmanager
def write_lock():
    """Only one process changes the index at a time (LanceDB supports a single writer). Waits."""
    config.RAG_DIR.mkdir(parents=True, exist_ok=True)
    with FileLock(config.LOCK_PATH):
        yield


class EmbeddedNote(NamedTuple):
    """A note ready to be stored: its path, its chunks and one vector per chunk."""

    source: str
    chunks: list[chunker.Chunk]
    vectors: list[list[float]]


def _chunks_of(sources: list[str]) -> str:
    """A filter that matches every chunk of these notes."""
    quoted = ", ".join("'" + source.replace("'", "''") + "'" for source in sources)
    return f"source IN ({quoted})"


class Store:
    def __init__(self) -> None:
        config.DB_DIR.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(config.DB_DIR)
        self._marker = config.DB_DIR / "indexed"
        self._table = self._open()

    def _open(self):
        fingerprint, _ = self._read_marker()
        exists = TABLE in self._db.list_tables().tables
        if fingerprint != FINGERPRINT or not exists:
            # Built with other settings, lost, or not set up yet: start afresh.
            if exists:
                self._db.drop_table(TABLE)
            self.set_indexed_commit("")
        return self._db.create_table(TABLE, schema=SCHEMA, exist_ok=True)

    def _read_marker(self) -> tuple[str, str]:
        """The fingerprint of the settings the index was built with, and the commit it matches."""
        try:
            fingerprint, _, commit = self._marker.read_text().partition("\n")
        except FileNotFoundError:
            return "", ""
        return fingerprint, commit

    def indexed_commit(self) -> str | None:
        """The git commit the index matches, or None if nothing has been indexed yet."""
        return self._read_marker()[1] or None

    def set_indexed_commit(self, commit: str) -> None:
        """Record the commit the index matches ("" for none), with the current settings."""
        temporary = self._marker.with_suffix(f".{os.getpid()}")
        temporary.write_text(f"{FINGERPRINT}\n{commit}")
        os.replace(temporary, self._marker)  # atomic

    def sources(self) -> set[str]:
        """The path of every indexed note."""
        rows = self._table.search().select(["source"]).limit(max(self.count(), 1)).to_arrow()
        return set(rows.column("source").to_pylist())

    def replace_notes(self, notes: list[EmbeddedNote]) -> None:
        """Store these notes in place of what the index holds for them, in one atomic write: a
        search sees the old chunks or the new ones, never a note with none. Every write creates
        data files, so callers pass several notes at a time."""
        rows = [
            {
                "source": note.source,
                "chunk_index": chunk.chunk_index,
                "header_path": chunk.header_path,
                "text": chunk.text,
                "vector": vector,
            }
            for note in notes
            for chunk, vector in zip(note.chunks, note.vectors, strict=True)
        ]
        (
            self._table.merge_insert(["source", "chunk_index"])
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .when_not_matched_by_source_delete(_chunks_of([note.source for note in notes]))
            .execute(rows)
        )

    def delete_notes(self, sources: list[str]) -> None:
        if sources:
            self._table.delete(_chunks_of(sources))

    def count(self) -> int:
        return self._table.count_rows()

    def search(self, vector: list[float], limit: int) -> list[dict]:
        """The `limit` chunks most similar to `vector`, best first. The two tuning settings only
        apply when there is a vector index (large indexes); without one the scan is exact."""
        query = (
            self._table.search(vector)
            .metric("cosine")
            .limit(limit)
            .nprobes(config.SEARCH_NPROBES)
            .refine_factor(config.SEARCH_REFINE_FACTOR)
        )
        return [
            {
                "text": row["text"],
                "source": row["source"],
                "header_path": row["header_path"],
                "score": 1 - row["_distance"],  # cosine distance -> similarity
            }
            for row in query.to_list()
        ]

    def _has_vector_index(self) -> bool:
        return any(i.name == VECTOR_INDEX for i in self._table.list_indices())

    def maintain(self) -> None:
        """Keep search fast as the index grows and changes."""
        rows = self.count()
        if rows >= config.INDEX_AFTER_ROWS and not self._has_vector_index():
            self._table.create_index(
                "vector",
                config=IvfHnswSq(distance_type="cosine", num_partitions=max(8, int(rows**0.5 / 2))),
                name=VECTOR_INDEX,
            )
        # Merges small files, adds new rows to the vector index, drops old versions: it costs
        # 0.03 s at 200,000 rows when there is nothing to do.
        self._table.optimize(cleanup_older_than=timedelta(days=1))
