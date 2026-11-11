"""Chunker tests: the behaviour that matters, then invariants that must hold for every kind of
Markdown (a catalogue of awkward notes and random mixes of them)."""

import random
import re
from collections import Counter

import pytest
from markdown_it import MarkdownIt

from rag.config import MAX_CHUNK_SIZE
from rag.index.chunker import chunk_markdown

WORDS = "word " * 70  # about 350 characters
PARAGRAPHS = "\n\n".join(f"Paragraph {i}. " + "word " * 50 for i in range(30))


def chunks(text: str, source: str = "notes/x.md"):
    return chunk_markdown(text, source)


def paths(text: str, source: str = "notes/x.md") -> list[str]:
    return [c.header_path for c in chunks(text, source)]


def all_text(text: str) -> str:
    return "\n".join(c.text for c in chunks(text))


# ---- headings -------------------------------------------------------------------------------


def test_header_paths_follow_the_heading_hierarchy():
    text = f"# T\n\n## A\n\n{WORDS}\n\n### A1\n\n{WORDS}\n\n## B\n\n{WORDS}"
    assert paths(text) == ["T > A", "T > A > A1", "T > B"]


def test_hash_comments_in_code_fences_are_not_headings():
    text = (
        f"# T\n\n## Real\n\n{WORDS}\n\n```bash\n# --- fake ---\necho hi\n```\n\n"
        f"## Second\n\n{WORDS}"
    )
    assert paths(text) == ["T > Real", "T > Second"]


def test_setext_headings_and_multiline_setext():
    assert "Title > Section" in paths(f"Title\n=====\n\nintro\n\nSection\n-------\n\n{WORDS}")
    assert paths(f"line one\nline two\n=====\n\n{WORDS}") == ["line one line two"]


def test_things_that_only_look_like_headings():
    text = (
        f"# T\n\n## A\n\n{WORDS}\n\n    # indented code\n\n> # quoted\n\n- # in a list\n\n"
        f"####### seven\n\n#NoSpace\n\n<!--\n# hidden\n-->\n\n## B\n\n{WORDS}"
    )
    assert paths(text) == ["T > A", "T > B"]


def test_heading_markup_is_dropped_from_the_path():
    text = f"# T\n\n## *Emph* [link](http://x) `code` ![img](a.png) &amp; Café ☕\n\n{WORDS}"
    assert paths(text) == ["T > Emph link code img & Café ☕"]


def test_indented_code_before_the_first_heading_is_kept():
    assert "# indented code" in all_text(f"    # indented code\n\n# T\n\n{WORDS}")


def test_a_small_start_of_a_long_section_is_not_joined_to_the_section_before():
    big_paragraph = "word " * 195  # fits alone, but not together with the small table
    table = "| a | b |\n|---|---|\n| 1 | 2 |"
    text = f"# T\n\n## Before\n\n{WORDS}\n\n## Long\n\n{table}\n\n{big_paragraph}"
    first_of_long = next(c for c in chunks(text) if "| 1 | 2 |" in c.text)
    assert first_of_long.header_path == "T > Long"


def test_notes_without_an_h1_use_the_filename():
    assert paths(f"## A\n\n{WORDS}", "notes/my-note.md") == ["My Note > A"]
    assert paths("just text\n", "notes/loose-note.md") == ["Loose Note"]
    assert paths("# \n\nSome text here.\n", "notes/my-note.md") == ["My Note"]


def test_skipped_heading_levels_and_duplicates_and_extra_h1():
    assert paths(f"# T\n\n### Deep\n\n{WORDS}\n\n## Back\n\n{WORDS}") == [
        "T > Deep",
        "T > Back",
    ]
    assert paths(f"# T\n\n## Same\n\n{WORDS}\n\n## Same\n\n{WORDS}") == [
        "T > Same",
        "T > Same",
    ]
    assert paths(f"# One\n\n{WORDS}\n\n# Two\n\n{WORDS}") == ["One", "Two"]


