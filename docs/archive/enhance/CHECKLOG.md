# Enhancement Checklog

This file is the shared decision and progress log for the RAG logic enhancement.
Future AI agents should read and update this file before and after work.

## Current Snapshot

**Date:** 2026-05-31
**Plan status:** Implemented and verified
**Active production RAG path:** custom LangGraph in `agent/graph.py` and
`agent/nodes/`
**Non-production path:** `agent/frameworks/llamaindex/` remains optional and
should not be wired into production unless a separate migration plan is approved.

## Findings Addressed From Review

- `agent/citation_validator.py` had an indentation syntax error around URL
  validation result handling.
- `search_source` was used by frontend/API/retrieval logic but was not fully wired
  through request schema and `run_agent_graph`.
- API-level routing and graph-level routing are separate, but their decision
  semantics overlap and are easy to confuse.
- Out-of-domain questions defaulted toward RAG/search instead of a clear
  out-of-scope response.
- Low KB confidence routed toward search, but low confidence can also
  mean out-of-domain, empty DB, weak evidence, or infra failure.
- `generate_node` could fall back to raw search results if merged snippets were
  empty, which can produce answers from weak evidence.
- Streaming path could generate twice: graph generation first, then streamed
  generation.
- Citation/source shape was inconsistent between agent state, API response, and
  streaming source events.

## Decisions

| Date | Decision | Rationale | Status |
|------|----------|-----------|--------|
| 2026-05-31 | Use `docs/enhance/` as the planning folder. | Keeps enhancement work separate from historical stage docs and LlamaIndex migration docs. | Accepted |
| 2026-05-31 | Keep custom LangGraph as the canonical production path. | `CLAUDE.md` states LlamaIndex is optional/in-progress, not wired into production. | Accepted |
| 2026-05-31 | Add an explicit query policy model before deeper routing changes. | Current route enums overlap and hide important cases like out-of-domain and no-source. | Accepted |
| 2026-05-31 | Add answerability before generation. | Evidence quality should decide whether generation is allowed. | Accepted |
| 2026-05-31 | Normalize source/citation shape. | API and streaming currently expect structured citations, while validator output can be strings. | Accepted |
| 2026-05-31 | Split streaming retrieval from generation. | Streaming should not generate once inside the graph and again in `stream_answer`. | Accepted |
| 2026-05-31 | Use `SearchSource` enum in `api.models.ChatRequest`. | Keeps API parsing strict while preserving `.value` usage in chat routes. | Accepted |
| 2026-05-31 | Keep query router unit tests model-free with fake intent collection. | Prevents Chroma/ONNX/model startup failures from breaking pure routing tests. | Accepted |
| 2026-05-31 | Manual `chat` maps to LLM-only and bypasses retrieval. | The UI mode is an explicit user override and should not spend retrieval/search work. | Accepted |
| 2026-05-31 | Manual `search` maps to hybrid retrieval but still goes through answerability. | Users can force retrieval, but weak/no evidence must still block generation. | Accepted |
| 2026-05-31 | Use `ANSWERABILITY_MIN_RERANK_SCORE` for weak-evidence tuning, default `-8.0`. | Existing rerankers can emit negative scores; the gate should be tunable without code edits. | Accepted |
| 2026-05-31 | Use `create_retrieval_graph()` plus `run_agent_retrieval()` for streaming. | Streaming needs retrieval/rerank/answerability without pre-generating a non-streamed answer. | Accepted |
| 2026-05-31 | Keep citation liveness synchronous for now. | This preserves the current response contract; async cached liveness is a future performance improvement. | Accepted |
| 2026-05-31 | Keep LlamaIndex Phase 2-6 tests optional behind `RUN_LLAMA_INDEX_OPTIONAL_TESTS=1`. | They require optional migration dependencies, external model/API configuration, or async plugins and are not part of the active production path. | Accepted |
| 2026-05-31 | Preserve `expand_query(..., llm=..., embedder=...)` and `dedup_queries()` compatibility hooks. | Existing Stage 2 search tests rely on pure unit hooks for query expansion without real LLM/search calls. | Accepted |
| 2026-05-31 | Rename optional LlamaIndex graph node id from `intent` to `classify_intent`. | Newer LangGraph rejects node ids that collide with `AgentState` keys. | Accepted |
| 2026-05-31 | Force the intent router collection to use `E5EmbeddingFunction` and rebuild stale intent collections. | Chroma's default ONNX MiniLM embedding can trigger macOS CoreML runtime failures and creates the wrong dimensions for the E5 intent router. | Accepted |

