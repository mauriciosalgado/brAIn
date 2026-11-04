# brAIn

brAIn is a RAG note taking system that uses a vector database to store and retrieve notes. It is designed to be used with a large language model (LLM).

## Connect your AI assistant (MCP)

brAIn ships an MCP server — the `rag-mcp` command (stdio) — that exposes a `search_notes` tool.
Add it to your MCP host so the assistant can search your notes and cite the source.

First build the index (once, and after adding notes):

```bash
uv sync            # install dependencies
uv run rag sync    # index notes/ (first run downloads the embedding model, ~100 MB)
```

Then register the server with your host.

**VS Code (GitHub Copilot)** — create `.vscode/mcp.json` in the repo:

```json
{
  "servers": {
    "brain": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "rag-mcp"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

Open the Chat view, switch to **Agent** mode, and click **Start** above the `brain` server in
`mcp.json` — `search_notes` then appears under the tools icon (🔧).

**IntelliJ / JetBrains IDEs (GitHub Copilot)** — open Copilot Chat, switch to **Agent** mode, click
the tools icon, then **Add MCP Tools**. Add the server to the `mcp.json` that opens:

```json
{
  "servers": {
    "brain": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/brAIn", "rag-mcp"]
    }
  }
}
```

Use the **absolute** path to the repo (JetBrains' `mcp.json` isn't workspace-relative). If `uv` isn't
found, use its full path from `which uv`.

**GitHub Copilot CLI** — run `/mcp` inside `copilot` to add a server, or edit
`~/.copilot/mcp-config.json` directly. Note the different key (`mcpServers`) and the `tools` field:

```json
{
  "mcpServers": {
    "brain": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/brAIn", "rag-mcp"],
      "tools": ["*"]
    }
  }
}
```

Once connected, ask a question about your notes and the assistant will call `search_notes` and answer
with citations.

## The `rag` and `rag-mcp` commands

Both commands are defined in the `[project.scripts]` table of `pyproject.toml`:

```toml
[project.scripts]
rag = "rag.cli:main"
rag-mcp = "rag.mcp.server:main"
```

Each entry maps a command name to a `module:function` entry point. So `rag` runs `main()` in
`rag/cli.py` (the `sync` / `query` / `clean` CLI), and `rag-mcp` runs `main()` in
`rag/mcp/server.py` (which starts the stdio MCP server your host launches).

`uv run <command>` executes them in the project's environment — uv installs the dependencies and
registers these scripts on the fly, so there's nothing to set up by hand:

```bash
uv run rag sync           # index notes/
uv run rag query "..."    # search from the terminal
uv run rag-mcp            # start the MCP server (normally your host runs this)
```

The same `pyproject.toml` also declares the project's `dependencies` and build backend, which is how
`uv sync` knows what to install. To add another command, add a line to `[project.scripts]` and
re-run `uv sync`.

## Modified Files

## Chunking Strategy

## References

- [langchain-markdown-splitter](https://docs.langchain.com/oss/python/integrations/splitters/markdown_header_metadata_splitter)
- [Chunking-tricks](https://medium.com/@dev_tips/25-chunking-tricks-for-rag-that-devs-actually-use-12bebd0375bc)
test
