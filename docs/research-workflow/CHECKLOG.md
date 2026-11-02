# Research Workflow Checklog

This file records decisions, assumptions, and handoff notes for the production
research workflow. Future agents should update it after each phase.

## Snapshot

**Date:** 2026-06-28
**Status:** Source cleanup checkpoint implemented. `/api/chat` and
`/api/chat/stream` use `agent/research/` as the canonical retrieval-backed chat
path; generated local artifacts are no longer tracked; legacy Ragas evaluation
and stale root/deployment notes are archived.
**Current default path:** `agent/research/` through `/api/chat` and
`/api/chat/stream`.
**Legacy path:** custom LangGraph modules remain for historical tests/comparison
only and are no longer chat routing dependencies. LlamaIndex remains optional
experiment code pending an explicit keep/archive/delete decision.

## Decisions

| Date | Decision | Rationale | Status |
|---|---|---|---|
| 2026-05-31 | Build a separate research workflow instead of only patching RAG nodes. | Paper discovery, ranking, and evidence synthesis need independent contracts and evals. | Accepted |
| 2026-05-31 | Keep current LangGraph path as baseline until evals prove improvement. | Avoid destabilizing working chat while redesigning retrieval. | Accepted |
| 2026-05-31 | Start with Paper Discovery before full-text indexing. | Current failures are mostly candidate discovery failures, not generation failures. | Accepted |
| 2026-05-31 | Use explicit schemas between layers. | Provider-specific dictionaries caused brittle logic and hidden coupling. | Accepted |
| 2026-05-31 | Treat arXiv as one provider, not the full research source of truth. | Production paper search needs broader metadata and citation context. | Accepted |
| 2026-05-31 | Add eval gates before replacing production routing. | Without retrieval metrics, changes are subjective and regressions are invisible. | Accepted |
| 2026-05-31 | Expose the new workflow only as `/api/research/preview` behind `RESEARCH_WORKFLOW_ENABLED`. | The existing chat stream contract must stay stable while the research workflow proves quality. | Implemented |
| 2026-05-31 | Keep preview generation deterministic unless `RESEARCH_PREVIEW_GENERATE=true`. | Local/dev environments may not have a valid LLM key; discovery/evidence can still be evaluated without generation. | Implemented |
| 2026-05-31 | Roll production adoption through `off -> manual -> shadow -> arxiv -> default` modes. | The workflow needs measurable promotion and config-only rollback before touching default chat behavior. | Planned |
| 2026-05-31 | Keep `.env.example` rollout at `manual` until user explicitly promotes runtime config. | The repo template should remain safe even if live eval passes locally. | Accepted |
| 2026-06-04 | Eval gate reports `PASS/FAIL/INCONCLUSIVE` (exit 0/1/2); labeled rows with zero live candidates count as inconclusive infra data, and the gate paces queries (`--sleep 3`). | The 2026-05-31 gate run failed on arXiv/S2 429s, not on quality; an unpassable gate cannot inform promotion. | Implemented |
| 2026-06-04 | Shadow runs via Starlette background tasks on both `/api/chat` and `/api/chat/stream`. | The web UI is streaming-only, so non-streaming-only shadow observed no real traffic; `asyncio.create_task` without a reference risked GC. | Implemented |
| 2026-06-04 | Chat rollout paths always call `run_research_preview(generate=True)`; `RESEARCH_PREVIEW_GENERATE` only affects `/api/research/preview`. | With generation off, end users received a placeholder instructing them to set an env var. | Implemented |
| 2026-06-04 | Streaming honors all active rollout modes (`manual`/`arxiv`/`default`) behind `RESEARCH_WORKFLOW_STREAMING`. | Manual-only streaming would split-brain the two chat endpoints after promotion. | Implemented |
| 2026-06-04 | Frontend hides `Research Papers` unless `GET /api/features` reports it available. | Selecting the option while rollout was off silently degraded to `mixed`. | Implemented |
| 2026-06-09 | Remove tracked Python bytecode and keep generated reports/cache ignored. | Generated artifacts caused dirty worktree noise and should not be part of code review or deployment diffs. | Implemented |
| 2026-06-09 | Do not delete the legacy LangGraph chat path until live eval, shadow, arxiv, and default rollout gates pass. | The old path is still the rollback baseline; deleting it before promotion would mix refactor risk with workflow quality risk. | Accepted |
| 2026-06-09 | Live gate now requires provider config, resumes from `.cache/research/eval-research-gate.json`, and uses arXiv provider-level pacing/cache. | The previous gate hammered arXiv/Semantic Scholar, lost progress on interruption, and conflated missing credentials with quality failure. | Implemented |
| 2026-06-14 | OpenAlex provider and live gate use `OPENALEX_API_KEY`, not `OPENALEX_MAILTO`. | OpenAlex production API access now uses the `api_key` request parameter; mailto is legacy and should not gate promotion. | Implemented |
| 2026-06-14 | Eval resume reuses only completed rows; rows marked `no_candidates=true` are retried. | A transient provider 429/504 should not be baked into the resume checkpoint forever. | Implemented |
| 2026-06-14 | Promotion gate uses `recall@k` + `MRR@k`, not `precision@k`. `precision_at_k` stays reported for diagnostics only. | The golden set has ~1 expected paper per query, so `precision@10` caps at ~0.10 — the old `min_precision=0.35` was mathematically unreachable and not a quality signal. `MRR@k` rewards ranking the seminal paper high without that ceiling. | Implemented |
| 2026-06-14 | P1.1: query planner drops request-descriptor words (`META_TERMS`: original, explained, compare, overview…) from entities and adds English function words (and, or, of, in…) to `FILLER_TERMS`. | "original BERT paper" produced `all:original AND all:BERT`, which excludes the seminal paper because its text lacks the word "original". Descriptor/function words must never become required AND terms. | Implemented |
| 2026-06-14 | P1.2: discovery scorer (`service.score_discovery_candidate`) gains a `citation_signal` term (log10 of citation_count, weight 0.18) and trims discovery `recency` to 0.04. | The eval/discovery scorer lacked the authority signal the production reranker already had, so high-citation seminal papers lost to recent incidental matches. Seminal papers are old (low recency) but heavily cited. | Implemented |
| 2026-06-15 | Exact arXiv ID lookups get an `identifier_match` boost in both discovery scoring and production candidate ranking. | `paper 1706.03762 summary` resolved the correct paper in arXiv discovery, but production reranking re-ordered citations behind incidental Semantic Scholar/OpenAlex matches. Exact ID lookup is a user intent stronger than recency/citation/lexical signals. | Implemented |
| 2026-06-15 | Eval report schema is now `report_schema_version=3`. | The exact-ID scoring change affects ranking metrics; schema v3 prevents stale schema-v2 gate rows from being resumed after this scoring change. | Implemented |
| 2026-06-15 | `ChatWorkflowOrchestrator` owns rollout route decisions for chat endpoints. | `api/routes/chat.py` was mixing HTTP/stream protocol, rollout checks, shadow decisions, and workflow selection. The first refactor increment centralizes decisioning without deleting legacy behavior. | Implemented |
| 2026-06-16 | Research and legacy chat execution are isolated behind `ResearchChatWorkflow` and `LegacyChatWorkflow` adapters. | Rollout decisioning was centralized, but `api/routes/chat.py` still owned workflow execution details. Adapter isolation makes the next cleanup step smaller while preserving rollback behavior. | Implemented |
| 2026-06-16 | Default rollout can be promoted only with an explicit rollback smoke back to `manual`. | `default` is the highest-risk mode because it routes ordinary paper-search traffic through `agent/research/`. A config-only rollback check proves `mixed` can still use the legacy path while explicit `research` remains available. | Implemented |
| 2026-06-16 | Phase 3 retires rollout/shadow/legacy chat routing. | Live eval, shadow, arxiv, default, and rollback smoke had passed; keeping rollout branches after promotion made the chat path harder to reason about and kept dead fallback behavior alive. | Implemented |
| 2026-06-16 | `/api/features` now reports `research_search_available=true` unconditionally. | Research search is no longer a gated optional UI source; it is the canonical retrieval-backed chat workflow. | Implemented |
| 2026-06-16 | Move `inject_memory_context` to `agent/memory/context.py`. | Production chat still needed memory context, but importing it from `agent/pipeline.py` kept a hidden dependency on the legacy LangGraph module. | Implemented |
| 2026-06-16 | Archive stale docs instead of deleting them. | Stage docs, old enhancement plans, and LlamaIndex migration/result notes are useful provenance but were no longer safe as current architecture guidance. | Implemented |
| 2026-06-16 | Add `docs/README.md` and archive READMEs as documentation routing. | Future agents need a quick way to distinguish canonical docs from historical notes. | Implemented |
| 2026-06-28 | Phase 4 evidence synthesis now extracts scored sentence-level spans and does not fallback to unrelated first sentences. | Fallback evidence made paper-present/no-evidence cases look answerable or weakly answerable, which hid the difference between `NO_EVIDENCE_FOUND` and `WEAK_EVIDENCE`. | Implemented |
| 2026-06-28 | Claim-grounded synthesis sends evidence IDs, sections, claim candidates, and quotes through `agent/generator.py`. | The prompt contract requires each major claim to cite evidence IDs; the generator handoff must carry enough evidence metadata for the model to obey that contract. | Implemented |
| 2026-06-28 | Eval report schema is now `report_schema_version=4`. | Phase 5 adds `hit_ranks`, `best_hit_rank`, `failure_stage`, and `failure_stage_counts`; old schema-v3 checkpoints should not be resumed because they cannot explain failure stages. | Implemented |
| 2026-06-28 | Research traces expose `latency_summary` with p50/p95/max per span name. | Raw spans are useful for debugging one request, but production observability needs compact stage-level latency summaries for discovery, ranking, retrieval, and synthesis. | Implemented |
| 2026-06-28 | Stop tracking generated local artifacts (`.coverage*`, `chroma_v2/**`). | Coverage and local Chroma indexes are generated machine state, not source code; keeping them tracked created noisy reviews and oversized diffs. | Implemented |
| 2026-06-28 | Archive legacy Ragas evaluation under `docs/archive/legacy-ragas/` and `experiments/legacy-ragas/`. | Current eval path is `eval/research_eval.py`; old Ragas scripts target the legacy LangGraph pipeline and should not sit in root/eval as active commands. | Implemented |
| 2026-06-28 | Archive stale root notes and stale quick deployment guide. | `DESIGN.md`, `INTEGRATION_PLAN.md`, `UI_AUDIT.md`, `QUICK_TUNNEL_README.md`, and the old quick deployment guide are provenance, not current architecture/deployment guidance. | Implemented |
| 2026-06-28 | Keep LlamaIndex prototype and legacy LangGraph baseline pending explicit retirement decisions. | Both are outside production chat, but moving/deleting them affects optional tests, historical comparison, and rollback context; the cleanup plan marks these as stop-condition decisions. | Deferred |
| 2026-06-28 | Answer-quality debugging is stage-first: discovery/ranking/evidence/synthesis/model are measured separately. | Manual UI failures showed wrong paper selection before model quality could be judged. Same-context model eval is required before upgrading synthesis models. | Implemented |
| 2026-06-28 | Canonical paper resolution handles seminal paper lookups and comparisons. | Queries like `Transformer paper có gì` and `compare LoRA and QLoRA papers` need canonical scholarly targets, not broad keyword search over incidental mentions. | Implemented |

