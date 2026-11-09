import pytest
from samples import AWS, CAKE, numbered

from rag import git
from rag.index import embeddings, indexer, search
from rag.index.store import Store


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
    indexer.sync()
    hits = search.query("how often should we rotate credentials", Store())
    assert [h["source"] for h in hits] == ["notes/aws-keys.md"]
    assert hits[0]["header_path"] == "AWS Keys > Rotation"
    assert set(hits[0]) == {"text", "source", "header_path", "score"}


def test_search_reads_the_supplied_database_without_checking_or_updating_git(
    vault, commit, monkeypatch
):
    (vault / "cake.md").write_text(CAKE)
    indexed = commit()
    indexer.sync()
    store = Store()
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    commit()

    def unexpected(*_):
        pytest.fail("Retrieval must not check Git or synchronize the index")

    monkeypatch.setattr(git, "branch_tip", unexpected)
    monkeypatch.setattr(indexer, "sync", unexpected)
    hits = search.query("how long do I bake the cake", store)
    assert "forty" in hits[0]["text"] and "fifty" not in hits[0]["text"]
    assert store.indexed_commit() == indexed


def test_a_query_returns_at_most_max_results(vault, commit):
    for i in range(6):
        (vault / f"aws-{i}.md").write_text(numbered(i))
    commit()
    indexer.sync()
    assert len(search.query("how often to rotate keys", Store(), max_results=3)) == 3


def test_a_query_without_notes_does_not_load_the_model(vault, commit, monkeypatch):
    commit()
    indexer.sync()
    monkeypatch.setattr(embeddings, "embed_query", lambda _: pytest.fail("loaded model"))
    with pytest.raises(ValueError, match="No notes"):
        search.query("anything", Store())
