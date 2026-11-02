# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Agentic RAG system for research papers (arXiv-focused). A **FastAPI** backend routes production chat through `agent/research/` for provider-backed paper discovery, ranking, evidence extraction, and grounded synthesis; a **Next.js** frontend (`web/`) streams answers with citations. LLM calls are backend-agnostic (Ollama / Gemini / OpenRouter).

The older LangGraph pipeline is retained as a legacy baseline only.

## Commands

All commands are driven from the `Makefile` (run `make help` for the full list).

```bash
# Setup
make install           # Backend (UV api extra) + frontend (npm) deps
make setup-env         # Create .env and web/.env.local from templates

# Dependencies: managed by UV (pyproject.toml + uv.lock). `uv sync` builds .venv.
# requirements.txt is auto-exported from the lock (`make export-reqs`) for non-UV use.

# Develop
make dev               # Backend + frontend concurrently
make run-api           # FastAPI on :8000 (uvicorn api.main:app --reload)
make run-web           # Next.js on :3000

# Frontend (from web/)
cd web && npm run dev | npm run build | npm run lint

# Deploy (free workflow)
make tunnel            # Cloudflare Quick Tunnel; auto-updates web/.env.local
make docker-build && make docker-run

# Migration
make migrate-e5        # Re-index ChromaDB to e5-base-v2 (with backup)
```

### Testing

```bash
uv run pytest tests/                          # All Python tests
uv run pytest tests/test_query_router.py      # A single file
uv run pytest tests/test_query_router.py::test_name   # A single test
uv run python tests/sanity_mvp.py             # End-to-end sanity check with pass/fail thresholds
make eval-research                            # Deterministic research workflow eval dry-run
make eval-research-live                       # Live provider eval without promotion thresholds
make eval-research-gate                       # Live provider promotion gate with recall/MRR thresholds
```

Note: many `tests/test_llamaindex_*_phaseN.py` files target the LlamaIndex migration framework, **not** the production research workflow. Phase 2-6 LlamaIndex tests are skipped by default; run them with `RUN_LLAMA_INDEX_OPTIONAL_TESTS=1 uv run pytest tests/test_llamaindex_* -q` after installing optional LlamaIndex Chroma/LLM dependencies.

## Architecture

### Routing and policy (important — don't conflate layers)

1. **API-level router** (`agent/query_router.py`, `RouteType` = `STATIC | LLM_ONLY | RAG`). Runs first in `api/routes/chat.py` to classify greetings/thanks, chitchat/help, and candidate RAG queries. Uses e5-base-v2 embeddings against an intent collection.
2. **Query policy** (`agent/query_policy.py`). Converts API route result + UI mode (`auto | chat | search`) into an explicit `QueryPolicy` with `decision`, `reason`, `confidence`, `source_policy`, and `answer_policy`. It handles `STATIC`, `CHAT`, conservative `OUT_OF_SCOPE`, and retrieval-backed policies before the research workflow is invoked.
3. **Legacy graph-level routing** (`agent/state.py` `route_type` = `kb_only | search | both | search_only`). Decided *inside* the legacy graph by the `route` node and dispatched by `route_decision` in `agent/graph.py`.

### Legacy LangGraph pipeline

`agent/pipeline.py::run_agent_graph` and `agent/pipeline.py::run_agent_retrieval`
are legacy LangGraph entry points retained for historical tests, comparison, and
future archival decisions. They are no longer called by `/api/chat` or
`/api/chat/stream`. Flow defined in `agent/graph.py`:

```
classify_intent → route → ┌ kb_only ───────────────→ retrieve → rerank → check_answerability → generate? → END
                          └ search/search_only/both → search → retrieve → rerank → check_answerability → generate? → END
```

- **State**: `AgentState` (`agent/state.py`, a `TypedDict(total=False)`) is the single source of truth. Each node reads it and returns a dict of **only the keys it owns** — never replace the whole state.
- **Nodes** live in `agent/nodes/` (`intent`, `route`, `search`, `retrieve`, `rerank`, `generate`) plus the answerability gate in `agent/answerability.py`, exported via `agent/nodes/__init__.py`. To add one: create the node, export it, register it in `create_graph()`, and wrap it with `_with_metrics(name, fn)` so per-node timing/counters land in `state["metrics"]`.
- The compiled graph is cached with `@lru_cache` in `pipeline.py`.

### Answerability and sources

