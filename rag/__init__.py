__version__ = "0.1.0"
__all__ = ["sync", "query"]


from pathlib import Path
from rag import chunker, config, db, embeddings
from rag.chunker import Chunk


def _build_embedding_text(chunk: Chunk, preamble: str):
    parts = []
    if preamble:
        parts.append(preamble)
    if chunk.header_path:
        parts.append(f"Section: {chunk.header_path}")
    parts.append(chunk.text)
    return "\n\n".join(parts)


def cleanup():
    db.cleanup()
    state_file = Path(config.STATE_FILE)
    if state_file.exists():
        state_file.unlink()


def sync():
    notes_dir = Path("notes")
    files = list(notes_dir.glob("**/*.md"))

    total_chunks = 0

    for filepath in files:
        preamble, chunks = chunker.get_chunks(filepath)

        if not chunks:
            continue

        db.delete_by_source(str(filepath))

        embeds = embeddings.get_embeddings(
            [_build_embedding_text(chunk, preamble) for chunk in chunks]
        )
        db.add(
            ids=[chunk.id for chunk in chunks],
            embeddings=embeds,
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {"source": chunk.source, "header_path": chunk.header_path}
                for chunk in chunks
            ],
        )
        total_chunks += len(chunks)

    return total_chunks


def query(question: str, n_results: int = 5) -> list[dict]:
    if db.count() == 0:
        raise ValueError("Database is empty. Please run sync() first.")

    query_embedding = embeddings.get_embeddings([question])[0]
    documents, metadatas = db.query([query_embedding], n_results=n_results)

    return [
        {"text": doc, "source": meta["source"], "header_path": meta["header_path"]}
        for doc, meta in zip(documents, metadatas)
    ]
