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
)

ROOT: Path = Path(__file__).resolve().parents[1]


class Settings(BaseModel):
    """What brain.toml may set. Each setting is explained there."""

    model_config = ConfigDict(extra="forbid", strict=True)

    branch: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = "main"
    remote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = "origin"
    skip_folders: list[str] = []
    skip_headings: list[str] = ["References", "Table of Contents", "TOC"]
    max_results: int = Field(10, ge=1, le=50)
    score_margin: float = Field(0.20, gt=0, le=1)
    min_score: float = Field(0.25, ge=0, le=1)
    max_chunk_size: int = Field(2000, ge=500, le=8000)


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

# Synchronization follows the remote-tracking branch, never unpushed local commits.
BRANCH: str = os.environ.get("BRAIN_BRANCH") or _SETTINGS.branch
REMOTE: str = _SETTINGS.remote
INDEX_REF: str = f"refs/remotes/{REMOTE}/{BRANCH}"
NOTES_DIR: Path = ROOT / "notes"
SKIP_FOLDERS: list[str] = _SETTINGS.skip_folders  # inside notes/
SKIP_HEADINGS: list[str] = _SETTINGS.skip_headings
MAX_RESULTS: int = _SETTINGS.max_results
SCORE_MARGIN: float = _SETTINGS.score_margin
MIN_SCORE: float = _SETTINGS.min_score
MAX_CHUNK_SIZE: int = _SETTINGS.max_chunk_size
DOCUMENT_CONTEXT_CHARS: int = 400
MAX_NOTE_BYTES: int = 2_000_000  # a larger note is not prose: it is skipped and reported

RAG_DIR: Path = ROOT / ".rag"  # the local index and model: never committed, always rebuildable
DB_DIR: Path = RAG_DIR / "lancedb"
LOCK_PATH: Path = RAG_DIR / "sync.lock"

READ_LOCK_TIMEOUT: float = 5  # seconds a search waits for a running sync before giving up
WRITE_BATCH_CHUNKS: int = 2000  # chunks per write, since each write creates a data file

# Apache-2.0 and multilingual. fastembed does not list it, so embeddings.py registers it.
MODEL: str = "Snowflake/snowflake-arctic-embed-m-v2.0"
EMBEDDING_SIZE: int = 768
# The context includes section paths and special tokens.
MODEL_MAX_TOKENS: int = 8192
MODEL_CACHE_DIR: str = str(RAG_DIR / "models")
