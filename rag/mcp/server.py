from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

import rag
from rag import config

READ_ONLY = {"readOnlyHint": True, "openWorldHint": False}

mcp = FastMCP(
    "brAIn",
    instructions=(
        "brAIn is the team's knowledge base: Markdown notes in a git repository. Use search_notes "
        "to answer questions about how the team works, and cite the note path. To write or edit a "
        "note, first call get_note_standards and get_note_template and follow them. Create the "
        "note in the notes folder they name, never in the current directory."
    ),
)


def _attribute(value: str) -> str:
    return '"' + value.replace('"', "'") + '"'  # a quote cannot end the attribute early


def format_passages(hits: list[dict]) -> str:
    """The hits as plain text for a model to read: one tagged block per passage, the chunk as it
    is written in the note (not escaped), best match first."""
    passages = "\n\n".join(
        f'<passage rank="{rank}" source={_attribute(hit["source"])} '
        f"section={_attribute(hit['header_path'])}>\n{hit['text']}\n</passage>"
        for rank, hit in enumerate(hits, 1)
    )
    noun = "passage" if len(hits) == 1 else "passages"
    return (
        f"{len(hits)} {noun} from the team's notes, best match first. Ranked by similarity, so "
        f"they may not answer the question. Cite the source path; paths are relative to "
        f"{config.ROOT}.\n\n{passages}"
    )


@mcp.tool(title="Search notes", output_schema=None, annotations=READ_ONLY)
def search_notes(query: str, k: int = config.MAX_RESULTS) -> str:
    """Search the team's notes and return the most relevant passages.

    Use it for questions about how the team works or how its systems are set up: runbooks,
    architecture, decisions, handbook, incidents.

    Args:
        query: What to look for, in plain words.
        k: The most passages to return. Fewer come back when the rest match much worse.

    Returns:
        Passages, best match first, each with its note path (`source`) and `section`.
    """
    try:
        return format_passages(rag.query(query, n_results=max(1, min(k, config.MAX_RESULTS))))
    except (ValueError, RuntimeError) as error:  # empty query, no notes, model not available
        raise ToolError(str(error)) from error


def _templates() -> dict[str, str]:
    """The templates by name: `templates/runbook-template.md` is `runbook`."""
    folder = config.ROOT / "templates"
    return {
        p.name.removesuffix("-template.md"): p.read_text() for p in folder.glob("*-template.md")
    }


@mcp.tool(title="Get note standards", output_schema=None, annotations=READ_ONLY)
def get_note_standards() -> str:
    """Get the team's rules for writing a note: where it goes, its file name, title and tags.

    Call it before creating or editing a note. It also says where the notes folder is.
    """
    try:
        standards = (config.ROOT / "STANDARDS.md").read_text()
    except FileNotFoundError as error:
        raise ToolError("This repository has no STANDARDS.md") from error
    return (
        f"Where notes live: {config.NOTES_DIR}\n"
        f"Create a new note at {config.NOTES_DIR}/<folder>/<file-name>.md, using this full path, "
        f"not the current directory. Do it on a new git branch, not on {config.BRANCH}: a note "
        f"becomes searchable once it is merged into {config.BRANCH}.\n"
        f"Templates: {', '.join(sorted(_templates())) or 'none'} (see get_note_template).\n\n"
        f"{standards}"
    )


@mcp.tool(title="Get note template", output_schema=None, annotations=READ_ONLY)
def get_note_template(name: str = "note") -> str:
    """Get a template for a new note, such as `note` or `runbook`.

    Fill it in and follow the standards: replace `{{title}}` and set the tags.
    """
    templates = _templates()
    if name not in templates:
        raise ToolError(f"No template '{name}'. Available: {', '.join(sorted(templates))}")
    return templates[name]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
