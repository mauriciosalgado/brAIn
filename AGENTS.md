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
- **Only the configured branch is indexed** (`main` by default). Do not run `rag sync` to make a
  draft appear.

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
| `rag/git.py` | Local branch state, note-change plans, and raw committed-file bytes. No database operations or whole-note tool. |
| `rag/index/` | `chunker.py` (Markdown to passages), `embeddings.py` (text to vectors), `store.py` (LanceDB operations), `indexer.py` (updates and prepares the index), `search.py` (retrieves passages from a supplied database) |
| `rag/` | `config.py` (settings), `cli.py` (terminal commands), `mcp/server.py` (the tools for agents) |
| `brain.toml` | Settings the user may change. Loaded when a process starts. |
| `STANDARDS.md`, `templates/` | How notes are written. Served to agents by the tools. |
| `setup.sh`, `doctor.sh`, `.githooks/` | Install, check, and the hook that syncs the index after local branch changes |
| `tests/` | Tests, laid out like `rag/`. `tests/fixtures/` holds sample notes used to test the chunker. |

Conventions:

- A setting a user might change goes in `brain.toml`: add it to `Settings` in
  `rag/config.py` with a validation rule and a test. Anything else lives in `rag/config.py`.
- Notes are read from the configured branch's local commit with git, never from the working tree.
- Keep Git planning independent of the database; pass commits and known paths, not store handles.
- Search only reads its supplied database. CLI/MCP explicitly prepare it through
  `indexer.prepare_index`, which synchronizes if needed and holds the lock through retrieval.
- Opening an existing store must not rebuild it. Only synchronization rebuilds incompatible
  caches and clears the commit marker before changing notes.
- The MCP `read_note` tool validates note paths and decodes Git's raw committed-file bytes.
- The sync hook is required. Setup enables `.githooks`; doctor checks it. `reference-transaction`
  runs sync after committed local branch-ref updates and reports the result, without fetching
  or pulling.
- Keep imports at module level, except heavy CLI dependencies: import those inside command
  handlers so help stays lightweight. Keep the CLI in one file with explicit command dispatch;
  pass ordinary values to handlers, not argparse objects.
- Keep the code simple and write only what the project needs. Add no workaround for a situation it
  does not have.
- Never commit `.rag/` (the local index).
