from __future__ import annotations
import re
import logging
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, UploadFile
from langchain_core.documents import Document
from qdrant_client.http import models
from backend.rag.chunking import chunk_text

from backend.config import settings
from backend.rag.hybrid_search import get_hybrid_searcher
from backend.rag.llm import get_llm
from backend.rag.pdf_loader import extract_text_from_pdf
from backend.rag.vector_store import (
    get_vector_store_instance as get_qdrant_vector_store_instance,
)
from backend.rag.metadata_extractor import extract_document_metadata
from backend.rag.metadata_filter import (
    build_filter_from_query,
    extract_query_metadata,
)

from backend.schemas.documents import (
    DocumentListResponse,
    DocumentSummary,
    DocumentUploadResponse,
    QueryRequest,
    QueryResponse,
)
from backend.rag.reranker import get_reranker

logger = logging.getLogger(__name__)

def read_text_from_upload(tmp_path: Path) -> str:
    if tmp_path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(tmp_path)

    return tmp_path.read_text(encoding="utf-8", errors="ignore")


def build_chunk_metadata(
    document_id: str,
    document_name: str,
    document_type: str,
    chunks: List[str],
    user_id: Optional[str],
    document_metadata: Dict[str, Any],
    session_id: Optional[str],
) -> List[dict]:
    metadata_list: List[dict] = []

    for index, _chunk in enumerate(chunks):
        metadata_list.append(
            {
                **document_metadata,
                "chunk_id": str(uuid.uuid4()),
                "document_id": document_id,
                "document_name": document_name,
                "document_type": document_type,
                "upload_date": datetime.utcnow().isoformat(),
                "chunk_index": index,
                "chunk_count": len(chunks),
                "user_id": user_id,
                "session_id": session_id,
            }
        )

    return metadata_list


async def process_document_upload(
    file: UploadFile,
    current_user: Optional[str],
    session_id: Optional[str] = None,
) -> DocumentUploadResponse:
    upload_start = time.perf_counter()

    logger.info(
        "UPLOAD_START | file=%s | user=%s | session_id=%s",
        file.filename,
        current_user or "anonymous",
        session_id,
    )
    suffix = Path(file.filename or "upload.txt").suffix or ".txt"

    document_id = str(uuid.uuid4())
    document_type = suffix.lower().lstrip(".")
    document_name = file.filename or "upload"
    tmp_path: Optional[Path] = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            logger.info(
                "FILE_READ | file=%s | size_bytes=%d",
                document_name,
                len(content),
            )
            tmp.write(content)
            tmp_path = Path(tmp.name)

        text = read_text_from_upload(tmp_path)
        logger.info(
            "TEXT_EXTRACTED | file=%s | characters=%d",
            document_name,
            len(text),
        )

        document_metadata = extract_document_metadata(
            text=text,
            filename=document_name,
        )
        logger.info(
            "METADATA_EXTRACTED | file=%s | company=%s | year=%s "
            "| quarter=%s | document_type=%s",
            document_name,
            document_metadata.get("company"),
            document_metadata.get("year"),
            document_metadata.get("quarter"),
            document_metadata.get("document_type_label"),
        )
        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail="Uploaded document contains no readable text",
            )

        # chunks = get_text_splitter().split_text(text)
        chunk_start = time.perf_counter()

        chunks = chunk_text(text)

        logger.info(
            "CHUNKING_COMPLETED | file=%s | chunk_count=%d "
            "| duration_seconds=%.3f",
            document_name,
            len(chunks),
            time.perf_counter() - chunk_start,
        )
        metadatas = build_chunk_metadata(
            document_id=document_id,
            document_name=document_name,
            document_type=document_type,
            chunks=chunks,
            user_id=current_user,
            document_metadata=document_metadata,
            session_id=session_id,
        )

        get_qdrant_vector_store_instance().add_texts(
            texts=chunks,
            metadatas=metadatas,
        )
        logger.info(
            "VECTOR_INDEX_COMPLETED | file=%s | indexed_chunks=%d",
            document_name,
            len(chunks),
        )
        if settings.hybrid_search_enabled:
            docs = [
                Document(page_content=chunk, metadata=metadata)
                for chunk, metadata in zip(chunks, metadatas)
            ]
            get_hybrid_searcher().index_documents(docs)
        logger.info(
            "UPLOAD_COMPLETED | file=%s | document_id=%s | total_seconds=%.3f",
            document_name,
            document_id,
            time.perf_counter() - upload_start,
        )

        return DocumentUploadResponse(
            status="ok",
            added_chunks=len(chunks),
            document_id=document_id,
            document_name=document_name,
            document_type=document_type,
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "UPLOAD_FAILED | file=%s | document_id=%s",
            document_name,
            document_id,
        )

        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {exc}",
        ) from exc

    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


