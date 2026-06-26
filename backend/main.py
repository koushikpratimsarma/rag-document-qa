from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel
from backend.auth import get_current_user_optional, router as auth_router
from backend.history import add_history, router as history_router

from backend.config import settings
from backend.rag.embeddings import get_embeddings
from backend.rag.pdf_loader import extract_text_from_pdf
from backend.rag.vector_store import get_vector_store_instance as get_qdrant_vector_store_instance

app = FastAPI(title="RAG Document QA Backend")

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = None

class DeleteRequest(BaseModel):
    chunk_ids: Optional[List[str]] = None

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
        # For local models, we'll use a simple approach
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

def get_text_splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.max_chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

# Global instances
vector_store = None
llm = None
text_splitter = None

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

app.include_router(auth_router)
app.include_router(history_router)

@app.on_event("startup")
async def startup_event():
    get_vector_store_instance()
    get_llm_instance()
    get_text_splitter_instance()

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    suffix = Path(file.filename).suffix or ".txt"

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

        # Create metadata for each chunk
        metadatas = [{"filename": file.filename, "chunk_id": str(uuid.uuid4())} for _ in chunks]

        # Use LangChain vector store directly
        get_vector_store_instance().add_texts(texts=chunks, metadatas=metadatas)

        return {"status": "ok", "added_chunks": len(chunks), "document_chunks": [m["chunk_id"] for m in metadatas]}
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

@app.post("/query")
async def query_document(
    request: QueryRequest,
    current_user: str | None = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # Use LangChain vector store for similarity search
        top_k = request.top_k or settings.top_k
        docs = get_vector_store_instance().similarity_search(request.query, k=top_k)

        # Build context from retrieved documents
        if docs:
            context = "\n\n".join([doc.page_content for doc in docs])

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
            if hasattr(llm_instance, 'invoke'):  # LangChain v0.1+
                messages = [{"role": "user", "content": prompt}]
                response = llm_instance.invoke(messages)
                answer = response.content if hasattr(response, 'content') else str(response)
            else:  # Older versions
                answer = llm_instance(prompt)

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
                normalized = "I’m sorry, I could not find enough information in the uploaded documents to answer that question."
            answer = normalized
        else:
            answer = "I apologize, but I could not find relevant information in the documents to answer your question."

        if current_user:
            add_history(current_user, request.query, answer)

        # Prepare response with retrieved chunks
        top_chunks = [
            {
                "id": doc.metadata.get("chunk_id", ""),
                "metadata": doc.metadata,
                "text": doc.page_content
            }
            for doc in docs
        ] if docs else []

        return {
            "query": request.query,
            "top_chunks": top_chunks,
            "answer": answer,
        }
    except Exception as e:
        error_message = str(e)
        if "collection" in error_message.lower() or "empty" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="The knowledge base is currently empty. Please upload a document before asking a question."
            )
        raise HTTPException(status_code=500, detail="An unexpected error occurred while processing your query.")

@app.delete("/delete")
async def delete_chunks(request: DeleteRequest) -> Dict[str, Any]:
    try:
        store = get_vector_store_instance()
        if not request.chunk_ids:
            # Delete entire collection using LangChain
            store.delete_collection()
            global vector_store
            vector_store = None
            return {"status": "ok", "deleted": "all"}
        else:
            # Delete specific documents using LangChain
            store.delete(ids=request.chunk_ids)
            return {"status": "ok", "deleted": len(request.chunk_ids)}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to delete data. Please try again.")

@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy"}

