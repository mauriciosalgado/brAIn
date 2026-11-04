# RAG Configuration

# ChromaDB Configuration
DB_PATH: str = ".rag/chroma_db"
COLLECTION_NAME: str = "notes"

# Chunking Configuration
# bge-small-en-v1.5 supports 512 tokens (~2000 chars)
MAX_CHUNK_SIZE: int = 1500
MIN_CHUNK_SIZE: int = 200
SKIP_HEADERS: list[str] = ["References", "Table of Contents", "TOC"]

# Embedding Configuration
MODEL: str = "BAAI/bge-small-en-v1.5"
