import pytest
from samples import AWS, CAKE, numbered

from rag import config, git
from rag.index import embeddings, indexer, search
from rag.index.chunker import chunk_markdown
from rag.index.store import EmbeddedNote, Store


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


def test_the_best_match_comes_first_with_its_section_and_score(vault, publish):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    publish()
    indexer.sync()
    hits = search.query("how often should we rotate credentials", Store())
    assert [h["source"] for h in hits] == ["notes/aws-keys.md"]
    assert hits[0]["header_path"] == "AWS Keys > Rotation"
    assert set(hits[0]) == {
        "text",
        "source",
        "header_path",
        "context",
        "score",
    }


def test_search_reads_the_supplied_database_without_checking_or_updating_git(
    vault, publish, monkeypatch
):
    (vault / "cake.md").write_text(CAKE)
    indexed = publish()
    indexer.sync()
    store = Store()
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    publish()

    def unexpected(*_):
        pytest.fail("Retrieval must not check Git or synchronize the index")

    monkeypatch.setattr(git, "remote_branch_tip", unexpected)
    monkeypatch.setattr(indexer, "sync", unexpected)
    hits = search.query("how long do I bake the cake", store)
    assert "forty" in hits[0]["text"] and "fifty" not in hits[0]["text"]
    assert store.indexed_commit() == indexed


def test_a_query_returns_at_most_max_results(vault, publish):
    for i in range(6):
        (vault / f"aws-{i}.md").write_text(numbered(i))
    publish()
    indexer.sync()
    assert len(search.query("how often to rotate keys", Store(), max_results=3)) == 3


def test_a_query_without_notes_does_not_load_the_model(vault, publish, monkeypatch):
    publish()
    indexer.sync()
    monkeypatch.setattr(embeddings, "embed_query", lambda _: pytest.fail("loaded model"))
    with pytest.raises(ValueError, match="No notes"):
        search.query("anything", Store())


@pytest.fixture
def controlled_index(vault, monkeypatch):
    vector = [1.0] + [0.0] * (config.EMBEDDING_SIZE - 1)
    monkeypatch.setattr(embeddings, "embed_query", lambda _: vector)
    return Store()


def save_ranked(index, source, text, priorities):
    chunks = chunk_markdown(text, source)
    vectors = []
    for chunk in chunks:
        priority = priorities.get(chunk.header_path, 0.0)
        vectors.append([priority, 1.0 - priority] + [0.0] * (config.EMBEDDING_SIZE - 2))
    index.replace_notes([EmbeddedNote(source, chunks, vectors)])


def test_tiny_hit_stays_independent_of_its_parent(controlled_index):
    save_ranked(
        controlled_index,
        "notes/keys.md",
        "# Keys\n\n## Steps\n\nCreate.\n\n### Verify\n\nCheck.",
        {"Keys > Steps > Verify": 1.0},
    )
    hits = search.query("verify", controlled_index)
    assert len(hits) == 1
    assert hits[0]["header_path"] == "Keys > Steps > Verify"
    assert hits[0]["text"] == "### Verify\n\nCheck."
