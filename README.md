<!-- markdownlint-disable MD012 -->
# AI Research Agent

Agentic RAG system for research papers, focused on arXiv-style research workflows. The production chat path is a FastAPI backend wired to `agent/research/` for provider-backed paper discovery, evidence retrieval, grounded synthesis, and a Next.js frontend that streams answers with citations.

The legacy Streamlit proof-of-concept UI has been removed. Use the Next.js app in `web/` for the local UI.

## Features

- **FastAPI API**: Chat, streaming chat, auth, health, and OpenAPI docs.
- **Next.js frontend**: Browser chat UI with streamed answers and citations.
- **Paper discovery**: arXiv, Semantic Scholar, and OpenAlex providers normalized into `PaperCandidate`.
- **Evidence retrieval**: Paper-aware chunks, evidence spans, explainable ranking, and grounded citations.
- **LLM backends**: Ollama, Gemini, or OpenRouter through `agent/generator.py`.

## Quickstart

### 1. Prerequisites

- Python 3.12
- UV installed (`uv --version`)
- Node.js 20+ and npm
- An LLM backend:
  - OpenRouter: set `OPENROUTER_API_KEY` in `.env`
  - Gemini: set `GENAI_API_KEY` in `.env`
  - Ollama: run `ollama serve` and `ollama pull llama3`

### 2. Install dependencies

```bash
make install
```

This runs `uv sync --extra api` for the backend and `npm install` in `web/`.

### 3. Create environment files

```bash
make setup-env
```

Then edit:

- `.env` for backend settings.
- `web/.env.local` for frontend settings.

Important defaults:

- `LLM_BACKEND=openrouter` in `.env.example`
- `NEXT_PUBLIC_API_URL=http://localhost:8000`
- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- `CHROMA_PATH=./chroma`

### 4. Run the full system

```bash
make dev
```

Open:

- Frontend: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

To run services separately:

```bash
make run-api
make run-web
```

### Docker Compose for Durable Memory

For the long-running memory/session stack, run Postgres with pgvector in Docker:

```bash
make setup-env
make compose-db
```

Then set this in `.env` if you run the API locally with `make run-api`:

```bash
PERSISTENT_TRANSCRIPT_ENABLED=true
SESSION_SUMMARY_ENABLED=true
LONG_TERM_MEMORY_ENABLED=true
RESEARCH_MEMORY_ENABLED=true
MEMORY_DATABASE_URL=postgresql://research:research@localhost:5432/research_memory
```

To run both the API and Postgres in Docker:

```bash
make compose-up
```

The compose stack persists Postgres data, Chroma data, and model/provider caches in Docker volumes.

### 5. Ingest papers for local RAG

Run these from the repo root:

```bash
uv run python -m ingest.search --q "retrieval augmented generation OR RAG" --out ./cache/search_results.json --max 5
uv run python -m ingest.crawl --from ./cache/search_results.json --out ./cache/raw
uv run python -m ingest.parse --input ./cache/raw --out ./cache/clean
uv run python -m ingest.index --input ./cache/clean --chroma ./chroma
```

Then ask questions in the Next.js UI, or use the CLI:

```bash
uv run python -m agent.query --chroma ./chroma --q "RAG trends 2025" --k 6
uv run python -m agent.answer --chroma ./chroma --q "Summarize RAG trends in 2024 and 2025" --k 6
```

### 6. Run tests

```bash
uv run pytest tests/ -q
uv run python tests/sanity_mvp.py
```

Some integration tests require a live model/backend and populated local data. Treat import or collection failures as dependency problems; treat model/network failures as environment setup issues.

## Project Structure

```text
ai-research-agent/
├── api/                  # FastAPI app, routes, streaming, schemas
├── agent/                # Research workflow, legacy graph utilities, generator, retrieval
├── ingest/               # Search, crawl, parse, and index CLI modules
├── web/                  # Next.js frontend
├── eval/                 # RAG evaluation scripts
├── tests/                # Unit, routing, graph, and sanity tests
├── cache/                # Local ingest cache
├── chroma/               # Local ChromaDB persistence
├── pyproject.toml        # Python dependencies managed by UV
├── uv.lock               # Locked Python dependency graph
└── Makefile              # Main development commands
```

## Configuration

See `.env.example` for the authoritative backend variables and `web/.env.example` for frontend variables.

## Documentation

Start with [docs/README.md](docs/README.md). It separates current architecture
docs from archived MVP, legacy RAG, and migration notes.

Common settings:

- **Models**: `LLM_BACKEND`, `LLM_MODEL`, `EMBED_MODEL`, `RERANK_MODEL`
- **Providers**: `OPENROUTER_API_KEY`, `GENAI_API_KEY`, `OLLAMA_BASE`
- **Retrieval**: `CHROMA_PATH`, `TOP_K`, `USE_BM25`, `RRF_K`
- **API**: `API_PORT`, `CORS_ORIGINS`

## Troubleshooting

- **`uv: command not found`**: Install UV, then rerun `make install`.
- **Frontend cannot reach API**: Check `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_API_BASE_URL` in `web/.env.local`.
- **No useful citations**: Ingest/index papers first and confirm parsed records preserve `source_url`.
- **Ollama timeout**: Start Ollama, pull the configured model, or increase `OLLAMA_TIMEOUT_SEC`.
- **Slow first run**: `sentence-transformers` and reranker models download on first use.
