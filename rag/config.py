import hashlib
import os
import tomllib
from pathlib import Path

# RAG Configuration

# Paths are anchored to the repository, so commands work from any directory
ROOT: Path = Path(__file__).resolve().parents[1]
NOTES_DIR: Path = ROOT / "notes"
RAG_DIR: Path = ROOT / ".rag"  # local to each developer, rebuildable, never committed
DB_DIR: Path = RAG_DIR / "lancedb"
LOCK_PATH: Path = RAG_DIR / "sync.lock"  # one syncer at a time (LanceDB allows one writer)

# Settings a team chooses live in brain.toml, which is committed, so every developer, the git hooks
# and the MCP server agree. What it does not set has the default below.
_TEAM_DEFAULTS = {
    "branch": "main",
    "skip_headings": ["References", "Table of Contents", "TOC"],
    "max_results": 10,
    "score_margin": 0.10,
    "max_chunk_size": 1000,
    "min_chunk_size": 150,
}


def load_team_settings(path: Path) -> dict:
    """The settings in `path` over the defaults. A typo or a wrong value is an error."""
    settings = dict(_TEAM_DEFAULTS)
    try:
        found = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return settings
    except tomllib.TOMLDecodeError as error:
        raise RuntimeError(f"{path.name} is not valid TOML: {error}") from error
    if unknown := sorted(set(found) - set(settings)):
        raise RuntimeError(f"{path.name}: unknown setting {unknown}; known: {sorted(settings)}")
    settings.update(found)

    def need(ok: bool, message: str) -> None:
        if not ok:
            raise RuntimeError(f"{path.name}: {message}")

    def whole(name: str, low: int, high: int) -> bool:
        return type(settings[name]) is int and low <= settings[name] <= high

    headings, margin = settings["skip_headings"], settings["score_margin"]
    need(isinstance(settings["branch"], str) and settings["branch"].strip(), "`branch` is a name")
    need(
        isinstance(headings, list) and all(isinstance(h, str) for h in headings),
        '`skip_headings` is a list like ["References"]',
    )
    need(whole("max_results", 1, 50), "`max_results` is a whole number from 1 to 50")
    need(
        isinstance(margin, int | float) and not isinstance(margin, bool) and 0 < margin <= 1,
        "`score_margin` is a number above 0 and up to 1",
    )
    need(whole("max_chunk_size", 500, 8000), "`max_chunk_size` is a whole number from 500 to 8000")
    need(
        whole("min_chunk_size", 1, settings["max_chunk_size"] // 2),
        "`min_chunk_size` is a whole number, at most half of `max_chunk_size`",
    )
    return settings


_TEAM = load_team_settings(ROOT / "brain.toml")

# Vector search. Small indexes are scanned exactly (about 25 ms at 100,000 chunks); above
# INDEX_AFTER_ROWS an approximate index (IVF-HNSW) keeps queries near 10 ms at 500,000 chunks
# with 97-100% recall.
INDEX_AFTER_ROWS: int = 50_000
# Notes are written in batches of about this many chunks (each write creates a data file)
WRITE_BATCH_CHUNKS: int = 2000
SEARCH_NPROBES: int = 40
SEARCH_REFINE_FACTOR: int = 10
# A query returns the chunks within SCORE_MARGIN (cosine) of the best match, at most MAX_RESULTS.
# Measured on a 353-chunk mock vault with near-duplicate notes: 0.88 of questions found their
# section, in 5.6 chunks on average. A per-note cap, a keyword (BM25) hybrid and an absolute score
# floor were all tried and made results worse.
MAX_RESULTS: int = _TEAM["max_results"]
SCORE_MARGIN: float = _TEAM["score_margin"]

# Chunking Configuration
# About 1000 characters is roughly 250-350 tokens, far inside the model's 8192-token limit. The
# default size was chosen for a 512-token model and has not been re-tuned since.
MAX_CHUNK_SIZE: int = _TEAM["max_chunk_size"]
MIN_CHUNK_SIZE: int = _TEAM["min_chunk_size"]
SKIP_HEADERS: list[str] = _TEAM["skip_headings"]
MAX_NOTE_BYTES: int = 2_000_000  # larger files are skipped: a note this size is not prose

# The index is built from this branch, whichever branch is checked out: notes become searchable
# once they are merged into it (reviewed and approved), so every developer ends up with the same
# knowledge base. Any other branch is only for writing and committing notes. BRAIN_BRANCH lets one
# person override the team's choice.
BRANCH: str = os.environ.get("BRAIN_BRANCH") or _TEAM["branch"]

# Embedding Configuration
# Snowflake arctic-embed-m-v2.0: Apache-2.0, English and multilingual (German included), 8K context.
# fastembed does not list it, so embeddings.py registers it; the int8 ONNX file is 311 MB.
MODEL: str = "Snowflake/snowflake-arctic-embed-m-v2.0"
MODEL_FILE: str = "onnx/model_int8.onnx"
MODEL_FILES: list[str] = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
]
EMBEDDING_SIZE: int = 768  # the size of the vectors the model gives
MODEL_CACHE_DIR: str = str(RAG_DIR / "models")  # fastembed would default to $TMPDIR
# fastembed's default batch of 256 peaks near 10 GB of RAM; small batches of similar
# length need under 1 GB and are faster.
EMBED_BATCH_SIZE: int = 8
# The model needs this prefix on queries (not on documents) for best retrieval
QUERY_PREFIX: str = "query: "

# Everything that shapes the stored chunks and vectors. When it changes, the index is rebuilt
# from the notes on the next sync. The chunker's own source is part of it (it also defines the
# text that gets embedded), so changing how notes are chunked can never leave stale chunks.
FINGERPRINT: str = hashlib.sha256(
    repr(
        (
            MODEL,
            EMBEDDING_SIZE,
            MAX_CHUNK_SIZE,
            MIN_CHUNK_SIZE,
            tuple(SKIP_HEADERS),
            Path(__file__).with_name("chunker.py").read_bytes(),
        )
    ).encode()
).hexdigest()
