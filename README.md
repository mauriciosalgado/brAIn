# brAIn

**Your notes: easy to write, easy to find, and searchable by your AI assistant.**

brAIn turns a folder of Markdown notes into a knowledge base, for one person or a whole team. Notes
follow one simple standard. You and your AI assistant find the right passage with a search that
runs on your own computer: no cloud, no API keys, no servers to run.

**Contents:** [What you get](#what-you-get) · [Set up](#set-up-once-a-few-minutes) ·
[Use it](#use-it) · [Write a note](#write-a-note) · [Alone or in a team](#alone-or-in-a-team) ·
[Configure](#configure) · [Commands](#commands) · [If something is wrong](#if-something-is-wrong) ·
[Good to know](#good-to-know) · [What is in this folder](#what-is-in-this-folder)

## What you get

| | What brAIn gives |
|---|------------------|
| **A standard for notes** | Folders, file names, titles and tags, plus templates, so notes stay easy to find. |
| **Search by meaning** | "How do we rotate keys" finds the note even if it never says "rotate". |
| **An assistant that knows your notes** | Your AI assistant answers from what you wrote and names the note it used. |
| **An assistant that writes notes your way** | It reads the standard and a template first, so its drafts follow your rules. |
| **Nothing to host** | One settings file, one health check, everything on your computer. |

## Set up (once, a few minutes)

You need **git** and **[uv](https://docs.astral.sh/uv/getting-started/installation/)**.

```bash
git clone <your-repo-url> brAIn && cd brAIn
./setup.sh      # installs, downloads the search model (about 320 MB, once), indexes the notes
./doctor.sh     # checks that everything works
```

Developed and tested on macOS. Linux should work the same; on Windows, use WSL (not tested).

## Use it

### 1. Ask your AI assistant

Connect brAIn once. It is a local [MCP](https://modelcontextprotocol.io) server: add this to your
assistant's MCP settings, with the real path to this folder, and restart the assistant.

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

Then ask in plain words. The assistant answers from your notes and names the note it used:

> *What do my notes say about rotating AWS keys?*
> *Which steps do we follow to copy an RDS snapshot to another account?*

It gets three tools:

| Tool | What it does |
|------|--------------|
| `search_notes` | Returns the passages of the notes that best match a question, each with its note path and section |
| `read_note` | Returns a whole note, by the path a search gave. Reads the searched branch, never the working copy |
| `get_note_standards` | Returns the rules for writing a note, and the full path of the notes folder |
| `get_note_template` | Returns a ready-to-fill template (`note`, `runbook`) |

### 2. Search from the terminal

```bash
uv run rag query "how do we rotate AWS keys"
```

### 3. Browse and edit as usual

`notes/` is plain Markdown in a git repository. Open it in Obsidian or any editor.

## Write a note

Every note follows [`STANDARDS.md`](STANDARDS.md): which folder it goes in, how the file is named,
what the title is and which tags it has.

- **By hand:** copy a template from [`templates/`](templates/), fill it in and save it in the
  right folder of `notes/`.
- **With your assistant:** ask, for example *"Write a handbook note about how I create an IAM
  role."* It reads the standard and a template through brAIn, then creates the note in `notes/`
  with the right name and tags.

Then commit the note. See the next section for when it becomes searchable.

**Never put secrets in a note** (passwords, keys, tokens). Search results are shown to your AI
assistant, and a shared repository is shared.

## Alone or in a team

Only one branch is searched: `main`, or the one you set in `brain.toml`. This is what keeps
everyone's search the same, and what keeps unfinished notes out of it.

| | Working alone | Working in a team |
|---|---------------|-------------------|
| **You write** | Commit the note on `main` | Commit it on a branch and open a pull request |
| **It becomes searchable** | On your next search | When the pull request is merged and you `git pull` |
| **Other machines or people** | Pull on the other machine | Everyone's next `git pull` updates their search |

- A note is found only once it is **committed** on that branch. Edits you have not committed are
  never indexed.
- After a `git pull`, only the notes that changed are re-indexed, in the background, in seconds.
  If that did not run, the next search brings the index up to date first.
- Notes you delete or rename disappear from search (a rename is a delete plus an add).
- The first setup indexes everything once: roughly two minutes for a 1,000-note vault. After that,
  only what changed is indexed.

## Configure

### Settings: `brain.toml`

[`brain.toml`](brain.toml) holds the settings you may want to change. Every setting is explained
in the file itself. It is committed, so everyone who uses the repository gets the same settings,
and it is read every time brAIn runs. Delete a line to get its default. After a change there is
nothing else to do: notes are re-indexed by themselves when a change needs it.

| Setting | Default | What it does |
|---------|---------|--------------|
| `branch` | `"main"` | The branch whose notes are searched. Use `"master"` or `"trunk"` if that is yours. |
| `skip_folders` | `[]` | Folders inside `notes/` that are not searched, such as `["archive", "drafts"]`. |
| `skip_headings` | `["References", "Table of Contents", "TOC"]` | Sections under these headings are not searched. |
| `max_results` | `10` | Most passages one search returns (1 to 50). |
| `score_margin` | `0.10` | How close to the best match a passage must be. Lower is stricter. |
| `max_chunk_size` | `1000` | Longest passage, in characters, before a section is split (500 to 8000). |
| `min_chunk_size` | `150` | Shorter sections join their neighbour (1 up to half of `max_chunk_size`). |

A mistake (a typo, a number out of range) stops brAIn with a message that says what to fix, and
`./doctor.sh` reports it too.

### Personal settings

| Setting | How | When |
|---------|-----|------|
| `BRAIN_BRANCH` | Environment variable, for example `BRAIN_BRANCH=trunk` | Your checkout uses a different branch than `brain.toml` says |
| MCP connection | Your assistant's MCP settings (the JSON above) | Once per assistant |

### What is not configurable

The search model and its vector size are fixed on purpose: changing them needs a code change (see
`PLAN.md`). To change how notes are written, edit `STANDARDS.md` and `templates/`. Assistants read
them from there.

## Commands

| Command | What it does |
|---------|--------------|
| `./setup.sh` | Install, download the model, turn on the git hooks, index the notes. Safe to run again. |
| `./doctor.sh` | Check every part and say how to fix what is wrong |
| `uv run rag query "text"` | Search from the terminal |
| `uv run rag sync` | Bring the index up to date with the searched branch |
| `uv run rag status` | Say whether the index is up to date |
| `uv run rag model` | Download the search model again, or repair it |

## If something is wrong

| Problem | Do this |
|---------|---------|
| Anything at all | `./doctor.sh` |
| Is my search up to date? | `uv run rag status` |
| A note does not show up | It must be committed on the searched branch (merged, if you use pull requests), and you must have pulled |
| A note is reported as skipped | `rag sync` lists notes it cannot index: empty notes, notes over 2 MB, notes that are not UTF-8 text |
| Search returns nothing or is broken | Rebuild the local index: `rm -rf .rag/lancedb && uv run rag sync` |
| The search model is missing or damaged | `uv run rag model` |
| Your assistant does not see brAIn | Check the path in its MCP settings, then restart the assistant |
| The assistant wrote a note in the wrong folder | It must use the full path `get_note_standards` gives. Tell it so, and move the file. |

After updating brAIn's own code with `git pull`, restart your AI assistant so it loads the new
version.

## Good to know

- **Passages, not answers.** Search returns the closest passages, best first. They may not answer
  the question: the assistant has to judge.
- **Only notes under `notes/`**, in `.md` files, outside hidden folders such as `.trash`.
- **Multilingual.** The search model supports many languages, German among them. Our own
  measurements so far are on English notes.
- **Resources.** The search model needs about 1.4 GB of memory while running and 320 MB of disk.
  The first search in a session takes a couple of seconds while it loads.
- **Privacy.** Everything runs locally. What leaves your computer is what your AI assistant sends to
  its own model: the passages it retrieved.

## What is in this folder

| Path | What it is |
|------|------------|
| `notes/` | The knowledge base |
| `templates/` | Starting points for new notes |
| `STANDARDS.md` | How notes are named, filed and tagged |
| `brain.toml` | Settings |
| `rag/` | The search: it cuts notes into passages, embeds them and stores them in `.rag/` |
| `setup.sh`, `doctor.sh`, `.githooks/` | Install, check, and the hooks that update search after a pull |
| `AGENTS.md`, `.github/copilot-instructions.md` | Instructions for AI assistants working in this repository |
| `PLAN.md` | What is done and what is next, with the decisions and measurements |

`.rag/` is your own local index. It can always be rebuilt from the notes and is never committed.

## For developers

```bash
uv run pytest          # the tests
uvx ruff check .       # lint
```