def list_uploaded_documents(
    current_user: Optional[str],
    session_id: Optional[str] = None,
) -> DocumentListResponse:
    store = get_qdrant_vector_store_instance()

    points = store.client.scroll(
        collection_name=store.collection_name,
        limit=100,
        with_payload=True,
    )[0]

    summaries: List[DocumentSummary] = []
    seen: set[str] = set()

    for point in points:
        metadata = point.payload or {}
        document_id = metadata.get("document_id")

        if not document_id or document_id in seen:
            continue

        if current_user and metadata.get("user_id") != current_user:
            continue
        if session_id and metadata.get("session_id") != session_id:
            continue

        seen.add(document_id)

        chunk_count = sum(
            1
            for item in points
            if (item.payload or {}).get("document_id") == document_id
        )

        summaries.append(
            DocumentSummary(
                document_id=document_id,
                document_name=metadata.get("document_name", "unknown"),
                document_type=metadata.get("document_type", "document"),
                upload_date=metadata.get(
                    "upload_date",
                    datetime.utcnow().isoformat(),
                ),
                chunk_count=chunk_count,
                user_id=metadata.get("user_id"),
            )
        )

    summaries.sort(key=lambda item: item.upload_date, reverse=True)

    return DocumentListResponse(documents=summaries)


def delete_document_by_id(
    document_id: Optional[str],
    current_user: Optional[str],
) -> Dict[str, Any]:
    if not document_id:
        raise HTTPException(
            status_code=400,
            detail="document_id is required",
        )

    store = get_qdrant_vector_store_instance()

    points = store.client.scroll(
        collection_name=store.collection_name,
        limit=100,
        with_payload=True,
    )[0]

    matching_ids = []

    for point in points:
        metadata = point.payload or {}

        if metadata.get("document_id") != document_id:
            continue

        if current_user and metadata.get("user_id") != current_user:
            continue

        matching_ids.append(point.id)

    if matching_ids:
        store.client.delete(
            collection_name=store.collection_name,
            points_selector=models.PointIdsList(points=matching_ids),
        )

    return {
        "status": "ok",
        "message": f"Deleted document {document_id}",
        "deleted_chunks": len(matching_ids),
    }


def is_latest_query(query: str) -> bool:
    latest_words = ["latest", "newest", "recent", "most recent", "current"]
    return any(word in query.lower() for word in latest_words)


def filter_latest_documents(docs):
    if not docs:
        return docs

    years = []

    for doc, score in docs:
        year = doc.metadata.get("year")
        if year:
            years.append(year)

    if not years:
        return docs

    latest_year = max(years)

    return [
        (doc, score)
        for doc, score in docs
        if doc.metadata.get("year") == latest_year
    ]