## Progress

- [x] Created enhancement planning folder.
- [x] Drafted multi-step implementation plan.
- [x] Captured initial decisions and findings.
- [x] Step 1 complete: repair blockers and contracts.
- [x] Step 2 complete: query policy model.
- [x] Step 3 complete: normalized source/citation shape.
- [x] Step 4 complete: answerability gate.
- [x] Step 5 complete: streaming/non-streaming generation cleanup.
- [x] Step 6 complete: edge-case test matrix.
- [x] Step 7 complete: docs and final handoff update.

## Implementation Notes

- Query policy lives in `agent/query_policy.py`. `api/routes/chat.py` now asks
  `agent/query_router.py` for the low-level route result, then converts it into
  a `QueryPolicy`.
- Answerability lives in `agent/answerability.py` and is registered as
  `check_answerability` in `agent/graph.py`; the metrics label remains
  `answerability`.
- Canonical source conversion lives in `agent/sources.py`.
  `validate_citation_sources()` annotates source dictionaries with
  `alive_status` rather than replacing them with strings.
- Streaming uses `run_agent_retrieval()` and then calls `stream_answer()` once.
  Non-streaming still uses `run_agent_graph()`, which runs the same retrieval,
  rerank, and answerability path before `generate`.
- Current out-of-scope detection is deliberately conservative and based on
  obvious unrelated terms unless domain terms are present.
- `intents_e5` is a derived cache. If its metadata does not match the E5 router
  marker, `EmbeddingQueryRouter` deletes and reseeds it with `E5EmbeddingFunction`
  to avoid Chroma's default ONNX embedding path.
- LlamaIndex migration tests Phase 2-6 are skipped by default in
  `tests/conftest.py`. Run them explicitly with
  `RUN_LLAMA_INDEX_OPTIONAL_TESTS=1 uv run pytest tests/test_llamaindex_* -q`
  after installing optional LlamaIndex Chroma/LLM dependencies.

## Suggested No-Answer Reasons

Use explicit reason codes instead of generic "Chua du nguon" everywhere:

- `OUT_OF_SCOPE`: query is outside AI/ML/research-assistant scope.
- `NO_KB_MATCH`: query is in-domain but local DB has no matching source.
- `NO_SEARCH_RESULTS`: external search was allowed but returned nothing usable.
- `WEAK_EVIDENCE`: retrieval returned sources, but scores/source quality are too low.
- `INFRA_ERROR`: retrieval/search/model dependency failed.
- `NEEDS_CLARIFICATION`: query is too broad or ambiguous to retrieve reliably.

## Troubleshooting No-Answer Outcomes

- `OUT_OF_SCOPE`: edit `DOMAIN_TERMS` / `OUT_OF_SCOPE_TERMS` in
  `agent/query_policy.py` if the product scope changes.
- `NO_KB_MATCH`: inspect Chroma collection health and ingestion coverage; this
  means no usable local snippets survived retrieval.
- `NO_SEARCH_RESULTS`: inspect arXiv/Tavily configuration, network access, and
  `search_source`.
- `WEAK_EVIDENCE`: tune `ANSWERABILITY_MIN_RERANK_SCORE` or reranker settings;
  do not bypass the gate unless there is a measured eval reason.
- `INFRA_ERROR`: inspect `state["error"]` from the graph and backend logs.

