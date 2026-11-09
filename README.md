# brAIn

**Your notes: easy to write, easy to find, and searchable by your AI assistant.**

brAIn turns a folder of Markdown notes (`notes/`) into a knowledge base for one person or a team.
Notes follow one standard ([`STANDARDS.md`](STANDARDS.md)). A local MCP server lets your AI
assistant search them by meaning, read them, and write new ones your way. Everything runs on your
computer: no cloud, no API keys, no servers.

## Set up

You need **Git 2.28+** and **[uv](https://docs.astral.sh/uv/getting-started/installation/)**
(macOS; Linux should work, Windows via WSL is untested).

```bash
git clone <your-repo-url> brAIn && cd brAIn
./setup.sh      # installs, downloads the search model (about 320 MB, once), indexes the notes
./doctor.sh     # checks that everything works
```

Setup also enables the required Git hook in `.githooks/`: it runs `rag sync` whenever the
configured remote-tracking branch (`origin/main` by default) changes through a push, fetch or pull.
It does not fetch or pull itself.

## Connect your AI assistant

Add the server to your assistant's MCP settings, with the real path to this folder, and restart it:

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

Then ask in plain words: *"What do my notes say about rotating AWS keys?"* The assistant answers
from your notes and names the note it used.

| Tool | What it does |
|------|--------------|
| `search_notes` | Passages that best match a question, each with its note path and section |
| `read_note` | The current whole Markdown file, by a path from a search (may include unpublished edits) |
| `get_note_standards` | The rules for writing a note, and the full path of the notes folder |
| `get_note_template` | A ready-to-fill template (`note`, `runbook`) |

To search from the terminal: `uv run rag query "how do we rotate AWS keys"`.

## How it works

**Sync** (`rag sync`, run by the hook) reads the notes from the last known commit of the configured
remote branch, never from the working tree:

1. `rag/git.py` lists the notes added, changed or removed since the last indexed commit.
2. `rag/index/chunker.py` cuts each note along its headings into passages (long sections are split,
   tiny ones joined, skipped headings dropped).
3. `rag/index/embeddings.py` turns each passage, with its section path, into a vector with a local
   model ([arctic-embed-m-v2.0](https://huggingface.co/Snowflake/snowflake-arctic-embed-m-v2.0),
   multilingual, run by [fastembed](https://github.com/qdrant/fastembed)).
4. `rag/index/store.py` writes them to a [LanceDB](https://lancedb.com) table in `.rag/`, together
   with the indexed commit. Changed settings, chunker code or embedding code rebuild the index on
   the next sync.

**Search** (CLI and MCP) only reads that index: it embeds the question, takes the closest passages
by cosine similarity, and keeps those within `score_margin` of the best one
(`rag/index/search.py`). It never checks Git, syncs or repairs the index; a missing or unusable
index produces an error asking for `rag sync`. If a sync is running, search waits at most 5 seconds.

Only published notes are searchable: uncommitted edits and unpushed commits are not indexed. Notes
that cannot be indexed (empty, over 2 MB, invalid UTF-8, over the model's token limit) are reported
by `rag sync` and skipped. A rename counts as a delete plus an add.

## Write a note

Copy a template from [`templates/`](templates/) and save it in the right folder of `notes/`, or ask
your assistant: it reads the standard and a template through brAIn first. Then commit and push.
The folder also opens as an [Obsidian](https://obsidian.md) vault: `.obsidian/` pins its plugins.

**Never put secrets in a note.** Search results are shown to your AI assistant, and a shared
repository is shared.

Working alone, commit on `main` and push. In a team, use a branch and a pull request; everyone's
next `git pull` updates their search.

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

If something is wrong, start with `./doctor.sh`. To rebuild the index from scratch:
`rm -rf .rag/lancedb && uv run rag sync`. After `git pull` brings new code, restart your assistant.

The search model needs about 1.4 GB of memory while running and 320 MB of disk; the first search
in a session takes a few seconds while it loads. Everything stays on your computer except what
your assistant sends to its own model: the passages it retrieved.

## Scale

Every person builds and searches a local index, which suits teams up to some tens of thousands of
notes. A note makes 4 to 8 passages (measured on 70 team notes and on this repository's notes). The
cost is the first index, not search. Measured on an Apple M4 Pro, CPU only:

| Passages  | Notes              | First index (28 ms per passage) | Exact search |
|----------:|-------------------:|--------------------------------:|-------------:|
|   100,000 |   12,500 to 25,000 |                      47 minutes |  about 40 ms |
|   200,000 |   25,000 to 50,000 |                       1.6 hours |  about 80 ms |
| 1,000,000 | 125,000 to 250,000 |                       7.9 hours |  about 0.4 s |

- Disk is about 3.5 KB per passage, and searching 1,000,000 passages uses about 1 GB of memory.
- 30,000 notes take 1 to 2 hours to index for each person. Later syncs only handle changed notes.
- If that first index is too slow for your team, build one shared index instead of one per person.
  This is not supported yet (see `PLAN.md`).
- Search timings use random vectors, so search quality at that size is not measured.

## Project structure

| Path | What it is |
|------|------------|
| `notes/`, `templates/`, `STANDARDS.md` | The knowledge base, note templates, and the writing standard |
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