## Known Current Weaknesses

- ArXiv search converts many multi-word queries into exact phrase queries, which
  fails for multilingual questions such as `ROS2 trong robotics là gì`.
- Query expansion is hardcoded around a few English patterns and abbreviations.
- UI source selection is intentionally simplified to `Research Papers`; legacy
  per-source search choices are retired from the chat UI.
- Candidate ranking has internal score breakdowns, but diagnostics still need better surfacing for UI/manual debugging.
- Full-text paper parsing and section-aware retrieval are not first-class yet.
- Golden query sets exist, but answer-quality labels are still small and curated.

## Golden Query Seeds

Start the eval dataset with these representative queries:

| Query | Expected Behavior |
|---|---|
| `ROS2 trong robotics là gì` | Finds ROS 2 robotics papers in `cs.RO`; answer defines ROS 2 using evidence. |
| `recent papers about retrieval augmented generation reranking` | Returns recent RAG/reranking papers, not static web pages. |
| `compare LoRA and QLoRA papers` | Finds original LoRA/QLoRA papers and comparison context. |
| `Mamba architecture paper explained` | Finds Mamba paper and related state-space model papers. |
| `best survey papers about graph neural networks` | Surfaces survey/review papers and cites survey evidence. |
| `paper 1706.03762 summary` | Resolves arXiv ID directly to the Transformer paper. |
| `what benchmarks are used in SWE-bench papers` | Extracts benchmark evidence from relevant papers. |