- `agent/answerability.py` gates generation after rerank. It writes `answerability` with `can_answer`, `reason`, `evidence_count`, `top_score`, `source_mix`, and `recommended_action`. No-answer reasons include `OUT_OF_SCOPE`, `NO_KB_MATCH`, `NO_SEARCH_RESULTS`, `WEAK_EVIDENCE`, `INFRA_ERROR`, and `NEEDS_CLARIFICATION`.
- `ANSWERABILITY_MIN_RERANK_SCORE` defaults to `-8.0`; tune this before bypassing the gate.
- `agent/sources.py` owns the canonical source shape: `id`, `title`, `url`, `source_type`, `score`, `relevance_score`, `snippet`, `published_at`, `alive_status`, `authors`, `arxiv_id`.
- `agent/citation_validator.py::validate_citation_sources` annotates source dicts with liveness instead of replacing them. API citations and streaming `source-url` events should use this same source list.

### Active and optional RAG implementations

- **Production research workflow** (`agent/research/`) — provider-backed paper
  discovery, paper-aware chunking, explainable ranking, evidence spans, and
  deterministic evals. `/api/chat` and `/api/chat/stream` use this as the
  canonical retrieval-backed chat path. `/api/research/preview` remains the
  dev-facing preview endpoint and is gated by `RESEARCH_WORKFLOW_ENABLED`.
- **Custom LangGraph** (`agent/nodes/`, `agent/graph.py`) — legacy baseline,
  not called by chat routing after Phase 3 legacy retirement.
- **LlamaIndex framework** (`agent/frameworks/llamaindex/`, entry `run_llamaindex_pipeline`) — an optional/in-progress migration target. Per `agent/frameworks/README.md` it is **not wired into production**; `agent/research/` is canonical for chat. See `docs/frameworks/README.md` and `docs/archive/llamaindex-migration/` for historical migration notes.

### LLM backend abstraction

All generation goes through `agent/generator.py::generate_answer`, which dispatches on `LLM_BACKEND` to `call_ollama` / `call_gemini` / `call_openrouter`. Add new capabilities behind this abstraction — don't call providers directly from nodes.

### Ingestion pipeline (`ingest/`, run as modules)

`search` (arXiv/Tavily) → `crawl` (fetch HTML) → `parse` (clean → JSON) → `index` (chunk, embed, upsert to Chroma). Each stage is a CLI: `python -m ingest.search --q "..." --out ...`. `source_url` must survive `parse` or citations break downstream.

### Frontend ↔ backend boundary

- `web/` is Next.js 16 (App Router) + React 19 + Tailwind v4 + next-auth v5 (beta) + Vercel AI SDK.
- It calls the backend at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). Client in `web/src/lib/api.ts`.
- Backend routes: `/api/chat` (non-streaming, `api/routes/chat.py`), `/api/chat/stream` (SSE), `/api/auth/*` (`signup`/`login`/`verify`), `/health`.
- **Streaming uses the Vercel AI SDK v3 UI Message Stream Protocol** — `chat_stream` emits `data:` SSE events of type `start` / `text-start` / `text-delta` / `text-end` / `source-url` / `finish`. Match this format exactly when editing streaming, and keep the `x-vercel-ai-ui-message-stream: v1` response header.

### Sessions & memory

`api/routes/chat.py` holds an **in-process** `sessions: Dict[str, ConversationMemory]` (TODO: Redis). `agent/memory/context.py::inject_memory_context` prepends the last 5 turns + top-2 semantically similar past turns to the query; the *original* query is used as the memory key.

### CORS / deployment

`api/main.py` has a **custom CORS middleware** (`CustomCORSMiddleware`) that handles `OPTIONS` preflight before routing and supports wildcard origins (`*.vercel.app`, `*.trycloudflare.com`) via `CORS_ORIGINS`. Lifespan registers signal/atexit handlers that call `cleanup_resources()` to release ChromaDB, embedding, rerank, and multiprocessing resources.

## Conventions

- **Absolute imports only** (`from agent.state import AgentState`) — everything runs as modules.
- **Config via `os.getenv` with defaults**; load with `dotenv`. `.env.example` is the authoritative list of variables.
- Node functions take `AgentState` → return state-update dict; wrap with `_with_metrics` when registering.

## Gotchas (code vs. README drift)

The root `README.md` is partly stale; trust `.env.example` and the code:
- Default embedding model is **`intfloat/e5-base-v2`** (not `all-MiniLM-L6-v2`).
- Default `LLM_BACKEND` in `.env.example` is **`openrouter`** (free models); code falls back to `ollama` when unset.
- Default reranker is **`BAAI/bge-reranker-base`**.
- Answerability weak-evidence threshold is **`ANSWERABILITY_MIN_RERANK_SCORE=-8.0`** when unset.

---

## Behavioral Guidelines

> Injected from https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md — guidelines to reduce common LLM coding mistakes. They bias toward caution over speed; for trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
