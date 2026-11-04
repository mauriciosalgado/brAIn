from fastmcp import FastMCP

import rag

mcp = FastMCP(
    "brAIn",
    instructions=(
        "brAIn is the user's personal knowledge base — their Obsidian notes / vault / "
        '"brain". Whenever the user asks about their own notes, docs, runbooks, or team '
        'knowledge — e.g. "search my notes", "search brain", "what do my notes say about X", '
        '"check the vault" — call `search_notes` and answer from the returned passages, '
        "citing the source file. Prefer it over web search for anything project- or "
        "team-specific."
    ),
)


@mcp.tool(
    name="search_notes",
    title="Search my notes (brAIn)",
    tags={"notes", "brain", "search", "knowledge-base", "obsidian", "rag"},
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def search_brain(query: str, k: int = 5) -> list[dict]:
    """Search MY NOTES / MY BRAIN / the knowledge base (the user's Obsidian vault).

    ALWAYS use this tool — never answer from memory — whenever the user refers to their
    own notes, brain, vault, docs, runbooks, or team knowledge. Trigger phrases include:
    "search my notes", "search brain", "search the vault", "check my notes",
    "what do my notes say about ...", "do I have a note on ...".

    IMPORTANT — do not confuse this with chat/session history tools. This searches the
    user's WRITTEN Markdown notes (their brAIn / Obsidian vault), NOT past Copilot
    sessions, conversation history, or memory. "My notes" and "my brain" mean THIS vault.
    Semantic search: matches by meaning, not just keywords.

    Args:
        query: What to look for, in natural language (infer it from the request if
            the user didn't state an explicit topic).
        k: Max passages to return (fewer if fewer are relevant).

    Returns:
        Up to `k` note chunks, each with its `text`, `source` path, and `header_path`
        (section), so answers can cite where they came from.
    """
    return rag.query(query, n_results=k)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
