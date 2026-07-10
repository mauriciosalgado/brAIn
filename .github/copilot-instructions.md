# Copilot Instructions

## Project Overview

brAIn is a RAG (Retrieval-Augmented Generation) note-taking system. It indexes markdown notes from `notes/` into a ChromaDB vector database, then exposes semantic search via a CLI and an MCP server. The project uses `uv` as its package manager.

## Architecture

The system has two main components:

- **`rag/`** — Python package that handles the full RAG pipeline: markdown chunking → embedding → ChromaDB storage → semantic query. Entry points are `rag.sync()` and `rag.query()`.
- **`mcp/server.py`** — FastMCP server (currently a scaffold) intended to expose RAG functionality over MCP protocol on `localhost:8000`.

### RAG Pipeline Flow

1. `rag.sync()` globs `notes/**/*.md` and processes each file
2. `chunker.py` splits markdown by headers, builds hierarchical header paths (e.g. `Title > H2 > H3`), and merges small chunks
3. `embeddings.py` generates embeddings via fastembed (`BAAI/bge-small-en-v1.5`)
4. `db.py` stores/queries chunks in ChromaDB (persisted at `.rag/chroma_db`)
5. `rag.query()` embeds the question and does similarity search

### Key Configuration (`rag/config.py`)

All chunking/embedding constants live in `config.py`: `MAX_CHUNK_SIZE`, `MIN_CHUNK_SIZE`, `CHUNK_OVERLAP`, `SKIP_HEADERS`, `MODEL`, and DB paths. Change settings there, not inline.

## Commands

```bash
# Install dependencies
uv sync

# Run CLI commands
uv run rag sync          # Index all notes into ChromaDB
uv run rag query "text"  # Semantic search
uv run rag clean         # Wipe the vector database

# Run MCP server
uv run python mcp/server.py
```

## Notes Conventions (from STANDARDS.md)

Notes in `notes/` follow strict naming and structure rules:

- **Naming pattern:** `[dsf-]domain-[subdomain]-description.md` (all lowercase, hyphenated)
- **Folder structure:** `architecture/`, `handbook/`, `decisions/`, `scripts/`, `incidents/`
- **Incidents use date prefix:** `YYYY-MM-DD-domain-description.md`
- **Every note needs:** at least two tags (`#domain #type`), a title matching the filename, and follows the template in STANDARDS.md
- **Headers `References`, `Table of Contents`, and `TOC`** are skipped during chunking (see `SKIP_HEADERS` in config)

## Code Patterns

- **Lazy singletons** — Both `db.py` and `embeddings.py` use module-level globals with `_get_*()` initializers. Follow this pattern for expensive resources.
- **`splitter.py` is legacy** — The langchain-based splitter exists alongside `chunker.py` but `chunker.py` is the active chunking implementation used by `sync()`.
- **Embedding text enrichment** — Before embedding, chunks are prepended with preamble and header path context (see `_build_embedding_text` in `__init__.py`).