## Open Questions

- Product boundary is currently AI/ML/research-assistant oriented. Broader
  research scope should update `agent/query_policy.py` and this checklog.
- Automatic web/arXiv expansion for all missing-KB in-domain questions still
  needs product confirmation; the current implementation preserves existing
  graph routing behavior instead of adding a new confirmation UX.
- Async cached citation liveness remains a future optimization.

## Agent Handoff Protocol

At the start of a new session:

1. Read `CLAUDE.md`.
2. Read this file.
3. Read `docs/enhance/IMPLEMENTATION_PLAN.md`.
4. Check `git status --short` and avoid overwriting unrelated user changes.
5. Pick exactly one step unless the user asks for a broader batch.

At the end of a session:

1. Update the `Progress` section.
2. Add any new decisions to the `Decisions` table.
3. Add blockers or changed assumptions under `Open Questions`.
4. Record verification commands run and whether they passed.

## Verification Log

| Date | Command | Result | Notes |
|------|---------|--------|-------|
| 2026-05-31 | `pytest tests/test_query_router.py tests/test_stage2_intent.py -q` | Failed at collection | Missing `sentence_transformers` in active interpreter and `IndentationError` in `agent/citation_validator.py`. |
| 2026-05-31 | `uv run python -m py_compile agent/citation_validator.py api/models.py agent/pipeline.py` | Passed | Uses uv-managed Python after uv migration. |
| 2026-05-31 | `uv run pytest tests/test_stage2_intent.py tests/test_query_router.py tests/test_chat_contract.py -q` | Passed | 59 passed, 3 warnings from existing Pydantic/LangGraph deprecations. |
| 2026-05-31 | `uv run pytest tests/test_query_policy.py tests/test_sources.py tests/test_citation_validator.py tests/test_answerability.py tests/test_chat_streaming.py -q` | Passed | 13 passed, 3 warnings. |
| 2026-05-31 | `uv run pytest tests/test_graph_construction.py tests/test_stage2_graph.py tests/test_stage2_scenarios.py -q` | Passed | 11 passed, 10 warnings. |
| 2026-05-31 | `uv run pytest tests/test_query_policy.py tests/test_answerability.py tests/test_chat_contract.py tests/test_sources.py tests/test_citation_validator.py tests/test_chat_streaming.py tests/test_edge_case_matrix.py -q` | Passed | 25 passed, 3 warnings. |
| 2026-05-31 | `uv run pytest tests/test_graph_construction.py tests/test_stage2_graph.py tests/test_stage2_scenarios.py tests/test_query_router.py tests/test_stage2_intent.py -q` | Passed | 67 passed, 10 warnings. |
| 2026-05-31 | `uv run pytest tests/test_stage2_search.py -q` | Passed | 3 passed after restoring query expansion/dedup pure test hooks. |
| 2026-05-31 | `uv run pytest tests/test_llamaindex_integration.py -q` | Passed | 3 passed, 2 skipped, 2 warnings after LlamaIndex graph node id compatibility fix. |
| 2026-05-31 | `find agent api tests -name '*.py' -print0 \| xargs -0 uv run python -m py_compile` | Passed | Fresh compile check for modified Python files and tests. |
| 2026-05-31 | `uv run pytest tests/ -q` | Passed | 119 passed, 30 skipped, 21 warnings. Phase 2-6 LlamaIndex migration tests are skipped by default. |
| 2026-05-31 | `uv run pytest tests/test_query_router.py -q` | Passed | 53 passed after intent collection E5/metadata rebuild fix. |
| 2026-05-31 | intent-router smoke with temp Chroma path | Passed | Routed `hello` to `static/greeting`; collection metadata shows `embedding_model=intfloat/e5-base-v2` and `hnsw:space=cosine`. |
| 2026-05-31 | `uv run pytest tests/ -q` | Passed | 121 passed, 30 skipped, 21 warnings after CoreML/ONNX intent router fix. |
