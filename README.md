# RAG Document QA

A simple RAG (Retrieval-Augmented Generation) system for document Q&A using LangChain, LangGraph, FastAPI, Qdrant, and Streamlit.

## Features

- Upload PDF or text documents
- Split documents into semantic chunks
- Store chunk embeddings in Qdrant
- Query documents using natural language
- Generate answers using OpenAI or local free models
- Clean Streamlit frontend with professional UX

## Demo-friendly Deployment

For public deployment and demo use, avoid exposing your OpenAI key by using local models only:

- `EMBEDDING_PROVIDER=sentence_transformers`
- `LLM_PROVIDER=local`

This allows you to deploy safely without sharing any paid API key.

## Setup

1. Create and activate a virtual environment with uv:
   ```bash
   uv venv
   .\.venv\Scripts\activate
   ```

2. Install dependencies with uv:
   ```bash
   uv pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root and configure providers:
   ```env
   # Use local/free models for deployment without OpenAI
   EMBEDDING_PROVIDER=sentence_transformers
   LLM_PROVIDER=local

   # Optional: only set if you want OpenAI support locally
   OPENAI_API_KEY=
   OPENAI_MODEL=gpt-3.5-turbo
   OPENAI_EMBEDDING_MODEL=text-embedding-3-small
   ```

4. (Optional) If you choose OpenAI, add your API key only on your local machine or backend server.

## Running Locally

1. Start the backend:
   ```bash
   uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. Start the frontend in another terminal:
   ```bash
   uv run streamlit run frontend/app.py
   ```

3. Open the Streamlit app in your browser.

## API Endpoints

- `POST /upload` - Upload one document
- `POST /query` - Ask a question against uploaded documents
- `DELETE /delete` - Delete chunks or clear the knowledge base
- `GET /health` - Check backend status

## Notes for GitHub Deployment

- Do not commit `.env` with any API keys.
- Use local/free models for public demos.
- Keep the frontend and backend separated so users cannot access your backend secrets.

## Project Structure

- `backend/` - FastAPI backend and LangChain pipeline
- `frontend/` - Streamlit application
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (not committed)

## Future Improvements

- Multiple-file upload support
- User query history and session tracking
- Document library and metadata management
- Deployment-ready authentication and secure hosting

## How it Works

1. Upload document → backend extracts text
2. Text is chunked into smaller segments
3. Chunks are embedded and stored in Qdrant
4. User asks a question
5. Backend retrieves relevant chunks and generates an answer
6. Frontend displays the answer cleanly
