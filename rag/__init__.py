__version__ = "0.1.0"
__all__ = ["Status", "SyncStats", "query", "status", "sync"]


from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from filelock import FileLock

from rag import chunker, config, embeddings, git
from rag.chunker import Chunk
from rag.db import EmbeddedNote, Index


@dataclass
class SyncStats:
    indexed: int = 0  # notes added or updated
    removed: int = 0  # notes deleted
    chunks: int = 0  # chunks written
    failed: dict[str, str] = field(default_factory=dict)  # notes that cannot be indexed, and why


def _is_note(path: str) -> bool:
    """A Markdown file under notes/, but not inside a hidden folder such as .trash."""
    relative = PurePosixPath(path).relative_to(config.NOTES_DIR.relative_to(config.ROOT))
    return path.endswith(".md") and not any(part.startswith(".") for part in relative.parts)


def _notes_only(paths: list[str]) -> list[str]:
    return [path for path in paths if _is_note(path)]


def _plan(index: Index, head: str) -> tuple[list[str], list[str]]:
    """The notes to (re)index and the notes to remove to bring the index to commit `head`."""
    since = index.indexed_commit()
    if since == head:
        return [], []
    if since:
        try:
            to_index, to_remove = git.changed_notes(since, head)
        except git.GitError:  # the commit is gone, for example after a history rewrite
            pass
        else:
            return _notes_only(to_index), _notes_only(to_remove)
    # Nothing is indexed yet, or the history changed: start over from every note in the commit.
    everything = sorted(_notes_only(git.list_notes(head)))
    return everything, sorted(index.sources() - set(everything))


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
    for source, content in git.read_notes(head, paths):
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


def _sync(index: Index) -> SyncStats:
    head = git.main_commit()
    to_write, to_delete = _plan(index, head)
    stats = SyncStats(removed=len(to_delete))
    for batch in _batches(_embedded(head, to_write, stats)):
        index.replace_notes(batch)
    index.delete_notes(to_delete + list(stats.failed))  # nothing stale stays for a failed note
    index.set_indexed_commit(head)  # last, so an interrupted sync is repeated
    if to_write or to_delete:
        index.maintain()
    return stats


@contextmanager
def _exclusive():
    """Only one process changes the index at a time (LanceDB supports a single writer)."""
    config.RAG_DIR.mkdir(parents=True, exist_ok=True)
    with FileLock(config.LOCK_PATH):
        yield


def sync() -> SyncStats:
    """Bring the index to the tip of main: index the notes git reports as added or modified since
    the last sync and remove the deleted ones. Which branch is checked out does not matter."""
    with _exclusive():  # waits for any sync already running
        return _sync(Index())


def _close_to_best(hits: list[dict]) -> list[dict]:
    """The hits (sorted best first) that score within SCORE_MARGIN of the best one. The scores of
    this model are compressed (a nonsense query still scores about 0.5), so noise is cut relative
    to the best hit, never with an absolute threshold. The best hit is always kept."""
    if not hits:
        return []
    return [hit for hit in hits if hit["score"] >= hits[0]["score"] - config.SCORE_MARGIN]


def query(question: str, n_results: int = config.MAX_RESULTS) -> list[dict]:
    """The chunks that match the question about as well as the best one does, best first, at most
    `n_results`. It is the chunks that count, not the notes: every close chunk is returned, even
    when several come from one note.

    If main moved since the last sync (a pull, for example), the notes are synced first.
    """
    vector = embeddings.embed_query(question)
    index = Index()
    if index.indexed_commit() != git.main_commit():
        with _exclusive():
            _sync(index)  # does nothing if another process has just synced
    if index.count() == 0:
        raise ValueError(f"No notes to search: {config.BRANCH} has no Markdown notes.")
    return _close_to_best(index.search(vector, n_results))


@dataclass
class Status:
    main_commit: str  # the tip of main
    indexed_commit: str | None  # the commit the index matches
    pending: int  # notes a sync would add, update or remove
    notes: int  # notes in the index
    chunks: int


def status() -> Status:
    """How the index compares with git. Changes nothing."""
    index = Index()
    main = git.main_commit()
    writes, deletes = _plan(index, main)
    return Status(
        main,
        index.indexed_commit(),
        len(writes) + len(deletes),
        len(index.sources()),
        index.count(),
    )
