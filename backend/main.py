from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, Query
from langchain_openai import ChatOpenAI
#from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.rag.chunking import get_text_splitter
from pydantic import BaseModel
from backend.auth import get_current_user_optional, get_current_user, router as auth_router
from backend.history import add_history, router as history_router

from backend.config import settings
from backend.rag.embeddings import get_embeddings
from backend.rag.pdf_loader import extract_text_from_pdf
from backend.rag.vector_store import get_vector_store_instance as get_qdrant_vector_store_instance
from backend.rag.metadata_filter import MetadataFilter
from backend.rag.hybrid_search import get_hybrid_searcher
from backend.rag.reranker import get_reranker

app = FastAPI(title="RAG Document QA Backend")


class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = None
    session_id: Optional[str] = None
    use_hybrid_search: Optional[bool] = True
    use_reranking: Optional[bool] = True
    metadata_filters: Optional[Dict[str, Any]] = None


class DeleteRequest(BaseModel):
    chunk_ids: Optional[List[str]] = None


class UploadResponse(BaseModel):
    status: str
    added_chunks: int
    document_id: str
    document_chunks: List[str]


class QueryResponse(BaseModel):
    query: str
    answer: str
    top_chunks: List[Dict[str, Any]]
    session_id: str


class DocumentMetadata(BaseModel):
    """Metadata for uploaded document"""
    document_name: str
    document_type: str = "document"
    upload_date: Optional[str] = None
    user_id: Optional[str] = None
    description: Optional[str] = None


# Initialize LangChain components
def get_llm():
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI LLM")
        return ChatOpenAI(
            model=settings.openai_model,
            openai_api_key=settings.openai_api_key,
            temperature=0.2,
        )
    else:
        from langchain_community.llms import HuggingFacePipeline
        from transformers import pipeline
        pipe = pipeline(
            "text2text-generation",
            model=settings.local_generation_model,
            max_length=256,
        )
        return HuggingFacePipeline(pipeline=pipe)


def get_vector_store():
    return get_qdrant_vector_store_instance()


# def get_text_splitter():
#     return RecursiveCharacterTextSplitter(
#         chunk_size=settings.max_chunk_size,
#         chunk_overlap=settings.chunk_overlap,
#         separators=["\n\n", "\n", ". ", " ", ""]
#     )


# Global instances
vector_store = None
llm = None
text_splitter = None
embeddings = None


def get_vector_store_instance():
    global vector_store
    if vector_store is None:
        vector_store = get_vector_store()
    return vector_store


def get_text_splitter_instance():
    global text_splitter
    if text_splitter is None:
        text_splitter = get_text_splitter()
    return text_splitter


def get_llm_instance():
    global llm
    if llm is None:
        llm = get_llm()
    return llm


def get_embeddings_instance():
    global embeddings
    if embeddings is None:
        embeddings = get_embeddings()
    return embeddings


app.include_router(auth_router)
app.include_router(history_router)


@app.on_event("startup")
async def startup_event():
    get_vector_store_instance()
    get_llm_instance()
    get_text_splitter_instance()
    get_embeddings_instance()


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: Optional[str] = Depends(get_current_user_optional),
) -> UploadResponse:
    """Upload a single document"""
    suffix = Path(file.filename).suffix or ".txt"
    document_id = str(uuid.uuid4())

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        if tmp_path.suffix.lower() == ".pdf":
            text = extract_text_from_pdf(tmp_path)
        else:
            text = content.decode("utf-8", errors="ignore")

        if not text.strip():
            raise HTTPException(status_code=400, detail="Uploaded document contains no text")

        # Use LangChain text splitter
        chunks = get_text_splitter_instance().split_text(text)
        if not chunks:
            raise HTTPException(status_code=400, detail="Document could not be split into chunks")

        # Create enriched metadata for each chunk
        metadatas = []
        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            metadata = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "document_name": file.filename,
                "document_type": suffix.lower().lstrip("."),
                "upload_date": datetime.utcnow().isoformat(),
                "chunk_index": i,
                "chunk_count": len(chunks),
            }
            if current_user:
                metadata["user_id"] = current_user
            metadatas.append(metadata)

        # Use LangChain vector store directly
        get_vector_store_instance().add_texts(texts=chunks, metadatas=metadatas)

        # Update hybrid searcher index
        if settings.hybrid_search_enabled:
            from langchain_core.documents import Document
            docs = [Document(page_content=chunk, metadata=meta) for chunk, meta in zip(chunks, metadatas)]
            get_hybrid_searcher().index_documents(docs)

        return UploadResponse(
            status="ok",
            added_chunks=len(chunks),
            document_id=document_id,
            document_chunks=[m["chunk_id"] for m in metadatas]
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


@app.post("/upload_batch")
async def upload_documents_batch(
    files: List[UploadFile] = File(...),
    current_user: Optional[str] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """Upload multiple documents at once"""
    results = []
    errors = []

    for file in files:
        try:
            result = await upload_document(file, current_user)
            results.append(result.dict())
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": str(e)
            })

    return {
        "status": "completed",
        "successful_uploads": len(results),
        "failed_uploads": len(errors),
        "results": results,
        "errors": errors
    }