## Handoff Notes

- Do not read `.env` in planning or review tasks. Use `.env.example` and code
  defaults for documentation.
- `/api/chat` and `/api/chat/stream` use `agent/research/` directly for
  retrieval-backed queries. `RESEARCH_WORKFLOW_ENABLED` only gates
  `/api/research/preview`; it does not gate chat.
- Provider API keys should be optional for dev paths but required for the live
  promotion gate. Semantic Scholar uses `SEMANTIC_SCHOLAR_API_KEY`; OpenAlex
  uses `OPENALEX_API_KEY`. OpenAlex `mailto` belongs to the historical polite
  pool and should not be treated as a live-gate credential.
- Store provider raw responses only in tests/fixtures or a cache layer with
  clear provenance. Runtime code should use `PaperCandidate`.
- The new preview path currently indexes abstracts/available text only. Full PDF
  fetching and parsing remain behind future `RESEARCH_ENABLE_FULLTEXT_FETCH`
  work.
- The 50-query golden set is present, but strict quality thresholds should be
  enabled only after running non-dry discovery evals against live providers.
- Production adoption plan lives at
  `docs/superpowers/plans/2026-05-31-research-workflow-production-adoption.md`.
- Legacy retirement plan lives at
  `docs/research-workflow/LEGACY_RETIREMENT_PLAN.md`.
