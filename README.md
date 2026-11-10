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
brAIn first. Or copy a template from [`templates/`](templates/) into `notes/` yourself (the folder
also opens as an [Obsidian](https://obsidian.md) vault). Never put secrets in a note: search results
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
- **Index**: each note is cut along its headings into passages, embedded locally with
  [arctic-embed-m-v2.0](https://huggingface.co/Snowflake/snowflake-arctic-embed-m-v2.0)
  ([fastembed](https://github.com/qdrant/fastembed), multilingual), and stored in a
  [LanceDB](https://lancedb.com) table in `.rag/`. Changed settings, chunker code or embedding code
  rebuild it on the next sync.
- **Search** only reads the index: it embeds the question and returns the closest passages, within
  `score_margin` of the best. It never checks Git or syncs. If a sync is running, it waits up to
  5 seconds.

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
| `score_margin` | `0.10` | How close to the best match a passage must be; lower is stricter |
| `max_chunk_size` | `1000` | Longest passage in characters before a section is split (500 to 8000) |
| `min_chunk_size` | `150` | Shorter sections join their neighbour (1 up to half of `max_chunk_size`) |

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
| `uv run rag model` | Download the search model again, or repair it |

If something is wrong, run `./doctor.sh`. To rebuild the index from scratch:
`rm -rf .rag/lancedb && uv run rag sync`. After `git pull` brings new code, restart your assistant.

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

Disk is about 3.5 KB per passage. Later syncs only handle changed notes. Search timings use random
vectors, so search quality at large sizes is not measured. A larger vault is yours to adapt.

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
