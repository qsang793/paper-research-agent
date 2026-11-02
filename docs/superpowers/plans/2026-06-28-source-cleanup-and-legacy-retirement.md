# Source Cleanup And Legacy Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repository layout match the current production architecture by removing generated artifacts, isolating or deleting obsolete legacy code, and documenting clear source ownership conventions.

**Architecture:** `agent/research/` is the canonical production research workflow. Old LangGraph modules, optional LlamaIndex migration code, and legacy Ragas evaluation must be treated as separate retirement tracks with characterization tests and explicit delete/archive decisions. Generated data and local prototypes are handled separately from source code so cleanup does not destroy user-owned work.

**Tech Stack:** Python/FastAPI, Next.js, pytest, uv, Makefile, ChromaDB local artifacts, Git.

---

## Current Findings From Repo Scan

- Canonical production path:
  - `api/routes/chat.py`
  - `api/chat_orchestrator.py`
  - `agent/research/**`
  - `agent/memory/**`
  - `agent/query_policy.py`
  - `agent/query_router.py`
  - `agent/generator.py`
  - `agent/sources.py`
- Legacy LangGraph path still present and test-referenced:
  - `agent/graph.py`
  - `agent/pipeline.py`
  - `agent/state.py`
  - `agent/nodes/**`
  - `tests/test_stage2_*`
  - `tests/test_graph_construction.py`
  - `tests/test_embed_query_fix.py`
  - `eval/evaluate.py`
- Optional LlamaIndex migration path is not production but still code/test-referenced:
  - `agent/frameworks/llamaindex/**`
  - `tests/test_llamaindex_*`
  - `agent/frameworks/README.md`
  - `docs/frameworks/README.md`
- Legacy Ragas/eval/debug files are mixed into root/eval:
  - `eval/evaluate.py`
  - `eval/METRICS_ANALYSIS.md`
  - `eval/RESULTS_SUMMARY.md`
  - `check_ragas.py`
  - `inspect_metrics.py`
  - `inspect_ragas.py`
  - `test_ragas_fix.py`
  - `run_performance_test.sh`
- Tracked generated data/artifacts:
  - `.coverage`
  - `.coverage.Sangs-MacBook-Pro.local.25668.XmHXvtMx`
  - `chroma_v2/**`
- Untracked local/user artifacts:
  - `cohere/`
  - `lovable-export/`
  - `reskin-landing.png`
  - `skills/`

## Cleanup Principles

- Do not mix behavior changes with file cleanup.
- Every commit must leave `tests/research`, full backend tests, and frontend build in a known state.
- Do not touch `.env`, `.env.local`, `.codex/`, `.claude/`, `.agents/`, or untracked `skills/` unless the user explicitly approves that specific scope.
- Archive before delete when the artifact has historical value.
- Delete directly only when the artifact is generated, duplicated, or covered by canonical docs/tests.
- Keep production code under `agent/research/`, API adapters under `api/`, and historical/experimental work out of the default import path.

## Target Source Convention

After cleanup, the repo should read like this:

```text
agent/
  research/          # canonical research-paper workflow
  memory/            # conversation memory and context injection
  stores/            # reusable store adapters still used by active paths
  utils/             # active runtime utilities
  generator.py       # shared LLM provider boundary
  query_policy.py    # active API policy layer
  query_router.py    # active API intent/router layer
  sources.py         # shared source/citation normalization

api/
  routes/            # HTTP endpoints only
  chat_orchestrator.py
  models.py
  streaming.py

eval/
  research_eval.py
  research_golden_set.jsonl

docs/archive/
  legacy-*           # historical notes and abandoned prototypes
```

Anything outside this shape needs one of three labels:

- **active:** used by production API, eval, or tests.
- **legacy:** retained temporarily with a retirement date.
- **archive:** moved out of source/import paths.

---

## Task 1: Baseline And Ownership Snapshot

**Files:**
- Create: `docs/research-workflow/SOURCE_OWNERSHIP.md`

