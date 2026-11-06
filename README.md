# brAIn

**Your team's notes: easy to write, easy to find, and searchable by your AI assistant.**

brAIn turns a folder of Markdown notes into a shared knowledge base. People write notes to one
simple standard. Everyone, and every AI assistant, finds the right passage with a search that runs
on your own computer: no cloud, no API keys, no servers to run.

**Contents:** [What you get](#what-you-get) · [Set up](#set-up-once-a-few-minutes) ·
[Use it](#use-it) · [Write a note](#write-a-note) · [Keeping everyone in sync](#keeping-everyone-in-sync) ·
[Configure](#configure) · [Commands](#commands) · [If something is wrong](#if-something-is-wrong) ·
[Good to know](#good-to-know) · [What is in this folder](#what-is-in-this-folder)

## What you get

| For | What brAIn gives you |
|-----|----------------------|
| **Writers** | One standard for folders, file names, titles and tags, plus templates. Your AI assistant can follow it for you. |
| **Readers** | A search that understands meaning, not just keywords: "how do we rotate keys" finds the note even if it never says "rotate". |
| **AI assistants** | A local tool that returns the right passages of your notes, with the note path to cite, plus the standards for writing new notes. |
| **The team** | Notes reviewed in pull requests. Everyone searches the same merged notes, and the search updates itself when they pull. |
| **Admins** | One settings file (`brain.toml`), one health check (`./doctor.sh`), nothing to host. |

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

Then ask in plain words, and the assistant answers from your notes and names the note it used:

> *What do our notes say about rotating AWS keys?*
> *Which steps do we follow when an RDS snapshot has to be copied to another account?*

The assistant gets three tools:

| Tool | What it does |
|------|--------------|
| `search_notes` | Returns the passages of the notes that best match a question, each with its note path and section |
| `get_note_standards` | Returns the team's rules for writing a note, and the full path of the notes folder |
| `get_note_template` | Returns a ready-to-fill template (`note`, `runbook`, ...) |

### 2. Search from the terminal

```bash
uv run rag query "how do we rotate AWS keys"
```

### 3. Browse and edit as usual

`notes/` is plain Markdown in a git repository. Open it in Obsidian or any editor.

## Write a note

Every note follows [`STANDARDS.md`](STANDARDS.md). The short version:

| | Rule | Example |
|---|------|---------|
| **Folder** | By kind of note: `architecture/`, `handbook/`, `decisions/`, `scripts/`, `incidents/`, `team/` | `notes/handbook/` |
| **File name** | lowercase, hyphens: `domain-description.md` (incidents start with the date) | `aws-iam-role-create.md` |
| **Title** | The `# Title` matches the file name, in words | `# AWS IAM Role Create` |
| **Tags** | At least two: the topic and the kind | `Tags: #aws #handbook` |

**By hand:** copy a template from [`templates/`](templates/), fill it in, save it in the right folder.

**With your assistant:** just ask.

> *Write a handbook note about how we create an IAM role, following our standards.*

The assistant calls `get_note_standards` and `get_note_template`, then creates the note in this
repository's `notes/` folder, on a new branch, with the right name and tags.

Either way: review the note, commit it on a branch and open a pull request.

**Never put secrets in a note** (passwords, keys, tokens). Search results are shown to your AI
assistant, and this repository is shared.

## Keeping everyone in sync

```
 your branch ──▶ pull request ──▶ merged into main ──▶ teammates run `git pull` ──▶ their search updates
```

- **Only the main branch is searched**, whichever branch you have checked out. A note you are still
  writing on a branch is never found by anyone, you included. Nothing unreviewed leaks into search.
- **After a `git pull`**, only the notes that changed are re-indexed, in the background, in
  seconds. If that did not run, the next search brings the index up to date first.
- **Notes you delete or rename** disappear from search (a rename is a delete plus an add).
- **First setup** indexes everything once: roughly two minutes for a 1,000-note vault. After that,
  only what changed is indexed.

## Configure

### Team settings: `brain.toml`

[`brain.toml`](brain.toml) is committed, so everyone gets the same settings, and it is read every
time brAIn runs. Delete a line to get its default. After a change there is nothing else to do:
notes are re-indexed by themselves when a change needs it.

| Setting | Default | What it does |
|---------|---------|--------------|
| `branch` | `"main"` | The branch your team merges notes into. Use `"master"` if that is yours. |
| `skip_headings` | `["References", "Table of Contents", "TOC"]` | Sections under these headings are not searched. |
| `max_results` | `10` | Most passages one search returns (1 to 50). More gives an assistant more context, and costs it more tokens. |
| `score_margin` | `0.10` | How close to the best match a passage must be (above 0, up to 1). Smaller is stricter. |
| `max_chunk_size` | `1000` | Longest passage in characters before a section is split (500 to 8000). |
| `min_chunk_size` | `150` | Shorter sections join their neighbour (1 up to half of `max_chunk_size`). |

A mistake (a typo, a number out of range) stops brAIn with a message that says what to fix, and
`./doctor.sh` reports it too.

### Personal settings

| Setting | How | When |
|---------|-----|------|
| `BRAIN_BRANCH` | Environment variable, for example `BRAIN_BRANCH=trunk` | One person's checkout uses a different main branch than the team file says |
| MCP connection | Your assistant's MCP settings (the JSON above) | Once per person, per assistant |

### What is not configurable

The search model, the vector size and the rules of the standard are fixed on purpose: changing them
needs a reviewed code change (see `PLAN.md`). To change the standard itself, edit `STANDARDS.md`
and `templates/` in a pull request. Assistants read them from there.

## Commands

| Command | What it does |
|---------|--------------|
| `./setup.sh` | Install, download the model, turn on the git hooks, index the notes. Safe to run again. |
| `./doctor.sh` | Check every part and say how to fix what is wrong |
| `uv run rag query "text"` | Search from the terminal |
| `uv run rag sync` | Bring the index up to date with the main branch |
| `uv run rag status` | Say whether the index is up to date |
| `uv run rag model` | Download the search model again, or repair it |

## If something is wrong

| Problem | Do this |
|---------|---------|
| Anything at all | `./doctor.sh` |
| Is my search up to date? | `uv run rag status` |
| A note does not show up | It must be committed, merged into the main branch, and you must have pulled |
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
| `brain.toml` | Team settings |
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
