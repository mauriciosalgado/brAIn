import shutil
from functools import cache

from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType

from rag.config import (
    EMBED_BATCH_SIZE,
    EMBEDDING_SIZE,
    MODEL,
    MODEL_CACHE_DIR,
    MODEL_FILE,
    MODEL_FILES,
    QUERY_PREFIX,
)

# fastembed does not list this model, so it is registered here.
TextEmbedding.add_custom_model(
    MODEL,
    PoolingType.CLS,
    True,
    ModelSource(hf=MODEL),
    EMBEDDING_SIZE,
    model_file=MODEL_FILE,
    license="apache-2.0",
    size_in_gb=0.31,
    additional_files=MODEL_FILES,
)


@cache
def get_model() -> TextEmbedding:
    try:
        return TextEmbedding(MODEL, cache_dir=MODEL_CACHE_DIR)
    except Exception as error:  # fastembed raises many types for download problems
        raise RuntimeError(
            f"Could not load the embedding model {MODEL}. The first run downloads it "
            f"(about 320 MB) into {MODEL_CACHE_DIR}, so it needs internet once: {error}"
        ) from error


def model_works() -> bool:
    """Whether the model is on disk and gives vectors of the right size. Never downloads."""
    try:
        model = TextEmbedding(MODEL, cache_dir=MODEL_CACHE_DIR, local_files_only=True)
        return len(next(iter(model.embed(["test"])))) == EMBEDDING_SIZE
    except Exception:  # missing, partial or corrupt files raise many different errors
        return False


def ensure_model() -> None:
    """Keep a working model, or else download it again from scratch."""
    if model_works():
        return
    get_model.cache_clear()
    shutil.rmtree(MODEL_CACHE_DIR, ignore_errors=True)  # a damaged download is not resumed
    get_model()
    if not model_works():
        raise RuntimeError(f"The embedding model {MODEL} was downloaded but does not work")


def embed_documents(texts: list[str]) -> list[list[float]]:
    """The vector of each text, in input order. Texts are embedded shortest first, so a batch holds
    texts of similar length and needs little padding."""
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    vectors = get_model().embed([texts[i] for i in order], batch_size=EMBED_BATCH_SIZE)
    result: list[list[float]] = [[] for _ in texts]
    for index, vector in zip(order, vectors, strict=True):
        result[index] = vector.tolist()
    return result


def embed_query(question: str) -> list[float]:
    if not question.strip():
        raise ValueError("Query is empty")
    return embed_documents([QUERY_PREFIX + question])[0]