- [x] (2026-06-28 09:40Z) **Step 1: Create the ownership document**

Create `docs/research-workflow/SOURCE_OWNERSHIP.md`:

```markdown
# Source Ownership

## Active Production Code

- `api/routes/chat.py`: HTTP and stream protocol adapter.
- `api/chat_orchestrator.py`: chat workflow adapter.
- `agent/research/`: canonical research workflow.
- `agent/memory/`: conversation memory and query context.
- `agent/query_policy.py`: API policy decisions.
- `agent/query_router.py`: static/chat/retrieval route classification.
- `agent/generator.py`: shared LLM provider boundary.
- `agent/sources.py`: source normalization.
- `eval/research_eval.py`: production research eval gate.

## Legacy Candidates

- `agent/graph.py`, `agent/pipeline.py`, `agent/state.py`, `agent/nodes/`: old LangGraph baseline.
- `eval/evaluate.py`: legacy Ragas evaluation over old pipeline.

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
```

- [x] (2026-06-28 09:40Z) **Step 2: Verify no code changed**

Run:

```bash
git diff --check
UV_CACHE_DIR=.uv-cache uv run pytest tests/research -q
```

Expected:

- `git diff --check` exits 0.
- Research suite passes.

- [x] (2026-06-28 09:40Z) **Step 3: Commit**

```bash
git add docs/research-workflow/SOURCE_OWNERSHIP.md
git commit -m "docs: define source ownership boundaries"
```

---

## Task 2: Remove Tracked Generated Artifacts

**Files:**
- Modify: `.gitignore`
- Remove from Git index: `.coverage`, `.coverage.Sangs-MacBook-Pro.local.25668.XmHXvtMx`, `chroma_v2/**`

- [x] (2026-06-28 09:40Z) **Step 1: Add generated artifact ignore rules**

Update `.gitignore`:

```gitignore
# Coverage
.coverage
.coverage.*

# ChromaDB local indexes
chroma/
chroma_v2/
```

Keep existing ignore rules and avoid touching `.env` behavior.

- [x] (2026-06-28 09:40Z) **Step 2: Untrack generated files without deleting local copies**

Run:

```bash
git rm --cached .coverage .coverage.Sangs-MacBook-Pro.local.25668.XmHXvtMx
git rm --cached -r chroma_v2
```

Expected:

- Files are removed from Git tracking.
- Local files may remain on disk.

- [x] (2026-06-28 09:40Z) **Step 3: Verify ignore behavior**

Run:

```bash
git check-ignore -v .coverage chroma_v2
git status --short --ignored
```

Expected:

- `.coverage` and `chroma_v2` are ignored.
- No tracked source files are modified except `.gitignore`.

- [x] (2026-06-28 09:40Z) **Step 4: Run fast verification**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research -q
git diff --check
```

Expected:

- Research suite passes.
- Whitespace check passes.

- [x] (2026-06-28 09:40Z) **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore(repo): stop tracking generated local artifacts"
```

---

## Task 3: Normalize Root-Level Legacy Scripts

**Files:**
- Move or remove:
  - `check_ragas.py`
  - `inspect_metrics.py`
  - `inspect_ragas.py`
  - `test_ragas_fix.py`
  - `run_performance_test.sh`
- Modify:
  - `README.md`
  - `CLAUDE.md`
  - `AGENTS.md`
  - `eval/README.md`
  - `docs/research-workflow/SOURCE_OWNERSHIP.md`

**Decision:** If the user still wants Ragas experiments, move these scripts under `experiments/legacy-ragas/`. If not, delete them and keep only archived docs.

- [x] (2026-06-28 09:40Z) **Step 1: Confirm imports**

Run:

```bash
rg -n "check_ragas|inspect_metrics|inspect_ragas|test_ragas_fix|run_performance_test" .
```

Expected:

- References are docs-only or absent.
- No production module imports these scripts.

- [x] (2026-06-28 09:40Z) **Step 2A: If keeping Ragas experiments, move scripts**

