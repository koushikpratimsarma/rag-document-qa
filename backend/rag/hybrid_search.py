"""
Hybrid search module combining BM25 and vector search
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from rank_bm25 import BM25Okapi
import numpy as np
from langchain_core.documents import Document

from backend.config import settings
from backend.rag.metadata_filter import MetadataFilter


class HybridSearcher:
    """Hybrid search combining BM25 and vector similarity"""
    
    def __init__(self):
        self.bm25: Optional[BM25Okapi] = None
        self.documents: List[Document] = []
        self.document_texts: List[str] = []
        self.tokenized_docs: List[List[str]] = []
    
    def index_documents(self, documents: List[Document]) -> None:
        """Index documents for BM25 search"""
        self.documents = documents
        self.document_texts = [doc.page_content for doc in documents]
        
        # Tokenize documents for BM25
        self.tokenized_docs = [doc.split() for doc in self.document_texts]
        
        # Initialize BM25
        if self.tokenized_docs:
            self.bm25 = BM25Okapi(self.tokenized_docs)
    
    def bm25_search(self, query: str, top_k: int = 10) -> List[tuple[Document, float]]:
        """
        BM25 keyword search
        
        Returns:
            List of (document, score) tuples
        """
        if not self.bm25:
            return []
        
        # Tokenize query
        tokenized_query = query.split()
        
        # Get BM25 scores
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-k results
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self.documents[idx], float(scores[idx])))
        
        return results
    
    def vector_search(
        self,
        query_embedding: List[float],
        vector_search_results: List[tuple[Document, float]],
        top_k: int = 10
    ) -> List[tuple[Document, float]]:
        """
        Vector similarity search results (pre-computed from vector store)
        
        Args:
            query_embedding: Query vector embedding
            vector_search_results: Results from vector store search
            top_k: Number of top results to return
        
        Returns:
            List of (document, score) tuples
        """
        # Already sorted by similarity, just take top-k
        return vector_search_results[:top_k]
    
    def hybrid_search(
        self,
        query: str,
        query_embedding: List[float],
        vector_search_results: List[tuple[Document, float]],
        top_k: int = 10,
        metadata_filter: Optional[MetadataFilter] = None
    ) -> List[tuple[Document, float]]:
        """
        Combine BM25 and vector search results
        
        Args:
            query: Query text
            query_embedding: Query embedding vector
            vector_search_results: Pre-computed vector search results
            top_k: Number of results to return
            metadata_filter: Optional metadata filter
        
        Returns:
            List of (document, combined_score) tuples
        """
        # Get results from both methods
        bm25_results = self.bm25_search(query, top_k=settings.reranking_top_k or top_k * 2)
        
        # Normalize scores to 0-1 range
        bm25_scores = {}
        if bm25_results:
            max_bm25_score = max(score for _, score in bm25_results)
            for doc, score in bm25_results:
                doc_id = self._get_doc_id(doc)
                bm25_scores[doc_id] = score / max_bm25_score if max_bm25_score > 0 else 0
        
        vector_scores = {}
        for doc, score in vector_search_results[:settings.reranking_top_k or top_k * 2]:
            doc_id = self._get_doc_id(doc)
            vector_scores[doc_id] = score
        
        # Combine scores
        combined_scores = {}
        all_doc_ids = set(bm25_scores.keys()) | set(vector_scores.keys())
        
        for doc_id in all_doc_ids:
            bm25_score = bm25_scores.get(doc_id, 0)
            vector_score = vector_scores.get(doc_id, 0)
            
            # Weighted combination
            combined = (
                settings.bm25_weight * bm25_score +
                settings.vector_weight * vector_score
            )
            combined_scores[doc_id] = combined
        
        # Create result list with combined scores
        result_docs = {self._get_doc_id(doc): doc for doc in self.documents}
        for doc, _ in vector_search_results:
            doc_id = self._get_doc_id(doc)
            result_docs[doc_id] = doc
        
        results = []
        for doc_id, score in combined_scores.items():
            if doc_id in result_docs:
                doc = result_docs[doc_id]
                
                # Apply metadata filter if provided
                if metadata_filter and not metadata_filter.matches_document(doc.metadata):
                    continue
                
                results.append((doc, score))
        
        # Sort by combined score
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def _get_doc_id(self, doc: Document) -> str:
        """Get unique document ID"""
        return doc.metadata.get("chunk_id", id(doc))
    
    def clear(self) -> None:
        """Clear indexed documents"""
        self.bm25 = None
        self.documents = []
        self.document_texts = []
        self.tokenized_docs = []


# Global hybrid searcher instance
_hybrid_searcher_instance: Optional[HybridSearcher] = None


def get_hybrid_searcher() -> HybridSearcher:
    """Get or create hybrid searcher instance"""
    global _hybrid_searcher_instance
    if _hybrid_searcher_instance is None:
        _hybrid_searcher_instance = HybridSearcher()
    return _hybrid_searcher_instance
