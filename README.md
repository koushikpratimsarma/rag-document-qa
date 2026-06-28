# RAG Document QA

A production-ready RAG (Retrieval-Augmented Generation) system for document Q&A with advanced search, authentication, and deployment options.

## ✨ Features

### Core RAG
- Upload PDF or text documents (single & batch)
- Semantic chunking with overlap
- Store embeddings in Qdrant vector database
- Natural language query with intelligent answers
- Support for OpenAI or local free models

### Advanced Search
- **Hybrid Search**: Combines BM25 keyword search with vector similarity
- **Document Re-ranking**: Cross-encoder re-ranking for improved accuracy
- **Metadata Filtering**: Filter results by document type, upload date, user
- Configurable search weights and parameters

### User Features
- User authentication with JWT tokens
- Secure bcrypt password hashing
- Query history tracking
- Conversation session management
- Multi-turn conversation support
- Search history with filtering

### Deployment
- Docker & Docker Compose support
- Professional Streamlit frontend
- RESTful FastAPI backend
- Local or cloud-hosted Qdrant
- Environment-based configuration

## 🚀 Quick Start

### Local Development

1. **Create virtual environment:**
   ```bash
   uv venv
   .\.venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Configure environment** (create `.env` in project root):
   ```env
   # Use local/free models for deployment without OpenAI
   EMBEDDING_PROVIDER=sentence_transformers
   LLM_PROVIDER=local
   
   # Optional: OpenAI support (only on local machine)
   OPENAI_API_KEY=your-key-here
   OPENAI_MODEL=gpt-3.5-turbo
   OPENAI_EMBEDDING_MODEL=text-embedding-3-small
   
   # JWT Configuration
   SECRET_KEY=your-secret-key-change-in-production
   JWT_EXPIRATION_HOURS=24
   
   # Search settings
   HYBRID_SEARCH_ENABLED=true
   ENABLE_RERANKING=true
   BM25_WEIGHT=0.5
   VECTOR_WEIGHT=0.5
   ```

4. **Start backend** (Terminal 1):
   ```bash
   uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Start frontend** (Terminal 2):
   ```bash
   uv run streamlit run frontend/app.py
   ```

6. **Open browser:**
   - Frontend: http://localhost:8501
   - API Docs: http://localhost:8000/docs

### Docker Deployment

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

2. **Access services:**
   - Frontend: http://localhost:8501
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Qdrant: http://localhost:6333

3. **View logs:**
   ```bash
   docker-compose logs -f
   ```

See [DOCKER_GUIDE.md](DOCKER_GUIDE.md) for detailed Docker setup.

## 📚 Project Structure

```
RAG_document_qa/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── auth.py              # JWT authentication
│   ├── config.py            # Configuration management
│   ├── history.py           # Query history & sessions
│   ├── data/                # Persistent data storage
│   └── rag/
│       ├── pdf_loader.py    # PDF extraction
│       ├── embeddings.py    # Embedding models
│       ├── vector_store.py  # Qdrant integration
│       ├── chunking.py      # Text chunking
│       ├── pipeline.py      # RAG pipeline
│       ├── hybrid_search.py # BM25 + Vector search
│       ├── reranker.py      # Cross-encoder re-ranking
│       └── metadata_filter.py # Metadata filtering
├── frontend/
│   └── app.py               # Streamlit UI
├── Dockerfile               # Backend container
├── Dockerfile.frontend      # Frontend container
├── docker-compose.yml       # Multi-container orchestration
├── requirements.txt         # Python dependencies
├── DOCKER_GUIDE.md         # Docker deployment guide
└── README.md               # This file
```

## 🔐 Authentication

### Register New User
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "password123"}'
```

### Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "password123"}'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

## 📤 Document Upload

### Single Document Upload
```bash
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf"
```

### Batch Upload
```bash
curl -X POST http://localhost:8000/upload_batch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@file1.pdf" \
  -F "files=@file2.txt"
```

## ❓ Query Documents

### Basic Query
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"query": "What is the main topic?"}'
```

### Advanced Query with Options
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "What is the main topic?",
    "top_k": 5,
    "use_hybrid_search": true,
    "use_reranking": true,
    "metadata_filters": {
      "document_type": "pdf"
    }
  }'