- Documentation entrypoint lives at `docs/README.md`.
- Historical/stale docs live under `docs/archive/` and should not be used as
  current architecture guidance.
- Source cleanup plan lives at
  `docs/superpowers/plans/2026-06-28-source-cleanup-and-legacy-retirement.md`.
  Tasks 5 and 6 are intentionally deferred until explicit decisions are made
  for LlamaIndex and legacy LangGraph retirement.

## Verification Log

| Date | Command | Result | Notes |
|---|---|---|---|
| 2026-05-31 | `find docs/research-workflow -maxdepth 1 -type f \| sort` | Passed | Confirmed README, architecture, roadmap, checklog, and five phase specs exist. |
| 2026-05-31 | `rg -n "TBD\|TODO\|fill in\|placeholder\|coming soon" docs/research-workflow` | Passed | No unresolved planning placeholders found. |
| 2026-05-31 | `uv run pytest tests/research -q` | Passed | 24 research workflow tests passed. |
| 2026-05-31 | `uv run python eval/research_eval.py --dataset eval/research_golden_set.jsonl --dry-run` | Passed | Loaded 50 golden queries without network calls. |
| 2026-05-31 | Live arXiv smoke: `discover_papers("ROS2 trong robotics là gì", provider_names=["arxiv"], max_results=3)` | Passed | Returned 3 ROS 2 robotics papers including `2306.17157` and `2209.14030`. |
| 2026-05-31 | `uv run pytest tests/ -q` | Passed | 145 passed, 30 skipped, 22 warnings. |
| 2026-05-31 | `make eval-research-gate` | Failed | Exit 2 (`make: *** [eval-research-gate] Error 1`); mean recall@k 0.038461538461538464 and mean precision@k 0.0038461538461538464 were below thresholds 0.55/0.35 amid repeated arXiv timeouts/429s and Semantic Scholar 429s, so rollout stays `manual`. |
| 2026-05-31 | Backend curl smoke with `RESEARCH_WORKFLOW_ENABLED=true RESEARCH_WORKFLOW_ROLLOUT=manual RESEARCH_WORKFLOW_STREAMING=true RESEARCH_PREVIEW_GENERATE=false`; Playwright UI smoke against Next.js dev server with `NEXT_PUBLIC_API_URL=http://127.0.0.1:8010` | Passed with caveat | Backend `/api/chat/stream` returned HTTP 200 with `x-vercel-ai-ui-message-stream: v1` and `start`, `text-start`, `text-delta`, `source-url`, and `finish` events for `{"query":"ROS2 trong robotics là gì","mode":"search","search_source":"research","top_k":3}`. Sources included ORICF (`2605.09656v1`), FogROS2-SGC (`2306.17157v1`), and a ROS 2 biosensor ecosystem paper (`2110.03840v1`). UI smoke logged in with a disposable in-memory test user, selected `Research Papers`, sent the query, and displayed the research workflow response. Browser signup page was blocked by backend CORS, so the disposable user was seeded through backend `/api/auth/signup`; rollout remains `manual` because the eval gate is still failed. |
| 2026-06-04 | Adversarial branch review | Completed | Report at `docs/research-workflow/REVIEW_2026-06-04.md`; verdict GO (merge flag-gated) / NO-GO (promotion) with findings 3.1-3.5. |
| 2026-06-08 | `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q -p no:cacheprovider` | Passed | 189 passed, 30 skipped, 22 warnings in 356.40s. |
| 2026-06-08 | `PYTHONDONTWRITEBYTECODE=1 make eval-research` | Passed | Dry-run gate returned `GATE VERDICT: PASS` with 50 queries, 26 labeled rows, and `no_candidate_query_count: 0`. |
| 2026-06-08 | `cd web && npm run build` | Passed | Next.js compiled successfully; 9 routes generated including `/api/features`. |
| 2026-06-09 | `PYTHONDONTWRITEBYTECODE=1 make eval-research-gate` | Stopped | Live providers returned repeated arXiv timeouts/429s and Semantic Scholar 429s; the run was terminated after several minutes (`make` exit 143). No PASS was produced, so rollout was not promoted beyond `manual`. |
| 2026-06-09 | `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research/test_arxiv_provider.py tests/research/test_research_eval_metrics.py -q -p no:cacheprovider` | Passed | 18 passed; covers arXiv cache/pacing/cache-corruption fallback plus eval resume/checkpoint/provider-config preflight. |
| 2026-06-09 | `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research/test_discovery_service.py tests/research/test_research_preview_api.py tests/research/test_research_chat_integration.py -q -p no:cacheprovider` | Passed | 25 passed, 4 warnings. |
| 2026-06-09 | `PYTHONDONTWRITEBYTECODE=1 make eval-research` | Passed | Dry-run gate still returns `GATE VERDICT: PASS`. |
| 2026-06-09 | `PYTHONDONTWRITEBYTECODE=1 make eval-research-gate` | Inconclusive | New preflight stopped before live provider calls because required provider config was absent in the runtime environment. No PASS was produced, so rollout was not promoted beyond `manual`. |
| 2026-06-14 | `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research/test_openalex_provider.py tests/research/test_discovery_service.py tests/research/test_research_eval_metrics.py -q -p no:cacheprovider` | Passed | 16 passed; OpenAlex now sends `OPENALEX_API_KEY` as `api_key` and ignores legacy `OPENALEX_MAILTO`. |
| 2026-06-14 | `PYTHONDONTWRITEBYTECODE=1 make eval-research-gate` | Inconclusive | Preflight now requires `OPENALEX_API_KEY`; runtime had Semantic Scholar configured but was missing OpenAlex API key. No PASS was produced, so rollout was not promoted beyond `manual`. |
| 2026-06-14 | `PYTHONDONTWRITEBYTECODE=1 make eval-research-gate` | Failed | Live gate completed with configured providers: `query_count=50`, `paper_labeled_query_count=26`, `no_candidate_query_count=0`, `mean_recall_at_k=0.46153846153846156`, and `mean_precision_at_k=0.04615384615384616`, below thresholds `0.55/0.35`. This is a quality/ranking gate failure, not a missing-config failure; rollout stays below `shadow`. |
| 2026-06-14 | `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research -q -p no:cacheprovider` | Passed | 87 passed, 4 warnings; covers eval resume retrying `no_candidates`, dry-run threshold behavior, and Semantic Scholar/OpenAlex cache/retry/backoff/pacing. |
| 2026-06-14 | Fresh live gate without resume: `PYTHONDONTWRITEBYTECODE=1 uv run python eval/research_eval.py --dataset eval/research_golden_set.jsonl --top-k 10 --min-recall 0.55 --min-precision 0.35 --sleep 3 --out .cache/research/eval-research-gate-fresh.json --require-provider-config` | Failed | Providers were configured and retry/backoff handled a Semantic Scholar 429, but final metrics remained `query_count=50`, `paper_labeled_query_count=26`, `no_candidate_query_count=0`, `mean_recall_at_k=0.46153846153846156`, and `mean_precision_at_k=0.04615384615384616`. This confirms remaining blocker is discovery/ranking quality, not provider infra; rollout stays below `shadow`. |
| 2026-06-14 | `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q -p no:cacheprovider` | Passed | 209 passed, 30 skipped, 22 warnings in 433.37s. |
| 2026-06-14 | Diagnosed why live gate fails: golden set has 25/26 rows with one expected paper, so max `mean_precision@10` (perfect ranking) = 0.1038 — `min_precision=0.35` was unreachable. 14 missed papers were absent from candidates even at `max_results=50` (retrieval miss, not ranking); even clean `ti:"BERT"` does not surface `1810.04805` (arXiv relevance lacks authority signal). | Diagnosis | Precision is a metric bug, not quality; recall is a retrieval gap. Drove the P0 metric switch and the P1 query-planner work. |
| 2026-06-14 | P0: switch gate to `recall@k`+`MRR@k`; `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research/test_research_eval_metrics.py -q -p no:cacheprovider` then `tests/research` | Passed | 16 then 90 passed. `make eval-research` dry-run still `GATE VERDICT: PASS`. Re-scoring the last live checkpoint under the new metric: `mean_recall=0.4615`, `mean_mrr=0.2402` → `FAIL` (now an honest quality signal, not a structural impossibility). Gate target now `--min-recall 0.55 --min-mrr 0.35`. |
| 2026-06-14 | P1.1 query-planner cleanup: `tests/research` (92 passed); arXiv-only probe on the 14 previously-missed labeled rows | Improved, not sufficient | Planner cleanup recovered 4/14 missed rows on arXiv alone (LoRA/QLoRA, Tree of Thoughts, Constitutional AI, Segment Anything). The remaining 10 are seminal papers (BERT, GPT-3, CLIP, RAG, DPR, LLaMA, ViT, HumanEval, Mamba, SWE-bench) that arXiv relevance cannot surface without an authority/citation signal; they need working Semantic Scholar/OpenAlex or citation-aware ranking. Rollout stays below `shadow`. |
| 2026-06-14 | P1.2 citation-aware discovery scoring: `tests/research` (93 passed) | Passed (mechanism), live effect pending providers | Unit test proves a high-citation seminal paper now outranks a recent incidental match. `citation_count` only comes from Semantic Scholar/OpenAlex (arXiv does not provide it), so the live recall/MRR gain requires those providers returning data; arXiv-only runs are unchanged. Re-run `make eval-research-gate` once `SEMANTIC_SCHOLAR_API_KEY`/`OPENALEX_API_KEY` are configured to measure true `recall@k`/`MRR@k`. |
| 2026-06-14 | `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research/test_research_eval_metrics.py -q -p no:cacheprovider`; `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research -q -p no:cacheprovider`; `make eval-research-gate` | Passed | Fixed stale resume poisoning after the P0 MRR switch by adding report schema versioning and requiring `mrr_at_k` before a row is resumable. Legacy checkpoints without MRR are ignored and recomputed; `no_candidates` rows remain non-resumable. Live gate recomputed from providers and passed with `query_count=50`, `paper_labeled_query_count=26`, `no_candidate_query_count=0`, `mean_recall_at_k=0.7115384615384616`, `mean_mrr_at_k=0.5576923076923077`. Current schema is v3 after the 2026-06-15 exact-ID scoring change. |
| 2026-06-15 | Shadow rollout smoke: `RESEARCH_WORKFLOW_ENABLED=true RESEARCH_WORKFLOW_STREAMING=true RESEARCH_WORKFLOW_ROLLOUT=shadow uv run uvicorn api.main:app --host 127.0.0.1 --port 8011`; `curl /api/features`; POST `/api/chat/stream` with `ROS2 trong robotics là gì` | Passed | `/api/features` returned `research_search_available=false` as expected in shadow mode. Visible stream returned HTTP 200, `x-vercel-ai-ui-message-stream: v1`, event types `start/text-start/text-delta/text-end/source-url/finish`, `finishReason=stop`, and 3 sources. No shadow failure warning appeared in server output. |
| 2026-06-15 | Arxiv rollout smoke before fix: `RESEARCH_WORKFLOW_ROLLOUT=arxiv` POST `/api/chat/stream` with `paper 1706.03762 summary` | Failed, fixed | Stream returned HTTP 200 and text mentioned `Attention Is All You Need`, but source cards pointed to incidental papers (`GLU Variants Improve Transformer`, etc.) instead of `1706.03762`. Root cause: discovery could resolve `id:1706.03762`, but production `rank_candidates()` lacked an exact-ID signal and re-ranked citations incorrectly. |
| 2026-06-15 | Exact-ID fix verification: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research/test_query_plan.py tests/research/test_discovery_service.py tests/research/test_candidate_ranking.py tests/research/test_research_eval_metrics.py -q -p no:cacheprovider`; `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research -q -p no:cacheprovider`; arxiv stream smoke for `paper 1706.03762 summary` | Passed | Focused tests: 31 passed. Research suite: 96 passed, 4 warnings. Arxiv stream returned source 1 as `Attention Is All You Need` with `https://arxiv.org/abs/1706.03762v7`, `has_1706_source=true`, and `finishReason=stop`. Query planner now normalizes versioned IDs like `1706.03762v7` to base `1706.03762`. |
| 2026-06-15 | `make eval-research-gate` | Passed | Schema v3 live gate recomputed from providers and passed despite intermittent Semantic Scholar/OpenAlex retries: `query_count=50`, `paper_labeled_query_count=26`, `paper_scored_query_count=26`, `no_candidate_query_count=0`, `mean_recall_at_k=0.75`, `mean_precision_at_k=0.07692307692307693`, `mean_mrr_at_k=0.5961538461538461`. |
| 2026-06-15 | `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research/test_chat_workflow_orchestrator.py tests/research/test_research_chat_integration.py tests/test_chat_streaming.py -q -p no:cacheprovider`; `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research -q -p no:cacheprovider`; `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q -p no:cacheprovider`; `cd web && npm run build`; codex-spark sidecar review | Passed | First routing refactor increment added `api/chat_orchestrator.py` and moved visible/shadow workflow decisions behind `ChatWorkflowOrchestrator`. Tests: 24 passed for chat/stream integration, 101 passed for research suite, 223 passed/30 skipped full backend suite, frontend build passed. Subagent review found no blocking issues for rollout semantics or Vercel stream protocol. |
| 2026-06-16 | `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research/test_chat_workflow_orchestrator.py tests/research/test_research_chat_integration.py tests/test_chat_streaming.py -q -p no:cacheprovider`; `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research -q -p no:cacheprovider`; codex-spark sidecar review | Passed | Adapter refactor added `ResearchChatWorkflow` and `LegacyChatWorkflow`. Focused chat/stream integration: 27 passed. Research suite: 103 passed. Sidecar review found one dependency-binding issue in adapter defaults; fixed by resolving default callables at construction time and covered with a regression test. |
| 2026-06-16 | Default rollout smoke: `RESEARCH_WORKFLOW_ENABLED=true RESEARCH_WORKFLOW_STREAMING=true RESEARCH_WORKFLOW_ROLLOUT=default uv run uvicorn api.main:app --host 127.0.0.1 --port 8012`; POST `/api/chat/stream` for exact-ID, ROS2, RAG reranking, static, and weak-evidence cases | Passed | `/api/features` returned `research_search_available=true`. Streams kept `x-vercel-ai-ui-message-stream: v1` and `finishReason=stop`. `paper 1706.03762 summary` returned `Attention Is All You Need` as `research_source_0`; ROS2/RAG queries returned paper sources; `hello` returned no sources; weak-evidence query returned the clean no-paper message. arXiv timed out on the weak-evidence subqueries but the response degraded safely. |
| 2026-06-16 | Manual rollback smoke: `RESEARCH_WORKFLOW_ROLLOUT=manual` on `/api/chat/stream` with `mode=search` | Passed | Manual `mixed` request used the legacy source IDs (`source_0`, etc.) and explicit `research` request used research source IDs (`research_source_0`) with `1706.03762v7`. This proves config-only rollback from `default` to `manual` keeps the old path available while preserving the Research Papers option. |
| 2026-06-16 | `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q -p no:cacheprovider`; `cd web && npm run build`; `git diff --check` | Passed | Full backend suite: 226 passed, 30 skipped, 22 warnings in 296.35s. Next.js production build passed. Whitespace check passed. |
| 2026-06-16 | Phase 3 legacy retirement verification: focused chat/memory/stream tests; `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research -q -p no:cacheprovider`; `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q -p no:cacheprovider`; `cd web && npm run build`; `PYTHONDONTWRITEBYTECODE=1 make eval-research`; `git diff --check` | Passed | Focused chat/memory/stream contract: 31 passed. Research suite: 75 passed. Full backend suite: 198 passed, 30 skipped, 22 warnings in 147.03s. Next.js production build passed. Dry-run eval returned `GATE VERDICT: PASS`. Whitespace check passed. Legacy Stage2 scenario tests now stub generation so historical graph tests no longer call live OpenRouter. |
| 2026-06-16 | Phase 4 docs cleanup verification: stale-guidance `rg` over current docs excluding `docs/archive/**`, `docs/superpowers/**`, and `CHECKLOG`; `PYTHONDONTWRITEBYTECODE=1 make eval-research`; `git diff --check` | Passed | Current guidance no longer reports stale production-path/source-option patterns. Dry-run eval returned `GATE VERDICT: PASS`. Whitespace check passed. Archive docs remain intentionally historical. |
| 2026-06-28 | Phase 4 evidence synthesis verification: `uv run pytest tests/research/test_evidence_extractor.py tests/research/test_evidence_retriever.py tests/research/test_claim_answer.py -q`; `uv run pytest tests/research -q`; `uv run pytest tests/research/test_research_preview_api.py tests/research/test_research_chat_integration.py tests/research/test_research_chat_adapter.py -q`; `PYTHONDONTWRITEBYTECODE=1 make eval-research`; `git diff --check` | Passed | Focused evidence/synthesis suite: 6 passed. Research suite: 77 passed, 3 warnings. API/stream adapter suite: 12 passed, 3 warnings. Dry-run eval returned `GATE VERDICT: PASS`. Whitespace check passed. |
| 2026-06-28 | Push + live smoke after Phase 4: `git push origin dev`; local API on `127.0.0.1:8013`; `curl /health`; `curl /api/features`; static `/api/chat/stream`; deterministic `/api/research/preview` with arXiv-only discovery | Passed | `dev` pushed to `b282364`. Health returned 200 and Chroma connected. Features returned `research_search_available=true`. Stream kept `x-vercel-ai-ui-message-stream: v1` and `finishReason=stop`. Research preview found `Attention Is All You Need` for `1706.03762` and returned `NO_EVIDENCE_FOUND` without fabricating evidence; content-overlap Transformer query returned 2 evidence spans and `ANSWERABLE`. |
| 2026-06-28 | Phase 5 eval/observability verification: `uv run pytest tests/research/test_research_eval_metrics.py tests/research/test_observability.py -q`; `uv run pytest tests/research -q`; `PYTHONDONTWRITEBYTECODE=1 make eval-research`; `git diff --check` | Passed | Focused eval/observability suite: 20 passed. Research suite: 80 passed, 3 warnings. Dry-run eval returned schema v4, `GATE VERDICT: PASS`, and `failure_stage_counts={"dry_run": 50}`. Whitespace check passed. |
| 2026-06-28 | Source cleanup verification: `UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q`; `cd web && npm run build`; `UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 make eval-research`; `git diff --check` | Passed | Backend `203 passed, 30 skipped, 22 warnings`; frontend build compiled 9 routes; eval dry-run returned `GATE VERDICT: PASS`; whitespace check passed. |
| 2026-06-28 | Answer-quality harness verification: `UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research -q`; `UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 uv run python eval/research_diagnostics.py --dataset eval/answer_quality_golden_set.jsonl --top-k 10`; `UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 make eval-research` | Passed | Research suite: 100 passed, 3 warnings. Diagnostics returned `stage_counts={"passed": 4}`: Transformer hit `1706.03762` at rank 1, LoRA/QLoRA hit `2305.14314` and `2106.09685` at ranks 1/2, ROS2 was not a discovery miss, and the private birthday query had `evidence_count=0`. Dry-run eval returned `GATE VERDICT: PASS`. Semantic Scholar still emitted transient 429 retries during diagnostics. |
