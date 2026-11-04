import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from rag.config import DB_PATH, COLLECTION_NAME

_client: ClientAPI | None = None
_collection: Collection | None = None


def _get_collection() -> Collection:
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=DB_PATH)
        _collection = _client.get_or_create_collection(COLLECTION_NAME)
    return _collection


def cleanup():
    global _client, _collection
    db = chromadb.PersistentClient(path=DB_PATH)
    existing = [collection.name for collection in db.list_collections()]
    if COLLECTION_NAME in existing:
        db.delete_collection(COLLECTION_NAME)


def add(ids, embeddings, metadatas, documents):
    _get_collection().add(
        ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
    )


def query(query_embeddings, n_results=5):
    result = _get_collection().query(
        query_embeddings=query_embeddings,
        n_results=n_results,
        include=["metadatas", "documents"],
    )

    if result["documents"] is None or result["metadatas"] is None:
        return [], []

    return result["documents"][0], result["metadatas"][0]


def count():
    return _get_collection().count()


def delete_by_source(source: str) -> int:
    collection = _get_collection()

    # First, get the IDs of chunks with this source
    existing = collection.get(where={"source": source})
    ids_to_delete = existing.get("ids", [])

    if ids_to_delete:
        collection.delete(ids=ids_to_delete)

    return len(ids_to_delete)
