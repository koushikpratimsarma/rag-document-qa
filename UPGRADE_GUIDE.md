# Upgrade Guide - New Features Overview

This guide helps you understand and use the new features added to your RAG system.

## What's New

Your RAG Document QA system has been upgraded with 7 major features:

### ✅ Multiple Document Upload
Upload one or many documents at once. The system automatically detects file types and creates metadata for each document.

**Try it:** 
- Frontend → Upload Documents tab
- Select multiple files → Upload
- See individual status for each file

### ✅ User Authentication
Secure login system with JWT tokens. Create an account, login, and your queries are saved privately.

**Try it:**
- Frontend → Login/Register tabs
- Create account and login
- Your profile appears in top bar

### ✅ Conversation History
All your queries and answers are saved automatically. Browse your history, view past sessions, and search previous queries.

**Try it:**
- Frontend → History tab
- View recent queries
- Click on session to see full conversation

### ✅ Metadata Filtering
Filter documents by type, upload date, or user. Narrow down search results to specific documents.

**Try it:**
- Query Documents tab → Advanced Filters expander
- Select document type
- See filtered results

### ✅ Hybrid Search (BM25 + Vector)
Combines keyword search and semantic search for better results. Now finds both exact matches and conceptually related content.

**Try it:**
- Query Documents tab
- Enable "Hybrid Search" toggle (enabled by default)
- Ask questions - get better results!

### ✅ Document Re-ranking
Advanced AI re-ranks search results by relevance. Puts the most relevant documents first, even if they weren't top in initial search.

**Try it:**
- Query Documents tab
- Enable "Re-ranking" toggle (enabled by default)
- Notice improved answer quality

### ✅ Docker Deployment
Deploy entire system with one command using Docker Compose. Perfect for production and team collaboration.

**Try it:**
```bash
docker-compose up -d
# Visit http://localhost:8501
```

## Quick Configuration

### Local Development (Recommended for Starting)

1. **Update requirements.txt is already done** ✓

2. **Create `.env` file:**
   ```env
   EMBEDDING_PROVIDER=sentence_transformers
   LLM_PROVIDER=local
   HYBRID_SEARCH_ENABLED=true
   ENABLE_RERANKING=true
   SECRET_KEY=your-secret-key-here
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   ```

4. **Run locally:**
   ```bash
   # Terminal 1 - Backend
   uv run uvicorn backend.main:app --reload
   
   # Terminal 2 - Frontend
   uv run streamlit run frontend/app.py
   ```

### Docker Deployment (Recommended for Production)

1. **Build and run:**
   ```bash
   docker-compose up -d
   ```

2. **Access:**
   - Frontend: http://localhost:8501
   - API Docs: http://localhost:8000/docs
   - Qdrant: http://localhost:6333

3. **Stop:**
   ```bash
   docker-compose down
   ```

See [DOCKER_GUIDE.md](DOCKER_GUIDE.md) for advanced Docker usage.

## File Structure Changes

### New Files Created
```
backend/rag/
├── hybrid_search.py       # Hybrid BM25 + Vector search
├── reranker.py            # Document re-ranking module
└── metadata_filter.py     # Metadata filtering

Docker Files:
├── Dockerfile             # Backend container
├── Dockerfile.frontend    # Frontend container
└── docker-compose.yml     # Multi-container setup

Documentation:
├── FEATURES.md            # Detailed feature guide
└── DOCKER_GUIDE.md        # Docker deployment guide
```

### Updated Files
```
backend/
├── main.py                # New API endpoints
├── auth.py                # JWT authentication
├── config.py              # New configuration options
└── history.py             # Session tracking

frontend/
└── app.py                 # New UI tabs and features

requirements.txt           # New dependencies
README.md                  # Updated docs
```

## API Changes

### New Endpoints

**Authentication:**
```
POST /auth/register        - Create account
POST /auth/login           - Login and get token
GET /auth/me               - Your profile
```

**Advanced Query:**
```
POST /query                - Now with optional parameters:
                            - use_hybrid_search
                            - use_reranking
                            - metadata_filters
                            - session_id
```

**Batch Upload:**
```
POST /upload_batch         - Upload multiple files
```

**History:**
```
GET /history/              - Your query history
GET /history/sessions      - Your conversation sessions
POST /history/clear        - Clear all history
GET /history/search        - Search past queries
```

### Example: Using New Features

**Before (Simple Query):**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this about?"}'
```

**After (With All Features):**
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is this about?",
    "use_hybrid_search": true,
    "use_reranking": true,
    "metadata_filters": {
      "document_type": "pdf"
    }
  }'
```

