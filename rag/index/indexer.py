"""Keeps the index in line with the notes on the searched branch."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from rag import config
from rag.index import embeddings
from rag.index.store import EmbeddedNote, Store, write_lock
from rag.notes import chunker, git, vault
from rag.notes.chunker import Chunk


@dataclass
class SyncStats:
    indexed: int = 0  # notes added or updated
    removed: int = 0  # notes deleted
    chunks: int = 0  # chunks written
    failed: dict[str, str] = field(default_factory=dict)  # notes that cannot be indexed, and why


def _plan(store: Store, head: str) -> tuple[list[str], list[str]]:
    """The notes to (re)index and the notes to remove to bring the index to commit `head`."""
    since = store.indexed_commit()
    if since == head:
        return [], []
    if since:
        try:
            to_index, to_remove = vault.changed_notes(since, head)
        except git.GitError:  # the commit is gone, for example after a history rewrite
            pass
        else:
            return to_index, to_remove
    # Nothing is indexed yet, or the history changed: start over from every note in the commit.
    everything = sorted(vault.list_notes(head))
    return everything, sorted(store.sources() - set(everything))


def _chunk(source: str, content: bytes) -> list[Chunk]:
    if len(content) > config.MAX_NOTE_BYTES:
        raise ValueError(f"larger than {config.MAX_NOTE_BYTES} bytes")
    chunks = chunker.chunk_markdown(content.decode("utf-8-sig"), source)
    if not chunks:
        raise ValueError("no content to index")
    return chunks


def _embedded(head: str, paths: list[str], stats: SyncStats) -> Iterator[EmbeddedNote]:
    """The notes to write, chunked and embedded one at a time. A note that cannot be indexed is
    recorded in `stats.failed` instead."""
    for source, content in vault.read_notes(head, paths):
        try:
            chunks = _chunk(source, content)
        except ValueError as error:  # too big, not UTF-8, or empty
            stats.failed[source] = str(error)
            continue
        stats.indexed += 1
        stats.chunks += len(chunks)
        vectors = embeddings.embed_documents([chunk.embedding_text for chunk in chunks])
        yield EmbeddedNote(source, chunks, vectors)


def _batches(notes: Iterable[EmbeddedNote]) -> Iterator[list[EmbeddedNote]]:
    """Groups of notes holding about WRITE_BATCH_CHUNKS chunks: every write to the index creates a
    data file, so notes are not written one by one."""
    batch, size = [], 0
    for note in notes:
        batch.append(note)
        size += len(note.chunks)
        if size >= config.WRITE_BATCH_CHUNKS:
            yield batch
            batch, size = [], 0
    if batch:
        yield batch


def sync(store: Store | None = None) -> SyncStats:
    """Bring the index to the tip of the branch: index the notes added or modified since the last
    sync and remove the deleted ones. Which branch is checked out does not matter."""
    with write_lock():
        store = store or Store()
        head = vault.branch_tip()
        to_write, to_delete = _plan(store, head)
        stats = SyncStats(removed=len(to_delete))
        for batch in _batches(_embedded(head, to_write, stats)):
            store.replace_notes(batch)
        store.delete_notes(to_delete + list(stats.failed))  # nothing stale stays for a failed note
        store.set_indexed_commit(head)  # last, so an interrupted sync is repeated
        if to_write or to_delete:
            store.maintain()
        return stats


@dataclass
class Status:
    branch_tip: str  # the latest commit of the searched branch
    indexed_commit: str | None  # the commit the index matches
    pending: int  # notes a sync would add, update or remove
    notes: int  # notes in the index
    chunks: int


def status() -> Status:
    """How the index compares with git. Changes nothing."""
    store = Store()
    head = vault.branch_tip()
    writes, deletes = _plan(store, head)
    return Status(
        head,
        store.indexed_commit(),
        len(writes) + len(deletes),
        len(store.sources()),
        store.count(),
    )
