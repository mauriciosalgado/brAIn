# brAIn

**Your notes: easy to write, easy to find, and searchable by your AI assistant.**

brAIn turns the Markdown notes in `notes/` into a knowledge base for one person or a team. Your AI
assistant searches them by meaning through a local MCP server, reads them, and writes new ones to
the standard in [`STANDARDS.md`](STANDARDS.md). Everything runs on your computer: no cloud, no API
keys.

## Set up

You need **Git 2.28+** and **[uv](https://docs.astral.sh/uv/getting-started/installation/)**
(macOS; Linux should work, Windows via WSL is untested).

```bash
git clone <your-repo-url> brAIn && cd brAIn
./setup.sh      # installs, downloads the search model (about 320 MB, once), indexes the notes
./doctor.sh     # checks that everything works
```

Setup also enables a Git hook that runs `rag sync` whenever `origin/main` changes (push, fetch or
pull). The hook does not fetch for you: run `git pull` to get your teammates' notes.

## Connect your AI assistant

Add the server to your assistant's MCP settings, with the real path to this folder, then restart
the assistant:

```json
{
  "mcpServers": {
    "brAIn": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/brAIn", "rag-mcp"],
      "tools": ["*"]
    }
  }
}
```

## Use it

**Search.** Ask in plain words: *"What do my notes say about rotating AWS keys?"* The assistant
answers from your notes and names the note it used. From the terminal:
`uv run rag query "how do we rotate AWS keys"`.

**Write a note.** Ask your assistant to write it: it reads the standard and a template through
brAIn first. Or copy a template from [`templates/`](templates/) into `notes/` yourself.
For [Obsidian](https://obsidian.md), open the repository root as your vault; the shared configuration
saves pasted or dragged attachments in `attachments/`. Never put secrets in a note: search results
go to your AI assistant.

**Publish.** Commit and push. Alone, push to `main`. In a team, use a branch and a pull request.
Only pushed notes are searchable: after `git pull`, the hook updates your index.

The assistant gets four tools:

| Tool | What it does |
|------|--------------|
| `search_notes` | Passages that best match a question, each with its note path and section |
| `read_note` | The current whole file, by a path from a search (may include unpublished edits) |
| `get_note_standards` | The rules for writing a note, and the full path of the notes folder |
| `get_note_template` | A ready-to-fill template (`note`, `runbook`) |

## How it works

Diagrams are in [`Excalidraw/`](Excalidraw/) (open them in Obsidian):

| Diagram | Shows |
|---------|-------|
| [`1-overview`](Excalidraw/1-overview.excalidraw.md) | The parts and how a question flows through them |
| [`2-git-lifecycle`](Excalidraw/2-git-lifecycle.excalidraw.md) | How Git decides what the index must update |
| [`3-chunking`](Excalidraw/3-chunking.excalidraw.md) | How a note is cut into passages |
| [`4-indexing`](Excalidraw/4-indexing.excalidraw.md) | What `rag sync` does for each note |

In short:

- **Sync** reads notes from the last known commit of `origin/main`, never from your working tree,
  and updates only the notes that changed since the last indexed commit. Notes that cannot be
  indexed (empty, over 2 MB, invalid UTF-8, over the model's token limit) are reported and skipped.
- **Index**: each heading section is embedded independently; tiny siblings and children never merge.
  Oversized sections split at Markdown blocks, then paragraphs, lines or words as needed.
  Each embedding includes the title, heading path, a short description from below `# Title`,
  and the fragment body. The description stops before `Links:` or `Tags:` and is capped at
  400 characters, with no `Summary` fallback. If absent, context is stored as `""` and omitted
  from embeddings and search output. Embeddings are made locally with
  [arctic-embed-m-v2.0](https://huggingface.co/Snowflake/snowflake-arctic-embed-m-v2.0)
  ([fastembed](https://github.com/qdrant/fastembed), multilingual), and stored in a
  [LanceDB](https://lancedb.com) table in `.rag/`, alongside original fragment text.
  Each row stores its source, chunk position, heading path, description, tags, text and vector.
  Tags are a native string list, such as `["aws", "runbook"]`: lowercase, unique and without `#`.
  This supports future exact tag membership queries without parsing text. Tags are not embedded,
  filtered or loaded during semantic search.
  Changed schema, chunker code, embedding code or indexing settings rebuild it on the next sync.
- **Search** only reads the index: it embeds the question and returns the closest passages, within
  `score_margin` of the best and at or above `min_score`, up to `max_results`.
  If every passage falls below the score floor, search explicitly reports no passages.
  Similarity is not calibrated confidence: unrelated passages can still exceed the floor.
  Treat passages as pointers to relevant notes; read the full notes for context.
  There is no parent-section
  expansion: even a tiny section keeps its own path and body. Blocks within the same section pack
  together when they fit. Results identify their indexed Git commit. `read_note` instead labels
  its output as working-tree content, which may contain unpublished edits; do not assume the two
  versions match. Search never checks Git or syncs.
  If a sync is running, it waits up to 5 seconds.

Heading boundaries are never crossed, even when two headings have the same name. A parent
section contains only its own text, not its children's text. A heading without body content makes
no chunk, but remains in its children's paths. A note without `# Title` uses its filename in
those paths and has no description context.

Within one section, consecutive Markdown blocks are packed in reading order when they fit.
Oversized code fences and tables repeat their fences or table headers when there is room;
lists split between fitting items, with paragraph/line/word splitting as a fallback. The body
limit does not include embedding prefixes. Description text also remains in its introduction
chunk; it is not removed from the original body.

## Configure

[`brain.toml`](brain.toml) holds the settings you may change; each one is explained in the file. It
is committed, so everyone gets the same settings. Delete a line to get its default. A mistake stops
brAIn with a message saying what to fix. After changing settings, restart your AI assistant, and
run `uv run rag sync` for changes that affect indexing.

| Setting | Default | What it does |
|---------|---------|--------------|
| `branch` | `"main"` | The remote branch whose notes are searched |
| `remote` | `"origin"` | The Git remote that holds it |
| `skip_folders` | `[]` | Folders inside `notes/` that are not searched, such as `["archive"]` |
| `skip_headings` | `["References", "Table of Contents", "TOC"]` | Sections under these headings are not searched |
| `max_results` | `10` | Most passages one search returns (1 to 50) |
| `score_margin` | `0.20` | How close to the best match a passage must be; lower is stricter |
| `min_score` | `0.25` | Minimum cosine similarity (0 to 1); weak best matches can also be discarded |
| `max_chunk_size` | `2000` | Maximum fragment body length in characters (500 to 8000), excluding its context and heading-path prefix |

`BRAIN_BRANCH` (environment variable) overrides `branch` for one checkout. The search model is
fixed in code on purpose (`rag/config.py`).

## Commands

| Command | What it does |
|---------|--------------|
| `./setup.sh` | Install, download the model, enable the git hook, index the notes. Safe to re-run. |
| `./doctor.sh` | Check every part and say how to fix what is wrong |
| `uv run rag sync` | Bring the index up to date with the searched branch |
| `uv run rag status` | Say whether the index is up to date |
| `uv run rag query "text"` | Search from the terminal |
| `uv run rag reset` | Delete the index (the next `rag sync` rebuilds it from the notes) |
| `uv run rag model` | Download the search model again, or repair it |

If something is wrong, run `./doctor.sh`. To rebuild the index from scratch:
`uv run rag reset && uv run rag sync`. After `git pull` brings new code, restart your assistant.

The search model needs about 1.4 GB of memory and 320 MB of disk; the first search in a session
takes a few seconds to load it. Only the passages your assistant retrieves leave your computer,
sent to its own model.

## Scale

Every person builds a local index, so brAIn suits one person or a team with up to some tens of
thousands of notes. The cost is the first index, not search (Apple M4 Pro, CPU only; a note makes 4
to 8 passages):

| Passages  | Notes              | First index (28 ms per passage) | Exact search |
|----------:|-------------------:|--------------------------------:|-------------:|
|   100,000 |   12,500 to 25,000 |                      47 minutes |  about 40 ms |
|   200,000 |   25,000 to 50,000 |                       1.6 hours |  about 80 ms |
| 1,000,000 | 125,000 to 250,000 |                       7.9 hours |  about 0.4 s |

These are vector-scan estimates, not measurements of the current chunking or context assembly.
Stored description strings add space beyond the vectors. Later syncs only handle changed notes.
Search timings use random vectors, so search quality at large sizes is not measured.
A larger vault is yours to adapt.

## Project structure

| Path | What it is |
|------|------------|
| `notes/`, `templates/`, `STANDARDS.md` | The knowledge base, note templates, and the writing standard |
| `Excalidraw/` | Architecture diagrams (see How it works) |
| `brain.toml` | Settings |
| `rag/config.py`, `rag/cli.py` | Settings and terminal commands |
| `rag/git.py` | Local Git state and committed-file reads |
| `rag/notes.py` | Which paths are notes, and whole-note reading |
| `rag/index/` | Chunking, embeddings, LanceDB store, synchronization and search |
| `rag/mcp/server.py` | The four MCP tools ([FastMCP](https://gofastmcp.com)) |
| `setup.sh`, `doctor.sh`, `.githooks/` | Install, health check, and the sync hook |
| `AGENTS.md`, `PLAN.md` | Instructions for AI agents working on this repository; roadmap and decisions |

`.rag/` is your local index. It can always be rebuilt and is never committed.

```bash
uv run pytest                                   # tests (about 6 minutes, real model)
uvx ruff check . && uvx ruff format --check rag tests
uv run ty check rag
```