def query_matches_document(
    query: str,
    metadata: dict,
    query_company: str | None = None,
    query_ticker: str | None = None,
) -> bool:
    """
    Soft company/document filter.
    """

    query = query.lower()

    searchable = " ".join(
        [
            str(metadata.get("company", "")).lower(),
            str(metadata.get("ticker", "")).lower(),
            str(metadata.get("document_name", "")).lower(),
            str(metadata.get("source_file", "")).lower(),
        ]
    )

    ignore = {
        "what",
        "is",
        "was",
        "the",
        "of",
        "in",
        "for",
        "revenue",
        "sales",
        "profit",
        "gross",
        "margin",
        "net",
        "total",
        "q1",
        "q2",
        "q3",
        "q4",
        "latest",
        "recent",
        "tell",
        "me",
        "a",
        "i",
        "s",
        "q",
        "and",
        "or",
        "by",
        "from",
        "company",
        "stock",
    }

    keywords = [
        word
        for word in re.findall(r"[A-Za-z]+", query.lower())
        if word not in ignore and len(word) > 1
    ]

    if query_company:
        normalized_company = normalize_company_name(query_company) or str(query_company).strip()
        normalized_company_lower = normalized_company.lower()
        company_name = str(metadata.get("company", "")).strip()
        company_name_lower = company_name.lower()
        ticker = str(metadata.get("ticker", "")).lower()

        if "apple" in normalized_company_lower:
            if "apple" not in company_name_lower and "aapl" not in ticker:
                return False
        elif "nvidia" in normalized_company_lower or "nvda" in normalized_company_lower:
            if "nvidia" not in company_name_lower and "nvda" not in ticker:
                return False
        else:
            if normalized_company_lower not in company_name_lower and normalized_company_lower not in ticker:
                return False

    if not keywords:
        return True

    return any(word in searchable for word in keywords)

def resolve_ticker_from_stored_metadata(
    query: str,
    store,
    current_user: Optional[str],
    session_id: Optional[str],
) -> tuple[str, Optional[str], Optional[str]]:
    """
    Convert a ticker in the query into the stored company name.

    Example:
        "What is NVDA revenue?"
        becomes:
        "What is NVIDIA Corporation revenue?"
    """

    try:
        points = store.client.scroll(
            collection_name=store.collection_name,
            limit=1000,
            with_payload=True,
        )[0]

    except Exception:
        logger.exception(
            "TICKER_RESOLUTION_FAILED | query=%r",
            query,
        )
        return query, None, None

    ticker_map: dict[str, str] = {}

    for point in points:
        metadata = point.payload or {}

        if current_user and metadata.get("user_id") != current_user:
            continue

        if session_id and metadata.get("session_id") != session_id:
            continue

        ticker = str(metadata.get("ticker") or "").strip()
        company = str(metadata.get("company") or "").strip()

        if ticker and company:
            ticker_map[ticker.lower()] = company

    normalized_query = query
    detected_ticker: Optional[str] = None
    detected_company: Optional[str] = None

    query_words = re.findall(
        r"\b[A-Za-z][A-Za-z0-9.-]*\b",
        query,
    )

    for word in query_words:
        company = ticker_map.get(word.lower())

        if not company:
            continue

        detected_ticker = word.upper()
        detected_company = company

        normalized_query = re.sub(
            rf"\b{re.escape(word)}\b",
            company,
            normalized_query,
            flags=re.IGNORECASE,
        )

        break

    logger.info(
        "TICKER_RESOLVED | original=%r | normalized=%r "
        "| ticker=%s | company=%s",
        query,
        normalized_query,
        detected_ticker,
        detected_company,
    )

    return normalized_query, detected_company, detected_ticker