```

## 📜 Query History & Sessions

### Get Query History
```bash
curl http://localhost:8000/history/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get Conversation Sessions
```bash
curl http://localhost:8000/history/sessions \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get Specific Session
```bash
curl http://localhost:8000/history/session/{session_id} \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Search History
```bash
curl "http://localhost:8000/history/search?q=keyword" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## ⚙️ Configuration

### Environment Variables

```env
# Embedding
EMBEDDING_PROVIDER=sentence_transformers|openai
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# LLM
LLM_PROVIDER=openai|local
LOCAL_GENERATION_MODEL=google/flan-t5-small
OPENAI_MODEL=gpt-3.5-turbo

# Search
HYBRID_SEARCH_ENABLED=true
ENABLE_RERANKING=true
BM25_WEIGHT=0.5          # BM25 score weight (0.0-1.0)
VECTOR_WEIGHT=0.5        # Vector score weight (0.0-1.0)
RERANKING_TOP_K=10       # Retrieve this many before re-ranking

# Chunking
MAX_CHUNK_SIZE=500
CHUNK_OVERLAP=50

# Vector Store
QDRANT_LOCATION=:memory:|/path/to/db
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=optional-key

# Authentication
SECRET_KEY=your-secret-key
JWT_EXPIRATION_HOURS=24
JWT_ALGORITHM=HS256

# Metadata
ENABLE_METADATA_FILTERING=true
```

## 🔍 Search Methods

### Hybrid Search (BM25 + Vector)
Combines keyword-based BM25 search with semantic vector similarity:
- BM25: Term frequency-based ranking
- Vector: Semantic similarity using embeddings
- Combined score = (BM25_weight × BM25_score) + (vector_weight × similarity)

**When to use:** Balance between keyword and semantic matching

### Vector Search Only
Pure semantic similarity based on embeddings.

**When to use:** Finding conceptually related documents

### With Re-ranking
Cross-encoder model re-ranks top-k results for better accuracy.

**Models available:**
- `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (fast, recommended)
- `cross-encoder/qnli-distilroberta-base` (accurate)
- `cross-encoder/ms-marco-MiniLM-L-6-v2` (balanced)

## 📊 Metadata Filtering

Filter documents by:
- **Document Type**: pdf, txt, docx, etc.
- **Upload Date**: Before/after specific date
- **User ID**: Results from specific user
- **Custom Fields**: Any document metadata

### Example
```json
{
  "metadata_filters": {
    "document_type": {"value": "pdf", "operator": "equals"},
    "upload_date": {"value": "2024-01-01", "operator": "gte"}
  }
}
```

## 🎯 Best Practices

### For Better Results
1. **Enable Hybrid Search** for balanced results
2. **Use Re-ranking** for improved accuracy
3. **Add Metadata** to documents for filtering
4. **Adjust Weights** based on your use case
5. **Session Management** for multi-turn conversations

### For Deployment
1. Use external Qdrant for production
2. Set strong `SECRET_KEY`
3. Never commit `.env` with real keys
4. Use environment variables for secrets
5. Enable logging and monitoring
6. Implement rate limiting
7. Use reverse proxy (Nginx, Traefik)
8. Enable CORS for frontend only

### Chunking Strategy
- Smaller chunks (300-400): Better for precise answers
- Larger chunks (600-1000): Better for context
- Overlap (50-150): Helps maintain context across chunks

## 🐛 Troubleshooting

### Qdrant Connection Issues
```bash
# Check if Qdrant is running
curl http://localhost:6333/health

# Check Qdrant logs
docker logs rag_qdrant
```

### High Memory Usage
- Reduce `LOCAL_EMBEDDING_MODEL` to lighter version
- Reduce `RERANKING_TOP_K`
- Use external Qdrant instance
- Limit batch upload size

### Slow Queries
- Enable caching
- Reduce `TOP_K` parameter
- Use lighter re-ranker model
- Optimize chunk size

## 📝 Future Improvements

- [ ] Async document processing
- [ ] Stream responses for long answers
- [ ] Advanced caching (Redis)
- [ ] Celery task queue
- [ ] API rate limiting
- [ ] Web UI authentication improvements
- [ ] Document lifecycle management
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Custom embedding models

## 📄 License

MIT License - feel free to use in production

## 🤝 Contributing

Contributions welcome! Please submit pull requests or issues.

## 📞 Support

For issues or questions:
1. Check troubleshooting section
2. Review Docker guide
3. Check backend API logs
4. Open a GitHub issue

