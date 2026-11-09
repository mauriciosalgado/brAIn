"""Four MCP tools for indexed search, current note files, standards, and templates."""

from pathlib import Path
from xml.sax.saxutils import quoteattr

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from rag import config, notes
from rag.index import search
from rag.index.store import open_index

READ_ONLY = {"readOnlyHint": True, "openWorldHint": False}

mcp = FastMCP(
    "brAIn",
    instructions=(
        "brAIn gives access to a knowledge base: Markdown notes in a git repository. To answer a "
        "question about what the notes say, call search_notes, answer from the passages and cite "
        "their paths; call read_note if a passage is cut off. To write or edit a note, first call "
        "get_note_standards and get_note_template and follow them."
    ),
)


def format_passages(hits: list[dict]) -> str:
    """The hits as plain text for a model to read: one tagged block per passage, the chunk as it
    is written in the note (not escaped), best match first."""
    passages = "\n\n".join(
        f'<passage rank="{rank}" source={quoteattr(hit["source"])} '
        f"section={quoteattr(hit['header_path'])}>\n{hit['text']}\n</passage>"
        for rank, hit in enumerate(hits, 1)
    )
    noun = "passage" if len(hits) == 1 else "passages"
    return (
        f"{len(hits)} {noun}, best match first, ranked by similarity: they may not answer the "
        f"question. If they do not, search again with other words. Cite the source path (relative "
        f"to {config.ROOT}).\n\n{passages}"
    )


@mcp.tool(title="Search notes", output_schema=None, annotations=READ_ONLY)
def search_notes(query: str, max_results: int = config.MAX_RESULTS) -> str:
    """Search the existing index by meaning and return the most relevant passages.

    Does not synchronize or check Git. Results reflect the last completed sync.

    Use it whenever the answer may be in the user's notes: how something is done, why it was
    decided, how a system is set up, what happened in an incident. Prefer several short, specific
    searches over one broad one.

    Args:
        query: What to look for, as a question or a short description, for example
            "how do we rotate AWS access keys".
        max_results: The most passages to return. Fewer come back when the rest match much worse.

    Returns:
        Passages, best match first, each with its note path (`source`) and `section`.
    """
    try:
        with open_index() as store:
            passages = search.query(
                query, store, max_results=max(1, min(max_results, config.MAX_RESULTS))
            )
        return format_passages(passages)
    except (OSError, ValueError, RuntimeError) as error:
        raise ToolError(str(error)) from error


@mcp.tool(title="Read note", output_schema=None, annotations=READ_ONLY)
def read_note(path: str) -> str:
    """Read the current whole note from the working tree, without Git or synchronization.

    It may include unpublished edits newer than the passages returned by search.

    Use it when a passage from search_notes is cut off, or when you need the rest of the note.

    Args:
        path: The note's path, as given by search_notes, for example "notes/handbook/keys.md".
    """
    try:
        return notes.read_note(path)
    except (OSError, ValueError, RuntimeError) as error:
        raise ToolError(str(error)) from error


def _templates() -> dict[str, Path]:
    """The templates by name: `templates/runbook-template.md` is `runbook`."""
    folder = config.ROOT / "templates"
    return {p.name.removesuffix("-template.md"): p for p in folder.glob("*-template.md")}


@mcp.tool(title="Get note standards", output_schema=None, annotations=READ_ONLY)
def get_note_standards() -> str:
    """Get the rules for writing a note: its folder, file name, title and tags.

    Call it before creating or editing a note, and follow it. It also gives the full path of the
    notes folder.
    """
    try:
        standards = (config.ROOT / "STANDARDS.md").read_text()
    except FileNotFoundError as error:
        raise ToolError("This repository has no STANDARDS.md") from error
    return (
        f"Where notes live: {config.NOTES_DIR}\n"
        f"Create a new note at {config.NOTES_DIR}/<folder>/<file-name>.md, using this full path, "
        f"not the current directory.\n"
        f"Notes are searchable once published on {config.REMOTE}/{config.BRANCH} "
        "and indexed by sync. "
        f"Unless the user says otherwise, create the note on a new branch, not on {config.BRANCH}, "
        f"and leave "
        f"committing and merging to them.\n"
        f"Templates: {', '.join(sorted(_templates())) or 'none'} (see get_note_template).\n\n"
        f"{standards}"
    )


@mcp.tool(title="Get note template", output_schema=None, annotations=READ_ONLY)
def get_note_template(template: str = "note") -> str:
    """Get a template for a new note: `note` for most notes, `runbook` for runnable procedures.

    Fill it in as the standards say: replace `{{title}}` and set the tags. The other templates
    are listed by get_note_standards.
    """
    templates = _templates()
    if template not in templates:
        raise ToolError(f"No template '{template}'. Available: {', '.join(sorted(templates))}")
    return templates[template].read_text()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