```bash
mkdir -p experiments/legacy-ragas
git mv check_ragas.py experiments/legacy-ragas/check_ragas.py
git mv inspect_metrics.py experiments/legacy-ragas/inspect_metrics.py
git mv inspect_ragas.py experiments/legacy-ragas/inspect_ragas.py
git mv test_ragas_fix.py experiments/legacy-ragas/test_ragas_fix.py
git mv run_performance_test.sh experiments/legacy-ragas/run_performance_test.sh
```

Add `experiments/legacy-ragas/README.md`:

```markdown
# Legacy Ragas Experiments

These scripts are retained for historical/manual evaluation only. They are not
part of the production research workflow.

Use `make eval-research` and `make eval-research-gate` for the canonical
research workflow evaluation.
```

- [ ] **Step 2B: If not keeping Ragas experiments, delete scripts**

```bash
git rm check_ragas.py inspect_metrics.py inspect_ragas.py test_ragas_fix.py run_performance_test.sh
```

- [x] (2026-06-28 09:40Z) **Step 3: Update docs away from old commands**

Replace mentions of:

```bash
uv run --extra eval python eval/evaluate.py
python eval/evaluate.py
```

with:

```bash
make eval-research
make eval-research-live
make eval-research-gate
```

Only keep `eval/evaluate.py` references inside legacy/archive docs if Task 4 keeps it.

- [x] (2026-06-28 09:40Z) **Step 4: Verify**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research -q
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 make eval-research
git diff --check
```

Expected:

- Research suite passes.
- Dry-run eval returns `GATE VERDICT: PASS`.

- [x] (2026-06-28 09:40Z) **Step 5: Commit**

Use one commit:

```bash
git add README.md CLAUDE.md AGENTS.md eval/README.md docs/research-workflow/SOURCE_OWNERSHIP.md
git add experiments/legacy-ragas || true
git commit -m "chore(repo): isolate legacy evaluation scripts"
```

Or, if deleting:

```bash
git add README.md CLAUDE.md AGENTS.md eval/README.md docs/research-workflow/SOURCE_OWNERSHIP.md
git commit -m "chore(repo): remove obsolete evaluation helper scripts"
```

---

## Task 4: Retire Or Archive Legacy Ragas Evaluation

**Files:**
- Candidate remove/archive:
  - `eval/evaluate.py`
  - `eval/METRICS_ANALYSIS.md`
  - `eval/RESULTS_SUMMARY.md`
- Keep:
  - `eval/research_eval.py`
  - `eval/research_golden_set.jsonl`

**Decision:** Delete `eval/evaluate.py` only after confirming no one needs Ragas over the old LangGraph path. The current production eval is `eval/research_eval.py`.

- [x] (2026-06-28 09:40Z) **Step 1: Add characterization check for canonical eval**

Run:

```bash
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 make eval-research
```

Expected:

- `GATE VERDICT: PASS`.
- Output has `report_schema_version: 4`.

- [x] (2026-06-28 09:40Z) **Step 2A: Archive legacy Ragas docs and script**

If preserving history:

```bash
mkdir -p docs/archive/legacy-ragas
git mv eval/METRICS_ANALYSIS.md docs/archive/legacy-ragas/METRICS_ANALYSIS.md
git mv eval/RESULTS_SUMMARY.md docs/archive/legacy-ragas/RESULTS_SUMMARY.md
git mv eval/evaluate.py docs/archive/legacy-ragas/evaluate.py
```

Add `docs/archive/legacy-ragas/README.md`:

```markdown
# Legacy Ragas Evaluation

This folder preserves the old Ragas evaluation flow that called the legacy
LangGraph pipeline. It is not the current production eval path.

Current eval commands:

```bash
make eval-research
make eval-research-live
make eval-research-gate
```
```

- [ ] **Step 2B: Delete legacy Ragas files**

If not preserving executable history:

```bash
git rm eval/evaluate.py eval/METRICS_ANALYSIS.md eval/RESULTS_SUMMARY.md
```

- [x] (2026-06-28 09:40Z) **Step 3: Rewrite `eval/README.md`**

Replace the old Ragas README with:

```markdown
# Research Evaluation

The canonical research workflow eval is `eval/research_eval.py`.

## Commands

```bash
make eval-research
make eval-research-live
make eval-research-gate
```

## Dataset

- `eval/research_golden_set.jsonl`

## Report Schema

Current schema: `report_schema_version=4`.

The report includes:

- `mean_recall_at_k`
- `mean_mrr_at_k`
- `failure_stage_counts`
- per-query `hit_ranks`
- per-query `failure_stage`
```

- [x] (2026-06-28 09:40Z) **Step 4: Verify no live references remain**

Run:

```bash
rg -n "eval/evaluate.py|Ragas|ragas|METRICS_ANALYSIS|RESULTS_SUMMARY" README.md CLAUDE.md AGENTS.md eval docs/research-workflow
```

Expected:

- Active docs point to `eval/research_eval.py`.
- Legacy references only appear under `docs/archive/`.

- [x] (2026-06-28 09:40Z) **Step 5: Verify**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_research_eval_metrics.py tests/research/test_observability.py -q
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 make eval-research
git diff --check
```

Expected:

- Focused eval tests pass.
- Dry-run eval passes.

- [x] (2026-06-28 09:40Z) **Step 6: Commit**

```bash
git add eval docs README.md CLAUDE.md AGENTS.md
git commit -m "docs(eval): make research eval the canonical path"
```

---

## Task 5: Decide LlamaIndex Code Fate

**2026-06-28 status:** Deferred. Subagent audit confirmed this path is optional
and not production, but moving/deleting it affects optional tests and historical
comparison. Requires explicit keep/archive/delete decision.

**Files:**
- Candidate keep/retire:
  - `agent/frameworks/llamaindex/**`
  - `tests/test_llamaindex_*`
  - `agent/frameworks/README.md`
  - `docs/frameworks/README.md`

**Decision Required From User:** Choose one:

1. **Keep as experiment:** Move to `experiments/llamaindex/` and keep tests opt-in.
2. **Archive/delete:** Remove source and tests; keep historical docs in `docs/archive/llamaindex-migration/`.

Recommended for production cleanup: option 2, because LlamaIndex is not wired into production chat and the historical docs are already archived.

- [ ] **Step 1: Confirm production does not import LlamaIndex**

Run:

```bash
rg -n "agent.frameworks.llamaindex|run_llamaindex_pipeline|create_llamaindex_graph" api agent/research eval scripts tests docs -g '!docs/archive/**'
```

Expected:

- Only optional tests, framework docs, or optional framework code reference it.
- No `api/` or `agent/research/` production module imports it.

- [ ] **Step 2A: If keeping as experiment**

```bash
mkdir -p experiments/llamaindex
git mv agent/frameworks/llamaindex experiments/llamaindex/agent_llamaindex
git mv tests/test_llamaindex_integration.py experiments/llamaindex/test_llamaindex_integration.py
git mv tests/test_llamaindex_vector_store_phase2.py experiments/llamaindex/test_llamaindex_vector_store_phase2.py
git mv tests/test_llamaindex_retriever_phase3.py experiments/llamaindex/test_llamaindex_retriever_phase3.py
git mv tests/test_llamaindex_llm_phase4.py experiments/llamaindex/test_llamaindex_llm_phase4.py
git mv tests/test_llamaindex_reranker_phase5.py experiments/llamaindex/test_llamaindex_reranker_phase5.py
git mv tests/test_llamaindex_full_integration_phase6.py experiments/llamaindex/test_llamaindex_full_integration_phase6.py
```

Then update imports inside moved tests from:

```python
from agent.frameworks.llamaindex import ...
```

to:

```python
from experiments.llamaindex.agent_llamaindex import ...
```

