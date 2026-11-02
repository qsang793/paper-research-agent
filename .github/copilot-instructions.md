# AI Research Agent - Copilot Instructions

## Current Architecture

This repository is an AI/ML research assistant with a **FastAPI + Next.js** product surface, a provider-backed paper research workflow under `agent/research/`, and persistent conversation memory under `agent/memory/`.

The custom LangGraph code under `agent/graph.py` remains a compatibility/legacy path. Do not treat it as the primary production API architecture.

## Ownership Boundaries

### Routing

- `agent/query_router.py` is the **only natural-language routing/classification layer**.
- It produces a structured decision including route type, confidence, freshness, `standalone_query`, and optional `memory_write`.
- `agent/query_policy.py` is deterministic execution policy only. It may honor explicit product controls such as `mode=chat` or `mode=search`, but must not maintain language phrase lists.
- Do not reintroduce:
  - embedding/Chroma intent-example collections;
  - `DOMAIN_TERMS` / `OUT_OF_SCOPE_TERMS`-style phrase lists;
  - separate `fresh/known/mixed` keyword classifiers;
  - fixed years such as 2024/2025 for freshness detection.
- The legacy `agent/nodes/intent.py` is only an adapter over the canonical router.

### Query and context

Keep these concepts separate:

- original/current user request: conversational wording;
- `standalone_query`: self-contained text used for discovery/retrieval;
- `memory_context`: transcript/summary/user-memory context used for continuity;
- retrieved evidence: the only factual grounding source for research answers.

Conversation context must **not** be concatenated into embedding, provider-search, paper-discovery, ranking, or evidence-retrieval queries.

Production research flow:

```text
request
  -> memory context assembly
  -> structured router / standalone-query rewrite
  -> language-agnostic query policy
  -> paper discovery/ranking/evidence retrieval using standalone_query
  -> synthesis using original question + memory_context + retrieved evidence
```

### Memory

- Persistent transcript/session summary/long-term memory lives in `agent/memory/`.
- Production durable storage is `PostgresMemoryStore` (pgvector/Postgres setup is exercised in CI).
- The in-process `ConversationMemory` and `SessionRegistry` are compatibility caches only.
- `ChatTranscriptWriter` persists conversation turns.
- Long-term memory writes come from explicit structured `memory_write`; do not scan raw queries for ad-hoc cue phrases.
- Authenticated durable facts/preferences should use `scope="user"` so they can be recalled across sessions belonging to the same user.
- Preserve source-message/user ownership validation and sensitive credential filtering.

### Research workflow

- Active path: `api/routes/chat.py` -> `api/chat_orchestrator.py` -> `agent/research/`.
- `run_research_preview(query=...)` receives the clean standalone retrieval query.
- Pass conversational wording as `question` and conversation continuity as `memory_context` separately.
- Conversation memory is not research evidence. Factual claims remain grounded in evidence spans/citations.
- Preserve `source_url` metadata through the entire source/evidence/synthesis path.

## Development and Verification

Prefer repo-root Makefile commands and the locked `uv` environment.

```bash
make install
make dev
make run-api
make run-web
pytest tests/
make eval-research
```

Frontend from `web/`:

```bash
npm ci
npm run lint
npx tsc --noEmit
npm run build
```

CI is the production contract and includes:

- Python compile and deterministic backend/research tests;
- conversational-memory evaluation dataset validation;
- real pgvector/Postgres memory integration;
- frontend contract tests, lint, typecheck, and production build;
- Docker image build and booted `/health` smoke test.

## Coding Conventions

- Use absolute imports (`from agent...`).
- Configuration is environment-driven; update `.env.example` when adding variables.
- All provider/model calls go through `agent/generator.py`.
- Prefer typed/validated schemas and invariant tests over growing lists of natural-language examples.
- Do not swallow persistent-state failures when that could silently reset/lose a conversation.
- Do not revive removed Streamlit architecture or archived legacy workflows as production paths.
- Keep secrets out of code, logs, tests, and prompts.

## References

- `AGENTS.md`
- `docs/stage_4b_gap_review.md`
- `docs/research-workflow/ARCHITECTURE.md`
- `docs/adr/ADR-001-production-memory-context.md`
