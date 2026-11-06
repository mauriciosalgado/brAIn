"""The local index: a LanceDB table on disk, one per developer, rebuilt from the notes.

The table holds every chunk with its vector. Next to it, a small marker file records the settings
the index was built with and the git commit it matches. The commit is written last, so an
interrupted sync is simply repeated.
"""

import os
from datetime import timedelta
from typing import NamedTuple

import lancedb
import pyarrow as pa
from lancedb.index import IvfHnswSq

from rag import config
from rag.chunker import Chunk

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


class EmbeddedNote(NamedTuple):
    """A note ready to be stored: its path, its chunks and one vector per chunk."""

    source: str
    chunks: list[Chunk]
    vectors: list[list[float]]


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class Index:
    def __init__(self) -> None:
        config.DB_DIR.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(config.DB_DIR)
        self._marker = config.DB_DIR / "indexed"
        self._table = self._open()

    def _open(self):
        built_here = (
            self._read_marker()[0] == config.FINGERPRINT and TABLE in self._db.list_tables().tables
        )
        if not built_here:
            # Built with other settings, lost, or not set up yet: start afresh.
            self._db.drop_table(TABLE, ignore_missing=True)
            self._write_marker("")
        return self._db.create_table(TABLE, schema=SCHEMA, exist_ok=True)

    def _read_marker(self) -> tuple[str, str]:
        """The fingerprint of the settings the index was built with, and the commit it matches."""
        try:
            fingerprint, _, commit = self._marker.read_text().partition("\n")
        except FileNotFoundError:
            return "", ""
        return fingerprint, commit

    def _write_marker(self, commit: str) -> None:
        temporary = self._marker.with_suffix(f".{os.getpid()}")
        temporary.write_text(f"{config.FINGERPRINT}\n{commit}")
        os.replace(temporary, self._marker)  # atomic

    def indexed_commit(self) -> str | None:
        """The git commit the index matches, or None if nothing has been indexed yet."""
        return self._read_marker()[1] or None

    def set_indexed_commit(self, commit: str) -> None:
        self._write_marker(commit)

    def sources(self) -> set[str]:
        """The path of every indexed note."""
        rows = self._table.search().select(["source"]).limit(max(self.count(), 1)).to_arrow()
        return set(rows.column("source").to_pylist())

    def replace_notes(self, notes: list[EmbeddedNote]) -> None:
        """Swap the chunks of several notes at once. Every write to LanceDB creates a new data
        fragment, so callers batch notes instead of writing them one by one."""
        rows = [
            {
                "source": source,
                "chunk_index": chunk.chunk_index,
                "header_path": chunk.header_path,
                "text": chunk.text,
                "vector": vector,
            }
            for source, chunks, vectors in notes
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self.delete_notes([note.source for note in notes])
        if rows:
            self._table.add(rows)

    def delete_notes(self, sources: list[str]) -> None:
        if sources:
            self._table.delete(f"source IN ({', '.join(_quote(s) for s in sources)})")

    def count(self) -> int:
        return self._table.count_rows()

    def search(self, vector: list[float], limit: int) -> list[dict]:
        """The `limit` chunks most similar to `vector`, best first."""
        query = self._table.search(vector).metric("cosine").limit(limit)
        if self._has_vector_index():
            query = query.nprobes(config.SEARCH_NPROBES).refine_factor(config.SEARCH_REFINE_FACTOR)
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
        if self.count() >= config.INDEX_AFTER_ROWS and not self._has_vector_index():
            self._table.create_index(
                "vector",
                config=IvfHnswSq(
                    distance_type="cosine", num_partitions=max(8, int(self.count() ** 0.5 / 2))
                ),
                name=VECTOR_INDEX,
            )
        # Merges small files, adds new rows to the vector index, drops old versions: it costs
        # 0.03 s at 200,000 rows when there is nothing to do.
        self._table.optimize(cleanup_older_than=timedelta(days=1))
