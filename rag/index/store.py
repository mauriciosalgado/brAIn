"""The local index: a LanceDB table on disk, one per developer, rebuilt from the notes.

The table holds passages and vectors. A marker records the settings and indexed commit.
Opening an existing table never rebuilds it; synchronization explicitly handles rebuilding.
"""

import hashlib
import os
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import NamedTuple, TypedDict, cast

import lancedb
import pyarrow as pa
from filelock import BaseFileLock, FileLock, Timeout
from lancedb.query import LanceVectorQueryBuilder

from rag import config
from rag.index import chunker, embeddings

TABLE = "chunks"
SCHEMA = pa.schema(
    [
        ("source", pa.string()),
        ("chunk_index", pa.int32()),
        ("header_path", pa.string()),
        ("tags", pa.list_(pa.string())),
        ("context", pa.string()),
        ("text", pa.string()),
        ("vector", pa.list_(pa.float32(), config.EMBEDDING_SIZE)),
    ]
)
_INDEX_UNAVAILABLE = "No usable search index. Run 'uv run rag sync' first."
_SYNC_RUNNING = "The index is being synchronized. Try again in a moment."

# Everything that decides what is stored: the settings and the code that cuts notes into passages
# and turns them into vectors. Code is shared with the team, so a pull that changes it must rebuild
# every index. When this changes, the index is rebuilt from the notes.
FINGERPRINT = hashlib.sha256(
    repr(
        (
            config.MODEL,
            config.EMBEDDING_SIZE,
            config.MODEL_MAX_TOKENS,
            config.MAX_CHUNK_SIZE,
            config.DOCUMENT_CONTEXT_CHARS,
            SCHEMA.to_string(),
            tuple(config.SKIP_HEADINGS),
            tuple(config.SKIP_FOLDERS),
            Path(chunker.__file__).read_bytes(),
            Path(embeddings.__file__).read_bytes(),
        )
    ).encode()
).hexdigest()


def index_lock(timeout: float = -1) -> BaseFileLock:
    """Keep index updates and readers from mixing table snapshots with commit markers."""
    return FileLock(config.LOCK_PATH, timeout=timeout)


def delete_index() -> None:
    """Delete the local index (not the model). The next `rag sync` rebuilds it from the notes."""
    with index_lock():
        if config.DB_DIR.is_dir():
            shutil.rmtree(config.DB_DIR)  # a real failure (permissions) must not report success


@contextmanager
def read_lock() -> Generator[None]:
    """The index lock for a reader. A sync can hold it for minutes, so a reader says so instead
    of hanging."""
    try:
        with index_lock(config.READ_LOCK_TIMEOUT):
            yield
    except Timeout as error:
        raise RuntimeError(_SYNC_RUNNING) from error


@contextmanager
def open_index():
    """Open a complete existing index for retrieval, without checking Git or synchronizing."""
    with read_lock():
        store = Store(create=False)
        if store.indexed_commit() is None:
            raise RuntimeError(_INDEX_UNAVAILABLE)
        yield store


class Hit(TypedDict):
    """A chunk found by a search."""

    text: str
    source: str
    header_path: str
    context: str
    score: float  # cosine similarity, higher is closer


class EmbeddedNote(NamedTuple):
    """A note ready to be stored: its path, its chunks and one vector per chunk."""

    source: str
    chunks: list[chunker.Chunk]
    vectors: list[list[float]]


def _source_filter(sources: list[str]) -> str:
    """A filter that matches every chunk of these notes."""
    quoted = ", ".join("'" + source.replace("'", "''") + "'" for source in sources)
    return f"source IN ({quoted})"


class Store:
    """LanceDB passage operations and the marker identifying the indexed commit."""

    def __init__(self, *, create: bool = True) -> None:
        if not create and not config.DB_DIR.is_dir():
            raise RuntimeError(_INDEX_UNAVAILABLE)
        self._db = lancedb.connect(config.DB_DIR)
        self._marker = config.DB_DIR / "indexed"
        if TABLE in self._db.list_tables().tables:
            self._table = self._db.open_table(TABLE)
        elif create:
            self._table = self._db.create_table(TABLE, schema=SCHEMA)
            self.set_indexed_commit(None)
        else:
            raise RuntimeError(_INDEX_UNAVAILABLE)

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
        sources: set[str] = set()
        for batch in batches:
            sources.update(batch.column("source").to_pylist())
        return sources

    def replace_notes(self, notes: list[EmbeddedNote]) -> None:
        """Store these notes in place of what the index holds for them, in one atomic write: a
        search sees the old chunks or the new ones, never a note with none. Every write creates
        data files, so callers pass several notes at a time."""
        rows = []
        for note in notes:
            for chunk, vector in zip(note.chunks, note.vectors, strict=True):
                rows.append(
                    {
                        "source": note.source,
                        "chunk_index": chunk.chunk_index,
                        "header_path": chunk.header_path,
                        "tags": chunk.tags,
                        "context": chunk.context,
                        "text": chunk.text,
                        "vector": vector,
                    }
                )
        (
            self._table.merge_insert(["source", "chunk_index"])
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .when_not_matched_by_source_delete(_source_filter([note.source for note in notes]))
            .execute(rows)
        )

    def delete_notes(self, sources: list[str]) -> None:
        if sources:
            self._table.delete(_source_filter(sources))

    def count(self) -> int:
        return self._table.count_rows()

    def search(self, vector: list[float], limit: int) -> list[Hit]:
        """The `limit` chunks most similar to `vector`, best first. It is an exact scan: LanceDB
        advises a vector index only from about a million rows."""
        query = (
            cast(LanceVectorQueryBuilder, self._table.search(vector))
            .distance_type("cosine")
            .limit(limit)
            .select(["text", "source", "header_path", "context", "_distance"])
        )
        return [
            {
                "text": row["text"],
                "source": row["source"],
                "header_path": row["header_path"],
                "context": row["context"],
                "score": 1 - row["_distance"],  # cosine distance -> similarity
            }
            for row in query.to_list()
        ]

    def optimize(self) -> None:
        """Merge the small data files that writes leave and drop old table versions."""
        self._table.optimize(cleanup_older_than=timedelta(days=1))