- [ ] **Step 2B: If archiving/deleting**

```bash
git rm -r agent/frameworks/llamaindex
git rm tests/test_llamaindex_integration.py
git rm tests/test_llamaindex_vector_store_phase2.py
git rm tests/test_llamaindex_retriever_phase3.py
git rm tests/test_llamaindex_llm_phase4.py
git rm tests/test_llamaindex_reranker_phase5.py
git rm tests/test_llamaindex_full_integration_phase6.py
```

Update `agent/frameworks/README.md`:

```markdown
# Framework Integrations

No optional framework integration is active in source.

Historical LlamaIndex migration notes are archived under
`docs/archive/llamaindex-migration/`.

The production chat path uses `agent/research/`.
```

- [ ] **Step 3: Simplify `tests/conftest.py`**

If deleting LlamaIndex tests, remove the optional LlamaIndex skip hook:

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
```

- [ ] **Step 4: Verify**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/ -q
cd web && npm run build
git diff --check
```

Expected:

- Full backend suite passes.
- Frontend build passes.

- [ ] **Step 5: Commit**

If keeping:

```bash
git add agent tests experiments docs
git commit -m "chore(experiments): isolate optional LlamaIndex prototype"
```

If deleting:

```bash
git add agent tests docs
git commit -m "chore(repo): retire unused LlamaIndex prototype"
```

---

## Task 6: Retire Legacy LangGraph Baseline

**2026-06-28 status:** Deferred. Subagent audit confirmed chat no longer uses
the legacy graph as the primary path, but the modules are still imported by
historical tests and `agent/answerability.py` remains active. Requires explicit
delete vs one-release-retention decision.

**Files:**
- Candidate remove:
  - `agent/graph.py`
  - `agent/pipeline.py`
  - `agent/state.py`
  - `agent/nodes/**`
  - `tests/test_stage2_*`
  - `tests/test_graph_construction.py`
  - `tests/test_embed_query_fix.py`
- Preserve or migrate first:
  - no-answer user messages currently imported by `api/routes/chat.py` from `agent/answerability.py`
  - shared source/citation utilities if still imported by active code

**Decision Required From User:** Delete the legacy LangGraph baseline now, or keep it one more release as comparison-only.

Recommended: delete after Task 4 and Task 5, because `/api/chat` no longer uses it and the current research workflow has passed full tests, frontend build, eval dry-run, and live smoke.

- [ ] **Step 1: Extract active no-answer messages away from legacy state**

Create `agent/research/answerability.py`:

```python
from __future__ import annotations

from enum import Enum


class AnswerabilityReason(str, Enum):
    ANSWERABLE = "ANSWERABLE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    NO_PAPER_FOUND = "NO_PAPER_FOUND"
    NO_EVIDENCE_FOUND = "NO_EVIDENCE_FOUND"
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
    INFRA_ERROR = "INFRA_ERROR"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"


NO_ANSWER_MESSAGES = {
    AnswerabilityReason.OUT_OF_SCOPE.value: (
        "Cau hoi nay nam ngoai pham vi tro ly nghien cuu AI/ML. "
        "Hay hoi ve paper, model, RAG, LLM, retrieval, evaluation, hoac chu de AI lien quan."
    ),
    AnswerabilityReason.NO_PAPER_FOUND.value: (
        "Khong tim thay paper phu hop de tra loi cau hoi nay."
    ),
    AnswerabilityReason.NO_EVIDENCE_FOUND.value: (
        "Da tim thay paper ung vien, nhung chua co evidence span du tin cay de tra loi."
    ),
    AnswerabilityReason.WEAK_EVIDENCE.value: (
        "Nguon tim duoc co do lien quan qua thap, nen toi khong tra loi de tranh bia dat."
    ),
    AnswerabilityReason.INFRA_ERROR.value: (
        "He thong truy xuat nguon dang gap loi, vui long thu lai sau."
    ),
    AnswerabilityReason.NEEDS_CLARIFICATION.value: (
        "Cau hoi hien chua du ro de truy xuat nguon chinh xac. Hay bo sung chu de, thoi gian, hoac loai nguon can tim."
    ),
}


def build_no_answer_message(reason: str) -> str:
    return NO_ANSWER_MESSAGES.get(reason, "Chua du nguon de tra loi cau hoi nay.")
```

