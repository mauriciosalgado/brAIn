"""The chunker on realistic documents: a 70-note team vault (runbooks, ADRs, post-mortems,
handbooks) and a set of deliberately messy notes of the kind teams paste into Obsidian. Every file
must satisfy the same guarantees, however it is cut, re-encoded or shuffled."""

import random
import re
import statistics
from pathlib import Path

import pytest
from test_chunker import check_invariants

from rag.chunker import _body_len, chunk_markdown
from rag.config import MAX_CHUNK_SIZE, MIN_CHUNK_SIZE, SKIP_HEADERS

FIXTURES = Path(__file__).parent / "fixtures"
TEAM_NOTES = sorted((FIXTURES / "team-vault" / "notes").glob("**/*.md"))
MESSY_NOTES = sorted((FIXTURES / "messy").glob("*.md"))
ALL_NOTES = TEAM_NOTES + MESSY_NOTES
IDS = [str(p.relative_to(FIXTURES)) for p in ALL_NOTES]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def messy(name: str) -> str:
    return read(FIXTURES / "messy" / f"{name}.md")


def chunks_of(path: Path):
    return chunk_markdown(read(path), str(path))


def blob(chunks) -> str:
    return "\n".join(f"{c.header_path}\n{c.text}" for c in chunks)


def squash(text: str) -> str:
    """Letters and digits only, lowercase: so heading markup and spacing do not matter."""
    return re.sub(r"[\W_]+", "", text).lower()


# ---- an independent reading of the headings (does not share code with the chunker) ----------


