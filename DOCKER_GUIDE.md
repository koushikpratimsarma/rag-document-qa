# Docker Build and Deployment Guide

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+
- Git

## Building Images

### Option 1: Build with Docker Compose (Recommended)

```bash
docker-compose build
```

### Option 2: Build Individual Images

```bash
# Backend
docker build -t rag-backend:latest -f Dockerfile .

# Frontend
docker build -t rag-frontend:latest -f Dockerfile.frontend .
```

## Running the Application

### Using Docker Compose (All Services)

```bash
docker-compose up -d
```

This will start:
- **Backend API**: http://localhost:8000
- **Frontend (Streamlit)**: http://localhost:8501
- **Qdrant Vector Store**: http://localhost:6333

### Using Individual Containers

```bash
# Start Qdrant
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest

# Start Backend
docker run -d --name rag-backend \
  -p 8000:8000 \
  -e EMBEDDING_PROVIDER=sentence_transformers \
  -e LLM_PROVIDER=local \
  -v $(pwd)/data:/app/data \
  rag-backend:latest

# Start Frontend
docker run -d --name rag-frontend \
  -p 8501:8501 \
  -e BACKEND_URL=http://localhost:8000 \
  --network host \
  rag-frontend:latest
```

## Environment Variables

Create a `.env` file in the project root:

```env
# Use local/free models for demo deployment
EMBEDDING_PROVIDER=sentence_transformers
LLM_PROVIDER=local

# OpenAI configuration (optional)
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-3.5-turbo

# Qdrant configuration
QDRANT_API_KEY=your-key-here

# Search settings
HYBRID_SEARCH_ENABLED=true
ENABLE_RERANKING=true

# Server settings
BACKEND_URL=http://localhost:8000
```

## Docker Compose Services

### Backend Service
- **Image**: Built from `Dockerfile`
- **Port**: 8000
- **Volumes**: 
  - `./data:/app/data` - Persistent data storage
  - `./backend:/app/backend` - Code for auto-reload in dev
- **Health Check**: Checks `/health` endpoint every 30s

### Frontend Service
- **Image**: Built from `Dockerfile.frontend`
- **Port**: 8501
- **Depends On**: Backend service (waits for health check)
- **Network**: Connected to backend via `rag_network`

### Qdrant Service
- **Image**: `qdrant/qdrant:latest`
- **Port**: 6333
- **Volumes**: 
  - `./data/qdrant:/qdrant/storage` - Persistent vector database

## Networking

Services communicate via the `rag_network` bridge network:

```
Client Browser
    ↓
Frontend (Streamlit) :8501
    ↓
Backend API :8000
    ↓
Qdrant :6333
```

## Troubleshooting

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f qdrant
```

### Stop Services

```bash
docker-compose down
```

### Remove Volumes (Clear Data)

```bash
docker-compose down -v
```

### Rebuild Without Cache

```bash
docker-compose build --no-cache
```

## Production Deployment

For production deployment:

1. Use secret management (AWS Secrets Manager, HashiCorp Vault, etc.)
2. Set `LLM_PROVIDER=openai` if using OpenAI
3. Use external Qdrant instance instead of container
4. Add reverse proxy (Nginx, Traefik)
5. Enable SSL/TLS certificates
6. Set resource limits in `docker-compose.yml`
7. Configure logging drivers

Example production configuration:

```yaml
backend:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
  restart_policy:
    condition: on-failure
    delay: 5s
    max_attempts: 3
```

## Development Workflow

### Hot Reload Development

The docker-compose configuration supports hot reload:

1. Backend code changes in `./backend` automatically reload (via `--reload`)
2. Frontend code changes in `./frontend` automatically reload

### Building Development Image

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml build
```

## Performance Tuning

- Increase backend memory if processing large documents
- Use external Qdrant for production loads
- Consider GPU acceleration for embeddings/LLM
- Add caching layer (Redis)
- Implement request queuing (Celery)
