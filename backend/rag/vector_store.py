import uuid
from typing import Any, List, Optional

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.http import models

from backend.config import settings
from backend.rag.embeddings import get_embeddings

vector_store = None


class QdrantVectorStore:
    def __init__(self, client: QdrantClient, collection_name: str, embeddings: Any):
        self.client = client
        self.collection_name = collection_name
        self.embeddings = embeddings
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=384,
                    distance=models.Distance.COSINE,
                ),
            )

    def add_texts(self, texts: List[str], metadatas: Optional[List[dict]] = None) -> None:
        if not texts:
            return

        metadata_list = metadatas or [{} for _ in texts]
        vectors = self.embeddings.embed_documents(list(texts))

        points = []
        for text, vector, metadata in zip(texts, vectors, metadata_list):
            payload = {"page_content": text}

            if metadata:
                payload.update(metadata)

            points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=payload,
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        results = self.similarity_search_with_score(query=query, k=k)
        return [doc for doc, _score in results]

    def similarity_search_with_score(self, query: str, k: int = 4) -> List[tuple[Document, float]]:
        vector = self.embeddings.embed_query(query)

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=k,
            with_payload=True,
            with_vectors=False,
        )

        results: List[tuple[Document, float]] = []

        for point in getattr(response, "points", []) or []:
            payload = point.payload or {}

            content = payload.get("page_content", "")
            metadata = {
                key: value
                for key, value in payload.items()
                if key != "page_content"
            }

            score = getattr(point, "score", 0.0)

            results.append(
                (
                    Document(
                        page_content=content,
                        metadata=metadata,
                    ),
                    float(score),
                )
            )

        return results

    def delete_collection(self) -> None:
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)

    def delete(self, ids: List[str]) -> None:
        if ids:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=ids),
            )


def get_vector_store():
    global vector_store

    if vector_store is None:
        embeddings = get_embeddings()

        if settings.qdrant_url:
            client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                prefer_grpc=settings.qdrant_prefer_grpc,
            )
        else:
            client = QdrantClient(location=settings.qdrant_location)

        vector_store = QdrantVectorStore(
            client=client,
            collection_name=settings.qdrant_collection_name,
            embeddings=embeddings,
        )

    return vector_store


def get_vector_store_instance():
    return get_vector_store()


def add_documents(texts, metadatas=None):
    store = get_vector_store()
    store.add_texts(texts=texts, metadatas=metadatas)


def search_documents(query, top_k=None):
    store = get_vector_store()
    top_k = top_k or settings.top_k
    return store.similarity_search(query, k=top_k)


def delete_documents(ids=None):
    store = get_vector_store()

    if ids is None:
        store.delete_collection()
    else:
        store.delete(ids=ids)