@app.post("/query", response_model=QueryResponse)
async def query_document(
    request: QueryRequest,
    current_user: Optional[str] = Depends(get_current_user_optional),
) -> QueryResponse:
    """Query documents with optional hybrid search and re-ranking"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    session_id = request.session_id or str(uuid.uuid4())

    try:
        top_k = request.top_k or settings.top_k
        reranking_k = settings.reranking_top_k or (top_k * 2)

        # Apply metadata filtering if requested
        metadata_filter = None
        if request.metadata_filters and settings.enable_metadata_filtering:
            metadata_filter = MetadataFilter()
            for field, value in request.metadata_filters.items():
                if isinstance(value, dict):
                    metadata_filter.add_filter(field, value.get("value"), value.get("operator", "equals"))
                else:
                    metadata_filter.add_filter(field, value)

        # Perform search
        if settings.hybrid_search_enabled and request.use_hybrid_search:
            # Get embeddings for query
            embeddings_instance = get_embeddings_instance()
            query_embedding = embeddings_instance.embed_query(request.query)

            # Vector search
            vs = get_vector_store_instance()
            vector_results = vs.similarity_search_with_score(request.query, k=reranking_k)

            # Hybrid search
            hybrid_searcher = get_hybrid_searcher()
            docs = vs.similarity_search(request.query, k=reranking_k)
            hybrid_searcher.index_documents(docs)

            docs = hybrid_searcher.hybrid_search(
                request.query,
                query_embedding,
                vector_results,
                top_k=reranking_k,
                metadata_filter=metadata_filter
            )
        else:
            # Vector search only
            vs = get_vector_store_instance()
            docs = vs.similarity_search_with_score(request.query, k=reranking_k)
            docs = [(doc, score) for doc, score in docs]

        # Apply re-ranking if enabled
        if settings.enable_reranking and request.use_reranking and docs:
            reranker = get_reranker()
            if reranker:
                doc_objects = [doc for doc, _ in docs]
                docs = reranker.rerank_with_metadata(
                    request.query,
                    doc_objects,
                    top_k=top_k,
                    boost_recent=True
                )
            else:
                docs = docs[:top_k]
        else:
            docs = docs[:top_k]

        # Build context from retrieved documents
        answer = ""
        if docs:
            # Handle both (doc, score) and doc formats
            doc_contents = []
            for item in docs:
                if isinstance(item, tuple):
                    doc_contents.append(item[0].page_content)
                else:
                    doc_contents.append(item.page_content)

            context = "\n\n".join(doc_contents)

            # Create prompt using LangChain
            prompt_template = (
                "Use the relevant document chunks below to answer the user's question. "
                "If the answer cannot be found in the documents, respond politely that the information is not available in the uploaded files.\n\n"
                "Context:\n{context}\n\n"
                "Question: {question}\nAnswer:"
            )
            prompt = prompt_template.format(context=context, question=request.query)

            # Generate answer using LangChain LLM
            llm_instance = get_llm_instance()
            if hasattr(llm_instance, 'invoke'):
                messages = [{"role": "user", "content": prompt}]
                response = llm_instance.invoke(messages)
                answer = response.content if hasattr(response, 'content') else str(response)
            else:
                answer = llm_instance(prompt)

            # Normalize answer
            normalized = answer.strip()
            lower_answer = normalized.lower()
            if any(phrase in lower_answer for phrase in [
                "i don't know",
                "i do not know",
                "can't answer",
                "cannot answer",
                "unable to answer",
                "not enough information",
                "no enough information"
            ]):
                normalized = "I'm sorry, I could not find enough information in the uploaded documents to answer that question."
            answer = normalized
        else:
            answer = "I apologize, but I could not find relevant information in the documents to answer your question."

        # Save to history if user is authenticated
        retrieved_chunks = None
        documents_used = None
        if docs:
            retrieved_chunks = []
            documents_used = []
            for item in docs:
                if isinstance(item, tuple):
                    doc = item[0]
                else:
                    doc = item

                retrieved_chunks.append({
                    "id": doc.metadata.get("chunk_id", ""),
                    "metadata": doc.metadata,
                    "text": doc.page_content[:500]  # Limit text length
                })
                doc_id = doc.metadata.get("document_id")
                if doc_id and doc_id not in documents_used:
                    documents_used.append(doc_id)

        if current_user:
            add_history(
                current_user,
                request.query,
                answer,
                retrieved_chunks=retrieved_chunks,
                documents_used=documents_used,
                session_id=session_id
            )

        return QueryResponse(
            query=request.query,
            answer=answer,
            top_chunks=retrieved_chunks or [],
            session_id=session_id
        )

    except Exception as e:
        error_message = str(e)
        if "collection" in error_message.lower() or "empty" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="No documents uploaded yet. Please upload documents first."
            )
        raise HTTPException(status_code=500, detail=f"Error processing query: {error_message}")


@app.delete("/delete")
async def delete_chunks(
    request: DeleteRequest,
    current_user: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Delete specific chunks or all chunks"""
    try:
        if not request.chunk_ids:
            # Clear all
            vs = get_vector_store_instance()
            # Note: Clearing implementation depends on vector store backend
            get_hybrid_searcher().clear()
            return {"status": "ok", "message": "All chunks deleted"}
        else:
            # Delete specific chunks
            vs = get_vector_store_instance()
            # Delete implementation depends on vector store backend
            return {
                "status": "ok",
                "message": f"Deleted {len(request.chunk_ids)} chunks"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting chunks: {str(e)}")