Update `api/routes/chat.py` import:

```python
from agent.research.answerability import build_no_answer_message
```

- [ ] **Step 2: Add focused tests for active no-answer messages**

Create `tests/research/test_research_answerability.py`:

```python
from agent.research.answerability import build_no_answer_message


def test_build_no_answer_message_returns_out_of_scope_message():
    message = build_no_answer_message("OUT_OF_SCOPE")

    assert "ngoai pham vi" in message


def test_build_no_answer_message_has_safe_fallback():
    assert build_no_answer_message("UNKNOWN") == "Chua du nguon de tra loi cau hoi nay."
```

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_research_answerability.py tests/research/test_research_chat_integration.py -q
```

Expected:

- Tests pass.

- [ ] **Step 3: Remove legacy graph modules and tests**

```bash
git rm agent/answerability.py
git rm agent/graph.py agent/pipeline.py agent/state.py
git rm -r agent/nodes
git rm tests/test_stage2_graph.py
git rm tests/test_stage2_intent.py
git rm tests/test_stage2_memory.py
git rm tests/test_stage2_scenarios.py
git rm tests/test_stage2_search.py
git rm tests/test_graph_construction.py
git rm tests/test_embed_query_fix.py
```

- [ ] **Step 4: Fix remaining imports**

Run:

```bash
rg -n "agent\\.graph|agent\\.pipeline|agent\\.state|agent\\.nodes|agent.answerability|from agent\\.answerability" agent api eval scripts tests docs README.md CLAUDE.md AGENTS.md -g '!docs/archive/**'
```

Expected:

- No active code imports removed modules.
- Any remaining references are under docs/archive or are rewritten to current architecture.

- [ ] **Step 5: Update docs**

Update active docs:

- `CLAUDE.md`
- `README.md`
- `docs/research-workflow/ARCHITECTURE.md`
- `docs/research-workflow/LEGACY_RETIREMENT_PLAN.md`
- `docs/research-workflow/CHECKLOG.md`
- `docs/research-workflow/SOURCE_OWNERSHIP.md`

Use this wording:

```markdown
The old LangGraph baseline has been removed from active source after the
research workflow became the canonical chat path. Historical notes remain under
`docs/archive/legacy-rag/`.
```

- [ ] **Step 6: Verify**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/ -q
cd web && npm run build
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 make eval-research
git diff --check
```

Expected:

- Full backend suite passes.
- Frontend build passes.
- Dry-run eval passes.

- [ ] **Step 7: Commit**

```bash
git add agent api tests docs README.md CLAUDE.md AGENTS.md
git commit -m "refactor(research): remove legacy LangGraph baseline"
```

---

## Task 7: Root Documentation And Deployment Docs Cleanup

**Files:**
- Candidate update/archive:
  - `README.md`
  - `CLAUDE.md`
  - `AGENTS.md`
  - `DESIGN.md`
  - `INTEGRATION_PLAN.md`
  - `LOVABLE_PROMPT.md`
  - `UI_AUDIT.md`
  - `QUICK_TUNNEL_README.md`
  - `docs/QUICK_DEPLOYMENT.md`
  - `docs/QUICK_TUNNEL_GUIDE.md`
  - `docs/CLOUDFLARE_TUNNEL_SETUP.md`
  - `docs/LOCAL_BACKEND_DEPLOYMENT.md`

- [x] (2026-06-28 09:40Z) **Step 1: Classify docs**

Create or update `docs/README.md` sections:

