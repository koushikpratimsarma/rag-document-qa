import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

class Settings(BaseSettings):
    openai_api_key: str | None = None
    embedding_provider: str = "sentence_transformers"  # openai or sentence_transformers
    llm_provider: str = "openai"  # openai or local
    openai_model: str = "gpt-3.5-turbo"
    openai_embedding_model: str = "text-embedding-3-small"
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    local_generation_model: str = "google/flan-t5-small"
    top_k: int = 4
    max_chunk_size: int = 500
    chunk_overlap: int = 50
    vector_store_path: Path = DATA_DIR / "qdrant_db"
    chroma_collection_name: str = "rag_docs"
    qdrant_url: str | None = None
    qdrant_location: str = ":memory:"
    qdrant_collection_name: str = "rag_docs"
    qdrant_api_key: str | None = None
    qdrant_prefer_grpc: bool = False

    class Config:
        env_file = BASE_DIR.parent / ".env"
        env_file_encoding = "utf-8"

settings = Settings()
