"""Chunker tests: exact behaviour of the important cases, then invariants that must hold for
every kind of Markdown (a catalogue of awkward notes plus seeded random ones)."""

import random
import re
from pathlib import Path

import pytest

from rag.chunker import chunk_markdown
from rag.config import MAX_CHUNK_SIZE

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


def test_tilde_and_nested_fences():
    text = (
        f"# T\n\n## A\n\n{WORDS}\n\n~~~\n# no\n~~~\n\n"
        f"````md\n```\n# nested\n```\n````\n\n## B\n\n{WORDS}"
    )
    assert paths(text) == ["T > A", "T > B"]


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


def test_closing_hashes_and_light_indentation_are_headings():
    assert paths(f"# T\n\n## Title ##\n\n{WORDS}") == ["T > Title"]
    assert paths(f"# T\n\n   ## Indented\n\n{WORDS}") == ["T > Indented"]


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
    assert "just text" in all_text("---\njust text\n---\n\n# T\n\nbody\n")  # not key: value
    assert "title: X" in all_text(f"---\ntitle: X\n\n# T\n\n{WORDS}")  # never closed
    assert "---" in all_text(f"# T\n\n{WORDS}\n\n---\n\n{WORDS}")  # a rule mid-note


def test_frontmatter_only_note_is_empty():
    assert chunks("---\ntitle: X\n---\n") == []


def test_line_endings_are_normalised():
    for newline in ("\r\n", "\r"):
        text = f"# T{newline}{newline}## A{newline}{newline}{WORDS}{newline}"
        assert paths(text) == ["T > A"] and "\r" not in all_text(text)
    assert "T > A" in paths(f"---\r\ntitle: X\r\n---\r\n# T\r\n\r\n## A\r\n\r\n{WORDS}\r\n")


def test_awkward_characters_do_not_break_anything():
    text = f"# T\n\n## A\n\nbad \x00 char \x0b \x0c \x1f \u2028 \u2029 مرحبا e\u0301 🚀 {WORDS}"
    assert paths(text) == ["T > A"]


# ---- code blocks -----------------------------------------------------------------------------


def test_oversized_code_block_is_cut_into_valid_fenced_pieces():
    lines = [f"echo line {i} " + "x" * 40 for i in range(120)]
    result = chunks("# T\n\n## Run\n\n```bash\n" + "\n".join(lines) + "\n```\n")
    assert len(result) > 1
    for chunk in result:
        assert chunk.text.count("```") % 2 == 0 and len(chunk.text) <= MAX_CHUNK_SIZE
        assert "```bash" in chunk.text  # every piece keeps the language
    joined = "\n".join(c.text for c in result)
    assert all(line in joined for line in lines)


def test_code_block_inside_a_long_list_is_never_cut_open():
    code = "\n".join(f"  echo line {i} " + "x" * 30 for i in range(80))
    text = f"# T\n\n## A\n\n- first\n\n  ```bash\n{code}\n  ```\n\n- second\n"
    result = chunks(text)
    assert len(result) > 1
    for chunk in result:
        assert len(re.findall(r"^\s*```", chunk.text, re.MULTILINE)) % 2 == 0


def test_code_block_inside_a_quote_is_cut_with_its_quote_marks():
    code = "\n".join(f"> echo {i} " + "x" * 40 for i in range(80))
    result = chunks(f"# T\n\n> ```bash\n{code}\n> ```\n")
    assert len(result) > 1
    assert all(c.text.count("```") % 2 == 0 for c in result)


def test_unclosed_fence_runs_to_the_end_of_the_note():
    text = "# T\n\n## A\n\n```bash\n# never closed\necho 1\n\n## Not a heading\n"
    assert paths(text) == ["T > A"] and "Not a heading" in all_text(text)


def test_inline_code_and_indented_code_are_plain_text():
    assert paths(f"# T\n\nUse `# not heading` and ``a ` b`` here. {WORDS}") == ["T"]


# ---- tables, lists, quotes and other blocks ---------------------------------------------------