def test_text_before_the_first_heading_is_kept():
    result = chunks(f"Intro paragraph. {WORDS}\n\n# T\n\n{WORDS}")
    assert "Intro paragraph." in result[0].text and result[0].header_path == "T"
    assert "Intro" in all_text("Intro text\n\n# T\n\nbody here\n")


def test_empty_and_tiny_notes():
    assert chunks("") == [] and chunks("\n\n") == [] and chunks(" \n\t\n") == []
    assert chunks("# Only a title") == []
    assert chunks("Only a title\n============\n") == []
    assert chunks("line one\nline two\n--------\n") == []
    assert chunks("# Only\u2028a title") == []
    assert chunks("Only\u2028a title\n============\n") == []
    assert chunks("# A\n\n## B\n\n### C\n") == []
    tiny = chunks("# Tiny\n\nA short note.\n")
    assert len(tiny) == 1 and "short note" in tiny[0].text
    assert len(chunks("x")) == 1 and len(chunks("# Tiny\n\nx")) == 1


# ---- frontmatter, line endings, encoding -----------------------------------------------------


def test_frontmatter_is_excluded():
    text = f"---\ntitle: X\ntags:\n  - a\n---\n\n# T\n\n{WORDS}"
    assert "title:" not in all_text(text) and paths(text) == ["T"]
    assert "title:" not in all_text(f"---\ntitle: X\n...\n\n# T\n\n{WORDS}")
    assert "k: v" not in all_text(f"---\n# a yaml comment\nk: v\n---\n# T\n\n{WORDS}")


def test_things_that_only_look_like_frontmatter_are_kept():
    assert "title: X" in all_text(f"---\ntitle: X\n\n# T\n\n{WORDS}")  # never closed
    assert "---" in all_text(f"# T\n\n{WORDS}\n\n---\n\n{WORDS}")  # a rule mid-note


# ---- code blocks -----------------------------------------------------------------------------


def test_oversized_code_block_is_cut_between_lines_and_loses_nothing():
    lines = [f"echo line {i} " + "x" * 40 for i in range(120)]
    result = chunks("# T\n\n## Run\n\n```bash\n" + "\n".join(lines) + "\n```\n")
    assert len(result) > 1 and all(len(c.text) <= MAX_CHUNK_SIZE for c in result)
    joined = "\n".join(c.text for c in result)
    assert all(line in joined for line in lines)


# ---- tables, lists, quotes and other blocks ---------------------------------------------------


def test_long_list_and_quote_are_split_between_items():
    lst = "\n".join(f"- item {i} " + "word " * 12 for i in range(60))
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in chunks(f"# T\n\n## A\n\n{lst}"))
    quote = "\n".join("> quoted line " + "word " * 10 for _ in range(60))
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in chunks(f"# T\n\n{quote}"))


def test_link_definitions_survive_splitting():
    text = (
        f"# T\n\n## Big\n\n{PARAGRAPHS}\n\n[1]: https://example.com/a\n[2]: https://example.com/b\n"
    )
    assert "[1]: https://example.com/a" in all_text(text)
    assert "[2]: https://example.com/b" in all_text(text)


# ---- skipped sections ------------------------------------------------------------------------


def test_references_and_table_of_contents_are_skipped_with_their_subsections():
    text = (
        f"# T\n\n## Body\n\n{WORDS}\n\n## References\n\n- l\n\n### Sub\n\n{WORDS}\n\n"
        f"## After\n\n{WORDS}"
    )
    assert paths(text) == ["T > Body", "T > After"]
    assert paths(f"# T\n\n## body\n\n{WORDS}\n\n## REFERENCES\n\n{WORDS}") == ["T > body"]
    assert paths(f"# T\n\n## Table of Contents\n\n- [a](#a)\n\n## Body\n\n{WORDS}") == ["T > Body"]
    assert chunks("# T\n\n## References\n\n- a\n") == []


# ---- sizes and splitting ---------------------------------------------------------------------


def test_oversized_prose_is_split_between_paragraphs():
    result = [c for c in chunks(f"# T\n\n## Big\n\n{PARAGRAPHS}") if c.header_path == "T > Big"]
    assert len(result) > 1
    assert all(len(c.text) <= MAX_CHUNK_SIZE and c.text.count("Paragraph") for c in result)


