# Legacy RAG Retirement Plan

This plan defines how to make `agent/research/` the canonical chat workflow
and remove the old LangGraph chat path without losing rollback safety.

## Current State

- `/api/chat` and `/api/chat/stream` now use `agent/research/` as the canonical
  retrieval-backed chat workflow.
- `/api/research/preview` is the dev-facing research workflow endpoint.
- The live provider promotion gate has passed locally. Shadow, `arxiv`,
  `default`, and manual rollback smoke passed before the chat route switch.
- `ResearchChatWorkflow` remains as the chat adapter. `ChatWorkflowOrchestrator`,
  `LegacyChatWorkflow`, and rollout/shadow route decisions have been removed.
- `agent/pipeline.py`, `agent/graph.py`, and `agent/nodes/` remain only for
  historical tests, comparison, and future archive/removal decisions.

## Non-Negotiable Gates

The legacy chat routing path has been deleted after all gates below passed:

1. `make eval-research-gate` returns `GATE VERDICT: PASS`.
2. Shadow mode observes real streaming UI traffic without response errors or
   citation regressions.
3. Arxiv rollout mode passes a manual UI smoke for representative paper-search
   queries.
4. Default rollout mode passes full tests, frontend build, and a manual
   rollback test.
5. Docs and tests identify `agent/research/` as canonical and the legacy path as
   deprecated.

## Phase 0: Repo Hygiene

Goal: remove generated files and prevent future artifact churn.

- Remove tracked Python bytecode from Git.
- Keep `__pycache__/`, `.pytest_cache/`, `.next/`, and transient code-review
  reports ignored.
- Do not delete user-owned artifacts such as design exports, local skill packs,
  or prototype archives unless the owner explicitly confirms they are disposable.

Validation:

```bash
git ls-files '*.pyc'
git status --short
```

## Phase 1: Make Routing Explicit

Goal: make `api/routes/chat.py` a protocol adapter instead of a mixed routing,
memory, shadow, and fallback implementation.

Suggested small commits:

1. Extract a `ChatWorkflowOrchestrator` that owns rollout decisions. Done.
2. Move research chat response helpers behind the orchestrator. Done.
3. Move legacy LangGraph calls behind a `LegacyChatWorkflow` adapter. Done.
4. Keep the HTTP and Vercel UI stream protocol code in `api/routes/chat.py`.

Acceptance:

- Existing `/api/chat` and `/api/chat/stream` tests still pass.
- Vercel stream events still emit one final `finish`.
- Default-off behavior remains unchanged.

## Phase 2: Prove Research Workflow As Default

Goal: promote by evidence, not by confidence.

Required checks:

```bash
make eval-research-gate
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q -p no:cacheprovider
cd web && npm run build
```

Manual smoke set:

- `ROS2 trong robotics là gì`
- `paper 1706.03762 summary`
- `recent papers about retrieval augmented generation reranking`
- an out-of-scope non-paper question
- a query that should return no reliable evidence

Promotion order:

```text
manual -> shadow -> arxiv -> default
```

Status: live gate, shadow, `arxiv`, `default`, and manual rollback smoke passed
locally before Phase 3. The chat route no longer has rollout-controlled fallback
branches.

## Phase 3: Delete Legacy Chat Path

Status: implemented on 2026-06-16.

Deleted from chat routing:

- Legacy branches in `/api/chat` and `/api/chat/stream`.
- `run_agent_graph` and `run_agent_retrieval` call sites in chat routing.
- Stage 2 chat tests that only verify legacy LangGraph behavior.
- Docs that claim LangGraph is the active chat production path.

Keep or archive:

- `agent/answerability.py`, source normalization, memory, and generator
  utilities if `agent/research/` still depends on them.
- Historical docs under `docs/archive/` for provenance.
- LlamaIndex code unless a separate decision says the optional migration is
  abandoned.

Acceptance:

- `api/routes/chat.py` has no `run_agent_graph` or `run_agent_retrieval`
  dependency.
- Full test suite and frontend build pass.
- README, CLAUDE, ROADMAP, and CHECKLOG all describe `agent/research/` as the
  canonical chat path.

## Phase 4: Docs Cleanup

Goal: remove stale guidance without deleting useful history blindly.

Status: implemented on 2026-06-16.

Canonical docs to keep current:

- `CLAUDE.md`
- `docs/research-workflow/README.md`
- `docs/research-workflow/ARCHITECTURE.md`
- `docs/research-workflow/ROADMAP.md`
- `docs/research-workflow/CHECKLOG.md`

Archived after review:

- MVP/stage and old LangGraph-centric docs:
  `docs/archive/legacy-rag/`.
- Early LlamaIndex migration summaries:
  `docs/archive/llamaindex-migration/`, including the old
  framework result notes.
- Completed RAG logic enhancement plan:
  `docs/archive/enhance/`.

Rule: archive when a doc is historically useful, delete only when it is both
stale and duplicated by a canonical document.
