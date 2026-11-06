import threading
import time

import pytest
from samples import AWS, CAKE, numbered

from rag.index import indexer, search
from rag.index.store import write_lock


def hit(source, score):
    return {"source": source, "score": score, "text": "", "header_path": ""}


def test_matches_far_below_the_best_are_dropped():
    hits = [hit("a", 0.90), hit("b", 0.85), hit("c", 0.60)]
    assert [h["source"] for h in search.best_matches(hits)] == ["a", "b"]


def test_close_chunks_from_one_note_are_all_kept():
    hits = [hit("a", 0.9), hit("a", 0.89), hit("b", 0.88)]
    assert len(search.best_matches(hits)) == 3


def test_the_best_match_is_kept_however_weak():
    assert search.best_matches([hit("a", -0.3)]) == [hit("a", -0.3)]


def test_the_best_match_comes_first_with_its_section_and_score(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    commit()
    hits = search.query("how often should we rotate credentials")
    assert [h["source"] for h in hits] == ["notes/aws-keys.md"]
    assert hits[0]["header_path"] == "AWS Keys > Rotation"
    assert set(hits[0]) == {"text", "source", "header_path", "score"}


def test_a_query_sees_commits_made_since_the_last_sync(vault, commit):
    (vault / "cake.md").write_text(CAKE)
    commit()
    assert "forty" in search.query("how long do I bake the cake")[0]["text"]
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    commit()
    assert "fifty" in search.query("how long do I bake the cake")[0]["text"]


def test_a_query_reads_the_branch_not_the_checked_out_one(vault, commit, vault_git):
    (vault / "cake.md").write_text(CAKE)
    commit()
    vault_git("checkout", "-q", "-b", "feature/edit")
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    commit()
    assert "forty" in search.query("how long do I bake the cake")[0]["text"]


def test_a_query_returns_at_most_max_results(vault, commit):
    for i in range(6):
        (vault / f"aws-{i}.md").write_text(numbered(i))
    commit()
    assert len(search.query("how often to rotate keys", max_results=3)) == 3


def test_a_query_without_notes_explains_the_problem(vault, commit):
    commit()
    with pytest.raises(ValueError, match="No notes"):
        search.query("anything")


def test_a_query_waits_for_a_running_sync(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    indexer.sync()
    (vault / "cake.md").write_text(CAKE)
    commit()
    holding = threading.Event()

    def other_process():
        with write_lock():
            holding.set()
            time.sleep(0.5)

    threading.Thread(target=other_process).start()
    holding.wait()
    assert search.query("bake a cake")[0]["source"] == "notes/cake.md"