def test_long_table_repeats_its_header_row_in_every_chunk():
    rows = "\n".join(f"| row {i} | " + "x" * 60 + " |" for i in range(60))
    result = chunks(f"# T\n\n## A\n\n| name | value |\n|---|---|\n{rows}")
    assert len(result) > 1
    assert all("| name | value |" in c.text for c in result)
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in result)


def test_table_with_a_very_wide_header_still_terminates():
    header = "| " + " | ".join(f"column-{i}" for i in range(150)) + " |\n|" + "---|" * 150
    rows = "\n".join("| " + " | ".join("x" for _ in range(150)) + " |" for _ in range(30))
    result = chunks(f"# T\n\n## A\n\n{header}\n{rows}")
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in result)


def test_deeply_indented_code_block_terminates():
    code = "\n".join(" " * 300 + f"line {i} " + "y" * 30 for i in range(60))
    fence = " " * 300 + "```"
    result = chunks(f"# T\n\n## A\n\n{fence}\n{code}\n{fence}\n")
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in result)


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


def test_obsidian_syntax_is_kept_as_text():
    text = f"# T\n\n![[image.png]] and [[Note|alias]] #tag ^block-id %%comment%%\n\n{WORDS}"
    body = all_text(text)
    assert "![[image.png]]" in body and "[[Note|alias]]" in body and "#tag" in body


def test_html_blocks_and_comments_do_not_create_headings():
    text = (
        "# T\n\n<details>\n<summary># Not heading</summary>\n\n"
        f"body {WORDS}\n</details>\n\n<!--\n## hidden\n-->\n\n{WORDS}"
    )
    assert paths(text) == ["T"]


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


def test_section_exactly_at_the_limit_is_not_split():
    header = "## A\n\n"
    body = "x" * (MAX_CHUNK_SIZE - len(header))
    assert len(chunks(f"# T\n\n{header}{body}")) == 1
    assert len(chunks(f"# T\n\n{header}{body}x")) == 2


def test_oversized_prose_is_split_and_repeats_its_heading():
    result = [c for c in chunks(f"# T\n\n## Big\n\n{PARAGRAPHS}") if c.header_path == "T > Big"]
    assert len(result) > 1
    assert all(len(c.text) <= MAX_CHUNK_SIZE and c.text.startswith("## Big") for c in result)


def test_unbreakable_long_text_is_cut():
    for text in (
        "x" * MAX_CHUNK_SIZE * 3,
        "see http://e.com/" + "a" * MAX_CHUNK_SIZE * 2,
    ):
        result = chunks(f"# T\n\n## A\n\n{text}")
        assert len(result) > 1 and all(len(c.text) <= MAX_CHUNK_SIZE for c in result)


def test_very_long_headings_are_not_repeated_but_still_fit():
    result = chunks("word " * 400 + "\nSetext\n======\n\n" + "word " * 300)
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in result)
    result = chunks(
        "# T\n\n```" + "x" * 900 + "\n" + "\n".join("y" * 80 for _ in range(60)) + "\n```"
    )
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in result)


def test_tiny_sections_are_merged_but_never_past_the_limit():
    text = "# T\n\n" + "\n".join(f"## S{i}\n\nok {i} " + "w " * 30 + "\n" for i in range(40))
    result = chunks(text)
    assert 1 < len(result) < 40 and all(len(c.text) <= MAX_CHUNK_SIZE for c in result)
    assert all(f"ok {i} " in "\n".join(c.text for c in result) for i in range(40))
    assert len(chunks("# T\n\n" + "\n".join(f"## S{i}\n\nok {i}\n" for i in range(40)))) == 1


def test_chunks_are_numbered_in_reading_order_and_deterministic():
    result = chunks(f"# T\n\n## A\n\n{WORDS}\n\n## B\n\n{WORDS}", "notes/x.md")
    assert [c.chunk_index for c in result] == [0, 1]
    assert chunks(f"# T\n\n## A\n\n{WORDS}") == chunks(f"# T\n\n## A\n\n{WORDS}")


# ---- bugs found by fuzzing real-world documents (each one has a test) ----------------------------


def test_an_indented_hash_line_before_any_heading_is_text_not_a_heading():
    text = "     # sample of the metric output\n\n   # Real heading\n\nbody " * 3
    assert "sample of the metric output" in all_text(text)


