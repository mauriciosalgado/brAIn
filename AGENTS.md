# AGENTS.md

Guidance for AI agents (Copilot, Claude, …) working in a **brAIn** repository.

brAIn is a local RAG over an Obsidian vault: Markdown notes in `notes/` are indexed
into a local vector database and exposed to AI hosts through an MCP server. No API keys, no cloud.
See `README.md` to get started.

## Repo map

| Path | What it is | Touch it when… |
|------|-----------|----------------|
| `notes/` | The knowledge base (Markdown) | creating / editing / auditing notes |
| `templates/` | Note scaffolds | starting a new note |
| `STANDARDS.md` | Naming, folder, and tagging rules | **read before creating notes** |
| `rag/` | RAG pipeline: chunk → embed → store → query | changing indexing / search behavior |
| `rag/config.py` | All tunable settings | adjusting chunking / model / paths |
| `rag/mcp_server.py` | MCP server (the `search_notes` / `read_note` tools) | changing what hosts can call |

## Working with notes (the common case)

Notes follow `STANDARDS.md` — **read it first.** In short:

- **Folder = type:** `architecture/ handbook/ decisions/ scripts/ incidents/ team/`.
- **Filename:** `domain-[subdomain]-description.md`, lowercase, hyphenated (incidents: `YYYY-MM-DD-…`).
- **Every note:** a title matching the filename, and **≥2 tags** (`#domain #type`).
- Start from `templates/`; keep the `References` and `Table of Contents` headers (they're skipped
  during indexing, so they add no retrieval noise).

Agents can help find notes (`grep -r "#tag" notes/`), draft standards-compliant notes, audit for
violations, and suggest cross-links.

## Searching notes

Prefer the MCP **`search_notes`** tool for meaning-based questions ("how do we rotate credentials?")
— it returns the most relevant passages with citations. Use **`read_note(source)`** for a full file.
The index self-updates on use; `uv run rag sync` rebuilds it if needed (only changed notes re-embed).

## Working with the code

```bash
uv sync                    # install dependencies
uv run rag sync            # index notes/ into the local vector DB
uv run rag query "text"    # semantic search from the CLI
```

Change behavior in `rag/config.py`, not inline.

## Golden rules

1. Follow `STANDARDS.md` for every note.
2. **No secrets** in notes or code — this repo is shared.
3. Keep shared runbooks generic; avoid environment-specific hardcoding (paths, accounts, hosts).
4. `.rag/` is a local, rebuildable index — never commit it.
