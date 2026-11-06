# AGENTS.md

Guidance for AI agents (Copilot, Claude, ...) working with a **brAIn** knowledge base. For humans,
see `README.md`.

brAIn is a team knowledge base: Markdown notes in `notes/`, written to one standard, searched
through a local index that is exposed to agents as an MCP server. No cloud, no API keys.

## Find information

Use the MCP tool **`search_notes`** for any question about how the team works or how its systems
are set up. It returns the most relevant passages, best first, each with its note path (`source`)
and section. Answer from the passages and **cite the source path**. The passages are ranked by
similarity, so they may not answer the question: say so when they do not.

Without MCP, run `uv run rag query "question"`.

## Write or edit a note

1. Call **`get_note_standards`** (or read `STANDARDS.md`) and follow it. It is the only place the
   rules are written, and it also says where the notes folder is.
2. Call **`get_note_template`** (or read `templates/`), for example `note` or `runbook`.
3. Create the note **inside this repository's `notes/` folder**, using the full path from the
   standards. Never create it in your current directory, even if that is another project.
4. Work on a new git branch, not on the main branch. A note becomes searchable once it is merged
   into main and the developer has pulled. Do not run `rag sync` to make it appear.
5. Never invent facts. If you are unsure, leave a clear `TODO` for a person.

## Repo map

| Path | What it is | Touch it when |
|------|------------|---------------|
| `notes/` | The knowledge base | creating, editing or auditing notes |
| `templates/` | Note starting points | starting a new note |
| `STANDARDS.md` | Naming, folders, tags | read before creating notes |
| `brain.toml` | Team settings (branch, search, chunking) | a team wants different behaviour |
| `rag/` | The search code | changing how indexing or search works |
| `rag/config.py` | Internal settings and the loader for `brain.toml` | adding a setting |
| `rag/mcp/server.py` | The MCP tools | changing what agents can call |

## Working on the code

```bash
uv sync                  # install dependencies
uv run pytest            # tests
uvx ruff check .         # lint
./doctor.sh              # check the installation
```

- Settings a team might change belong in `brain.toml` and are read at run time. Add them to
  `_TEAM_DEFAULTS` in `rag/config.py` with a validation rule and a test. Everything else lives in
  `rag/config.py`, not inline.
- Notes are read from the main branch's commit with git, never from the working tree.
- Keep the code simple. Do not add workarounds for situations this project does not have.

## Golden rules

1. Follow `STANDARDS.md` for every note.
2. **No secrets** in notes or code. This repository is shared.
3. Keep runbooks generic: no hardcoded paths, accounts or hosts.
4. `.rag/` is a local, rebuildable index. Never commit it.