def test_a_line_that_only_starts_like_a_closing_fence_is_content():
    text = "# T\n\n```\n" + "\n".join(f"line {i} " + "x" * 40 for i in range(40)) + "\n```text\n"
    assert "```text" in all_text(text)


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


def test_a_tiny_title_section_is_folded_into_the_next_one_not_left_alone():
    text = "# T\n\nTags: #a\n\n## S\n\n" + "content sentence here. " * 10
    result = chunks(text)
    assert len(result) == 1 and "Tags: #a" in result[0].text


# ---- invariants for every kind of note --------------------------------------------------------

FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def fences_balanced(text: str) -> bool:
    """Whether every code fence opened in `text` is also closed."""
    opened = None
    for line in text.split("\n"):
        match = FENCE_LINE.match(line.lstrip(" >"))
        if not match:
            continue
        marker = match.group(1)
        if opened is None:
            opened = marker
        elif marker[0] == opened[0] and len(marker) >= len(opened) and line.strip(" >") == marker:
            opened = None
    return opened is None


def check_invariants(text: str, fences: bool = True) -> None:
    """`fences=False` skips the code-fence balance check, which this file's simple fence scanner
    cannot judge once an HTML block or random lines decide what is a fence."""
    result = chunks(text)
    normal = text.replace("\r\n", "\n").replace("\r", "\n")
    assert [c.chunk_index for c in result] == list(range(len(result)))
    for chunk in result:
        assert chunk.text.strip() and chunk.header_path.strip()
        assert len(chunk.text) <= MAX_CHUNK_SIZE, f"{len(chunk.text)} characters"
        assert "\r" not in chunk.text
        if fences and fences_balanced(normal):
            assert fences_balanced(chunk.text), chunk.text[:80]
    if result and not re.search(
        r"^ {0,3}(?:#{1,6}[ \t]*)?(References|Table of Contents|TOC)[ \t]*#*[ \t]*$"
        r"|^ {0,3}(?:References|Table of Contents|TOC)[ \t]*\n {0,3}(?:=+|-+)[ \t]*$",
        re.sub(r"[*_`~]|<[^>\n]*>", "", normal),  # markup in a heading is not part of its text
        re.IGNORECASE | re.MULTILINE,
    ):
        assert_no_text_lost(normal, "\n".join(f"{c.header_path}\n{c.text}" for c in result))


def assert_no_text_lost(source: str, chunked: str) -> None:
    body = re.sub(
        r"\A---[ \t]*\n(?=[^\n]*:|[ \t]*#).*?\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)",
        "",
        source,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"^ {0,3}#{1,6}(?:\s.*)?$", "", body, flags=re.MULTILINE
    )  # carried by header_path (as is a setext heading's text, which the path is searched for)
    body = re.sub(r"^[=\-]+\s*$", "", body, flags=re.MULTILINE)
    kept, flat = set(re.findall(r"\S+", chunked)), re.sub(r"\s+", "", chunked)
    kept |= {bare(word) for word in kept}
    for word in set(re.findall(r"\S+", body)):
        if not bare(word) or re.fullmatch(r"[=\-]+", word):  # only syntax: rules, fence markers
            continue
        if len(word) <= 200:
            assert word in kept or bare(word) in kept, f"lost {word[:40]!r}"
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
    for _ in range(600):
        check_invariants("\n\n".join(rng.choice(pieces) for _ in range(rng.randint(1, 6))))


def test_random_line_noise_keeps_every_invariant():
    rng = random.Random(7)
    atoms = [
        "# H",
        "## H",
        "```",
        "~~~",
        "> ",
        "- ",
        "1. ",
        "| a | b |",
        "|---|---|",
        "---",
        "===",
        "",
        "text " * 30,
    ]
    for _ in range(600):
        check_invariants(
            "\n".join(
                rng.choice(atoms) + rng.choice(["", " x", " word " * 9])
                for _ in range(rng.randint(1, 40))
            )
        )


def test_real_notes_chunk_cleanly():
    for path in Path("notes").glob("**/*.md"):
        check_invariants(path.read_text(encoding="utf-8-sig"))
        assert chunks(path.read_text(encoding="utf-8-sig"), str(path)), path
