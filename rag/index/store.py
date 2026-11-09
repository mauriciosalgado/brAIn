"""The local index: a LanceDB table on disk, one per developer, rebuilt from the notes.

The table holds passages and vectors. A marker records the settings and indexed commit.
Opening an existing table never rebuilds it; synchronization explicitly handles rebuilding.
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
from lancedb.query import LanceVectorQueryBuilder

from rag import config
from rag.index import chunker

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
            config.MODEL_MAX_TOKENS,
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
    """Keep updates and prepared readers from mixing table snapshots with newer commit markers."""
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
    """LanceDB passage operations and the marker identifying the indexed commit."""

    def __init__(self) -> None:
        self._db = lancedb.connect(config.DB_DIR)
        self._marker = config.DB_DIR / "indexed"
        if TABLE in self._db.list_tables().tables:
            self._table = self._db.open_table(TABLE)
        else:
            self._table = self._db.create_table(TABLE, schema=SCHEMA)
            self.set_indexed_commit(None)

    def rebuild_if_needed(self) -> None:
        """Rebuild a cache made with different settings. Only synchronization calls this."""
        if self._read_marker()[0] != FINGERPRINT:
            self._table = self._db.create_table(TABLE, schema=SCHEMA, mode="overwrite")
            self.set_indexed_commit(None)

    def _read_marker(self) -> tuple[str, str]:
        """The fingerprint of the settings the index was built with, and the commit it matches."""
        try:
            fingerprint, _, commit = self._marker.read_text().partition("\n")
        except FileNotFoundError:
            return "", ""
        return fingerprint, commit

    def indexed_commit(self) -> str | None:
        """The matching commit, or None for an incomplete or incompatible index."""
        fingerprint, commit = self._read_marker()
        if fingerprint != FINGERPRINT:
            return None
        return commit or None

    def set_indexed_commit(self, commit: str | None) -> None:
        """Record a completed commit, or None before changing indexed notes."""
        temporary = self._marker.with_suffix(f".{os.getpid()}")
        temporary.write_text(f"{FINGERPRINT}\n{commit or ''}")
        os.replace(temporary, self._marker)  # atomic

    def sources(self) -> set[str]:
        """The path of every indexed note."""
        batches = self._table.search().select(["source"]).limit(None).to_batches()
        return {source for batch in batches for source in batch.column("source").to_pylist()}

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
        query = self._table.search(vector)
        if not isinstance(query, LanceVectorQueryBuilder):
            raise RuntimeError("LanceDB did not create a vector query")
        query = (
            query.metric("cosine")
            .limit(limit)
            .nprobes(config.SEARCH_NPROBES)
            .refine_factor(config.SEARCH_REFINE_FACTOR)
            .select(["text", "source", "header_path", "_distance"])
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
