"""Finds the passages of the notes that match a question."""

from rag import config
from rag.index import embeddings
from rag.index.store import Hit, Store


def best_matches(hits: list[Hit]) -> list[Hit]:
    """The hits (best first) that score within SCORE_MARGIN of the best one. The scores of this
    model are compressed (a nonsense query still scores about 0.5), so noise is cut relative to
    the best hit, never with an absolute threshold."""
    if not hits:
        return []
    cutoff = hits[0]["score"] - config.SCORE_MARGIN
    return [hit for hit in hits if hit["score"] >= cutoff]


def query(question: str, store: Store, max_results: int = config.MAX_RESULTS) -> list[Hit]:
    """The chunks that match the question about as well as the best one does, best first, at most
    `max_results`. Every close chunk is returned, even when several come from one note.

    Reads the supplied database only. Its freshness and lifecycle belong to the caller.
    """
    if store.count() == 0:
        raise ValueError("No notes to search: the local index is empty.")
    vector = embeddings.embed_query(question)
    return best_matches(store.search(vector, max_results))