def headings_in(text: str, with_body: bool = False) -> list[tuple[int, str]]:
    """(level, name) of the ATX and setext headings outside code fences, skipping the sections
    under References and Table of Contents, as a person reading the note would find them. With
    `with_body`, only the headings that have some text of their own before the next heading."""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[0].startswith("---"):  # frontmatter
        end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() in ("---", "...")), 0)
        lines = [""] * (end + 1) + lines[end + 1 :]
    found, fence = [], None  # (level, name, first line, first line after the heading)
    for i, line in enumerate(lines):
        stripped = line.strip(" >\t")
        marker = re.match(r"(`{3,}|~{3,})", stripped)
        if fence:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
            continue
        if marker:
            fence = marker.group(1)
            continue
        atx = re.match(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$", line)
        if atx and atx.group(2).strip("# \t"):
            found.append((len(atx.group(1)), atx.group(2), i, i + 1))
        elif i and re.match(r"^ {0,3}(=+|-+)[ \t]*$", line) and lines[i - 1].strip():
            above = lines[i - 1]
            if not re.match(r"^\s*([-*+]|\d+[.)])\s", above) and "|" not in above:
                level = 1 if line.strip()[0] == "=" else 2
                found.append((level, above.strip(), i - 1, i + 1))
    starts = [start for _, _, start, _ in found] + [len(lines)]
    kept = []
    for n, (level, name, _, body_start) in enumerate(found):
        has_body = any(line.strip() for line in lines[body_start : starts[n + 1]])
        kept.append((level, name, has_body))
    return [(lv, name) for lv, name, body in drop_skipped(kept) if body or not with_body]


def drop_skipped(found: list[tuple[int, str, bool]]) -> list[tuple[int, str, bool]]:
    skip = {name.lower() for name in SKIP_HEADERS}
    kept, below = [], None
    for level, name, body in found:
        if below is not None and level > below:
            continue
        below = level if name.strip().lower() in skip else None
        if below is None:
            kept.append((level, name, body))
    return kept


# ---- every document ----------------------------------------------------------------------------


@pytest.mark.parametrize("path", ALL_NOTES, ids=IDS)
def test_every_document_keeps_every_invariant(path):
    check_invariants(read(path))


@pytest.mark.parametrize("path", ALL_NOTES, ids=IDS)
def test_every_heading_with_a_name_can_still_be_found(path):
    """A heading is in the path or the text of some chunk, even if its section was merged."""
    where = squash(blob(chunks_of(path)))
    for _, name in headings_in(read(path), with_body=True):
        if squash(name):
            assert squash(name) in where, f"heading {name!r} is gone"


@pytest.mark.parametrize("path", ALL_NOTES, ids=IDS)
def test_every_path_is_made_of_real_headings(path):
    """A chunk's path names headings that exist in the note, or its title: never invented text."""
    real = {squash(name) for _, name in headings_in(read(path))}
    first = chunks_of(path)[0].header_path.split(" > ")[0] if chunks_of(path) else ""
    for chunk in chunks_of(path):
        for part in chunk.header_path.split(" > "):
            assert squash(part) in real | {squash(first), ""}, f"{part!r} is not a heading"


@pytest.mark.parametrize("path", ALL_NOTES, ids=IDS)
def test_line_endings_and_trailing_spaces_change_nothing(path):
    text = read(path)
    plain = [(c.header_path, c.text) for c in chunk_markdown(text, "n.md")]
    for variant in (text.replace("\n", "\r\n"), text.replace("\n", "\r")):
        assert [(c.header_path, c.text) for c in chunk_markdown(variant, "n.md")] == plain
    padded = chunk_markdown(text.replace("\n", "  \n"), "n.md")
    assert len(padded) == len(plain)  # the same cuts, whatever the spaces at line ends


@pytest.mark.parametrize("path", ALL_NOTES, ids=IDS)
def test_chunking_twice_gives_the_same_result(path):
    assert chunks_of(path) == chunks_of(path)


@pytest.mark.parametrize("path", MESSY_NOTES, ids=[p.name for p in MESSY_NOTES])
def test_a_note_cut_off_at_any_line_still_keeps_every_invariant(path):
    """An editor can save at any moment: a note ending inside a fence or table is still fine."""
    lines = read(path).split("\n")
    for end in range(1, len(lines) + 1):
        check_invariants("\n".join(lines[:end]))


@pytest.mark.parametrize("path", MESSY_NOTES, ids=[p.name for p in MESSY_NOTES])
def test_shuffled_lines_keep_every_invariant(path):
    rng = random.Random(path.name)
    lines = read(path).split("\n")
    for _ in range(40):
        rng.shuffle(lines)
        check_invariants("\n".join(lines), fences=False)


@pytest.mark.parametrize("path", MESSY_NOTES, ids=[p.name for p in MESSY_NOTES])
def test_two_notes_pasted_together_keep_every_invariant(path):
    rng = random.Random(path.name)
    for other in rng.sample(ALL_NOTES, 5):
        check_invariants(read(path) + "\n\n" + read(other))


# ---- the team vault as a whole -----------------------------------------------------------------


def test_the_team_vault_has_no_tiny_or_oversized_chunks():
    everything = [c for path in TEAM_NOTES for c in chunks_of(path)]
    assert len(everything) > 250
    assert all(_body_len(c.text) >= MIN_CHUNK_SIZE for c in everything)
    assert max(len(c.text) for c in everything) <= MAX_CHUNK_SIZE
    assert statistics.median(len(c.text) for c in everything) > 200


def test_a_title_and_tags_line_is_folded_into_the_first_section():
    text = "# Title\n\nTags: #a #b\n\n## First\n\n" + "Real content sentence. " * 12
    result = chunk_markdown(text, "n.md")
    assert len(result) == 1
    assert result[0].header_path.endswith("First") and "Tags: #a #b" in result[0].text


# ---- the questions with known answers still land in a chunk of the right section -----------------


def test_every_answer_section_in_the_gold_set_is_findable():
    import json

    gold = json.loads((FIXTURES / "team-vault" / "gold.json").read_text())
    by_note = {p.stem: chunks_of(p) for p in TEAM_NOTES}
    for question in gold:
        for answer in question["relevant"]:
            where = squash(blob(by_note[answer["note"]]))
            assert squash(answer["section"]) in where, answer


# ---- exact expectations on the messy documents -------------------------------------------------


def test_frontmatter_is_not_indexed_but_the_rest_of_the_meeting_note_is():
    text = blob(chunk_markdown(messy("obsidian-meeting-notes"), "n.md"))
    assert "attendees" not in text and "tags:" not in text
    assert "Karpenter rollout" in text and "WhenUnderutilized" in text
    assert "```dataview" in text and "[[team-meeting-cadence|the cadence note]]" in text


def test_references_and_toc_sections_are_left_out_with_their_subsections():
    text = blob(chunk_markdown(messy("adr-with-references"), "n.md"))
    assert "Argo CD documentation" not in text and "(#status)" not in text
    assert "Notes on the references" not in text
    assert "Drift is detected" in text and "Flux" in text


def test_link_definitions_and_footnotes_survive():
    text = blob(chunk_markdown(messy("toc-footnotes-and-link-definitions"), "n.md"))
    assert "[checklist]: https://wiki.example.com/tls/checklist" in text
    assert "[^2]: See the incident note" in text and "aliases" not in text
    assert "(#why)" not in text and "RFC 5280" not in text


def test_degenerate_headings_never_make_empty_or_invented_chunks():
    result = chunk_markdown(messy("empty-and-degenerate-sections"), "n.md")
    assert all(c.text.strip() for c in result)
    text = blob(result)
    assert "Second duplicate" in text and "First duplicate" in text
    assert "seven hashes" in text and "hashtag-without-space" in text  # plain text, not headings
    assert not any("seven hashes" in c.header_path for c in result)


def test_a_long_log_is_cut_into_valid_fences_and_the_long_token_survives():
    result = chunk_markdown(messy("log-and-stacktrace-paste"), "n.md")
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in result)
    assert sum("```text" in c.text for c in result) >= 2
    assert re.sub(r"\s", "", messy("log-and-stacktrace-paste")).count("SflKxwRJSMeKKF2QT4fw") > 3
    assert "pool wait id=a22" in blob(result) and "pool wait id=a2 " in blob(result)


