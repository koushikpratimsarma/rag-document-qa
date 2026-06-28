import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

class Settings(BaseSettings):
    # API settings
    api_key: str | None = None
    secret_key: str = "your-secret-key-change-this-in-production"
    jwt_expiration_hours: int = 24
    jwt_algorithm: str = "HS256"
    
    # OpenAI settings
    openai_api_key: str | None = None
    embedding_provider: str = "sentence_transformers"  # openai or sentence_transformers
    llm_provider: str = "openai"  # openai or local
    openai_model: str = "gpt-3.5-turbo"
    openai_embedding_model: str = "text-embedding-3-small"
    
    # Local model settings
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    local_generation_model: str = "google/flan-t5-small"
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"  # For re-ranking
    
    # Search settings
    top_k: int = 4
    hybrid_search_enabled: bool = True
    bm25_weight: float = 0.5  # Weight for BM25 in hybrid search (0.0-1.0)
    vector_weight: float = 0.5  # Weight for vector search in hybrid search
    enable_reranking: bool = True
    reranking_top_k: int = 10  # Retrieve more before re-ranking
    
    # Chunking settings
    max_chunk_size: int = 500
    chunk_overlap: int = 50
    
    # Vector store settings
    vector_store_path: Path = DATA_DIR / "qdrant_db"
    chroma_collection_name: str = "rag_docs"
    qdrant_url: str | None = None
    qdrant_location: str = ":memory:"
    qdrant_collection_name: str = "rag_docs"
    qdrant_api_key: str | None = None
    qdrant_prefer_grpc: bool = False
    
    # Metadata settings
    enable_metadata_filtering: bool = True
    metadata_fields: list[str] = ["document_name", "document_type", "upload_date", "user_id"]

    class Config:
        env_file = BASE_DIR.parent / ".env"
        env_file_encoding = "utf-8"

settings = Settings()
