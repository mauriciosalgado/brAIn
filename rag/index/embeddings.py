"""Load the search model and convert passages or questions to vectors."""

import shutil
from functools import cache
from pathlib import Path

from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType
from fastembed.text.onnx_embedding import OnnxTextEmbedding

from rag.config import EMBEDDING_SIZE, MODEL, MODEL_CACHE_DIR, MODEL_MAX_TOKENS

MODEL_FILE = "onnx/model_int8.onnx"  # the 320 MB quantized weights, not the default full-size ones
EMBED_BATCH_SIZE = 8  # fastembed's default of 256 needs about 10 GB of memory
QUERY_PREFIX = "query: "  # the model wants it on questions, not on notes

# fastembed does not list this model, so it is registered here. Its tokenizer and config files
# are downloaded by default.
TextEmbedding.add_custom_model(
    model=MODEL,
    pooling=PoolingType.CLS,
    normalization=True,
    sources=ModelSource(hf=MODEL),
    dim=EMBEDDING_SIZE,
    model_file=MODEL_FILE,
)


def _load_model(*, local_files_only: bool = False) -> OnnxTextEmbedding:
    model = TextEmbedding(MODEL, cache_dir=MODEL_CACHE_DIR, local_files_only=local_files_only).model
    if not isinstance(model, OnnxTextEmbedding) or model.tokenizer is None:
        raise RuntimeError(f"{MODEL} requires the ONNX text backend and a tokenizer")
    # The bundled tokenizer defaults to 512 tokens; the model supports a larger context.
    model.tokenizer.enable_truncation(max_length=MODEL_MAX_TOKENS)
    return model


@cache
def get_model() -> OnnxTextEmbedding:
    """Reuse one model per process instead of loading it for every request."""
    try:
        return _load_model()
    except Exception as error:  # fastembed raises many types for download problems
        raise RuntimeError(
            f"Could not load the embedding model {MODEL}. The first run downloads it "
            f"(about 320 MB) into {MODEL_CACHE_DIR}, so it needs internet once: {error}"
        ) from error


def _embeds(model: OnnxTextEmbedding) -> bool:
    """Whether the model gives vectors of the right size."""
    try:
        return len(next(iter(model.embed(["test"])))) == EMBEDDING_SIZE
    except Exception:  # damaged files raise many different errors
        return False


def model_works() -> bool:
    """Whether the model is on disk and works. Never downloads."""
    try:
        return _embeds(_load_model(local_files_only=True))
    except Exception:  # missing, partial or corrupt files raise many different errors
        return False


def ensure_model() -> None:
    """Keep a working model, or else download it again from scratch."""
    if model_works():
        return
    get_model.cache_clear()
    if Path(MODEL_CACHE_DIR).exists():
        shutil.rmtree(MODEL_CACHE_DIR)  # a damaged download is not resumed
    if not _embeds(get_model()):
        raise RuntimeError(f"The embedding model {MODEL} was downloaded but does not work")


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Return vectors in input order; FastEmbed handles batching."""
    model = get_model()
    if model.tokenizer is None:
        raise RuntimeError("The embedding model has no tokenizer")
    if any(encoding.overflowing for encoding in model.tokenizer.encode_batch(texts)):
        raise ValueError(
            f"Embedding text exceeds the model's {MODEL_MAX_TOKENS}-token limit. "
            "Shorten the question or reduce max_chunk_size."
        )
    return [vector.tolist() for vector in model.embed(texts, batch_size=EMBED_BATCH_SIZE)]


def embed_query(question: str) -> list[float]:
    if not question.strip():
        raise ValueError("Query is empty")
    return embed_documents([QUERY_PREFIX + question])[0]
