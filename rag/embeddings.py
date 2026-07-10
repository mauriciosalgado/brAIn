from fastembed import TextEmbedding
from rag.config import MODEL

_model: TextEmbedding | None = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(MODEL)
    return _model


def get_embeddings(documents: list[str]) -> list[list[float]]:
    return [embedding.tolist() for embedding in get_model().embed(documents)]
