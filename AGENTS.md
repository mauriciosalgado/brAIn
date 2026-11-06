# AGENTS.md

brAIn is a knowledge base: Markdown notes in `notes/`, searched through a local index and exposed
over MCP. One person or a team uses it. For humans, see `README.md`. This file is the only place
with instructions for agents.

## Using the knowledge base

Use the brAIn MCP tools: `search_notes`, `read_note`, `get_note_standards` and
`get_note_template`. Their descriptions say when to use each. Without MCP, run `uv run rag query "question"` to search, and
read `STANDARDS.md` and `templates/` before writing a note.

Rules for writing notes that the standard does not cover:

- **Search first.** If a note on the topic exists, update it instead of adding a duplicate, and
  link the related notes.
- **Never invent facts.** If you are unsure, leave a clear `TODO` for a person.
- **No secrets** in notes. Keep runbooks generic: no hardcoded paths, accounts or hosts.
- **Create notes on a new branch**, not on the main branch, and leave committing and merging to the
  user unless they ask you to.
- **Only the main branch is indexed.** Do not run `rag sync` to make a draft appear.

## Working on the code

Run these from the repository root. The first run needs internet once, to download the search model
(about 320 MB).

```bash
./setup.sh            # install, download the model, index the notes (once)
uv run pytest         # all tests, about a minute; they use the real model
uvx ruff check .      # lint; also run: uvx ruff format --check rag tests
uv run ty check rag   # types
./doctor.sh           # check the installation
```

| Path | What it is |
|------|------------|
| `rag/notes/` | Getting text out of the repository: `git.py` (plain git: branch tip, changes, file contents), `vault.py` (which files are notes, and their text on the searched branch), `chunker.py` (note to passages) |
| `rag/index/` | The searchable index: `embeddings.py` (text to vectors), `store.py` (the LanceDB table), `indexer.py` (keeps it in line with git), `search.py` (question to passages) |
| `rag/` | `config.py` (settings), `cli.py` (the `rag` command), `mcp/server.py` (the tools for agents) |
| `brain.toml` | Settings the user may change. Read at run time. |
| `STANDARDS.md`, `templates/` | How notes are written. Served to agents by the tools. |
| `setup.sh`, `doctor.sh`, `.githooks/` | Install, check, and the hooks that sync the index after a pull |
| `tests/` | Tests, laid out like `rag/`. `tests/fixtures/` holds sample notes used to test the chunker. |

Conventions:

- A setting a user might change goes in `brain.toml`: add it to `_DEFAULTS` in
  `rag/config.py` with a validation rule and a test. Anything else lives in `rag/config.py`.
- Notes are read from the main branch's commit with git, never from the working tree.
- Keep the code simple and write only what the project needs. Add no workaround for a situation it
  does not have.
- Never commit `.rag/` (the local index).
