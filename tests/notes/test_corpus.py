"""The chunker on realistic documents: a 70-note team vault (runbooks, ADRs, post-mortems,
handbooks) and a set of deliberately messy notes of the kind teams paste into Obsidian. Every file
must satisfy the same guarantees, however it is cut, re-encoded or shuffled."""

import re
import statistics
from pathlib import Path

import pytest
from test_chunker import check_invariants

from rag.config import MAX_CHUNK_SIZE
from rag.notes.chunker import _is_tiny, chunk_markdown

FIXTURES = Path(__file__).parents[1] / "fixtures"
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


# ---- every document ----------------------------------------------------------------------------


@pytest.mark.parametrize("path", ALL_NOTES, ids=IDS)
def test_every_document_keeps_every_invariant(path):
    check_invariants(read(path))


# ---- the team vault as a whole -----------------------------------------------------------------


def test_the_team_vault_has_no_tiny_or_oversized_chunks():
    everything = [c for path in TEAM_NOTES for c in chunks_of(path)]
    assert len(everything) > 250
    assert not any(_is_tiny(c.text) for c in everything)
    assert max(len(c.text) for c in everything) <= MAX_CHUNK_SIZE
    assert statistics.median(len(c.text) for c in everything) > 200


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