def test_unbreakable_long_text_is_cut():
    for text in (
        "x" * MAX_CHUNK_SIZE * 3,
        "see http://e.com/" + "a" * MAX_CHUNK_SIZE * 2,
    ):
        result = chunks(f"# T\n\n## A\n\n{text}")
        assert len(result) > 1 and all(len(c.text) <= MAX_CHUNK_SIZE for c in result)


def test_splitting_keeps_repeated_words_in_order():
    body = "alpha beta alpha gamma " * 300
    result = chunks("# Title\n\n## Body\n\n" + body)
    returned = "\n".join(chunk.text for chunk in result).replace("## Body", "")
    assert returned.split() == body.split()


def test_very_long_headings_are_not_repeated_but_still_fit():
    result = chunks("word " * 400 + "\nSetext\n======\n\n" + "word " * 300)
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in result)
    result = chunks(
        "# T\n\n```" + "x" * 900 + "\n" + "\n".join("y" * 80 for _ in range(60)) + "\n```"
    )
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in result)


def test_tiny_sections_remain_independent_and_bounded():
    text = "# T\n\n" + "\n".join(f"## S{i}\n\nok {i} " + "w " * 30 + "\n" for i in range(40))
    result = chunks(text)
    assert len(result) == 40 and all(len(c.text) <= MAX_CHUNK_SIZE for c in result)
    assert all(f"ok {i} " in "\n".join(c.text for c in result) for i in range(40))
    assert len(chunks("# T\n\n" + "\n".join(f"## S{i}\n\nok {i}\n" for i in range(40)))) == 40


FULL = "word " * 198  # no room left for another section in the same passage


def test_a_tiny_sibling_keeps_its_own_path_even_with_spare_space():
    result = chunks(f"# T\n\n## A\n\n{WORDS}\n\n## Tiny\n\nok\n\n## B\n\n{WORDS}")
    assert [c.header_path for c in result] == ["T > A", "T > Tiny", "T > B"]
    assert result[1].text == "## Tiny\n\nok"


def test_a_tiny_section_does_not_join_forward_either():
    result = chunks(f"# T\n\n## A\n\n{FULL}\n\n## Tiny\n\nok\n\n## B\n\n{WORDS}")
    assert [c.header_path for c in result] == ["T > A", "T > Tiny", "T > B"]


def test_a_tiny_section_that_cannot_join_is_its_own_passage():
    result = chunks(f"# T\n\n## A\n\n{FULL}\n\n## Tiny\n\nok\n\n## B\n\n{FULL}")
    assert [c.header_path for c in result] == ["T > A", "T > Tiny", "T > B"]


@pytest.mark.parametrize("separator", ["\n", "\n\n"])
def test_description_context_stops_before_metadata_and_is_embedded_with_each_chunk(separator):
    description = "Rotate IAM keys without interrupting workloads."
    result = chunks(
        f"# Keys\n\n{description}{separator}Links:\nTags: #aws\n\n"
        "Reading instructions.\n\n## Steps\n\nCreate a key."
    )
    assert len(result) == 2 and all(c.context == description for c in result)
    assert result[1].embedding_text == (
        f"Section: Keys > Steps\n\nContext: {description}\n\n## Steps\n\nCreate a key."
    )
    assert all("Tags:" not in c.embedding_text for c in result)


def test_parent_and_tiny_child_remain_separate():
    result = chunks("# Keys\n\n## Steps\n\nCreate.\n\n### Verify\n\nCheck.")
    assert [c.header_path for c in result] == ["Keys > Steps", "Keys > Steps > Verify"]
    assert result[0].text == "## Steps\n\nCreate."
    assert result[1].text == "### Verify\n\nCheck."


def test_repeated_heading_names_do_not_merge():
    result = chunks("# Keys\n\n## Steps\n\nFirst.\n\n## Steps\n\nSecond.")
    assert result[0].header_path == result[1].header_path
    assert [c.text for c in result] == ["## Steps\n\nFirst.", "## Steps\n\nSecond."]