def test_a_big_json_block_is_cut_into_json_fences_with_nothing_lost():
    result = chunk_markdown(messy("api-reference-big-json"), "n.md")
    pieces = [c.text for c in result if "```json" in c.text]
    assert len(pieces) >= 2 and all(p.rstrip().endswith("```") for p in pieces)
    assert "Musterstrasse 12" in blob(result) and "experiment" in blob(result)


def test_a_wide_table_is_cut_with_its_header_row_repeated():
    result = chunk_markdown(messy("incident-timeline-tables"), "n.md")
    header = "| Time (UTC) | Event | Who |"
    assert sum(header in c.text for c in result) >= 1
    assert "\\| wc -l" in blob(result) and "cart abandonment rose<br>from 3% to 11%" in blob(result)


def test_german_cjk_and_rtl_text_is_kept_whole():
    german = blob(chunk_markdown(messy("german-notiz"), "n.md"))
    for word in ("Übersicht", "Häufige Fragen", "Größe", "Rindfleischetikettierungsüberwachungs"):
        assert word in german
    other = chunk_markdown(messy("cjk-emoji-rtl"), "n.md")
    assert all(len(c.text) <= MAX_CHUNK_SIZE for c in other)
    text = blob(other)
    assert "バックアップ" in text and "备份每天" in text and "قاعدة البيانات" in text
    assert "👨‍👩‍👧‍👦" in text


def test_hard_wrapped_text_with_setext_headings_and_rules_is_sectioned():
    result = chunk_markdown(messy("hard-wrapped-prose"), "n.md")
    paths = {c.header_path for c in result}
    assert any(p.endswith("Handover") for p in paths) or any("Handover" in c.text for c in result)
    assert "Appendix" in blob(result) and "Phone numbers" in blob(result)


def test_nested_fences_in_lists_never_leave_a_chunk_open():
    for chunk in chunk_markdown(messy("runbook-nested-code"), "n.md"):
        assert len(chunk.text) <= MAX_CHUNK_SIZE
    check_invariants(messy("runbook-nested-code"))
