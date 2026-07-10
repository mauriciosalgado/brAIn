# brAIn — Project Structure & Engineering Standards

> **Date:** 2026-06-06
> **Purpose:** Define the target project structure, configuration patterns, and Python best practices for brAIn
> **Audience:** Contributors and teams adopting brAIn

---

## Table of Contents

1. [Current vs Target Project Layout](#1-current-vs-target-project-layout)
2. [Why `src/` Layout](#2-why-src-layout)
3. [Configuration Strategy](#3-configuration-strategy)
4. [Dependency Management](#4-dependency-management)
5. [CLI Design](#5-cli-design)
6. [Logging](#6-logging)
7. [Error Handling](#7-error-handling)
8. [Chunking Strategy](#8-chunking-strategy)
9. [Linting, Formatting & Type Checking](#9-linting-formatting--type-checking)
10. [Testing](#10-testing)
11. [Git & CI/CD Hygiene](#11-git--cicd-hygiene)
12. [Module Design Principles](#12-module-design-principles)

---

## 1. Current vs Target Project Layout

### Current (flat layout, no tests, no config file)

```
brAIn/
├── rag/
│   ├── __init__.py          ← sync/query/cleanup live here (too much)
│   ├── chunker.py
│   ├── cli.py               ← raw sys.argv
│   ├── config.py             ← hardcoded constants
│   ├── db.py
│   ├── embeddings.py
│   ├── git.py                ← stubs, unused
│   └── splitter.py           ← dead code
├── mcp/
│   └── server.py             ← scaffold, not a package
├── notes/
├── pyproject.toml
└── README.md
```

**Problems:**
- `rag/` sits at the root, so `import rag` can accidentally import from source instead of the installed package
- No tests, no linting config, no type checking
- `mcp/` is a loose directory, not a proper package
- Config is hardcoded constants — no file, no env vars, no validation
- `__init__.py` does too much (business logic + API surface)

### Target (`src/` layout, proper packages, config file)

```
brAIn/
├── src/
│   └── brain/                        ← renamed from "rag" to match the project
│       ├── __init__.py               ← version + public API only
│       ├── chunker.py                ← markdown → chunks
│       ├── cli.py                    ← click/argparse CLI
│       ├── config.py                 ← pydantic-settings, loads brain.toml + env
│       ├── db.py                     ← ChromaDB wrapper
│       ├── embeddings.py             ← fastembed wrapper
│       ├── reranker.py               ← cross-encoder reranking (new)
│       ├── sync.py                   ← incremental sync engine (new, from __init__)
│       ├── query.py                  ← query pipeline (new, from __init__)
│       └── models.py                 ← dataclasses: Chunk, QueryResult (new)
├── src/
│   └── mcp_server/                   ← proper package
│       ├── __init__.py
│       └── server.py
├── tests/
│   ├── conftest.py                   ← shared fixtures
│   ├── test_chunker.py
│   ├── test_sync.py
│   ├── test_query.py
│   └── test_config.py
├── notes/                            ← the actual knowledge base
├── brain.toml                        ← team-specific config
├── pyproject.toml                    ← project metadata, deps, tool config
├── README.md
├── STANDARDS.md
├── .gitignore
└── .github/
    ├── copilot-instructions.md
    └── workflows/
        └── ci.yml                    ← lint + test on push/PR
```

### Key Changes

| What | Why |
|------|-----|
| `src/` layout | Prevents accidental imports from source; catches packaging bugs early |
| `rag/` → `brain/` | Package name should match the project, not a generic acronym |
| Business logic out of `__init__.py` | `__init__.py` should only define the public API surface and version |
| Dedicated `sync.py` and `query.py` | Single responsibility — each module does one thing |
| `models.py` for dataclasses | Shared types (`Chunk`, `QueryResult`) in one place |
| `mcp_server/` as a package | Proper package with `__init__.py`, not a loose script |
| `tests/` at the root | Standard location, outside the package |

---

## 2. Why `src/` Layout

The `src/` layout is the **recommended standard** for Python projects in 2025+
(per PyPA, Hynek Schlawack, and the broader packaging community).

```
    FLAT LAYOUT (current)                 SRC LAYOUT (target)
    ─────────────────────                 ─────────────────────

    brAIn/                                brAIn/
    ├── rag/                              ├── src/
    │   ├── __init__.py                   │   └── brain/
    │   └── ...                           │       ├── __init__.py
    ├── tests/                            │       └── ...
    └── pyproject.toml                    ├── tests/
                                          └── pyproject.toml

    $ cd brAIn                            $ cd brAIn
    $ python -c "import rag"              $ python -c "import brain"
    ✅ Works (imports from source)        ❌ Fails (must install first)

    Problem: You think your packaging     Benefit: Forces you to install.
    works, but you're importing from      If it works, it works everywhere.
    the local directory, not the
    installed package.
```

The only cost is adding `src/` to the package discovery in `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/brain"]
```

---

## 3. Configuration Strategy

### The Problem Today

`config.py` has hardcoded constants. There's no way for teams to customize behavior
without editing source code. No environment variable support. No validation.

### The Solution: Layered Configuration

Configuration should come from multiple sources, merged in a clear order of precedence:

```
    LOWEST PRIORITY                                    HIGHEST PRIORITY
    ──────────────                                     ────────────────

    ┌─────────────┐    ┌─────────────┐    ┌──────────────┐    ┌────────────┐
    │  Code        │ ←  │  brain.toml  │ ←  │  Environment │ ←  │  CLI flags │
    │  Defaults    │    │  (project)   │    │  Variables   │    │  (runtime) │
    └─────────────┘    └─────────────┘    └──────────────┘    └────────────┘

    Hardcoded in        Checked into        Set per machine     Override for
    the Python code.    the repo. Shared    or CI environment.  a single run.
    Always present.     across the team.    Not committed.
```

### What Goes Where

| Setting | brain.toml | Env var | CLI flag |
|---------|-----------|---------|----------|
| Embedding model | ✅ | ✅ `BRAIN_EMBEDDING_MODEL` | — |
| Notes directory | ✅ | ✅ `BRAIN_NOTES_DIR` | — |
| Reranking on/off | ✅ | ✅ `BRAIN_RERANKING_ENABLED` | — |
| Number of results | ✅ | — | `--top-n 10` |
| Query text | — | — | `rag query "..."` |
| Log level | — | ✅ `BRAIN_LOG_LEVEL` | `--verbose` |

### Implementation: `pydantic-settings`

Use `pydantic-settings` (not raw `tomllib` or `os.environ`).
It gives you type validation, layered sources, and clear error messages — all in one.

**Why `pydantic-settings` over alternatives:**

| Library | Type-safe | TOML | Env vars | Validation | Verdict |
|---------|-----------|------|----------|------------|---------|
| `pydantic-settings` | ✅ | ✅ | ✅ | ✅ | **Best fit** — modern, typed, layered |
| `dynaconf` | ❌ | ✅ | ✅ | ❌ | Flexible but no type safety |
| `tomllib` + `os.environ` | ❌ | ✅ | Manual | ❌ | DIY — fragile, no validation |
| `python-dotenv` | ❌ | ❌ | ✅ | ❌ | Only .env files, no structure |

### Environment Variable Naming Convention

All env vars use the prefix `BRAIN_` and follow the section/key structure:

```
brain.toml section      Key                 Env var
──────────────────      ───                 ───────
[embedding]             model               BRAIN_EMBEDDING_MODEL
[chunking]              max_chunk_size      BRAIN_CHUNKING_MAX_CHUNK_SIZE
[reranking]             enabled             BRAIN_RERANKING_ENABLED
[general]               notes_dir           BRAIN_NOTES_DIR
```

Env vars always win over `brain.toml` values. This lets developers override
team defaults locally without modifying the config file.

---

## 4. Dependency Management

### Current Problems

- `langchain-text-splitters` is a dependency but only used by dead code (`splitter.py`)
- No separation between runtime and development dependencies
- No version pinning strategy beyond `>=`

### Target `pyproject.toml`

```toml
[project]
name = "brain"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "chromadb>=1.0.0",
    "fastembed>=0.4.0",
    "fastmcp>=3.0.0",
    "pydantic-settings>=2.0.0",
    "click>=8.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.8.0",
    "mypy>=1.13",
]

[project.scripts]
brain = "brain.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/brain"]
```

### Dependency Principles

| Principle | Rule |
|-----------|------|
| **No dead dependencies** | Every dep must be imported somewhere. Remove `langchain-text-splitters`. |
| **Separate runtime from dev** | Runtime deps in `dependencies`, dev tools in `[project.optional-dependencies]` |
| **Minimum Python 3.11** | Gives us `tomllib` in stdlib, better error messages, performance improvements |
| **Use `uv` for everything** | `uv sync` for install, `uv run` for execution. Consistent across team. |
| **Lock file committed** | `uv.lock` is committed to ensure reproducible builds across machines |

### Install Commands

```bash
uv sync                   # Install runtime dependencies
uv sync --extra dev       # Install runtime + dev dependencies
uv run brain sync         # Run the CLI
uv run pytest             # Run tests
uv run ruff check .       # Run linter
```

---

## 5. CLI Design

### Current Problem

`cli.py` uses raw `sys.argv` parsing — no help text, no flags, no validation,
no error messages. `query()` prints results and returns `None`, which the CLI then prints.

### Target: Use `click`

`click` is the standard for Python CLIs. It gives you help text, argument validation,
typed parameters, and composable commands for free.

**Design the CLI as a thin layer.** It should parse arguments, call the library,
and format output. No business logic in the CLI.

```
    CLI Layer (thin)                    Library Layer (all logic)
    ────────────────                    ────────────────────────

    cli.py                              sync.py, query.py, db.py
    ├── parse args                      ├── chunk files
    ├── call library functions          ├── embed text
    ├── format output for terminal      ├── store/query vectors
    └── set exit codes                  └── return structured results

    The CLI is a UI.                    The library is the engine.
    It could be replaced by MCP         It works the same regardless
    or a Python import.                 of who calls it.
```

### Target CLI Commands

```
$ brain sync              # Incremental sync (default)
$ brain sync --full       # Force full re-index
$ brain query "question"  # Search notes
$ brain query "q" -n 10   # Return 10 results
$ brain clean             # Wipe the database
$ brain status            # Show index health: files, chunks, model, last sync
```

---

## 6. Logging

### Current Problem

`chunker.py` uses `logging.getLogger(__name__)` (correct), but there's no logging
configuration anywhere. No other module logs anything. Errors are silent.

### Target: `logging` stdlib (keep it simple)

For a CLI tool, stdlib `logging` is the right choice. `structlog` is overkill here —
brAIn is not a web service with request contexts and JSON log aggregation.

**Rules:**

| Rule | Why |
|------|-----|
| Every module gets `logger = logging.getLogger(__name__)` | Consistent, filterable by module |
| Default level: `WARNING` | CLI users shouldn't see noise by default |
| `--verbose` flag sets level to `INFO` | Developer-friendly when debugging |
| `BRAIN_LOG_LEVEL` env var for fine control | e.g., `BRAIN_LOG_LEVEL=DEBUG` |
| Log to `stderr`, not `stdout` | `stdout` is for results; `stderr` is for diagnostics |
| Never `print()` for operational messages | Use `logger.info()` instead |
| `print()` only in the CLI layer for user-facing output | The library layer never prints |

### What to Log

```
    Level     What to log                                  Example
    ─────     ──────────────────────────────────────────  ───────
    DEBUG     Internal state, chunk details               "Chunk 3: 450 chars, header: Install > macOS"
    INFO      Operational progress                        "Syncing 3 changed files..."
    WARNING   Non-fatal issues                            "Large chunk (2100 chars) in notes/x.md"
    ERROR     Failures that affect results                "Failed to embed notes/x.md: model not found"
```

---

## 7. Error Handling

### Current Problem

No try/except anywhere. If ChromaDB fails or a file is unreadable, the entire
process crashes with a raw traceback.

### Target: Fail Gracefully, Fail Loudly

```
    SYNC errors                          QUERY errors
    ───────────                          ────────────

    One file fails to chunk?             Database is empty?
    → Log the error                      → Clear error message:
    → Skip the file                        "No notes indexed. Run: brain sync"
    → Continue syncing the rest
                                         Embedding model fails to load?
    File is unreadable?                  → Clear error message with fix:
    → Log warning                          "Model not found. Run: uv sync"
    → Skip it
                                         ChromaDB corrupted?
    Embedding fails?                     → Suggest: "Run: brain clean && brain sync"
    → Log error with file path
    → Skip the file
    → Continue
```

### Principles

| Principle | Example |
|-----------|---------|
| **Never crash silently** | Always log what went wrong and why |
| **Never crash on one bad file** | Sync should process all files it can, report failures at the end |
| **User-facing errors should suggest a fix** | "Database empty. Run `brain sync` to index your notes." |
| **Library functions raise exceptions** | `query()` raises `ValueError` if DB is empty |
| **CLI catches exceptions and formats them** | The CLI turns exceptions into readable messages + exit codes |
| **Use custom exception classes** | `BrainConfigError`, `BrainSyncError`, `BrainQueryError` |

---

## 8. Chunking Strategy

### The Industry Landscape (2025-2026)

There are six major approaches to chunking documents for RAG. Each has different
tradeoffs in retrieval quality, speed, and complexity.

```
┌──────────────────────────┬───────────┬───────────┬──────────────────────────────────────────┐
│ Strategy                 │ Quality   │ Complexity│ When to Use                              │
├──────────────────────────┼───────────┼───────────┼──────────────────────────────────────────┤
│ ① Fixed-Size             │ ★★☆☆☆    │ Trivial   │ Prototyping only. Splits mid-sentence,   │
│   (every N tokens)       │           │           │ loses all structure. Never for prod.      │
├──────────────────────────┼───────────┼───────────┼──────────────────────────────────────────┤
│ ② Recursive Character    │ ★★★☆☆    │ Low       │ Generic text without clear structure.     │
│   (LangChain default)    │           │           │ Tries paragraph → sentence → char.       │
│                          │           │           │ Decent baseline for unknown formats.      │
├──────────────────────────┼───────────┼───────────┼──────────────────────────────────────────┤
│ ③ Markdown Header        │ ★★★★☆    │ Low       │ Structured docs with consistent headers.  │
│   (split on ## / ###)    │           │           │ ★ OUR APPROACH. Perfect for notes with   │
│                          │           │           │ predictable hierarchy.                   │
├──────────────────────────┼───────────┼───────────┼──────────────────────────────────────────┤
│ ④ Semantic Chunking      │ ★★★★★    │ High      │ Complex docs where topic shifts mid-     │
│   (embedding similarity) │           │           │ section. 10-14x slower than header-based.│
│                          │           │           │ Overkill for well-structured markdown.   │
├──────────────────────────┼───────────┼───────────┼──────────────────────────────────────────┤
│ ⑤ Parent-Child           │ ★★★★★    │ Medium    │ Deeply nested docs. Index children for   │
│   (hierarchical)         │           │           │ search, but return the parent section    │
│                          │           │           │ for full context. Best with markdown.    │
├──────────────────────────┼───────────┼───────────┼──────────────────────────────────────────┤
│ ⑥ Proposition-Based      │ ★★★★★    │ Very High │ Fact-heavy Q&A (legal, medical). Each    │
│   (atomic facts)         │           │           │ chunk = one fact. Requires NLP parsing.  │
│                          │           │           │ Overkill for engineering notes.          │
└──────────────────────────┴───────────┴───────────┴──────────────────────────────────────────┘
```

### Our Approach: Header-Based + Contextual Enrichment

For structured markdown notes (which is exactly what brAIn indexes), **header-based
chunking** is the right strategy. It's the natural choice because:

- Notes already have semantic boundaries (headers)
- It's fast (regex, no ML model needed at chunk time)
- Chunks are self-contained, meaningful sections
- It preserves document hierarchy as metadata

But we augment it with **contextual enrichment** (a technique Anthropic recommends),
where each chunk's embedding text is prepended with the note's preamble and its
position in the header hierarchy. This gives the search engine context that the
raw chunk text alone lacks.

```
    OUR STRATEGY: Header-Based + Contextual Enrichment
    ═══════════════════════════════════════════════════

    ┌────────────────────────────────────────────────────────────────┐
    │  RAW MARKDOWN                                                  │
    │                                                                │
    │  # Deploying EDC Connectors              ← title               │
    │  A guide for deploying connectors...     ← preamble            │
    │                                                                │
    │  ## Prerequisites                        ← chunk 0 starts      │
    │  You need Kubernetes 1.28+ and...                              │
    │                                                                │
    │  ## Helm Configuration                   ← chunk 1 starts      │
    │  The values.yaml file controls...                              │
    │                                                                │
    │  ### Ingress Settings                    ← chunk 2 starts      │
    │  Enable ingress by setting...                                  │
    │                                                                │
    └────────────────────────────────────────────────────────────────┘
                           │
                           ▼ chunking
    ┌────────────────────────────────────────────────────────────────┐
    │  CHUNK 2                                                       │
    │                                                                │
    │  Stored text (what the user sees):                             │
    │  ┌────────────────────────────────────────────────────────┐    │
    │  │ ### Ingress Settings                                   │    │
    │  │ Enable ingress by setting...                           │    │
    │  └────────────────────────────────────────────────────────┘    │
    │                                                                │
    │  Embedding text (what the model sees, richer):                 │
    │  ┌────────────────────────────────────────────────────────┐    │
    │  │ A guide for deploying connectors...    ← preamble      │    │
    │  │                                                        │    │
    │  │ Section: Deploying EDC > Helm Config > Ingress         │    │
    │  │                                        ← hierarchy     │    │
    │  │ ### Ingress Settings                                   │    │
    │  │ Enable ingress by setting...           ← content       │    │
    │  └────────────────────────────────────────────────────────┘    │
    │                                                                │
    │  Metadata:                                                     │
    │  ├── source: "notes/architecture/edc-deploy.md"                │
    │  └── header_path: "Deploying EDC > Helm Config > Ingress"     │
    │                                                                │
    └────────────────────────────────────────────────────────────────┘
```

### Advanced Option: Parent-Child Retrieval

For teams with deeply nested, long documents, we can add **parent-child retrieval**
as an optional enhancement. The idea:

- **Index at the child level** (H3, H4 sub-sections) — fine-grained for search
- **Return the parent** (H2 section) — more context for the LLM to reason over

```
    PARENT-CHILD RETRIEVAL (optional enhancement)
    ═════════════════════════════════════════════

    Index:
    ┌─────────────────────────────────────────────────────────┐
    │  Chunk A (child): "### macOS\nbrew install opencode"    │──┐
    │  Chunk B (child): "### Linux\napt-get install..."       │──┤
    │  Chunk C (child): "### Windows\nwinget install..."      │──┤
    └─────────────────────────────────────────────────────────┘  │
                                                                 │
    Query: "How do I install on Mac?"                             │
    Match: Chunk A (child)                                       │
                                                                 │
    Instead of returning just the child, return the PARENT:      │
    ┌─────────────────────────────────────────────────────────┐  │
    │  ## Installation                            (parent)    │◄─┘
    │  Run the following for your platform:                   │
    │                                                         │
    │  ### macOS                                              │
    │  brew install opencode                                  │
    │                                                         │
    │  ### Linux                                              │
    │  apt-get install opencode                               │
    │                                                         │
    │  ### Windows                                            │
    │  winget install opencode                                │
    └─────────────────────────────────────────────────────────┘

    The LLM gets the full section context, not just one sub-section.
```

This requires storing a `parent_id` in chunk metadata and doing a lookup
after retrieval. It adds complexity but dramatically helps when notes have
many short sub-sections under meaningful parent sections.

### Chunk Size & Overlap: What the Research Says

| Parameter | Recommendation | Reasoning |
|-----------|---------------|-----------|
| **Max chunk size** | 1,000–1,500 chars | Fits within embedding context windows (512 tokens ≈ 2,000 chars). Smaller = more precise retrieval. |
| **Min chunk size** | 100–200 chars | Below this, a chunk has too little meaning to be useful on its own. Merge into the previous. |
| **Overlap** | 0–200 chars | 2026 research shows overlap provides **diminishing returns** for header-based chunking. Useful for recursive/fixed-size where boundaries are arbitrary, but less needed when boundaries are semantic (headers). Start with 0, add if retrieval quality suffers. |

### Decision: What brAIn Should Implement

| Level | Strategy | When it activates |
|-------|---------|-------------------|
| **Default** | Header-based + contextual enrichment | Always. Every team gets this. |
| **Enhancement** | Parent-child retrieval | Configurable. For teams with deep hierarchies. |
| **Not needed** | Semantic chunking | Notes already have headers. Semantic splitting adds cost without benefit for structured markdown. |
| **Not needed** | Proposition-based | Engineering notes aren't atomic fact databases. Overkill. |
| **Not needed** | Fixed-size / recursive | These are fallbacks for unstructured text. Our notes are structured by convention (STANDARDS.md). |

### Chunking Config

```toml
# brain.toml
[chunking]
max_chunk_size = 1500
min_chunk_size = 200
chunk_overlap = 0                    # start with 0 for header-based; tune if needed
skip_headers = ["References", "Table of Contents", "TOC"]
parent_child_retrieval = false       # enable for deeply nested docs
```

---

## 9. Linting, Formatting & Type Checking

### Current State

A `.ruff_cache/` exists (so ruff has been run manually), but there's no config
in `pyproject.toml` and no CI enforcement.

### Target: Ruff + Mypy, configured in `pyproject.toml`

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = [
    "F",      # pyflakes — catches unused imports, undefined names
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "I",      # isort — import sorting
    "UP",     # pyupgrade — modernize syntax
    "B",      # bugbear — catches common bugs
    "SIM",    # simplify — suggests cleaner code
    "N",      # pep8-naming — naming conventions
]

[tool.ruff.lint.isort]
known-first-party = ["brain"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
check_untyped_defs = true
disallow_untyped_defs = true
no_implicit_optional = true
show_error_codes = true
```

### Enforcement

```bash
uv run ruff check .          # Lint
uv run ruff format .         # Format
uv run mypy src/             # Type check
```

All three run in CI on every push and PR. PRs cannot merge if any fail.

### Type Annotations

Every public function must have type annotations. This is non-negotiable for
a library that other tools (MCP server, CLI) depend on.

```python
# ✅ Good
def query(question: str, n_results: int = 5) -> list[QueryResult]:
    ...

# ❌ Bad
def query(question, n_results=5):
    ...
```

---

## 10. Testing

### Current State

Zero tests. No `tests/` directory. No pytest in dependencies.

### Target: pytest with fixtures

```
tests/
├── conftest.py              ← shared fixtures (temp notes dir, test DB)
├── test_chunker.py          ← chunking logic
├── test_sync.py             ← incremental sync
├── test_query.py            ← query pipeline
├── test_config.py           ← config loading + validation
└── test_models.py           ← dataclass serialization
```

### What to Test

| Module | What to test | Type |
|--------|-------------|------|
| `chunker` | Header splitting, preamble extraction, merging, skip headers, edge cases | Unit |
| `config` | TOML loading, env var overrides, defaults, validation errors | Unit |
| `sync` | New/changed/deleted file detection, hash tracking, model change detection | Unit |
| `query` | Result structure, empty DB handling, reranker integration | Integration |
| `db` | Add/query/delete roundtrip | Integration |

### Testing Principles

| Principle | Rule |
|-----------|------|
| **No network in tests** | Tests must work offline. Use fastembed with a tiny model or mock. |
| **No shared state** | Each test gets its own temp directory and fresh DB. Use `tmp_path` fixture. |
| **Test behavior, not implementation** | Test "chunking this markdown produces these chunks", not "function X calls function Y" |
| **Fast by default** | Unit tests should complete in < 5 seconds total |

---

## 11. Git & CI/CD Hygiene

### `.gitignore` (target)

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/

# Environment
.venv/
.env

# brAIn local state
.rag/

# Tools
.ruff_cache/
.mypy_cache/
.pytest_cache/

# OS
.DS_Store
Thumbs.db
```

### CI Pipeline (GitHub Actions)

```
    On push / PR to main
    ─────────────────────

    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │  Lint    │    │  Type    │    │  Test    │
    │  (ruff)  │    │  Check   │    │ (pytest) │
    │          │    │  (mypy)  │    │          │
    └──────────┘    └──────────┘    └──────────┘

    All three must pass. PRs cannot merge if any fail.
```

### Git Hooks

| Hook | Action |
|------|--------|
| `pre-commit` | Run `ruff check` and `ruff format --check` |
| `post-merge` | Run `brain sync` (keep the local index fresh after `git pull`) |

Consider using [pre-commit](https://pre-commit.com/) framework to manage hooks
across the team without manual setup.

---

## 12. Module Design Principles

### Single Responsibility

Every module should do **one thing**. If you can't describe what a module does
in one sentence without using "and", split it.

```
    Current                              Target
    ───────                              ──────

    __init__.py                          sync.py
    ├── sync()          ──────────────►  └── sync() — incremental indexing
    ├── query()         ──────────────►  query.py
    ├── cleanup()                        └── query() — search + rerank
    └── _build_embedding_text()          models.py
                                         └── Chunk, QueryResult dataclasses
```

### Dependency Direction

Modules should depend downward, never upward or sideways in a cycle.

```
    cli.py / mcp_server/server.py        ← entry points (depend on everything)
         │
         ▼
    sync.py, query.py                    ← orchestrators (depend on components)
         │
         ▼
    chunker.py, embeddings.py,           ← components (depend on config/models)
    reranker.py, db.py
         │
         ▼
    config.py, models.py                 ← foundations (depend on nothing internal)
```

No module in the bottom layers should import from the top layers.
If `db.py` needs a `Chunk` type, it imports from `models.py` — not from `sync.py`.

### Public API Surface

`__init__.py` should be a clean public API — just imports and the version.
No business logic, no helper functions.

```python
# src/brain/__init__.py

__version__ = "0.1.0"

from brain.sync import sync
from brain.query import query
from brain.config import get_config

__all__ = ["sync", "query", "get_config"]
```

Users can do `import brain; brain.sync()` or `from brain import query`.
The internal module structure is hidden.

### Lazy Initialization Pattern

For expensive resources (embedding model, ChromaDB client, reranker model),
use the lazy singleton pattern already established in `db.py` and `embeddings.py`.

This means:
- The resource is `None` at module load time
- A `_get_*()` function creates it on first use
- Subsequent calls return the cached instance
- This avoids slow imports and unnecessary memory use

This is the right pattern. Keep it. Apply it consistently to the reranker too.

### No Print in Library Code

The library layer (`sync.py`, `query.py`, `chunker.py`, `db.py`, etc.) must
**never call `print()`**. All output goes through `logging` or return values.

Only two places may call `print()`:
1. `cli.py` — formatting results for the terminal
2. `mcp_server/server.py` — only if needed for MCP protocol

This separation means the same library works correctly whether called from
the CLI, the MCP server, or a Python import.

---

## Summary of Changes

| Area | Current | Target |
|------|---------|--------|
| **Layout** | Flat (`rag/` at root) | `src/brain/` |
| **Package name** | `rag` | `brain` |
| **Config** | Hardcoded constants | `brain.toml` + env vars via `pydantic-settings` |
| **CLI** | `sys.argv` | `click` |
| **Logging** | Ad-hoc | `logging` stdlib, configured, level via env var |
| **Errors** | Crash on failure | Graceful skip + user-friendly messages |
| **Linting** | Manual ruff runs | `ruff` + `mypy` in `pyproject.toml` + CI |
| **Testing** | None | `pytest` with unit + integration tests |
| **Types** | No annotations | Full annotations on public API |
| **Git** | Minimal `.gitignore` | Complete `.gitignore` + pre-commit + post-merge hooks |
| **CI** | None | GitHub Actions: lint + type check + test |
| **Dependencies** | Dead deps, no dev group | Clean deps, `[dev]` optional group |
