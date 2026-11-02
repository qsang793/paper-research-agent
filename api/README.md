# AI Research Agent API

RESTful API for the AI Research Agent with provider-backed research workflow capabilities.

## Quick Start

### Installation

```bash
# Install API dependencies
uv sync --extra api
```

### Running the Server

```bash
# Start development server with auto-reload
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Server will be available at:
- API: `http://localhost:8000`
- Swagger Docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Health & Info
app
#### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-06T23:58:54.089256",
  "chroma_status": "connected"
}
```

#### `GET /info`
Get API configuration information.

**Response:**
```json
{
  "embed_model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
  "llm_backend": "openrouter",
  "reranking_enabled": true,
  "rerank_model": "cross-encoder/ms-marco-MiniLM-L-6-v2"
}
```

### Chat

#### `POST /api/chat`
Process user query through policy routing and the canonical research workflow.

**Request Body:**
```json
{
  "query": "What is RAG?",
  "session_id": "user-123",  // optional, auto-generated if not provided
  "top_k": 6                 // optional, default: 6
}
```

**Response:**
```json
{
  "answer": "RAG stands for Retrieval-Augmented Generation...",
  "citations": [
    {
      "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
      "authors": ["Patrick Lewis", "Ethan Perez"],
      "url": "https://arxiv.org/abs/2005.11401",
      "arxiv_id": "2005.11401",
      "relevance_score": 0.95,
      "snippet": "We introduce RAG models..."
    }
  ],
  "session_id": "user-123",
  "response_time_ms": 3450.5,
  "tokens_used": 512
}
```

#### `DELETE /api/session/{session_id}`
Delete a conversation session.

**Response:**
```json
{
  "message": "Session user-123 deleted"
}
```

**Note**: Session deletion is currently in-memory only. Sessions will be lost on server restart.

## Usage Examples

### curl

```bash
# Health check
curl http://localhost:8000/health

# Chat request
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is RAG?",
    "session_id": "test-123",
    "top_k": 6
  }'
```

### Python

```python
import requests

# Chat request
response = requests.post(
    "http://localhost:8000/api/chat",
    json={
        "query": "What is RAG?",
        "session_id": "my-session",
        "top_k": 6
    }
)

result = response.json()
print(f"Answer: {result['answer']}")
print(f"Citations: {len(result['citations'])}")
```

### JavaScript/TypeScript

```typescript
// Using fetch API
const response = await fetch('http://localhost:8000/api/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    query: 'What is RAG?',
    session_id: 'my-session',
    top_k: 6
  })
});

const result = await response.json();
console.log('Answer:', result.answer);
console.log('Citations:', result.citations);
```

## Configuration

Configure via environment variables in `.env`:

```bash
# API Server
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

# LLM & Embeddings
LLM_BACKEND=openrouter
EMBED_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
CHROMA_PATH=./chroma

# Retrieval
TOP_K=6
ENABLE_RERANKING=true
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

## Features

- ✅ **RESTful API** with OpenAPI documentation
- ✅ **Session Management** for multi-turn conversations
- ✅ **CORS Support** for frontend integration
- ✅ **Type Safety** with Pydantic models
- ✅ **Error Handling** with meaningful error messages
- ✅ **Auto-reload** in development mode
- 🚧 **Streaming** support (planned with SSE)
- 🚧 **Authentication** (planned)
- 🚧 **Rate Limiting** (planned)

## Development

### Project Structure

```
api/
├── main.py              # FastAPI app entry point
├── models.py            # Pydantic schemas
├── routes/
│   ├── chat.py         # Chat endpoints
│   └── health.py       # Health/info endpoints
└── streaming.py         # Streaming response helpers
```

### Testing

Use the interactive Swagger UI at `http://localhost:8000/docs` to test all endpoints.

## Next Steps

1. **Frontend Integration**: Connect Next.js frontend to this API
2. **Streaming**: Implement Server-Sent Events for real-time responses
3. **Caching**: Add Redis for session storage and response caching
4. **Monitoring**: Add logging and metrics collection
5. **Deployment**: Dockerize and deploy to production
