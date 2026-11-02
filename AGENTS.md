# AGENTS.md

This repository contains `ai-research-agent`, an agentic research system for papers.
Treat this file as the concise project architecture index; deeper decisions belong in
focused docs such as `docs/stage_4b_gap_review.md` and `docs/research-workflow/`.

## Project Overview

- Backend: FastAPI routes chat through canonical structured routing and `agent/research/`.
- Retrieval: provider-backed paper discovery, evidence extraction, ranking, and grounded synthesis.
- Memory: transcript/session summary/long-term memory through `agent/memory/`, with pgvector/Postgres in production.
- Frontend: Next.js app in `web/` streams answers and citations.
- LLM backends: Ollama, Gemini, and OpenRouter through `agent/generator.py`.

## Core Commands

Prefer the `Makefile` from repo root.

```bash
make help
make install
make setup-env
make dev
make run-api
make run-web
pytest tests/
make eval-research
make eval-research-live
make eval-research-gate
```

Frontend commands run from `web/`:

```bash
npm run dev
npm run build
npm run lint
```

## Canonical Architecture

- **Natural-language routing has one owner:** `agent/query_router.py`.
  - It returns a validated structured result including route, confidence, freshness, `standalone_query`, and optional `memory_write`.
  - Do not add intent example datasets, natural-language phrase lists, or fixed-year classifiers elsewhere.
- **Execution policy is language-agnostic:** `agent/query_policy.py` maps the router result plus explicit UI mode (`auto/chat/search`) to behavior.
- **Production research path:** `api/routes/chat.py` -> `api/chat_orchestrator.py` -> `agent/research/`.
- **Legacy LangGraph path:** `agent/graph.py` / `agent/pipeline.py` remains a compatibility baseline, not the primary research API path. Its intent node consumes the canonical router instead of classifying independently.
- **Memory source of truth:** `agent/memory/` and `PostgresMemoryStore` when configured. The process-local `ConversationMemory`/session registry is compatibility cache only.

## Query / Memory Boundary

This invariant is mandatory:

```text
latest user request + conversation context
              -> structured router
              -> standalone_query
              -> discovery / ranking / evidence retrieval
```

- Conversation transcript, summaries, and durable memories must **never be concatenated into retrieval/search/embedding queries**.
- Use conversation context to resolve follow-ups and preferences, then send only `standalone_query` into research discovery/retrieval.
- Synthesis may receive conversation context separately, but it is **not research evidence**. Factual claims must remain grounded in retrieved evidence/citations.

## Durable Memory Rules

- Persist transcripts and summaries through `ChatTranscriptWriter` / `MemoryStore`.
- Durable long-term memory is written only from an explicit structured `memory_write` decision; do not infer it using ad-hoc phrase lists such as `remember`/`prefer` checks in persistence code.
- When an authenticated `user_id` exists, durable preferences/facts use `scope="user"` so they can be recalled from another session owned by the same user.
- Keep credential/secret filtering in `MemoryWriter`; that is a data-safety rule, not intent classification.
- Session ownership checks must be preserved on all persistent reads/writes.

## Research / Evidence Rules

- `run_research_preview(query=...)` receives a clean standalone retrieval query.
- Original conversational wording can be passed separately as `question` for synthesis.
- Conversation context can be passed separately as `memory_context` for continuity only.
- `source_url` must survive discovery/indexing/synthesis so citations remain traceable.
- Streaming must preserve the Vercel AI SDK UI Message Stream Protocol and `x-vercel-ai-ui-message-stream: v1`.

## Coding Conventions

- Use absolute Python imports such as `from agent.state import AgentState`.
- Configuration comes from `os.getenv`; `.env.example` is the authoritative variable list.
- All model/provider calls go through `agent/generator.py`; do not call provider SDKs directly from orchestration nodes.
- Add deterministic contract tests for boundary changes. Prefer schema/invariant tests over lists of example natural-language phrases.
- Do not silently convert persistent-store failures into empty/new conversation state when correctness depends on the stored context.
- Keep changes scoped to the active architecture instead of reviving archived Streamlit/legacy paths.
- Do not read or print `.env`, keys, tokens, or credentials.

## Key References

- `docs/stage_4b_gap_review.md` — canonical Stage 4B requirement/gap matrix.
- `docs/research-workflow/ARCHITECTURE.md` — research workflow details.
- `docs/adr/ADR-001-production-memory-context.md` — production memory/context decision.
- `CLAUDE.md` — broader project/development notes.
