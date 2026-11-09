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
- **Only the configured remote-tracking branch is indexed** (`origin/main` by default).
  Unpushed commits are never indexed. Do not run `rag sync` to make a draft appear.

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
| `rag/index/` | `chunker.py` (Markdown to passages), `embeddings.py` (text to vectors), `store.py` (LanceDB operations and locked retrieval), `indexer.py` (synchronization), `search.py` (retrieves passages from a supplied database) |
| `rag/notes.py` | Shared note eligibility and whole-note reading |
| `rag/` | `config.py` (settings), `cli.py` (terminal commands), `mcp/server.py` (the tools for agents) |
| `brain.toml` | Settings the user may change. Loaded when a process starts. |
| `STANDARDS.md`, `templates/` | How notes are written. Served to agents by the tools. |
| `setup.sh`, `doctor.sh`, `.githooks/` | Install, check, and the hook that syncs after remote-tracking branch changes |
| `tests/` | Tests, laid out like `rag/`. `tests/fixtures/` holds sample notes used to test the chunker. |

Conventions:

- A setting a user might change goes in `brain.toml`: add it to `Settings` in
  `rag/config.py` with a validation rule and a test. Anything else lives in `rag/config.py`.
- Synchronization reads notes from the configured remote-tracking branch's commit with Git,
  never from unpushed local commits or the working tree.
- Keep Git planning independent of the database; pass commits and known paths, not store handles.
  Rebuild plans for missing history only; unexpected Git errors must propagate.
- Check committed blob sizes before requesting contents. Oversized notes are reported and skipped.
- Search only reads its supplied database. CLI/MCP open an existing complete index through
  `store.open_index`, holding the lock through retrieval. They never check Git or sync.
  Missing or unusable caches report an error asking for explicit synchronization.
- Opening an existing store must not rebuild it. Only synchronization rebuilds incompatible
  caches and clears the commit marker before changing notes.
  Status may inspect Git, but must not create or repair an index.
- The MCP `read_note` tool delegates to `notes.read_note`, which reads the current working-tree
  file and validates paths. It may show unpublished edits newer than indexed passages.
  Keep reading backend details out of MCP and reuse `notes.is_note` for note eligibility.
- The sync hook is required. Setup enables `.githooks`; doctor checks it. `reference-transaction`
  runs sync after committed updates to the configured remote-tracking ref and reports the result,
  without fetching or pulling. Local commits, merges and rebases do not trigger synchronization.
- Keep imports at module level, except heavy CLI dependencies: import those inside command
  handlers so help stays lightweight. Keep the CLI in one file with explicit command dispatch;
  pass ordinary values to handlers, not argparse objects.
- Keep the code simple and write only what the project needs. Add no workaround for a situation it
  does not have.
- Never commit `.rag/` (the local index).
