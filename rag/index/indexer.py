"""Synchronize published notes into the local index. Retrieval lives in store and search."""

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from rag import config, git
from rag.index import chunker, embeddings
from rag.index.store import EmbeddedNote, Store, index_lock, read_lock

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    indexed: int = 0  # notes added or updated
    removed: int = 0  # notes deleted
    chunks: int = 0  # chunks written
    failed: dict[str, str] = field(default_factory=dict)  # notes that cannot be indexed, and why


def _chunk_and_embed_notes(head: str, paths: list[str], stats: SyncStats) -> Iterator[EmbeddedNote]:
    """The notes to write, chunked and embedded one at a time. A note that cannot be indexed is
    recorded in `stats.failed` instead."""
    for source in paths:
        try:
            if git.committed_file_size(head, source) > config.MAX_NOTE_BYTES:
                raise ValueError(f"larger than {config.MAX_NOTE_BYTES} bytes")
            text = git.read_committed_file(head, source)
            chunks = chunker.chunk_markdown(text, source)
            if not chunks:
                raise ValueError("no content to index")
            vectors = embeddings.embed_documents([chunk.embedding_text for chunk in chunks])
        except ValueError as error:  # unreadable or empty content, too large or too many tokens
            stats.failed[source] = str(error)
            logger.warning("skipped %s: %s", source, error)
            continue
        yield EmbeddedNote(source, chunks, vectors)


def _group_into_write_batches(notes: Iterable[EmbeddedNote]) -> Iterator[list[EmbeddedNote]]:
    """Groups of notes holding about WRITE_BATCH_CHUNKS chunks: every write to the index creates a
    data file, so notes are not written one by one."""
    batch: list[EmbeddedNote] = []
    size = 0
    for note in notes:
        batch.append(note)
        size += len(note.chunks)
        if size >= config.WRITE_BATCH_CHUNKS:
            yield batch
            batch = []
            size = 0
    if batch:
        yield batch


def sync() -> SyncStats:
    """Update the local index from the configured remote branch, independent of search."""
    with index_lock():
        head = git.remote_branch_tip(config.REMOTE, config.BRANCH)
        store = Store()
        since = store.indexed_commit()
        if since == head:
            return SyncStats()
        store.rebuild_if_needed()
        to_write, to_delete = git.plan_index(since, head, store.sources())
        stats = SyncStats(removed=len(to_delete))
        if to_write or to_delete:
            store.set_indexed_commit(None)  # partial writes must never claim to match a commit
        for batch in _group_into_write_batches(_chunk_and_embed_notes(head, to_write, stats)):
            store.replace_notes(batch)
            stats.indexed += len(batch)
            stats.chunks += sum(len(note.chunks) for note in batch)
        store.delete_notes(to_delete + list(stats.failed))  # nothing stale stays for a failed note
        store.set_indexed_commit(head)
        if to_write or to_delete:
            store.optimize()
        return stats


@dataclass
class Status:
    branch_tip: str  # the last known commit of the searched remote branch
    indexed_commit: str | None  # the commit the index matches
    pending: int  # notes a sync would add, update or remove
    notes: int  # notes in the index
    chunks: int


def status() -> Status:
    """Compare the index with Git without creating it, embedding or synchronizing notes."""
    # Read counts and the commit marker from the same locked snapshot.
    with read_lock():
        head = git.remote_branch_tip(config.REMOTE, config.BRANCH)
        if config.DB_DIR.is_dir():
            store = Store(create=False)
            indexed = store.indexed_commit()
            sources = store.sources()
            chunks = store.count()
        else:
            indexed = None
            sources = set()
            chunks = 0
        writes, deletes = git.plan_index(indexed, head, sources)
        return Status(
            branch_tip=head,
            indexed_commit=indexed,
            pending=len(writes) + len(deletes),
            notes=len(sources),
            chunks=chunks,
        )
