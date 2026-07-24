"""
Document re-ranking module for improved retrieval accuracy
"""
from __future__ import annotations

from typing import List, Optional
try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

from langchain_core.documents import Document
from backend.config import settings
import logging
logger = logging.getLogger(__name__)


class DocumentReranker:
    """Re-rank documents based on relevance using cross-encoders"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize reranker
        
        Args:
            model_name: Hugging Face model name for cross-encoder
        """
        self.model_name = model_name or settings.reranker_model
        self.model = None
        self._init_model()
    
    def _init_model(self):
        """Load cross-encoder model"""
        if CrossEncoder is None:
            raise ImportError("sentence_transformers is required for document re-ranking")
        
        try:
            logger.info(
                "RERANKER_LOADING | model=%s",
                self.model_name,
            )
            self.model = CrossEncoder(self.model_name)

            logger.info(
                "RERANKER_READY | model=%s",
                self.model_name,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load re-ranker model {self.model_name}: {e}")
    
    def rerank(
        self,
        query: str,
        documents: List[Document],
        top_k: Optional[int] = None
    ) -> List[tuple[Document, float]]:
        """
        Re-rank documents by relevance to query
        
        Args:
            query: Query text
            documents: List of documents to rerank
            top_k: Return only top-k documents
        
        Returns:
            List of (document, score) tuples sorted by relevance
        """
        if not documents or self.model is None:
            return [(doc, 1.0) for doc in documents][:top_k]
        

        logger.info(
            "RERANK_START | query=%r | candidate_chunks=%d",
            query,
            len(documents),
        )
        
        # Prepare pairs for cross-encoder
        pairs = [[query, doc.page_content] for doc in documents]
        
        # Get relevance scores
        scores = self.model.predict(pairs)
        
        # Create results with scores
        results = list(zip(documents, scores))
        
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        for rank, (doc, score) in enumerate(results, start=1):
            logger.info(
                "RERANK_RESULT | rank=%d | score=%.4f | chunk_index=%s | document=%s",
                rank,
                score,
                doc.metadata.get("chunk_index"),
                doc.metadata.get("document_name"),
            )

        logger.info(
            "RERANK_FINISHED | returned=%d",
            len(results),
        )
        
        if top_k:
            results = results[:top_k]
        
        return results


# Global reranker instance
_reranker_instance: Optional[DocumentReranker] = None


def get_reranker(force_reload: bool = False) -> Optional[DocumentReranker]:
    """
    Get or create document reranker instance
    
    Args:
        force_reload: Force reload of model
    
    Returns:
        DocumentReranker instance or None if disabled
    """
    global _reranker_instance
    
    if not settings.enable_reranking:
        return None
    
    if force_reload or _reranker_instance is None:
        try:
            _reranker_instance = DocumentReranker()
        except Exception as e:
            print(f"Warning: Could not load re-ranker: {e}")
            return None
    
    return _reranker_instance