```markdown
## Canonical Docs

- `../README.md`
- `../CLAUDE.md`
- `research-workflow/README.md`
- `research-workflow/ARCHITECTURE.md`
- `research-workflow/ROADMAP.md`
- `research-workflow/CHECKLOG.md`

## Deployment Docs

- `LOCAL_BACKEND_DEPLOYMENT.md`
- `QUICK_TUNNEL_GUIDE.md`
- `CLOUDFLARE_TUNNEL_SETUP.md`

## Archived Docs

Historical or stale docs live under `archive/`.
```

- [x] (2026-06-28 09:40Z) **Step 2: Archive stale root docs only after review**

If a doc is stale and duplicated by canonical docs:

```bash
mkdir -p docs/archive/root-notes
git mv DESIGN.md docs/archive/root-notes/DESIGN.md
git mv INTEGRATION_PLAN.md docs/archive/root-notes/INTEGRATION_PLAN.md
git mv UI_AUDIT.md docs/archive/root-notes/UI_AUDIT.md
```

Do not move `LOVABLE_PROMPT.md` unless the user confirms Lovable exports are no longer used.

- [x] (2026-06-28 09:40Z) **Step 3: Verify docs references**

Run:

```bash
rg -n "DESIGN.md|INTEGRATION_PLAN.md|UI_AUDIT.md|LOVABLE_PROMPT.md" README.md CLAUDE.md AGENTS.md docs -g '!docs/archive/**'
```

Expected:

- No active docs point at archived stale files.
- Lovable references remain only if Lovable is still part of the workflow.

- [x] (2026-06-28 09:40Z) **Step 4: Commit**

```bash
git add README.md CLAUDE.md AGENTS.md docs
git commit -m "docs: route stale notes into archive"
```

---

## Task 8: Final Verification And Release Report

**Files:**
- Modify: `docs/research-workflow/CHECKLOG.md`

- [x] (2026-06-28 09:40Z) **Step 1: Run complete verification**

```bash
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q
cd web && npm run build
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 make eval-research
git diff --check
```

Expected:

- Full backend suite passes.
- Frontend build passes.
- Dry-run eval returns `GATE VERDICT: PASS`.
- Whitespace check passes.

- [x] (2026-06-28 09:40Z) **Step 2: Record decisions**

Append to `docs/research-workflow/CHECKLOG.md`:

```markdown
| 2026-06-28 | Source cleanup removed generated artifacts and retired unused legacy paths. | Production chat uses `agent/research/`; keeping obsolete importable paths made source ownership ambiguous. | Implemented |
```

Also record explicit user decisions:

- whether LlamaIndex code was kept, moved, or deleted,
- whether Ragas legacy eval was archived or deleted,
- whether LangGraph baseline was deleted or retained for one release.

- [x] (2026-06-28 09:40Z) **Step 3: Commit**

```bash
git add docs/research-workflow/CHECKLOG.md
git commit -m "docs: record source cleanup decisions"
```

---

## Recommended Execution Order

1. Task 1: ownership document.
2. Task 2: generated artifacts cleanup.
3. Task 3 and Task 4: legacy Ragas cleanup.
4. Task 5: LlamaIndex decision and cleanup.
5. Task 6: legacy LangGraph deletion.
6. Task 7: root docs cleanup.
7. Task 8: final verification.

## Stop Conditions

Stop and ask the user before:

- deleting `agent/frameworks/llamaindex/**`,
- deleting `agent/graph.py`, `agent/pipeline.py`, `agent/state.py`, or `agent/nodes/**`,
- deleting or moving `skills/`, `.codex/`, `.claude/`, `.agents/`, `cohere/`, `lovable-export/`, or `reskin-landing.png`,
- deleting `LOVABLE_PROMPT.md`,
- changing runtime behavior or API contracts.

## Verification Baseline

Last known green baseline before this cleanup plan:

```text
Backend full suite: 203 passed, 30 skipped, 22 warnings
Frontend build: passed
Research eval dry-run: GATE VERDICT: PASS, report_schema_version=4
Branch: dev
Remote: origin/dev at 8742ca2
```
