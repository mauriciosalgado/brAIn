import os
import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

ROOT: Path = Path(__file__).resolve().parents[1]


class Settings(BaseModel):
    """What brain.toml may set. Each setting is explained there."""

    model_config = ConfigDict(extra="forbid", strict=True)

    branch: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = "main"
    skip_folders: list[str] = []
    skip_headings: list[str] = ["References", "Table of Contents", "TOC"]
    max_results: int = Field(10, ge=1, le=50)
    score_margin: float = Field(0.10, gt=0, le=1)
    max_chunk_size: int = Field(1000, ge=500, le=8000)
    min_chunk_size: int = Field(150, ge=1)

    @model_validator(mode="after")
    def _min_chunk_size_is_at_most_half_of_max(self):
        if self.min_chunk_size > self.max_chunk_size // 2:
            raise ValueError("min_chunk_size must be at most half of max_chunk_size")
        return self


def load_settings(path: Path) -> Settings:
    """The settings in `path`; anything it does not set has its default."""
    try:
        found = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        found = {}
    except tomllib.TOMLDecodeError as error:
        raise RuntimeError(f"{path.name} is not valid TOML: {error}") from error
    try:
        return Settings(**found)
    except ValidationError as error:
        problems = "; ".join(
            f"`{e['loc'][0] if e['loc'] else ''}` {e['msg']}" for e in error.errors()
        )
        raise RuntimeError(f"{path.name}: {problems}") from error


_SETTINGS = load_settings(ROOT / "brain.toml")

# The index holds this branch, whichever branch is checked out. BRAIN_BRANCH overrides brain.toml.
BRANCH: str = os.environ.get("BRAIN_BRANCH") or _SETTINGS.branch
NOTES_DIR: Path = ROOT / "notes"
SKIP_FOLDERS: list[str] = _SETTINGS.skip_folders  # inside notes/
SKIP_HEADINGS: list[str] = _SETTINGS.skip_headings
MAX_RESULTS: int = _SETTINGS.max_results
SCORE_MARGIN: float = _SETTINGS.score_margin
MAX_CHUNK_SIZE: int = _SETTINGS.max_chunk_size
MIN_CHUNK_SIZE: int = _SETTINGS.min_chunk_size
MAX_NOTE_BYTES: int = 2_000_000  # a larger note is not prose: it is skipped and reported

RAG_DIR: Path = ROOT / ".rag"  # the local index and model: never committed, always rebuildable
DB_DIR: Path = RAG_DIR / "lancedb"
LOCK_PATH: Path = RAG_DIR / "sync.lock"

INDEX_AFTER_ROWS: int = 50_000  # from here on, search uses an approximate index, not a full scan
WRITE_BATCH_CHUNKS: int = 2000  # chunks per write, since each write creates a data file
SEARCH_NPROBES: int = 40
SEARCH_REFINE_FACTOR: int = 10

# Apache-2.0 and multilingual. fastembed does not list it, so embeddings.py registers it.
MODEL: str = "Snowflake/snowflake-arctic-embed-m-v2.0"
MODEL_FILE: str = "onnx/model_int8.onnx"
MODEL_FILES: list[str] = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
]
EMBEDDING_SIZE: int = 768
MODEL_CACHE_DIR: str = str(RAG_DIR / "models")
EMBED_BATCH_SIZE: int = 8  # fastembed's default of 256 needs about 10 GB of memory
QUERY_PREFIX: str = "query: "  # the model wants it on questions, not on notes
