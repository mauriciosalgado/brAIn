"""Finds the passages of the notes that match a question."""

from rag import config
from rag.index import embeddings, indexer
from rag.index.store import Store
from rag.notes import vault


def best_matches(hits: list[dict]) -> list[dict]:
    """The hits (best first) that score within SCORE_MARGIN of the best one. The scores of this
    model are compressed (a nonsense query still scores about 0.5), so noise is cut relative to
    the best hit, never with an absolute threshold."""
    if not hits:
        return []
    return [hit for hit in hits if hit["score"] >= hits[0]["score"] - config.SCORE_MARGIN]


def query(question: str, max_results: int = config.MAX_RESULTS) -> list[dict]:
    """The chunks that match the question about as well as the best one does, best first, at most
    `max_results`. Every close chunk is returned, even when several come from one note.

    If the branch moved since the last sync (a pull, for example), the notes are synced first.
    """
    vector = embeddings.embed_query(question)
    store = Store()
    if store.indexed_commit() != vault.branch_tip():
        indexer.sync(store)  # does nothing if another process has just synced
    if store.count() == 0:
        raise ValueError(f"No notes to search: {config.BRANCH} has no Markdown notes.")
    return best_matches(store.search(vector, max_results))
