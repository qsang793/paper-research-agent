# Source Ownership

## Active Production Code

- `api/routes/chat.py`: HTTP and stream protocol adapter.
- `api/main.py`: FastAPI app setup, CORS, lifespan, and route registration.
- `api/models.py`: shared request/response API models.
- `api/streaming.py`: stream protocol helpers shared by API routes.
- `api/routes/health.py`: health and readiness endpoints.
- `api/chat_orchestrator.py`: chat workflow adapter.
- `agent/research/`: canonical research workflow.
- `agent/answerability.py`: legacy answerability gate retained with the LangGraph baseline.
- `agent/memory/`: conversation memory and query context.
- `agent/query_policy.py`: API policy decisions.
- `agent/query_router.py`: static/chat/retrieval route classification.
- `agent/generator.py`: shared LLM provider boundary.
- `agent/sources.py`: source normalization.
- `eval/research_eval.py`: production research eval gate.

## Legacy Candidates

- `agent/graph.py`, `agent/pipeline.py`, `agent/state.py`, `agent/nodes/`: old LangGraph baseline.
- `docs/archive/legacy-ragas/evaluate.py`: archived Ragas evaluation over the old pipeline.

## Optional Experiment Candidates

- `agent/frameworks/llamaindex/`: optional migration prototype, not production.

## Generated Or Local Artifacts

- `.coverage*`
- `chroma/`
- `chroma_v2/`
- `.pytest_cache/`
- `.uv-cache/`
- `.venv/`
- `web/.next/`
- `web/node_modules/`

## User-Owned Local Artifacts

Do not modify without explicit approval:

- `cohere/`
- `lovable-export/`
- `reskin-landing.png`
- `skills/`
- `.codex/`
- `.claude/`
- `.agents/`
