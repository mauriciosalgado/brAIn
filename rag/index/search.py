"""Finds the passages of the notes that match a question."""

from rag import config
from rag.index import embeddings
from rag.index.store import Hit, Store


def best_matches(hits: list[Hit]) -> list[Hit]:
    """Keep hits above the absolute floor and within the margin of the best score.

    Cosine similarity is not calibrated confidence: irrelevant hits may exceed either cutoff.
    """
    if not hits:
        return []
    cutoff = max(config.MIN_SCORE, hits[0]["score"] - config.SCORE_MARGIN)
    return [hit for hit in hits if hit["score"] >= cutoff]


def query(question: str, store: Store, max_results: int = config.MAX_RESULTS) -> list[Hit]:
    """Return at most max_results matching fragments, ranked by similarity.

    Reads the supplied database only. Its freshness and lifecycle belong to the caller.
    """
    if store.count() == 0:
        raise ValueError("No notes to search: the local index is empty.")
    vector = embeddings.embed_query(question)
    return best_matches(store.search(vector, max_results))