## Feature Tuning

### Hybrid Search Weight Adjustment

In `.env`:
```env
BM25_WEIGHT=0.5        # Increase for keyword-focused (0.0-1.0)
VECTOR_WEIGHT=0.5      # Increase for semantic (0.0-1.0)
```

**Examples:**
- `BM25=0.7, VECTOR=0.3` → More keyword matching
- `BM25=0.3, VECTOR=0.7` → More semantic matching
- `BM25=0.5, VECTOR=0.5` → Balanced (recommended)

### Re-ranking Configuration

```env
ENABLE_RERANKING=true           # Enable/disable
RERANKER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
RERANKING_TOP_K=10              # Retrieve 10, then re-rank
```

### Search Top-K

```json
// In query request
{
  "query": "Your question",
  "top_k": 5              // Return top 5 results
}
```

## Security Considerations

1. **API Key Management:**
   - Never commit `.env` to git
   - Use environment variables in production
   - Rotate `SECRET_KEY` regularly

2. **Authentication:**
   - Passwords hashed with bcrypt (not MD5)
   - JWT tokens expire after 24 hours (configurable)
   - Change `SECRET_KEY` in production

3. **Deployment:**
   - Use HTTPS in production
   - Add reverse proxy (Nginx)
   - Implement rate limiting
   - Use environment-based secrets

## Performance Tips

1. **Faster Queries:**
   - Set `top_k=3` instead of default 5
   - Disable re-ranking if not needed
   - Use smaller re-ranker model

2. **Faster Uploads:**
   - Process documents in batches
   - Use smaller chunk sizes
   - Consider async processing

3. **Reduce Memory:**
   - Use `sentence-transformers/all-MiniLM-L6-v2` (lightweight)
   - Reduce `RERANKING_TOP_K` to 5
   - Clear history periodically

## Testing the New System

### 1. Full Workflow Test

```bash
# 1. Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test123"}'

# Save the token from response

# 2. Upload document
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -F "file=@sample.pdf"

# 3. Query with all options
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Main topic?",
    "use_hybrid_search": true,
    "use_reranking": true
  }'

# 4. View history
curl http://localhost:8000/history/ \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

### 2. Comparing Search Methods

Ask same question with different settings:

```bash
# Method 1: Hybrid + Re-ranking (Default)
{
  "query": "What is X?",
  "use_hybrid_search": true,
  "use_reranking": true
}

# Method 2: Vector only
{
  "query": "What is X?",
  "use_hybrid_search": false,
  "use_reranking": false
}

# Method 3: Hybrid without re-ranking
{
  "query": "What is X?",
  "use_hybrid_search": true,
  "use_reranking": false
}
```

Compare results to see which works best for your use case.

## Troubleshooting

### Model Download on First Run
First use downloads ~500MB of models. This is normal and takes 2-5 minutes.

**Solution:** Wait for download to complete, or disable re-ranking:
```env
ENABLE_RERANKING=false
```

### Memory Issues
If system uses too much memory:

```env
ENABLE_RERANKING=false
RERANKING_TOP_K=5
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Docker Issues
```bash
# View logs
docker-compose logs -f backend

# Rebuild
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

See [DOCKER_GUIDE.md](DOCKER_GUIDE.md) for more help.

## Next Steps

1. **Try all features** in the frontend
2. **Read [FEATURES.md](FEATURES.md)** for detailed documentation
3. **Deploy with Docker** using [DOCKER_GUIDE.md](DOCKER_GUIDE.md)
4. **Configure settings** in `.env` for your needs
5. **Test API** with your own documents and queries

## Support

For issues or questions:
1. Check [FEATURES.md](FEATURES.md)
2. Check [DOCKER_GUIDE.md](DOCKER_GUIDE.md)
3. View logs: `docker-compose logs`
4. Review [README.md](README.md)

## Version Info

**Upgraded System:**
- ✅ Multiple document upload
- ✅ User authentication with JWT
- ✅ Conversation history & sessions
- ✅ Metadata filtering
- ✅ Hybrid search (BM25 + Vector)
- ✅ Document re-ranking
- ✅ Docker deployment

**Dependencies Added:**
- `python-jose[cryptography]` - JWT tokens
- `passlib[bcrypt]` - Password hashing
- `rank-bm25` - BM25 keyword search
- `aiofiles` - Async file operations

Enjoy your improved RAG system! 🚀