async def query_uploaded_documents(
    request: QueryRequest,
    current_user: Optional[str],
) -> QueryResponse:
    query_start = time.perf_counter()
    request_id = str(uuid.uuid4())
    session_id = request.session_id or str(uuid.uuid4())

    # ---------------------------------------------------------
    # 1. Validate user question
    # ---------------------------------------------------------
    original_query = request.query.strip()

    if not original_query:
        logger.warning(
            "QUERY_REJECTED | request_id=%s | reason=empty_query",
            request_id,
        )

        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    final_top_k = request.top_k or settings.top_k

    logger.info(
        "QUESTION_RECEIVED | request_id=%s | user=%s "
        "| session_id=%s | top_k=%d | question=%r",
        request_id,
        current_user or "anonymous",
        session_id,
        final_top_k,
        original_query,
    )

    # ---------------------------------------------------------
    # 2. Get Qdrant vector store
    # ---------------------------------------------------------
    try:
        store = get_qdrant_vector_store_instance()

        resolved_query, detected_company, detected_ticker = (
            resolve_ticker_from_stored_metadata(
                query=original_query,
                store=store,
                current_user=current_user,
                session_id=request.session_id,
            )
        )

        logger.info(
            "VECTOR_STORE_READY | request_id=%s | collection=%s",
            request_id,
            store.collection_name,
        )

    except Exception:
        logger.exception(
            "VECTOR_STORE_CONNECTION_FAILED | request_id=%s",
            request_id,
        )

        return QueryResponse(
            query=original_query,
            answer=(
                "The document search service is currently unavailable. "
                "Please make sure Qdrant is running."
            ),
            citations=[],
            session_id=session_id,
        )

    # ---------------------------------------------------------
    # 3. Build metadata filter
    # ---------------------------------------------------------
    query_metadata = extract_query_metadata(original_query)

    try:
        query_filter = build_filter_from_query(
            query=resolved_query,
            current_user=current_user,
            session_id=request.session_id,
        )

        logger.info(
            "QUERY_FILTER_CREATED | request_id=%s | filter=%s",
            request_id,
            query_filter,
        )

    except Exception:
        logger.exception(
            "QUERY_FILTER_FAILED | request_id=%s | query=%r",
            request_id,
            original_query,
        )

        query_filter = None

    search_query = re.sub(
        r"\bq[1-4]\b|\b20\d{2}\b",
        "",
        resolved_query,
        flags=re.IGNORECASE,
    )

    search_query = re.sub(
        r"\s+",
        " ",
        search_query,
    ).strip()

    search_query = re.sub(
        r"\b(in|for|during)\s*[?.!]*$",
        "",
        search_query,
        flags=re.IGNORECASE,
    ).strip()

    if not search_query:
        search_query = original_query

    # Improve retrieval for common financial questions.
    query_lower = original_query.lower()

    if "revenue" in query_lower:
        search_query = (
            f"{search_query} "
            "total revenue revenue by market platform "
            "net revenue three months ended"
        )

    logger.info(
        "SEMANTIC_SEARCH_QUERY | request_id=%s "
        "| original=%r | cleaned=%r",
        request_id,
        original_query,
        search_query,
    )

    # ---------------------------------------------------------
    # 5. Decide how many candidate chunks to retrieve
    #
    # If reranking is enabled:
    # retrieve many candidates, then keep the best final_top_k.
    # ---------------------------------------------------------
    if settings.enable_reranking:
        retrieval_k = max(
            settings.reranking_top_k,
            final_top_k,
        )
    else:
        retrieval_k = final_top_k

    logger.info(
        "RETRIEVAL_CONFIG | request_id=%s | retrieval_k=%d "
        "| final_top_k=%d | reranking_enabled=%s",
        request_id,
        retrieval_k,
        final_top_k,
        settings.enable_reranking,
    )

    # ---------------------------------------------------------
    # 6. Vector retrieval
    # ---------------------------------------------------------
    retrieval_start = time.perf_counter()

    logger.info(
        "RETRIEVAL_STARTED | request_id=%s | query=%r",
        request_id,
        search_query,
    )

    try:
        docs = store.similarity_search_with_score(
            query=search_query,
            k=retrieval_k,
            query_filter=query_filter,
        )

        # Fallback: if metadata filter returned no results, retry with a relaxed filter.
        if not docs and query_filter is not None:
            from backend.rag.metadata_filter import build_user_session_filter

            if query_metadata.get("company"):
                logger.info(
                    "METADATA_FILTER_FALLBACK_TRIGGERED | request_id=%s "
                    "| original_filter=%s | retrying_with_company_and_user_session_filter=True",
                    request_id,
                    query_filter,
                )

                user_session_filter = build_user_session_filter(
                    current_user=current_user,
                    session_id=request.session_id,
                )

                company_filter = models.FieldCondition(
                    key="company",
                    match=models.MatchValue(value=query_metadata["company"]),
                )

                relaxed_filter = models.Filter(
                    must=[*(user_session_filter.must if user_session_filter else []), company_filter]
                )

                docs = store.similarity_search_with_score(
                    query=search_query,
                    k=retrieval_k,
                    query_filter=relaxed_filter,
                )
            else:
                logger.info(
                    "METADATA_FILTER_FALLBACK_TRIGGERED | request_id=%s "
                    "| original_filter=%s | retrying_with_user_session_filter=True",
                    request_id,
                    query_filter,
                )

                user_session_filter = build_user_session_filter(
                    current_user=current_user,
                    session_id=request.session_id,
                )

                docs = store.similarity_search_with_score(
                    query=search_query,
                    k=retrieval_k,
                    query_filter=user_session_filter,
                )

        logger.info(
            "VECTOR_SEARCH_COMPLETED | request_id=%s "
            "| raw_chunk_count=%d | duration_seconds=%.3f",
            request_id,
            len(docs),
            time.perf_counter() - retrieval_start,
        )
        for rank, (doc, score) in enumerate(docs[:5], start=1):
            logger.info(
                "RAW_RETRIEVED_CHUNK | request_id=%s "
                "| rank=%d | score=%.4f "
                "| document=%s | company=%s "
                "| ticker=%s | year=%s "
                "| year_type=%s | chunk_index=%s "
                "| preview=%r",
                request_id,
                rank,
                float(score),
                doc.metadata.get("document_name"),
                doc.metadata.get("company"),
                doc.metadata.get("ticker"),
                doc.metadata.get("year"),
                type(doc.metadata.get("year")).__name__,
                doc.metadata.get("chunk_index"),
                doc.page_content[:200],
            )

    except Exception:
        logger.exception(
            "RETRIEVAL_FAILED | request_id=%s "
            "| original_query=%r | search_query=%r",
            request_id,
            original_query,
            search_query,
        )

        docs = []

    # ---------------------------------------------------------
    # 6b. Hybrid BM25 + vector re-ranking
    # ---------------------------------------------------------
    if settings.hybrid_search_enabled and request.use_hybrid_search:
        hybrid_start = time.perf_counter()
        try:
            hybrid_searcher = get_hybrid_searcher()
            hybrid_docs = hybrid_searcher.hybrid_search(
                query=search_query,
                query_embedding=None,
                vector_search_results=docs,
                top_k=retrieval_k,
            )
            if hybrid_docs:
                docs = hybrid_docs
                logger.info(
                    "HYBRID_SEARCH_APPLIED | request_id=%s "
                    "| hybrid_doc_count=%d | top_k=%d "
                    "| bm25_weight=%.2f | vector_weight=%.2f",
                    request_id,
                    len(docs),
                    retrieval_k,
                    settings.bm25_weight,
                    settings.vector_weight,
                )
            else:
                logger.info(
                    "HYBRID_SEARCH_SKIPPED | request_id=%s "
                    "| reason=no_hybrid_results",
                    request_id,
                )
        except Exception:
            logger.exception(
                "HYBRID_SEARCH_FAILED | request_id=%s | query=%r",
                request_id,
                search_query,
            )
        finally:
            logger.info(
                "HYBRID_SEARCH_COMPLETED | request_id=%s "
                "| duration_seconds=%.3f",
                request_id,
                time.perf_counter() - hybrid_start,
            )

    elif settings.hybrid_search_enabled:
        logger.info(
            "HYBRID_SEARCH_DISABLED_BY_REQUEST | request_id=%s",
            request_id,
        )

    # ---------------------------------------------------------
    # 7. Soft company/document filtering
    # ---------------------------------------------------------
    before_soft_filter = len(docs)

    metadata_filter_query = {
        "company": None,
        "ticker": None,
    }

    try:
        from backend.rag.metadata_filter import extract_query_metadata

        query_metadata = extract_query_metadata(original_query)
        metadata_filter_query["company"] = query_metadata.get("company")
    except Exception:
        pass

    matched_docs = [
        (doc, score)
        for doc, score in docs
        if query_matches_document(
            original_query,
            doc.metadata,
            query_company=metadata_filter_query["company"],
        )
    ]

    # This is a soft filter:
    # Use matched results only when at least one match is found.
    # Otherwise, preserve the original vector-search results.
    if matched_docs:
        docs = matched_docs
        soft_filter_fallback_used = False
    else:
        soft_filter_fallback_used = True

    logger.info(
        "SOFT_DOCUMENT_FILTER_COMPLETED | request_id=%s "
        "| before=%d | matched=%d | after=%d "
        "| fallback_used=%s",
        request_id,
        before_soft_filter,
        len(matched_docs),
        len(docs),
        soft_filter_fallback_used,
    )
    # ---------------------------------------------------------
    # 8. Safety filtering by user
    # ---------------------------------------------------------
    if current_user:
        before_user_filter = len(docs)

        docs = [
            (doc, score)
            for doc, score in docs
            if doc.metadata.get("user_id") == current_user
        ]

        logger.info(
            "USER_FILTER_COMPLETED | request_id=%s "
            "| user=%s | before=%d | after=%d",
            request_id,
            current_user,
            before_user_filter,
            len(docs),
        )

    # ---------------------------------------------------------
    # 9. Safety filtering by session
    #---------------------------------------------------------
    if request.session_id:
        before_session_filter = len(docs)

        docs = [
            (doc, score)
            for doc, score in docs
            if doc.metadata.get("session_id")
            == request.session_id
        ]

        logger.info(
            "SESSION_FILTER_COMPLETED | request_id=%s "
            "| session_id=%s | before=%d | after=%d",
            request_id,
            request.session_id,
            before_session_filter,
            len(docs),
        )

    # ---------------------------------------------------------
    # 10. Handle "latest" queries
    # ---------------------------------------------------------
    if is_latest_query(original_query):
        before_latest_filter = len(docs)

        docs = filter_latest_documents(docs)

        logger.info(
            "LATEST_FILTER_COMPLETED | request_id=%s "
            "| before=%d | after=%d",
            request_id,
            before_latest_filter,
            len(docs),
        )

    logger.info(
        "RERANK_CANDIDATES_READY | request_id=%s "
        "| candidate_count=%d",
        request_id,
        len(docs),
    )

    # Save original vector results as fallback
    vector_ranked_docs = list(docs)

    # ---------------------------------------------------------
    # 11. Reranking
    # ---------------------------------------------------------
    reranker = get_reranker()

    if (
        settings.enable_reranking
        and reranker is not None
        and docs
    ):
        rerank_start = time.perf_counter()

        try:
            candidate_documents = [
                doc
                for doc, _vector_score in docs
            ]

            docs = reranker.rerank(
                query=search_query,
                documents=candidate_documents,
                top_k=final_top_k,
            )

            logger.info(
                "RERANKING_COMPLETED | request_id=%s "
                "| candidate_count=%d | returned_count=%d "
                "| duration_seconds=%.3f",
                request_id,
                len(candidate_documents),
                len(docs),
                time.perf_counter() - rerank_start,
            )

        except Exception:
            logger.exception(
                "RERANKING_FAILED | request_id=%s | query=%r",
                request_id,
                search_query,
            )

            docs = vector_ranked_docs[:final_top_k]

    else:
        docs = docs[:final_top_k]

        logger.info(
            "RERANKING_SKIPPED | request_id=%s "
            "| enabled=%s | reranker_available=%s "
            "| final_chunk_count=%d",
            request_id,
            settings.enable_reranking,
            reranker is not None,
            len(docs),
        )

    # ---------------------------------------------------------
    # 12. Log final chunks sent to LLM
    # ---------------------------------------------------------
    for rank, (doc, score) in enumerate(
        docs,
        start=1,
    ):
        logger.info(
            "FINAL_RETRIEVED_CHUNK | request_id=%s "
            "| rank=%d | score=%.4f | document=%s "
            "| document_id=%s | chunk_index=%s "
            "| company=%s | year=%s | quarter=%s",
            request_id,
            rank,
            float(score),
            doc.metadata.get("document_name"),
            doc.metadata.get("document_id"),
            doc.metadata.get("chunk_index"),
            doc.metadata.get("company"),
            doc.metadata.get("year"),
            doc.metadata.get("quarter"),
        )
        logger.info(
            "TOP_CHUNK_PREVIEW | request_id=%s | rank=%d | text=%r",
            request_id,
            rank,
            doc.page_content[:250],
        )

    # ---------------------------------------------------------
    # 13. No relevant chunks
    # ---------------------------------------------------------
    if not docs:
        logger.warning(
            "NO_RELEVANT_CHUNKS | request_id=%s "
            "| query=%r | total_seconds=%.3f",
            request_id,
            original_query,
            time.perf_counter() - query_start,
        )

        return QueryResponse(
            query=original_query,
            answer=(
                "I could not find relevant information "
                "in the uploaded documents."
            ),
            citations=[],
            session_id=session_id,
        )

    # ---------------------------------------------------------
    # 14. Build LLM context
    # ---------------------------------------------------------
    context_parts = []

    for rank, (doc, _score) in enumerate(
        docs,
        start=1,
    ):
        context_parts.append(
            f"[Chunk {rank}]\n"
            f"Document: "
            f"{doc.metadata.get('document_name', 'unknown')}\n"
            f"Company: "
            f"{doc.metadata.get('company', 'unknown')}\n"
            f"Year: "
            f"{doc.metadata.get('year', 'unknown')}\n"
            f"Quarter: "
            f"{doc.metadata.get('quarter', 'unknown')}\n"
            f"Text:\n{doc.page_content}"
        )

    context = "\n\n".join(context_parts)

    logger.info(
        "CONTEXT_CREATED | request_id=%s "
        "| chunk_count=%d | context_characters=%d",
        request_id,
        len(docs),
        len(context),
    )

    # ---------------------------------------------------------
    # 15. Prompt
    # ---------------------------------------------------------
    prompt = f"""
You are a careful financial document question-answering assistant.

Answer the user's question using ONLY the uploaded document context below.

Rules:
- Do not use outside knowledge.
- Do not guess or invent missing information.
- Answer only what the user asked.
- If the answer is not clearly supported by the context, say:
  "I could not find this information in the uploaded documents."
- If financial numbers are present, include the exact number and unit.
- Do not mix information from different companies, years, or quarters.
- If several chunks repeat the same information, combine them into one clear answer.
- Keep the answer concise but complete.
- Do not mention the words "context", "retrieved chunks", or "vector search"
  in the final answer.

Uploaded document context:
{context}

User question:
{original_query}

Final answer:
""".strip()

    # ---------------------------------------------------------
    # 16. LLM generation
    # ---------------------------------------------------------
    generation_start = time.perf_counter()

    logger.info(
        "LLM_GENERATION_STARTED | request_id=%s "
        "| model=%s | prompt_characters=%d",
        request_id,
        settings.openai_model,
        len(prompt),
    )

    try:
        llm = get_llm()

        response = llm.invoke(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )

        answer = (
            response.content
            if hasattr(response, "content")
            else str(response)
        )

        answer = str(answer).strip()

        logger.info(
            "ANSWER_GENERATED | request_id=%s "
            "| answer_characters=%d "
            "| duration_seconds=%.3f",
            request_id,
            len(answer),
            time.perf_counter() - generation_start,
        )

    except Exception:
        logger.exception(
            "LLM_GENERATION_FAILED | request_id=%s "
            "| query=%r",
            request_id,
            original_query,
        )

        answer = (
            "I found relevant information in the uploaded "
            "documents, but I could not generate the final answer. "
            f"The most relevant passage is: "
            f"{docs[0][0].page_content[:800]}"
        )

    # ---------------------------------------------------------
    # 17. Build citations
    # ---------------------------------------------------------
    citations = []

    for doc, score in docs:
        citations.append(
            {
                "document_name": doc.metadata.get(
                    "document_name",
                    "unknown",
                ),
                "document_id": doc.metadata.get(
                    "document_id"
                ),
                "chunk_id": doc.metadata.get(
                    "chunk_id"
                ),
                "text": doc.page_content[:400],
                "score": round(
                    float(score),
                    4,
                ),
            }
        )

    # ---------------------------------------------------------
    # 18. Complete request
    # ---------------------------------------------------------
    logger.info(
        "QUESTION_ANSWERING_COMPLETED | request_id=%s "
        "| citation_count=%d | total_seconds=%.3f",
        request_id,
        len(citations),
        time.perf_counter() - query_start,
    )

    return QueryResponse(
        query=original_query,
        answer=answer,
        citations=citations,
        session_id=session_id,
    )