def test_metadata_and_skipped_sections_are_not_answer_chunks_or_context():
    result = chunks(
        "---\ntype: example\n---\n# Keys\n\n  Tags: #aws\n\n---\n\n"
        "## Steps\n\nCreate.\n\n## References\n\nExcluded.\n\n### Child\n\nExcluded too."
    )
    assert len(result) == 1 and result[0].tags == ["aws"]
    assert "Tags:" not in result[0].embedding_text
    assert result[0].context == ""
    assert all(word not in result[0].text for word in ("Tags:", "Excluded", "type:"))


def test_tags_are_normalized_lists_without_changing_prose_or_code():
    result = chunks(
        "# Keys\n\nRotate IAM keys.\n\nTags: #AWS #runbook #aws #aws/iam\n"
        "tags: #runbook #key-rotation\n\n## Steps\n\nCreate a key.\n\n"
        "```text\nTags: #example-only\n```\n"
    )
    assert result and all(c.tags == ["aws", "runbook", "aws/iam", "key-rotation"] for c in result)
    assert all("Tags: #AWS" not in c.embedding_text for c in result)
    assert "Tags: #example-only" in result[-1].text
    assert result[-1].context == "Rotate IAM keys."
    assert all(c.tags == [] for c in chunks("# Keys\n\n## Steps\n\nCreate a key."))


@pytest.mark.parametrize("first", ["Links:", "Tags: #aws"])
def test_context_never_uses_instructions_after_metadata_or_a_summary_section(first):
    result = chunks(f"# Keys\n\n{first}\n\nRun these instructions.\n\n## Summary\n\nDetails.")
    assert result and all(c.context == "" for c in result)
    assert all(c.context == "" for c in chunks("## Summary\n\nNo title description."))


def test_description_context_is_bounded():
    description = "Rotate IAM keys without interrupting workloads. " * 20
    result = chunks(f"# Keys\n\n{description}\n\n## Steps\n\nCreate.")
    assert all(0 < len(c.context) <= 400 and description.startswith(c.context) for c in result)


@pytest.mark.parametrize("description", ["", "x", "Rotate IAM keys."])
def test_context_has_no_minimum_length(description):
    result = chunks(f"# Keys\n\n{description}\n\nLinks:\nTags: #aws\n\n## Steps\n\nCreate.")
    assert result and all(c.context == description for c in result)
    if not description:
        assert all(c.embedding_text == f"Section: {c.header_path}\n\n{c.text}" for c in result)


def test_oversized_fences_and_tables_repeat_their_structural_wrappers():
    code = "```sh\n" + "\n".join(f"echo row-{i}" for i in range(250)) + "\n```"
    result = chunks("# Keys\n\n" + code)
    assert len(result) > 1
    assert all(c.text.startswith("```sh\n") and c.text.endswith("\n```") for c in result)
    header = "| setting | value |\n| --- | --- |"
    table = header + "\n" + "\n".join(f"| setting-{i} | {i} seconds |" for i in range(150))
    result = chunks("# Keys\n\n" + table)
    assert len(result) > 1 and all(header in c.text for c in result)


# ---- bugs found by fuzzing real-world documents (each one has a test) ----------------------------


def test_a_paragraph_that_became_a_heading_stays_in_the_text_and_not_in_the_path():
    paragraph = " ".join(f"sentence number {i} says something useful." for i in range(12))
    result = chunks(f"# T\n\n{paragraph}\n---\n\nAfter it. " + "word " * 40)
    assert all(len(c.header_path) < 200 for c in result)
    assert "sentence number 11 says something useful." in "\n".join(c.text for c in result)


def test_a_long_fence_info_string_is_kept_as_text():
    info = " ".join(f"word{i}" for i in range(80))
    body = "\n".join(f"echo {i} " + "x" * 40 for i in range(40))
    text = f"# T\n\n```{info}\n{body}\n```\n"
    assert "word79" in all_text(text)
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in chunks(text))


# ---- invariants for every kind of note --------------------------------------------------------


