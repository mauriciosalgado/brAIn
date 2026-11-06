import asyncio
import re

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from rag import config
from rag.mcp.server import mcp

NOTE = (
    "# Keys\n\n## Rotation\n\n"
    + "Rotate access keys every ninety days and delete the old ones. " * 4
    + "\n"
)


def call_raw(query: str, **arguments):
    async def run():
        async with Client(mcp) as client:
            return await client.call_tool("search_notes", {"query": query, **arguments})

    return asyncio.run(run())


def call(query: str, **arguments) -> str:
    return call_raw(query, **arguments).content[0].text


def passages(text: str) -> list[str]:
    return re.findall(r"<passage .*?</passage>", text, re.DOTALL)


def test_the_tool_is_listed_with_a_description():
    async def run():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(run())
    assert [t.name for t in tools] == ["search_notes", "get_note_standards", "get_note_template"]
    assert "team's notes" in tools[0].description
    assert [t.title for t in tools] == ["Search notes", "Get note standards", "Get note template"]
    assert all(tool.outputSchema is None for tool in tools)


def test_search_returns_readable_passages_with_citations(vault, commit):
    (vault / "keys.md").write_text(NOTE)
    commit()
    text = call("how often do we rotate keys")
    first = passages(text)[0]
    assert text.startswith("1 passage from the team's notes, best match first.")
    assert f"paths are relative to {config.ROOT}" in text
    assert first.startswith('<passage rank="1" source="notes/keys.md" section="Keys > Rotation">')
    assert "Rotate access keys every ninety days" in first and first.endswith("</passage>")


def test_the_text_is_not_escaped_or_duplicated_as_structured_data(vault, commit):
    (vault / "code.md").write_text(
        '# Code\n\n## Run\n\nRun it like this:\n\n```bash\necho "hello"  # a comment\n```\n'
    )
    commit()
    result = call_raw("how to run it")
    assert 'echo "hello"  # a comment' in result.content[0].text
    assert "\\n" not in result.content[0].text and result.structured_content is None


def test_quotes_in_a_path_or_heading_cannot_end_the_attribute_early(vault, commit):
    (vault / "odd.md").write_text('# "Quoted" & more\n\n## It\'s "here"\n\n' + "text here. " * 20)
    commit()
    first = passages(call("text here"))[0]
    assert "section=\"'Quoted' & more > It's 'here'\">" in first


def test_several_passages_come_best_first_with_ranks(vault, commit):
    for name in ("a", "b", "c"):
        (vault / f"{name}.md").write_text(NOTE.replace("Keys", f"Keys {name}"))
    commit()
    found = passages(call("rotate keys", k=3))
    assert [re.match(r'<passage rank="(\d)"', p).group(1) for p in found] == ["1", "2", "3"]


@pytest.mark.parametrize("k", [0, -5])
def test_k_below_one_still_returns_one_result(vault, commit, k):
    (vault / "keys.md").write_text(NOTE)
    commit()
    assert len(passages(call("rotate keys", k=k))) == 1


def test_k_is_capped(vault, commit):
    for i in range(config.MAX_RESULTS + 5):
        (vault / f"note-{i}.md").write_text(NOTE.replace("Keys", f"Keys {i}"))
    commit()
    assert len(passages(call("rotate keys", k=1000))) <= config.MAX_RESULTS


def test_an_empty_query_is_a_clear_tool_error(vault, commit):
    (vault / "keys.md").write_text(NOTE)
    commit()
    with pytest.raises(ToolError, match="empty"):
        call("   ")


def test_no_notes_is_a_clear_tool_error(vault, commit):
    commit()
    with pytest.raises(ToolError, match="No notes to search"):
        call("anything")


def call_tool(tool: str, **arguments) -> str:
    async def run():
        async with Client(mcp) as client:
            return (await client.call_tool(tool, arguments)).content[0].text

    return asyncio.run(run())


def test_an_agent_can_read_the_standards_and_the_templates(vault):
    (vault.parent / "STANDARDS.md").write_text("# Standards\n\nName notes in lowercase.\n")
    templates = vault.parent / "templates"
    templates.mkdir()
    (templates / "note-template.md").write_text("# {{title}}\n\nTags: #domain #type\n")
    (templates / "runbook-template.md").write_text("# {{title}}\n\n## Steps\n")
    standards = call_tool("get_note_standards")
    assert "Name notes in lowercase." in standards and "Templates: note, runbook" in standards
    assert call_tool("get_note_template", name="runbook") == "# {{title}}\n\n## Steps\n"
    assert call_tool("get_note_template").startswith("# {{title}}\n\nTags:")


def test_the_standards_say_exactly_where_to_create_a_note_and_that_it_is_not_on_main(vault):
    (vault.parent / "STANDARDS.md").write_text("# Standards\n")
    standards = call_tool("get_note_standards")
    assert f"Where notes live: {vault}" in standards
    assert f"at {vault}/<folder>/<file-name>.md" in standards
    assert "not the current directory" in standards and "new git branch, not on main" in standards


def test_an_unknown_template_or_a_path_trick_is_refused_with_the_choices(vault):
    templates = vault.parent / "templates"
    templates.mkdir()
    (templates / "note-template.md").write_text("# {{title}}\n")
    (vault.parent / "secret-template.md").write_text("private")
    for name in ("adr", "../secret", "../../etc/passwd"):
        with pytest.raises(ToolError, match="Available: note"):
            call_tool("get_note_template", name=name)


def test_a_repository_without_standards_says_so(vault):
    with pytest.raises(ToolError, match=r"no STANDARDS\.md"):
        call_tool("get_note_standards")


def test_a_repository_without_commits_is_a_clear_tool_error(vault):
    with pytest.raises(ToolError, match="No 'main' branch"):
        call("anything")
