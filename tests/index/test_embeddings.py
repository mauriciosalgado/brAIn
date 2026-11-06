import math
from pathlib import Path
from typing import ClassVar

import pytest

from rag import config
from rag.index import embeddings
from rag.notes.chunker import Chunk


@pytest.fixture(scope="module", autouse=True)
def _load_model():
    embeddings.get_model()


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def test_output_order_matches_input_order():
    texts = ["a much longer text " * 30, "short", "medium length text here " * 5]
    batched = embeddings.embed_documents(texts)
    singly = [embeddings.embed_documents([t])[0] for t in texts]
    assert [cosine(a, b) > 0.999 for a, b in zip(batched, singly, strict=True)] == [True] * 3


def test_vectors_are_finite_and_normalized():
    for vector in embeddings.embed_documents(["hello world", "kubectl get pods"]):
        assert len(vector) == config.EMBEDDING_SIZE
        assert all(math.isfinite(x) for x in vector)
        assert abs(math.sqrt(sum(x * x for x in vector)) - 1) < 1e-3


def test_query_is_prefixed_and_rejects_empty():
    plain = embeddings.embed_documents(["how do I rotate keys"])[0]
    assert cosine(embeddings.embed_query("how do I rotate keys"), plain) < 0.999
    with pytest.raises(ValueError):
        embeddings.embed_query("   ")


def test_relevant_passage_beats_unrelated():
    docs = ["Rotate AWS access keys every 90 days", "Chocolate cake recipe with eggs"]
    doc_vectors = embeddings.embed_documents(docs)
    query = embeddings.embed_query("how often should we rotate credentials")
    assert cosine(query, doc_vectors[0]) > cosine(query, doc_vectors[1])


def test_embedding_text_contains_breadcrumb():
    chunk = Chunk("body text", "Title > Section", 0)
    assert chunk.embedding_text == "Section: Title > Section\n\nbody text"


class FakeModel:
    """Stands in for fastembed: it works once its folder holds an `ok` file."""

    downloads = 0
    local_only_calls: ClassVar[list[bool]] = []

    def __init__(self, name, cache_dir, local_files_only=False):
        FakeModel.local_only_calls.append(local_files_only)
        self.folder = Path(cache_dir)
        if not (self.folder / "ok").exists():
            if local_files_only:
                raise ValueError("model not found on disk")
            FakeModel.downloads += 1
            self.folder.mkdir(parents=True, exist_ok=True)
            (self.folder / "ok").write_text("model")

    def embed(self, texts, **_):
        return ([0.1] * config.EMBEDDING_SIZE for _ in texts)


@pytest.fixture
def fake_model(tmp_path, monkeypatch):
    FakeModel.downloads, FakeModel.local_only_calls = 0, []
    monkeypatch.setattr(embeddings, "TextEmbedding", FakeModel)
    monkeypatch.setattr(embeddings, "MODEL_CACHE_DIR", str(tmp_path / "models"))
    embeddings.get_model.cache_clear()  # no real model from an earlier test
    yield tmp_path / "models"
    embeddings.get_model.cache_clear()  # and no fake one left for the next


def test_model_works_never_downloads(fake_model):
    assert embeddings.model_works() is False
    assert FakeModel.downloads == 0 and FakeModel.local_only_calls == [True]
    assert not (fake_model / "ok").exists()


def test_ensure_model_downloads_a_missing_model(fake_model):
    embeddings.ensure_model()
    assert FakeModel.downloads == 1 and embeddings.model_works()


def test_ensure_model_replaces_a_damaged_download(fake_model):
    fake_model.mkdir()
    (fake_model / "model.onnx").write_text("")  # a cut-short file, and no `ok`
    embeddings.ensure_model()
    assert FakeModel.downloads == 1 and not (fake_model / "model.onnx").exists()


def test_ensure_model_reports_a_download_that_still_does_not_work(fake_model, monkeypatch):
    monkeypatch.setattr(FakeModel, "embed", lambda _self, texts, **_: ([0.1] * 3 for _ in texts))
    with pytest.raises(RuntimeError, match="does not work"):
        embeddings.ensure_model()


def test_a_failed_download_gets_a_helpful_message(fake_model, monkeypatch):
    def offline(*_args, **_kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(embeddings, "TextEmbedding", offline)
    with pytest.raises(RuntimeError, match="needs internet once"):
        embeddings.ensure_model()