def check_invariants(text: str) -> None:
    result = chunks(text)
    normal = text.replace("\r\n", "\n").replace("\r", "\n")
    assert [c.chunk_index for c in result] == list(range(len(result)))
    for chunk in result:
        assert chunk.text.strip() and chunk.header_path.strip()
        assert chunk.text == chunk.text.rstrip()
        assert len(chunk.text) <= MAX_CHUNK_SIZE, f"{len(chunk.text)} characters"
        assert "\r" not in chunk.text
    if result and not re.search(
        r"^ {0,3}(?:#{1,6}[ \t]*)?(References|Table of Contents|TOC)[ \t]*#*[ \t]*$"
        r"|^ {0,3}(?:References|Table of Contents|TOC)[ \t]*\n {0,3}(?:=+|-+)[ \t]*$",
        re.sub(r"[*_`~]|<[^>\n]*>", "", normal),  # markup in a heading is not part of its text
        re.IGNORECASE | re.MULTILINE,
    ):
        assert_no_text_lost(
            normal,
            "\n".join(
                c.embedding_text + "\nTags: " + " ".join("#" + tag for tag in c.tags)
                for c in result
            ),
        )


def assert_no_text_lost(source: str, chunked: str) -> None:
    body = re.sub(
        r"\A---[ \t]*\n(?=[^\n]*:|[ \t]*#).*?\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)",
        "",
        source,
        flags=re.DOTALL,
    )
    lines = body.split("\n")
    for token in MarkdownIt("commonmark").parse(body):
        if token.type == "heading_open" and not token.level and token.map:
            start, end = token.map
            lines[start:end] = [""] * (end - start)  # headings are metadata, not body content
    body = "\n".join(lines)
    words = re.findall(r"\S+", chunked)
    kept, normalized = Counter(words), Counter(bare(word) for word in words)
    flat = re.sub(r"\s+", "", chunked)
    for word, count in Counter(re.findall(r"\S+", body)).items():
        if not bare(word) or re.fullmatch(r"[=\-]+", word):  # only syntax: rules, fence markers
            continue
        if len(word) <= 200:
            assert max(kept[word], normalized[bare(word)]) >= count, f"lost {word[:40]!r}"
        else:  # very long words may be cut, so check their ends
            squeezed = re.sub(r"\s+", "", word)
            assert squeezed[:50] in flat and squeezed[-50:] in flat, f"lost {word[:40]!r}"


def bare(word: str) -> str:
    """The word without quote marks, fence markers and emphasis, which headings and fence
    openers drop (their text is kept, their markup is not)."""
    return re.sub(r"^[>\s]*(?:`{3,}|~{3,})|[`*_~\\]", "", word.strip("> "))


