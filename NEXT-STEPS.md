# brAIn — Architecture Review & Next Steps

> **Date:** 2026-06-06
> **Purpose:** Full audit of the current system, target architecture, and production roadmap
> **Audience:** Engineers and teams adopting brAIn for their knowledge base

---

## Table of Contents

1. [Where We Are Today](#1-where-we-are-today)
2. [Target Architecture](#2-target-architecture)
3. [Efficiency: How Syncing Works](#3-efficiency-how-syncing-works)
4. [Database Design & ChromaDB Strategy](#4-database-design--chromadb-strategy)
5. [Efficiency: How Querying Works](#5-efficiency-how-querying-works)
6. [How Notes Become Searchable (Chunking)](#6-how-notes-become-searchable-chunking)
7. [Choosing an Embedding Model](#7-choosing-an-embedding-model)
8. [Improving Results with Reranking](#8-improving-results-with-reranking)
9. [MCP Server — Connecting to LLMs](#9-mcp-server--connecting-to-llms)
10. [Configuration for Different Teams](#10-configuration-for-different-teams)
11. [Implementation Roadmap](#11-implementation-roadmap)

---

## 1. Where We Are Today

### What's Built

brAIn has a working RAG pipeline: notes go in, chunks come out, questions get answered.

```
    ┌───────────┐        ┌──────────┐        ┌───────────┐        ┌──────────┐
    │  Markdown │──────► │  Chunker │──────► │ Embedder  │──────► │ ChromaDB │
    │  Notes    │        │          │        │(fastembed)│        │ (local)  │
    └───────────┘        └──────────┘        └───────────┘        └──────────┘
                                                                      │
    ┌───────────┐                                                     │
    │  Question │─── embed ──────────────── cosine search ────────────┘
    └───────────┘                                  │
                                                   ▼
                                            ┌──────────┐
                                            │ Results  │
                                            └──────────┘
```

**What works:** `rag sync` indexes all notes. `rag query` searches them. All local, no API keys.

**What's missing:**

| Gap                                | Impact                                                       |
| ---------------------------------- | ------------------------------------------------------------ |
| Every sync re-indexes everything   | Slow at scale — 1K+ notes takes minutes needlessly           |
| Deleted notes stay in the database | Stale results returned for files that no longer exist        |
| MCP server is a scaffold           | LLM clients (Copilot, Claude) can't access notes yet         |
| No reranking                       | Search results are "close enough" but not precisely relevant |
| No config file                     | Teams can't customize models, chunking, or behavior          |

---

## 2. Target Architecture

Every developer clones the notes repo, runs sync, and gets their own local vector database.
No shared servers, no auth, no network dependency. Notes stay private on each machine.

```
    DEVELOPER MACHINE
    ═══════════════════════════════════════════════════════════════

    ┌───────────┐        ┌────────────┐        ┌────────────┐
    │  Obsidian │◄──────►│  notes/    │◄──────►│ Git Remote │
    │  (edit)   │  save  │  (*.md)    │  push  │            │
    └───────────┘        └─────┬──────┘  pull  └────────────┘
                               │
                    ┌──────────┘
                    │  git hook or manual trigger
                    ▼
              ┌───────────┐
              │   SYNC    │  Only processes new, changed, or deleted files.
              │  ENGINE   │  Skips everything unchanged.
              └─────┬─────┘
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
    ┌──────────┐ ┌────────┐ ┌──────────┐
    │ Chunker  │ │Embedder│ │ ChromaDB │
    │          │ │        │ │ (local)  │
    └──────────┘ └────────┘ └────┬─────┘
                                 │
                          ┌──────┘
                          │  query
                          ▼
                    ┌───────────┐
                    │   QUERY   │  Vector search → rerank → results
                    │  PIPELINE │
                    └─────┬─────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        ┌──────────┐ ┌─────────┐ ┌──────────┐
        │   CLI    │ │  MCP    │ │  Python  │
        │          │ │ Server  │ │   API    │
        │ rag sync │ │ (stdio) │ │          │
        │ rag query│ │         │ │ rag.query│
        └──────────┘ └────┬────┘ └──────────┘
                          │
                          ▼
                     ┌──────────┐
                     │LLM Client│  Copilot, Claude Desktop,
                     │          │  Cursor, etc.
                     └──────────┘
```

---

## 3. Efficiency: How Syncing Works

### The Problem

Currently, every `rag sync` re-processes **every file** — re-chunks it, re-embeds it,
and re-stores it. This is wasteful. If you have 1,000 notes and edit one, why
reprocess the other 999?

### Source of Truth: Main Branch Only

Only committed content on `main` is indexed. This ensures:

- Notes are only searchable **after** they've been reviewed and merged via PR
- Feature branches don't pollute the database with draft content
- Every developer's DB reflects the same reviewed truth

If `rag sync` is run on a non-main branch, it skips with a message.

### The Solution: Git as the Change Detector

Instead of hashing every file on disk, we use **git itself** to tell us what
changed. Git already tracks every modification — we just ask it.

```
    Developer runs: git pull → rag sync (or post-merge hook triggers it)

    ┌──────────────────────────────────────────────────────────┐
    │                     SYNC ENGINE                          │
    │                                                          │
    │  1. Check: am I on main? (if not → skip)                │
    │  2. Read .rag/last_sync_ref (the commit we last synced)  │
    │  3. Ask git: what changed between that ref and HEAD?     │
    │                                                          │
    │     git diff --name-status <last-ref> HEAD -- notes/     │
    │                                                          │
    │     Output              Action                           │
    │     ──────              ──────                           │
    │     A notes/new.md      ADD ✚  → chunk, embed, store    │
    │     M notes/edited.md   UPDATE ✎ → delete old, re-store │
    │     D notes/removed.md  DELETE ✖ → remove from DB       │
    │     (not listed)        unchanged → nothing (free!)      │
    │                                                          │
    │  4. Store current HEAD as .rag/last_sync_ref             │
    │                                                          │
    └──────────────────────────────────────────────────────────┘
```

### Why Git Instead of File Hashing?

| Aspect                | Git-based (our approach) | Hash manifest                |
| --------------------- | ------------------------ | ---------------------------- |
| Speed (1,000 files)   | ~5ms (git already knows) | ~50ms (hash every file)      |
| Speed (10,000 files)  | ~5ms (still instant)     | ~500ms (must read all files) |
| Scales with repo size | O(1) — diffing is free   | O(N) — touches every file    |
| Ignores uncommitted   | ✅ by design             | ❌ would detect and process  |
| Storage               | 1 file (40-char SHA)     | 1 file with N hashes         |
| Detects deletes       | Free (in diff output)    | Must compare file lists      |
| Implementation        | ~15 lines                | ~30 lines                    |

Git is simpler, faster, and eliminates an entire category of state management.

### What This Means in Practice

| Scenario                              | What happens                                      | Time     |
| ------------------------------------- | ------------------------------------------------- | -------- |
| First sync ever (1,000 notes)         | Full index — no prior ref exists                  | ~2-5 min |
| `git pull` brings 3 changed files     | Git diff shows 3 files → only those processed     | ~2 sec   |
| `git pull` deletes a file             | Git diff shows `D` → chunks removed from DB       | instant  |
| `git pull` with no note changes       | Git diff is empty → nothing to do                 | ~5ms     |
| Someone changes the embedding model   | Full re-index (embeddings are model-specific)     | ~2-5 min |
| Developer on a feature branch         | `rag sync` skips — DB stays on main               | instant  |
| Branch merged via PR, developer pulls | `post-merge` hook fires → sync the merged changes | ~2 sec   |

### Automatic Safety Rails

The system tracks which embedding model was used to build the database.
If someone changes the model in the config, the next sync detects the mismatch
and automatically does a full re-index. This prevents mixing incompatible
embeddings from different models.

### Git Hook: Hands-Free Sync

A `post-merge` git hook runs `rag sync` automatically after every `git pull`.
Developers never need to remember to sync — their database stays current
as they pull changes from the team.

Since we only index main, the hook only fires on main merges (fast-forward pulls).
Branch switches and rebases don't trigger it.

---

## 4. Database Design & ChromaDB Strategy

How to organize, store, and query data in ChromaDB for maximum efficiency.
A single collection holds all note chunks. Metadata filters handle scoping.

### Collection Configuration

The collection is created with explicit settings. If the existing collection
doesn't match the expected config (distance metric changed, model changed),
it's deleted and recreated — triggering a full re-index on next sync.

```
    Collection init:
    ├── Does collection exist?
    │   ├── YES → does config match? (distance metric, embedding model)
    │   │   ├── YES → use it
    │   │   └── NO  → delete, recreate, full re-index
    │   └── NO → create with config
```

Since this is a local database, each developer can tune these settings for their
own hardware and preferences. Changing any setting triggers a one-time re-index.

#### Distance Metric (`hnsw:space`)

How "similarity" between two vectors is measured.

| Value    | What it measures                                     | When to use                                                    | Default?   |
| -------- | ---------------------------------------------------- | -------------------------------------------------------------- | ---------- |
| `cosine` | Angle between vectors (ignores magnitude)            | Most embedding models — they normalize vectors during training | ✅ **Yes** |
| `l2`     | Euclidean distance (straight-line distance in space) | When vector magnitude carries meaning (rare for text)          | No         |
| `ip`     | Inner product (dot product)                          | Already-normalized vectors + marginal speed gain               | No         |

**In practice:** `cosine` and `ip` produce identical results for normalized
embeddings (which `bge-small-en-v1.5` and most models output). Stick with
`cosine` unless you have a specific reason.

#### Search Breadth (`hnsw:search_ef`)

How many candidates the search algorithm explores before returning results.

| Value        | Effect                                         | Tradeoff                            |
| ------------ | ---------------------------------------------- | ----------------------------------- |
| 10 (default) | Fast queries, might miss some relevant results | Speed over recall                   |
| 50           | Explores more candidates                       | Better recall, ~2-3x slower queries |
| 200          | Near-exhaustive search                         | Best recall, ~10x slower queries    |

**At our scale (<50K chunks):** queries are <50ms regardless. A developer who
wants better recall can safely set this to 50-100 with no perceptible slowdown.

#### Graph Connectivity (`hnsw:M`)

How many "shortcut links" each vector has to other vectors in the index.
Think of it as how well-connected the road network is.

| Value        | Effect                    | Tradeoff                       |
| ------------ | ------------------------- | ------------------------------ |
| 8            | Sparse graph, less memory | Faster build, lower recall     |
| 16 (default) | Balanced                  | Good for most cases            |
| 32+          | Dense graph, more memory  | Higher recall, slower to build |

**Memory impact:** each doubling of M roughly doubles index memory.
At 10K chunks with 384-dim vectors, the index is ~30MB at M=16. Negligible.

#### Build Quality (`hnsw:construction_ef`)

How thoroughly the index is built. Higher = better connections between vectors,
but slower initial sync.

| Value         | Effect              | Tradeoff                                 |
| ------------- | ------------------- | ---------------------------------------- |
| 50            | Fast index build    | Slightly worse search quality            |
| 100 (default) | Good balance        | —                                        |
| 200+          | Very thorough build | 2x slower sync, marginally better search |

**When it matters:** only during `rag sync` (building/updating the index).
Has zero impact on query speed. A developer who wants faster syncs on a slow
machine could lower this; one who wants maximum recall could raise it.

#### Configuration Summary

| Setting                | Default  | Safe to change?        | Triggers re-index?      |
| ---------------------- | -------- | ---------------------- | ----------------------- |
| `hnsw:space`           | `cosine` | Yes, but rarely needed | ✅ Yes                  |
| `hnsw:search_ef`       | `10`     | Yes, freely            | ❌ No (query-time only) |
| `hnsw:M`               | `16`     | Yes                    | ✅ Yes                  |
| `hnsw:construction_ef` | `100`    | Yes                    | ✅ Yes                  |

Note: `search_ef` is the only setting that can be changed without rebuilding
the database — it's applied at query time, not build time.

### What Gets Stored Per Chunk

ChromaDB stores three things per record: an **ID**, a **document** (text), and
**metadata** (structured fields for filtering).

```
    ┌─────────────────────────────────────────────────────────────┐
    │  ChromaDB Record                                            │
    │                                                             │
    │  id:        "a3f2c9e1"                                      │
    │                                                             │
    │  document:  "## Prerequisites\nYou need Node.js 18+..."     │
    │             (raw chunk text — what gets returned to user)    │
    │                                                             │
    │  embedding: [0.023, -0.118, 0.445, ...]  (auto-generated)   │
    │             (what gets searched — created from enriched text)│
    │                                                             │
    │  metadata:                                                  │
    │  ├── source:      "notes/handbook/opencode-install.md"      │
    │  ├── header_path: "OpenCode Install > Prerequisites"        │
    │  ├── folder:      "handbook"                                │
    │  ├── tags:        "handbook,opencode,ai"                    │
    │  └── title:       "OpenCode Install"                        │
    │                                                             │
    └─────────────────────────────────────────────────────────────┘
```

### Metadata Schema

| Field         | Type   | Purpose                                    | Example                          |
| ------------- | ------ | ------------------------------------------ | -------------------------------- |
| `source`      | string | File path — used for delete-before-upsert  | `notes/handbook/opencode.md`     |
| `header_path` | string | Section hierarchy — displayed in results   | `"Guide > Installation > macOS"` |
| `folder`      | string | Top-level category — enables scoped search | `"handbook"`, `"decisions"`      |
| `tags`        | string | Comma-separated tags from note frontmatter | `"handbook,opencode,ai"`         |
| `title`       | string | Note title — useful for grouping results   | `"OpenCode Install"`             |

**Why string for tags?** ChromaDB metadata only supports string, int, float, and
bool. No arrays. Store tags as comma-separated, filter with `$contains`.

### What Gets Embedded vs What Gets Stored

This is a critical distinction. The **embedding text** (what the model sees for
vector similarity) is enriched with context. The **document** (what gets returned)
is the clean chunk.

```
    EMBEDDING INPUT (rich, for search)     STORED DOCUMENT (clean, for display)
    ──────────────────────────────────     ──────────────────────────────────────

    "A guide to installing OpenCode.       "## Prerequisites
                                            You need Node.js 18+..."
     Section: OpenCode Install
     > Prerequisites

     ## Prerequisites
     You need Node.js 18+..."
```

ChromaDB lets you provide embeddings separately from documents. We:

1. Build the enriched text (preamble + header path + content)
2. Generate the embedding from it
3. Store the **raw chunk** as the document (for clean retrieval)
4. Pass the **pre-computed embedding** to ChromaDB (it won't re-embed)

```python
collection.upsert(
    ids=[chunk.id for chunk in chunks],
    documents=[chunk.text for chunk in chunks],           # clean text (returned)
    embeddings=[chunk.embedding for chunk in chunks],     # pre-computed from enriched text
    metadatas=[{"source": c.source, ...} for c in chunks],
)
```

### Filtered Queries (Scoped Search)

ChromaDB supports metadata filters on queries. This lets users narrow search
without changing the embedding math:

```
    "How do I deploy?" (search all notes)
    → collection.query(query_embeddings=[...], n_results=10)

    "How do I deploy?" (only in decisions/)
    → collection.query(query_embeddings=[...], n_results=10,
                        where={"folder": "decisions"})

    "How do I deploy?" (only notes tagged #kubernetes)
    → collection.query(query_embeddings=[...], n_results=10,
                        where={"tags": {"$contains": "kubernetes"}})
```

This is **free filtering** — no extra index needed. ChromaDB applies metadata
filters after the vector search, narrowing results without re-embedding.

### Chunk ID Strategy

Currently, chunk IDs are positional: `notes/guide.md#0`, `notes/guide.md#1`, etc.
This is fragile if you upsert without deleting first (inserting a section shifts
all subsequent IDs, leaving orphans). But since we use **delete-before-upsert**,
orphans aren't a risk — all chunks for a file are wiped before re-inserting.

So the question becomes: what do we **gain** from a different ID scheme?

| Approach             | Format                                | Pros                                   | Cons                                         |
| -------------------- | ------------------------------------- | -------------------------------------- | -------------------------------------------- |
| Positional (current) | `notes/guide.md#0`                    | Readable, simple                       | Meaningless if you look at it out of context |
| Content-hash         | `a3f2c9e1` (hash of source + content) | Deterministic — same content = same ID | Opaque, harder to debug                      |
| Source + header      | `notes/guide.md#installation`         | Human-readable, stable across reorders | Duplicate headers in same file would collide |

**Recommendation: Source + header slug**

```
    notes/guide.md#prerequisites
    notes/guide.md#installation-macos
    notes/guide.md#installation-linux
```

Why:

- **Readable** — you see exactly what file and section it represents
- **Stable** — reordering sections doesn't change IDs
- **Debuggable** — easy to inspect the DB and understand what's stored
- **Unique enough** — header paths are unique within a file (by markdown convention)

For the edge case of duplicate headers in the same file (rare), append a counter:
`notes/guide.md#prerequisites-2`.

Since we delete-before-upsert, the ID doesn't need to be content-aware for
correctness. It just needs to be unique per chunk and ideally human-readable.

### Batch Upserts (One Call Per File)

All chunks from a single file are upserted in one ChromaDB call, not one
call per chunk. This is faster and transactional at the file level.

```python
collection.upsert(
    ids=[chunk.id for chunk in chunks],
    documents=[chunk.text for chunk in chunks],
    embeddings=[chunk.embedding for chunk in chunks],
    metadatas=[{"source": c.source, "header_path": c.header_path, ...} for c in chunks],
)
```

### Delete-Before-Upsert (Handles Edits Cleanly)

When a file changes, the sync engine:

1. **Deletes** all existing chunks for that file (`where={"source": filepath}`)
2. **Upserts** the new chunks

This handles all edit scenarios — added sections, removed sections, rewritten
content — without leaving orphan chunks in the database.

```
    FILE EDIT: Remove "## Setup" section, edit "## Deploy"

    Step 1 — Delete old chunks:
    ├── a3f2c9e1 (Intro)     ← removed from DB
    ├── 7b4d1f08 (Setup)     ← removed from DB
    └── e5a09c3d (Deploy)    ← removed from DB

    Step 2 — Upsert new chunks:
    ├── a3f2c9e1 (Intro)     ← re-inserted (same hash, unchanged content)
    └── 91c7e4b2 (Deploy)    ← new hash (content was edited)

    Net result: Setup gone, Deploy updated, Intro untouched semantically
```

### Why Not Just Upsert Without Deleting?

If a section is removed from a file, its chunk would stay in the DB forever —
a ghost result that points to content that no longer exists. Delete-before-upsert
guarantees the DB always mirrors what's on disk.

### Database File Structure

```
    .rag/
    ├── last_sync_ref          ← 40-char git SHA (what we last synced)
    ├── model_info.json        ← which embedding model built this DB
    └── chroma_db/             ← ChromaDB persistence directory
        ├── chroma.sqlite3     ← metadata + IDs
        └── *.bin              ← HNSW index files (vectors)
```

The entire `.rag/` directory is gitignored. Each developer builds their own
local copy. It's disposable — `rag clean && rag sync` rebuilds from scratch.

---

## 5. Efficiency: How Querying Works

### The Two-Stage Search

The query pipeline uses two stages: a fast, broad search followed by a precise reranking.
This is like using a metal detector to find a general area, then carefully digging to find the exact item.

```
    "How do I publish a Helm chart?"
         │
         │  STAGE 1: FAST SEARCH (milliseconds)
         │  ─────────────────────
         │  Convert question to a vector (same math as indexing).
         │  Ask ChromaDB: "find the 20 most similar chunks."
         │  This is approximate — good recall, imperfect precision.
         │
         ▼
    ┌─────────────────────────────────────────────────┐
    │  20 candidate chunks (ranked by vector distance) │
    │  Some are very relevant, some are just similar   │
    └────────────────────────┬────────────────────────┘
                             │
         │  STAGE 2: PRECISE RERANK (optional, ~200ms)
         │  ────────────────────────
         │  A cross-encoder reads each (question + chunk) pair
         │  together and scores how relevant each one actually is.
         │  Much more accurate than vector distance alone.
         │
         ▼
    ┌─────────────────────────────────────────────────┐
    │  Top 5 results, sorted by true relevance        │
    │  Each with: source file, section path, score    │
    └─────────────────────────────────────────────────┘
```

### Why Two Stages?

| Approach            | Speed       | Precision   | Used for                               |
| ------------------- | ----------- | ----------- | -------------------------------------- |
| Vector search alone | ⚡ ~5ms     | Good enough | Narrowing 10K+ chunks to 20 candidates |
| Cross-encoder alone | 🐌 Too slow | Excellent   | Can't scan the whole database          |
| Vector → Rerank     | ⚡ + 200ms  | Excellent   | Best of both worlds                    |

### Without vs With Reranking

```
    WITHOUT RERANKING                      WITH RERANKING
    ─────────────────                      ──────────────

    "How do I deploy EDC?"                 "How do I deploy EDC?"

    1. EDC overview            0.82        1. Helm chart publish     0.94  ✅
    2. EDC architecture        0.79        2. EDC architecture       0.91  ✅
    3. CloudEvents spec        0.77        3. EDC deployment steps   0.88  ✅
    4. Helm chart publish      0.75        4. EDC overview           0.72
    5. OpenCode install        0.74  ❌    5. CloudEvents spec       0.41

    #5 is completely irrelevant.           Every result is on-topic.
    #4 (most useful) is buried.            Most useful result is #1.
```

### Query Performance at Scale

| Collection size            | Vector search | + Rerank (top 20) | Total  |
| -------------------------- | ------------- | ----------------- | ------ |
| 100 notes (~500 chunks)    | ~2ms          | ~200ms            | ~200ms |
| 1,000 notes (~5K chunks)   | ~5ms          | ~200ms            | ~205ms |
| 10,000 notes (~50K chunks) | ~10ms         | ~200ms            | ~210ms |

ChromaDB uses an HNSW index, so vector search scales logarithmically.
Reranking time is constant (always scoring the same 20 candidates).
**Queries stay fast regardless of collection size.**

---

## 6. How Notes Become Searchable (Chunking)

Notes are split into chunks at header boundaries. Each chunk carries its
position in the document hierarchy, so the search engine understands context.

```
    INPUT: handbook/opencode-install.md
    ───────────────────────────────────

    # OpenCode Installation Guide        ← title (extracted, not chunked)
    Tags: #handbook #tools
    A guide to installing OpenCode...     ← preamble (adds context to embeddings)

    ## Prerequisites                      ← chunk boundary
    You need Node.js 18+ and...

    ## Installation                       ← chunk boundary
    Run the following command...

    ### macOS                             ← chunk boundary (sub-section)
    brew install opencode

    ### Linux                             ← chunk boundary
    apt-get install opencode

    ## References                         ← SKIPPED (configurable)
    - https://...


    OUTPUT: Searchable chunks
    ─────────────────────────

    Chunk 0
    ├── section: "OpenCode Installation Guide > Prerequisites"
    ├── content: "## Prerequisites\nYou need Node.js 18+..."
    └── source:  "notes/handbook/opencode-install.md"

    Chunk 1
    ├── section: "OpenCode Installation Guide > Installation"
    ├── content: "## Installation\nRun the following..."
    └── source:  "notes/handbook/opencode-install.md"

    Chunk 2  (macOS + Linux merged — both were too small alone)
    ├── section: "...> Installation > macOS"
    ├── content: "### macOS\nbrew install...\n\n### Linux\napt-get..."
    └── source:  "notes/handbook/opencode-install.md"
```

### What Gets Embedded vs What Gets Returned

The text that's embedded (turned into a vector) is **enriched** with the note's
preamble and section hierarchy. This helps the search engine find the right chunk
even when the chunk text alone lacks context.

But what's **returned to the user** is just the raw chunk content — clean and readable.

```
    WHAT THE EMBEDDING MODEL SEES          WHAT THE USER GETS BACK
    ──────────────────────────────         ────────────────────────

    "A guide to installing OpenCode.       "### macOS
                                            brew install opencode
     Section: OpenCode Install Guide
     > Installation > macOS                 ### Linux
                                            apt-get install opencode"
     ### macOS
     brew install opencode

     ### Linux
     apt-get install opencode"
```

### Chunking Rules

| Rule           | Value           | Purpose                                            |
| -------------- | --------------- | -------------------------------------------------- |
| Max chunk size | 1,500 chars     | Oversized chunks get split at paragraph boundaries |
| Min chunk size | 200 chars       | Tiny chunks get merged into the previous one       |
| Skip headers   | References, TOC | Noise sections are excluded from indexing          |

All values are configurable per team.

### Code Block Protection

Headers inside fenced code blocks (e.g. `# bash comment`) must not be treated
as chunk boundaries. Before splitting, the chunker identifies all fenced code
block ranges (` ``` ... ``` `) and excludes any header matches inside them.

Tables are safe by design — their lines start with `|`, never `#`.

### Splitting Oversized Chunks

When a chunk exceeds `MAX_CHUNK_SIZE`, it's split at **paragraph boundaries**
(double newlines). This preserves complete thoughts without cutting mid-sentence.

```
    OVERSIZED CHUNK (2,800 chars)
    ─────────────────────────────

    ## Deployment Guide                  ← original header
    First paragraph explaining...
                                         ← double newline = split point
    Second paragraph with steps...
                                         ← double newline = split point
    Third paragraph with details...


    RESULT: 2 chunks, same header_path
    ───────────────────────────────────

    Chunk A (1,400 chars)
    ├── section: "Guide > Deployment Guide"
    └── content: "## Deployment Guide\nFirst paragraph...\n\nSecond paragraph..."

    Chunk B (1,400 chars)
    ├── section: "Guide > Deployment Guide"
    └── content: "Third paragraph with details..."
```

Paragraph splitting is simple, robust, and requires no NLP dependencies.
For typical documentation notes, individual paragraphs are almost always under
1,500 chars — this is a safety net, not the primary splitting strategy.

---

## 7. Choosing an Embedding Model

The embedding model converts text into vectors. Better models = better search results,
but larger models take more disk space and are slower to load on first run.

All models below are **verified available** in fastembed and run locally on CPU.
No API keys, no network required.

```
┌──────────────────────────┬───────┬───────────┬─────────┬─────────────────────────────────┐
│ Model                    │ Dims  │ Download  │ Quality │ Best For                        │
├──────────────────────────┼───────┼───────────┼─────────┼─────────────────────────────────┤
│ BAAI/bge-small-en-v1.5   │ 384   │ 67 MB     │ ★★★☆☆  │ Fastest. Good for <1K notes.    │
│ (current default)        │       │           │         │ English only, 512-token context │
├──────────────────────────┼───────┼───────────┼─────────┼─────────────────────────────────┤
│ nomic-ai/nomic-embed-    │ 768   │ 520 MB    │ ★★★★★  │ ★ RECOMMENDED. Best quality.    │
│ text-v1.5                │       │           │         │ 8K-token context. Matryoshka    │
│                          │       │           │         │ (can shrink to 256d to save     │
│                          │       │           │         │ space with only ~2% quality     │
│                          │       │           │         │ loss).                          │
├──────────────────────────┼───────┼───────────┼─────────┼─────────────────────────────────┤
│ BAAI/bge-base-en-v1.5    │ 768   │ 210 MB    │ ★★★★☆  │ Middle ground. Good upgrade     │
│                          │       │           │         │ from bge-small.                 │
├──────────────────────────┼───────┼───────────┼─────────┼─────────────────────────────────┤
│ snowflake/snowflake-     │ 768   │ 430 MB    │ ★★★☆☆  │ Alternative. English.           │
│ arctic-embed-m           │       │           │         │                                 │
└──────────────────────────┴───────┴───────────┴─────────┴─────────────────────────────────┘

  ⚠️  Changing the model requires a full re-index (the sync engine handles this
      automatically). Embeddings from different models are incompatible.

  ⚠️  nomic-embed-text requires query/document prefixes ("search_query: ",
      "search_document: "). fastembed handles this automatically.

  ⚠️  BAAI/bge-m3 (popular multilingual model) is NOT available in fastembed.
      For multilingual needs, use paraphrase-multilingual-MiniLM-L12-v2
      (available in fastembed, 384d, 220MB).
```

---

## 8. Improving Results with Reranking

Reranking is an optional second pass that dramatically improves search precision.
Vector search finds "kind of similar" chunks; the reranker reads each one carefully
and tells you which are actually relevant to your question.

All models below are **verified available** in fastembed.

```
┌────────────────────────────────┬──────────┬─────────────┬──────────────────────────┐
│ Model                          │ Download │ Multilingual │ Best For                │
├────────────────────────────────┼──────────┼─────────────┼──────────────────────────┤
│ BAAI/bge-reranker-base         │ 1.04 GB  │ English     │ ★ RECOMMENDED.          │
│                                │          │ mainly      │ Best quality in          │
│                                │          │             │ fastembed. MIT license.  │
├────────────────────────────────┼──────────┼─────────────┼──────────────────────────┤
│ Xenova/ms-marco-MiniLM-L-12-v2│ 120 MB   │ English     │ Lightweight. Good        │
│                                │          │ only        │ speed/quality tradeoff.  │
├────────────────────────────────┼──────────┼─────────────┼──────────────────────────┤
│ Xenova/ms-marco-MiniLM-L-6-v2 │ 80 MB    │ English     │ Fastest. Minimal         │
│                                │          │ only        │ overhead.               │
├────────────────────────────────┼──────────┼─────────────┼──────────────────────────┤
│ jinaai/jina-reranker-v2-base-  │ 1.11 GB  │ Yes         │ Best multilingual        │
│ multilingual                   │          │             │ option in fastembed.     │
└────────────────────────────────┴──────────┴─────────────┴──────────────────────────┘

  ⚠️  bge-reranker-v2-m3 (often recommended online) is NOT in fastembed.
      bge-reranker-base is the best available option.

  Reranking adds ~200ms to each query. For interactive use this is imperceptible.
  It can be disabled in config for teams that prefer raw speed.
```

---

## 9. MCP Server — Connecting to LLMs

The MCP server is how AI tools (Copilot, Claude Desktop, Cursor) talk to brAIn.
It runs locally as a subprocess — no network, no ports, no authentication.

```
    ┌──────────────┐       stdin/stdout        ┌──────────────┐
    │  LLM Client  │◄────────────────────────► │  brAIn MCP   │
    │  (Copilot,   │       (local pipes)       │   Server     │
    │   Claude)    │                           │              │
    └──────────────┘                           └──────────────┘

    The LLM client starts brAIn as a subprocess.
    They communicate over stdin/stdout (stdio transport).
    No network. No ports. No auth. Fully local.
```

### Tools Exposed to the LLM

| Tool             | What it does                                                |
| ---------------- | ----------------------------------------------------------- |
| **query_notes**  | Semantic search across all indexed notes. The primary tool. |
| **sync_notes**   | Re-index (incremental). Safe to call anytime.               |
| **get_note**     | Read the full content of a specific note file.              |
| **list_sources** | List all indexed note files.                                |

### How Developers Configure It

Add to Claude Desktop, VS Code, or any MCP-compatible client:

```json
{
  "mcpServers": {
    "brain": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/brAIn",
        "python",
        "mcp/server.py"
      ]
    }
  }
}
```

---

## 10. Configuration for Different Teams

All settings live in a single `brain.toml` file at the project root.
Each team checks this into their notes repo. Every setting can also be
overridden with an environment variable.

```toml
# brain.toml

[general]
notes_dir = "notes"
db_dir = ".rag"
glob_pattern = "**/*.md"

[embedding]
model = "nomic-ai/nomic-embed-text-v1.5"

[chunking]
max_chunk_size = 1500
min_chunk_size = 200
chunk_overlap = 200
skip_headers = ["References", "Table of Contents", "TOC"]

[reranking]
enabled = true
model = "BAAI/bge-reranker-base"

[query]
initial_candidates = 20      # how many chunks the vector search retrieves
final_results = 5             # how many results are returned after reranking

[mcp]
transport = "stdio"
```

### Example: Two Different Teams

```
    Team A — Small, fast                   Team B — Large, precise
    ────────────────────                   ──────────────────────

    [embedding]                            [embedding]
    model = "BAAI/bge-small-en-v1.5"       model = "nomic-ai/nomic-embed-text-v1.5"

    [reranking]                            [reranking]
    enabled = false                        enabled = true

    [chunking]                             [chunking]
    max_chunk_size = 2000                  max_chunk_size = 1000

    → Fast sync, basic search             → Better results, reranked
    → 67 MB model download                → 520 MB + 1 GB model downloads
```

---

## 11. Implementation Roadmap

### Phase 1 — Fix Foundations

Clean up bugs and dead code so the codebase is trustworthy.

- ~~Remove dead `splitter.py` and the `langchain` dependency~~ ✅ Done
- Fix `query()` to return structured results instead of printing
- Fix chunker: pass actual preamble (not empty string), preserve header context on merge
- Add code-block protection (skip `#` matches inside fenced blocks)
- Add paragraph-based splitting for oversized chunks
- Use content-hash chunk IDs instead of positional
- Fix `.gitignore` to exclude `.rag/` and build artifacts
- Replace minimal CLI with proper argument parsing and help text

### Phase 2 — Incremental Sync + DB Operations

Make sync fast enough to run on every `git pull` without anyone noticing.

- Use git diff to detect changes (no file hashing — git is the source of truth)
- Only sync on main branch (skip on feature branches)
- Store last-synced commit ref in `.rag/last_sync_ref`
- Delete-before-upsert per file (no orphan chunks on edits)
- Batch upserts (one ChromaDB call per file, not per chunk)
- Track the embedding model in state; auto-reindex on model change
- Add `rag status` command to show index health
- Add git `post-merge` hook for hands-free sync

### Phase 3 — Wire the MCP Server

Connect brAIn to LLM clients so developers can ask questions about their notes.

- Wire `query_notes`, `sync_notes`, `get_note`, `list_sources` tools
- Support `stdio` transport (local subprocess)
- Add config examples for Claude Desktop and VS Code to README

### Phase 4 — Quality & Configurability

Make search results excellent and let teams customize everything.

- Add `brain.toml` config file loader with environment variable overrides
- Add reranking pipeline (optional, configurable)
- Upgrade default embedding model to `nomic-embed-text-v1.5`

### Phase 5 — Polish

Production hardening and developer experience.

- Add tests for chunking, sync, and query pipelines
- GitHub Actions CI for linting and tests
- Rewrite README with setup guide and architecture overview

---

## Summary

brAIn has the right architecture. The core choices — local ChromaDB, fastembed for
embeddings, header-based chunking — scale from 4 docs to 100K+ without changes.

The main gaps are efficiency (incremental sync), usability (MCP server, config file),
and precision (reranking). None require architectural changes — they're additive
improvements to a solid foundation.

Every developer gets their own local vector database, built from the same git repo.
No servers to maintain. No auth to manage. No network dependency.

**Estimated total effort to production: ~20 hours of focused work.**