FENCED_LIST = (
    "- step\n\n  ```bash\n" + "\n".join(f"  echo {i} " + "x" * 30 for i in range(80)) + "\n  ```\n"
)
CATALOGUE = {
    "atx closing hashes": f"# T\n\n## Title ##\n\n{WORDS}",
    "heading with markup": f"# T\n\n## *a* [b](http://x) `c` ![d](e.png) <b>f</b> &amp;\n\n{WORDS}",
    "empty headings": f"# \n\n## \n\n{WORDS}",
    "setext": f"Line one\nline two\n=========\n\n{WORDS}\n\nSub\n---\n\n{WORDS}",
    "heading in list and quote": f"# T\n\n- # no\n\n> # no\n\n{WORDS}",
    "h2 first": f"## A\n\n{WORDS}\n\n## B\n\n{WORDS}",
    "text before heading": f"Intro. {WORDS}\n\n# T\n\n{WORDS}",
    "only headings": "# A\n\n## B\n\n### C\n",
    "frontmatter": f"---\ntitle: X\ntags:\n  - a\n---\n\n# T\n\n{WORDS}",
    "frontmatter unterminated": f"---\ntitle: X\n\n# T\n\n{WORDS}",
    "frontmatter crlf": f"---\r\ntitle: X\r\n---\r\n# T\r\n\r\n{WORDS}\r\n",
    "rule mid note": f"# T\n\n{WORDS}\n\n---\n\n{WORDS}",
    "setext dashes": f"# T\n\nSome text\n---\n\n{WORDS}",
    "tilde fence": f"# T\n\n~~~python\n# comment\nx = 1\n~~~\n\n{WORDS}",
    "nested fences": f"# T\n\n````md\n```\n# in\n```\n````\n\n{WORDS}",
    "unclosed fence": "# T\n\n```bash\n# never closed\necho 1\n\n## Not a heading\n",
    "fence in list": f"# T\n\n- one\n\n  ```bash\n  # c\n  echo hi\n  ```\n\n{WORDS}",
    "fence in quote": f"# T\n\n> ```\n> # quoted\n> ```\n\n{WORDS}",
    "indented code": f"# T\n\n    # indented code\n\n{WORDS}",
    "fence info attributes": f'# T\n\n```bash {{title="x"}}\n# c\n```\n\n{WORDS}',
    "table": f"# T\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n{WORDS}",
    "nested lists": f"# T\n\n- a\n  - b\n    - c\n\n{WORDS}",
    "callout": f"# T\n\n> [!NOTE]\n> text {WORDS}\n\n{WORDS}",
    "html block": (
        f"# T\n\n<details>\n<summary># x</summary>\n\nbody {WORDS}\n</details>\n\n{WORDS}"
    ),
    "math": f"# T\n\n$$\n# x\n$$\n\n{WORDS}",
    "footnotes": f"# T\n\nText[^1] and [ref].\n\n[^1]: note\n[ref]: http://x\n\n{WORDS}",
    "obsidian": f"# T\n\n![[a.png]] [[B|c]] #tag ^id %%x%%\n\n{WORDS}",
    "huge paragraph": f"# T\n\n{'word ' * 2000}",
    "huge table": "# T\n\n| a | b |\n|---|---|\n"
    + "\n".join(f"| r{i} | {'x' * 60} |" for i in range(60)),
    "huge list": "# T\n\n" + "\n".join(f"- item {i} " + "word " * 12 for i in range(60)),
    "huge list with fence": f"# T\n\n{FENCED_LIST}",
    "huge quote": "# T\n\n" + "\n".join("> quoted " + "word " * 10 for _ in range(60)),
    "huge fence": "# T\n\n```bash\n"
    + "\n".join(f"echo {i} " + "x" * 40 for i in range(100))
    + "\n```\n",
    "fence line longer than limit": "# T\n\n```\n" + "y" * MAX_CHUNK_SIZE * 2 + "\n```\n",
    "many tiny sections": "# T\n\n" + "\n".join(f"## S{i}\n\nok {i}\n" for i in range(40)),
    "references": (
        f"# T\n\n## Body\n\n{WORDS}\n\n## References\n\n- l\n\n### Sub\n\n{WORDS}\n\n"
        f"## After\n\n{WORDS}"
    ),
    "crlf": f"# T\r\n\r\n## A\r\n\r\n{WORDS}\r\n",
    "cr only": f"# T\r\r## A\r\r{WORDS}\r",
    "mixed endings": f"# T\n\r\n## A\r\n\n{WORDS}\r\n",
    "tabs and trailing spaces": f"# T  \n\n## A\t\n\n{WORDS}  \n",
    "control characters": f"# T\n\nbad \x00 \x0b \x0c \x1f {WORDS}",
    "unicode separators": f"# T\n\nline\u2028sep\u2029para {WORDS}",
    "rtl and combining": f"# T\n\n## مرحبا\n\n{WORDS} e\u0301",
    "many headings": "\n".join(
        f"{'#' * (1 + i % 6)} H{i}\n\ntext {i} " + "w " * 40 for i in range(300)
    ),
    "empty": "",
    "whitespace": " \n\t\n  \n",
    "single character": "x",
    "only a hash": "#",
}


@pytest.mark.parametrize("name", list(CATALOGUE))
def test_catalogue_invariants(name):
    check_invariants(CATALOGUE[name])


def test_random_combinations_keep_every_invariant():
    rng = random.Random(2024)
    pieces = [text for text in CATALOGUE.values() if text]
    for _ in range(200):
        check_invariants("\n\n".join(rng.choice(pieces) for _ in range(rng.randint(1, 6))))
