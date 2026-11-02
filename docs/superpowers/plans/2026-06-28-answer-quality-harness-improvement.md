# Answer Quality Harness Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve paper-answer quality by proving whether failures come from discovery/ranking/evidence/synthesis/model, then fixing the highest-leverage harness gaps before upgrading the LLM.

**Architecture:** Keep `agent/research/` as the canonical production workflow. Add diagnostic evals and stage-level labels first, then add canonical paper resolution, intent-aware retrieval/ranking, evidence-quality gates, and structured synthesis. Model quality is evaluated only with fixed oracle context so it cannot hide retrieval failures.

**Tech Stack:** Python/FastAPI, pytest, uv, existing `agent/research/` workflow, provider-backed discovery (arXiv/Semantic Scholar/OpenAlex), OpenRouter/Gemini/Ollama through `agent/generator.py`, Next.js frontend citation rendering.

---

## Context

Recent manual tests showed:

- `Transformer paper có gì` returned a list of transformer-related papers instead of prioritizing `Attention Is All You Need` (`1706.03762`).
- `compare LoRA and QLoRA papers` returned downstream application papers instead of prioritizing the original LoRA and QLoRA papers.
- `ROS2 trong robotics là gì` found plausible sources but returned a thin answer with citations grouped at the end.
- The frontend did not render source cards even when backend emitted `source-url` stream events; this was fixed separately in `web/src/app/chat/page.tsx` and `web/src/components/chat/chat-message.tsx` but is currently outside this plan.

Working diagnosis:

- Discovery/ranking is the main issue for seminal-paper queries.
- Evidence quality is the main issue for explanation depth.
- Synthesis prompt/model is a secondary issue until oracle-context eval proves otherwise.
- A model upgrade should happen only after same-context synthesis eval shows the current model cannot follow the contract.

Public references used for direction:

- OpenAI Codex and AGENTS.md: https://github.com/openai/codex and https://developers.openai.com/codex/guides/agents-md
- OpenAI Harness Engineering: https://openai.com/index/harness-engineering/
- Anthropic Context Engineering and Contextual Retrieval: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents and https://www.anthropic.com/engineering/contextual-retrieval
- Anthropic eval guidance for agents: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Cohere RAG citations: https://docs.cohere.com/docs/rag-citations
- LlamaIndex citation query engine: https://developers.llamaindex.ai/python/examples/query_engine/citation_query_engine/

## File Structure

New files:

- `eval/answer_quality_golden_set.jsonl` — small diagnostic set for answer-quality failures observed in UI.
- `eval/research_diagnostics.py` — stage-by-stage diagnostic CLI for discovery, ranking, evidence, and oracle synthesis.
- `agent/research/canonical_papers.py` — curated canonical registry for seminal papers and alias resolution.
- `tests/research/test_canonical_papers.py` — deterministic canonical resolver tests.
- `tests/research/test_research_diagnostics.py` — diagnostic CLI/report tests.
- `tests/research/test_structured_synthesis.py` — synthesis contract tests using fixed evidence.

Modified files:

- `agent/research/query_plan.py` — add query intent and canonical target fields.
- `agent/research/discovery/service.py` — use canonical target signals while scoring and querying.
- `agent/research/ranking/features.py` — add canonical-match and comparison-coverage features.
- `agent/research/ranking/reranker.py` — preserve exact/canonical matches against cross-encoder demotion.
- `agent/research/synthesis/claim_answer.py` — output claim-grounded structure and validate citation coverage.
- `agent/research/evals/metrics.py` — add stage-specific answer-quality metrics.
- `eval/research_eval.py` — include stage diagnosis for diagnostic runs without changing the existing promotion gate semantics.
- `docs/research-workflow/CHECKLOG.md` — record answer-quality decisions and verification.

Do not touch in this plan:

- `.env`, `.env.*`, keys, or credentials.
- `agent/frameworks/llamaindex/**` and legacy LangGraph retirement files.
- Untracked local folders: `cohere/`, `lovable-export/`, `skills/`, `reskin-landing.png`.
- Existing uncommitted frontend citation UI changes unless explicitly batching them into a separate commit before this plan starts.

---

## Task 1: Add Answer-Quality Diagnostic Golden Set

**Files:**
- Create: `eval/answer_quality_golden_set.jsonl`
- Test: `tests/research/test_research_eval_metrics.py`

- [x] (2026-06-28 16:04Z) **Step 1: Create the diagnostic dataset**

Create `eval/answer_quality_golden_set.jsonl`:

```jsonl
{"id":"transformer-original-vi","query":"Transformer paper có gì","task_type":"paper_lookup","expected_papers":["1706.03762"],"expected_terms":["attention mechanism","self-attention","encoder","decoder"],"expected_answer_type":"canonical_paper_explanation"}
{"id":"lora-qlora-comparison","query":"compare LoRA and QLoRA papers","task_type":"comparison","expected_papers":["2106.09685","2305.14314"],"expected_terms":["low-rank adaptation","4-bit","quantization","memory"],"expected_answer_type":"paper_comparison"}
{"id":"ros2-robotics-concept","query":"ROS2 trong robotics là gì","task_type":"concept","expected_papers":["2306.17157","2209.14030"],"expected_terms":["ROS 2","Robot Operating System 2","robotics","middleware"],"expected_answer_type":"concept_grounded"}
{"id":"no-evidence-personal","query":"paper about my private birthday plan","task_type":"no_answer","expected_papers":[],"expected_terms":[],"expected_answer_type":"no_evidence"}
```

- [x] (2026-06-28 16:04Z) **Step 2: Verify dataset loads**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run python - <<'PY'
from pathlib import Path
from agent.research.evals.datasets import load_golden_dataset
rows = load_golden_dataset(Path("eval/answer_quality_golden_set.jsonl"))
assert len(rows) == 4
assert rows[0].id == "transformer-original-vi"
assert rows[1].expected_papers == ["2106.09685", "2305.14314"]
print("answer-quality dataset ok")
PY
```

Expected:

```text
answer-quality dataset ok
```

- [x] (2026-06-28 16:04Z) **Step 3: Add a regression test for the diagnostic dataset**

Append to `tests/research/test_research_eval_metrics.py`:

```python
def test_answer_quality_dataset_loads_observed_ui_failures():
    rows = load_golden_dataset(Path("eval/answer_quality_golden_set.jsonl"))

    assert [row.id for row in rows] == [
        "transformer-original-vi",
        "lora-qlora-comparison",
        "ros2-robotics-concept",
        "no-evidence-personal",
    ]
    assert rows[0].expected_papers == ["1706.03762"]
    assert rows[1].expected_papers == ["2106.09685", "2305.14314"]
```

- [x] (2026-06-28 16:04Z) **Step 4: Run focused tests**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_research_eval_metrics.py::test_answer_quality_dataset_loads_observed_ui_failures -q
```

Expected:

```text
1 passed
```

- [x] (2026-06-28 16:04Z) **Step 5: Commit**

```bash
git add eval/answer_quality_golden_set.jsonl tests/research/test_research_eval_metrics.py
git commit -m "test(research): add answer quality diagnostic set"
```

---

## Task 2: Add Stage Diagnostic CLI

**Files:**
- Create: `eval/research_diagnostics.py`
- Create: `tests/research/test_research_diagnostics.py`

- [x] (2026-06-28 16:04Z) **Step 1: Write the failing tests**

Create `tests/research/test_research_diagnostics.py`:

```python
from pathlib import Path

from agent.research.discovery.models import PaperCandidate
from eval.research_diagnostics import diagnose_row, summarize_diagnostics


def test_diagnose_row_marks_discovery_miss(monkeypatch):
    def fake_discover(plan, provider_names=None, max_results=10):
        return [PaperCandidate(title="Unrelated", arxiv_id="9999.99999")]

    monkeypatch.setattr("eval.research_diagnostics.discover_papers", fake_discover)

    row = {
        "id": "transformer-original-vi",
        "query": "Transformer paper có gì",
        "expected_papers": ["1706.03762"],
        "expected_terms": ["self-attention"],
        "task_type": "paper_lookup",
    }

    result = diagnose_row(row, top_k=5, providers=["fake"])

    assert result["id"] == "transformer-original-vi"
    assert result["stage"] == "discovery_or_ranking_miss"
    assert result["paper_hit_ranks"] == {}


def test_summarize_diagnostics_counts_stages():
    report = summarize_diagnostics(
        [
            {"stage": "passed"},
            {"stage": "discovery_or_ranking_miss"},
            {"stage": "discovery_or_ranking_miss"},
        ]
    )

    assert report["stage_counts"] == {
        "passed": 1,
        "discovery_or_ranking_miss": 2,
    }
```

- [x] (2026-06-28 16:04Z) **Step 2: Run tests to verify failure**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_research_diagnostics.py -q
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'eval.research_diagnostics'
```

- [x] (2026-06-28 16:04Z) **Step 3: Implement the diagnostic CLI**

Create `eval/research_diagnostics.py`:

```python
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

from agent.research.discovery.service import discover_papers
from agent.research.evals.metrics import paper_hit_ranks_at_k, paper_recall_at_k
from agent.research.indexing.contextual_chunks import create_contextual_chunks
from agent.research.indexing.paper_store import PaperStore
from agent.research.indexing.section_parser import parse_paper_text
from agent.research.query_plan import plan_research_query
from agent.research.ranking.reranker import rank_candidates
from agent.research.evidence.retriever import retrieve_evidence


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def diagnose_row(row: Dict[str, Any], *, top_k: int = 10, providers: List[str] | None = None) -> Dict[str, Any]:
    plan = plan_research_query(row["query"])
    candidates = discover_papers(plan, provider_names=providers, max_results=max(top_k * 3, 10))
    ranked = rank_candidates(plan, candidates, top_k=top_k)
    expected = row.get("expected_papers", [])
    hit_ranks = paper_hit_ranks_at_k(ranked, expected, k=top_k)
    paper_recall = paper_recall_at_k(ranked, expected, k=top_k) if expected else 0.0

    stage = "passed"
    if expected and paper_recall == 0.0:
        stage = "discovery_or_ranking_miss"

    evidence_count = 0
    if stage == "passed":
        store = PaperStore()
        chunks = []
        for candidate in ranked:
            paper = store.upsert_candidate(candidate)
            parsed = parse_paper_text(candidate.abstract, candidate=candidate)
            chunks.extend(create_contextual_chunks(paper, parsed))
        evidence = retrieve_evidence(row["query"], chunks, paper_ids=[paper.paper_id for paper in store.all()], top_k=top_k)
        evidence_count = len(evidence)
        if expected and evidence_count == 0:
            stage = "evidence_miss"

    return {
        "id": row["id"],
        "query": row["query"],
        "stage": stage,
        "paper_hit_ranks": hit_ranks,
        "paper_recall_at_k": paper_recall,
        "candidate_count": len(candidates),
        "ranked_count": len(ranked),
        "evidence_count": evidence_count,
        "top_papers": [
            {"title": item.title, "arxiv_id": item.arxiv_id, "score": item.score}
            for item in ranked[:top_k]
        ],
    }


def summarize_diagnostics(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    items = list(results)
    return {
        "query_count": len(items),
        "stage_counts": dict(Counter(item["stage"] for item in items)),
        "results": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="eval/answer_quality_golden_set.jsonl")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--providers", default="")
    args = parser.parse_args()

    providers = [item.strip() for item in args.providers.split(",") if item.strip()] or None
    rows = _load_jsonl(Path(args.dataset))
    report = summarize_diagnostics(diagnose_row(row, top_k=args.top_k, providers=providers) for row in rows)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] (2026-06-28 16:04Z) **Step 4: Run focused tests**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_research_diagnostics.py -q
```

Expected:

```text
2 passed
```

- [x] (2026-06-28 16:04Z) **Step 5: Run diagnostic dry command**

```bash
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 uv run python eval/research_diagnostics.py --dataset eval/answer_quality_golden_set.jsonl --top-k 10
```

Expected:

- JSON report prints `query_count: 4`.
- `stage_counts` identifies whether observed failures are discovery/ranking/evidence.

- [x] (2026-06-28 16:04Z) **Step 6: Commit**

```bash
git add eval/research_diagnostics.py tests/research/test_research_diagnostics.py
git commit -m "feat(research): add answer quality diagnostics"
```

---

## Task 3: Add Canonical Paper Registry

**Files:**
- Create: `agent/research/canonical_papers.py`
- Create: `tests/research/test_canonical_papers.py`
- Modify: `agent/research/query_plan.py`

- [x] (2026-06-28 16:04Z) **Step 1: Write resolver tests**

Create `tests/research/test_canonical_papers.py`:

```python
from agent.research.canonical_papers import resolve_canonical_papers


def test_resolves_transformer_paper_from_vietnamese_lookup():
    matches = resolve_canonical_papers("Transformer paper có gì")

    assert matches[0].arxiv_id == "1706.03762"
    assert matches[0].title == "Attention Is All You Need"


def test_resolves_lora_and_qlora_for_comparison():
    matches = resolve_canonical_papers("compare LoRA and QLoRA papers")

    assert [match.arxiv_id for match in matches] == ["2106.09685", "2305.14314"]


def test_does_not_resolve_generic_transformer_survey():
    matches = resolve_canonical_papers("recent transformer surveys for time series")

    assert matches == []
```

- [x] (2026-06-28 16:04Z) **Step 2: Run tests to verify failure**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_canonical_papers.py -q
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'agent.research.canonical_papers'
```

- [x] (2026-06-28 16:04Z) **Step 3: Implement registry**

Create `agent/research/canonical_papers.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class CanonicalPaper:
    key: str
    title: str
    arxiv_id: str
    aliases: tuple[str, ...]


CANONICAL_PAPERS: tuple[CanonicalPaper, ...] = (
    CanonicalPaper(
        key="transformer",
        title="Attention Is All You Need",
        arxiv_id="1706.03762",
        aliases=("transformer paper", "original transformer", "attention is all you need"),
    ),
    CanonicalPaper(
        key="lora",
        title="LoRA: Low-Rank Adaptation of Large Language Models",
        arxiv_id="2106.09685",
        aliases=("lora paper", "low-rank adaptation", "original lora"),
    ),
    CanonicalPaper(
        key="qlora",
        title="QLoRA: Efficient Finetuning of Quantized LLMs",
        arxiv_id="2305.14314",
        aliases=("qlora paper", "quantized low-rank adaptation", "original qlora"),
    ),
    CanonicalPaper(
        key="bert",
        title="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        arxiv_id="1810.04805",
        aliases=("bert paper", "original bert"),
    ),
    CanonicalPaper(
        key="rag",
        title="Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        arxiv_id="2005.11401",
        aliases=("rag paper", "original rag", "retrieval augmented generation original"),
    ),
)


def _contains_lookup_intent(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ("paper", "original", "summary", "có gì", "explained", "compare"))


def resolve_canonical_papers(query: str) -> List[CanonicalPaper]:
    lowered = query.lower()
    if not _contains_lookup_intent(query):
        return []

    matches: List[CanonicalPaper] = []
    for paper in CANONICAL_PAPERS:
        if any(alias in lowered for alias in paper.aliases) or paper.key in lowered:
            matches.append(paper)

    if "compare" in lowered and "lora" in lowered and "qlora" in lowered:
        ordered = [paper for key in ("lora", "qlora") for paper in CANONICAL_PAPERS if paper.key == key]
        return ordered

    return matches
```

- [x] (2026-06-28 16:04Z) **Step 4: Extend query plan**

Modify `agent/research/query_plan.py`:

```python
from agent.research.canonical_papers import resolve_canonical_papers
```

Add to `QueryPlan`:

```python
canonical_arxiv_ids: List[str] = field(default_factory=list)
canonical_titles: List[str] = field(default_factory=list)
```

Inside `plan_research_query`, before returning:

```python
canonical_matches = resolve_canonical_papers(query)
canonical_arxiv_ids = [paper.arxiv_id for paper in canonical_matches]
canonical_titles = [paper.title for paper in canonical_matches]
```

Add to the returned `QueryPlan`:

```python
canonical_arxiv_ids=canonical_arxiv_ids,
canonical_titles=canonical_titles,
```

- [x] (2026-06-28 16:04Z) **Step 5: Add query plan regression tests**

Append to `tests/research/test_query_plan.py`:

```python
def test_plan_research_query_resolves_canonical_transformer_lookup():
    plan = plan_research_query("Transformer paper có gì")

    assert plan.canonical_arxiv_ids == ["1706.03762"]
    assert plan.canonical_titles == ["Attention Is All You Need"]


def test_plan_research_query_resolves_lora_qlora_comparison_targets():
    plan = plan_research_query("compare LoRA and QLoRA papers")

    assert plan.canonical_arxiv_ids == ["2106.09685", "2305.14314"]
```

- [x] (2026-06-28 16:04Z) **Step 6: Run focused tests**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_canonical_papers.py tests/research/test_query_plan.py -q
```

Expected:

```text
all tests passed
```

- [x] (2026-06-28 16:04Z) **Step 7: Commit**

```bash
git add agent/research/canonical_papers.py agent/research/query_plan.py tests/research/test_canonical_papers.py tests/research/test_query_plan.py
git commit -m "feat(research): resolve canonical paper targets"
```

---

## Task 4: Use Canonical Targets In Discovery And Ranking

**Files:**
- Modify: `agent/research/discovery/service.py`
- Modify: `agent/research/ranking/features.py`
- Modify: `agent/research/ranking/reranker.py`
- Test: `tests/research/test_discovery_service.py`
- Test: `tests/research/test_candidate_ranking.py`

- [x] (2026-06-28 16:04Z) **Step 1: Add failing discovery tests**

Append to `tests/research/test_discovery_service.py`:

```python
def test_discover_papers_boosts_canonical_transformer_target():
    def fake_provider(plan, max_results=20):
        return [
            PaperCandidate(
                title="Robotics Transformer for Real-World Control at Scale",
                abstract="A transformer model for robotics.",
                arxiv_id="2212.06817",
                citation_count=1000,
                year=2022,
                provider_rank=1,
            ),
            PaperCandidate(
                title="Attention Is All You Need",
                abstract="We propose the Transformer architecture.",
                arxiv_id="1706.03762",
                citation_count=100000,
                year=2017,
                provider_rank=2,
            ),
        ]

    results = discover_papers("Transformer paper có gì", providers={"fake": fake_provider}, provider_names=["fake"])

    assert results[0].arxiv_id == "1706.03762"
    assert results[0].score_breakdown["canonical_match"] == 1.0
```

- [x] (2026-06-28 16:04Z) **Step 2: Add failing ranking tests**

Append to `tests/research/test_candidate_ranking.py`:

```python
def test_rank_candidates_keeps_canonical_transformer_first():
    plan = plan_research_query("Transformer paper có gì")
    candidates = [
        PaperCandidate(
            title="Robotics Transformer for Real-World Control at Scale",
            abstract="A transformer model for robotics.",
            arxiv_id="2212.06817",
            citation_count=1000,
            year=2022,
            provider_rank=1,
        ),
        PaperCandidate(
            title="Attention Is All You Need",
            abstract="We propose the Transformer architecture.",
            arxiv_id="1706.03762",
            citation_count=100000,
            year=2017,
            provider_rank=2,
        ),
    ]

    ranked = rank_candidates(plan, candidates, top_k=2)

    assert ranked[0].arxiv_id == "1706.03762"
    assert ranked[0].score_breakdown["canonical_match"] == 1.0
```

- [x] (2026-06-28 16:04Z) **Step 3: Run tests to verify failure**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_discovery_service.py::test_discover_papers_boosts_canonical_transformer_target tests/research/test_candidate_ranking.py::test_rank_candidates_keeps_canonical_transformer_first -q
```

Expected before implementation:

```text
KeyError: 'canonical_match'
```

- [x] (2026-06-28 16:04Z) **Step 4: Implement canonical scoring in discovery**

In `agent/research/discovery/service.py`, inside `score_discovery_candidate`, add:

```python
    canonical_ids = {_normalize_arxiv_id(arxiv_id) for arxiv_id in getattr(plan, "canonical_arxiv_ids", [])}
    canonical_titles = {title.lower() for title in getattr(plan, "canonical_titles", [])}
    canonical_match = (
        1.0
        if (
            canonical_ids
            and _normalize_arxiv_id(candidate.arxiv_id) in canonical_ids
        )
        or candidate.title.lower() in canonical_titles
        else 0.0
    )
```

Add to `breakdown`:

```python
        "canonical_match": canonical_match,
```

Add to score:

```python
        + 1.2 * canonical_match
```

- [x] (2026-06-28 16:04Z) **Step 5: Implement canonical scoring in ranking**

In `agent/research/ranking/features.py`, mirror the same `canonical_match` feature and include it in the score with strong weight:

```python
    canonical_ids = {_normalize_arxiv_id(arxiv_id) for arxiv_id in getattr(plan, "canonical_arxiv_ids", [])}
    canonical_titles = {title.lower() for title in getattr(plan, "canonical_titles", [])}
    canonical_match = (
        1.0
        if (
            canonical_ids
            and _normalize_arxiv_id(candidate.arxiv_id) in canonical_ids
        )
        or candidate.title.lower() in canonical_titles
        else 0.0
    )
```

Add to returned breakdown:

```python
        "canonical_match": canonical_match,
```

Add to score:

```python
        + 1.2 * canonical_match
```

- [x] (2026-06-28 16:04Z) **Step 6: Preserve canonical matches from cross-encoder demotion**

In `agent/research/ranking/reranker.py`, after rerank scores are added but before final sorting, ensure canonical/exact matches stay first:

```python
def _final_sort_key(candidate: PaperCandidate) -> tuple[float, float]:
    exact = candidate.score_breakdown.get("identifier_match", 0.0)
    canonical = candidate.score_breakdown.get("canonical_match", 0.0)
    return (max(exact, canonical), candidate.score)
```

Use:

```python
return sorted(scored, key=_final_sort_key, reverse=True)[:top_k]
```

- [x] (2026-06-28 16:04Z) **Step 7: Run focused tests**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_discovery_service.py tests/research/test_candidate_ranking.py -q
```

Expected:

```text
all tests passed
```

- [x] (2026-06-28 16:04Z) **Step 8: Run answer-quality diagnostics**

```bash
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 uv run python eval/research_diagnostics.py --dataset eval/answer_quality_golden_set.jsonl --top-k 10
```

Expected improvement:

- `transformer-original-vi` is no longer `discovery_or_ranking_miss`.
- `lora-qlora-comparison` includes both expected papers if providers return them.

- [x] (2026-06-28 16:04Z) **Step 9: Commit**

```bash
git add agent/research/discovery/service.py agent/research/ranking/features.py agent/research/ranking/reranker.py tests/research/test_discovery_service.py tests/research/test_candidate_ranking.py
git commit -m "feat(research): boost canonical paper matches"
```

---

## Task 5: Add Comparison Coverage Ranking

**Files:**
- Modify: `agent/research/ranking/features.py`
- Test: `tests/research/test_candidate_ranking.py`

- [x] (2026-06-28 16:17Z) **Step 1: Add failing test**

Append to `tests/research/test_candidate_ranking.py`:

```python
def test_rank_candidates_keeps_both_lora_and_qlora_for_comparison():
    plan = plan_research_query("compare LoRA and QLoRA papers")
    candidates = [
        PaperCandidate(
            title="A photovoltaic defect classifier using QLoRA",
            abstract="QLoRA is used for classification.",
            arxiv_id="2401.00001",
            provider_rank=1,
            year=2024,
        ),
        PaperCandidate(
            title="LoRA: Low-Rank Adaptation of Large Language Models",
            abstract="LoRA reduces trainable parameters.",
            arxiv_id="2106.09685",
            provider_rank=2,
            year=2021,
            citation_count=10000,
        ),
        PaperCandidate(
            title="QLoRA: Efficient Finetuning of Quantized LLMs",
            abstract="QLoRA uses 4-bit quantization and low-rank adapters.",
            arxiv_id="2305.14314",
            provider_rank=3,
            year=2023,
            citation_count=8000,
        ),
    ]

    ranked = rank_candidates(plan, candidates, top_k=2)

    assert {item.arxiv_id for item in ranked} == {"2106.09685", "2305.14314"}
    assert all(item.score_breakdown["comparison_target_match"] == 1.0 for item in ranked)
```

- [x] (2026-06-28 16:17Z) **Step 2: Run test to verify failure if Task 4 is insufficient**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_candidate_ranking.py::test_rank_candidates_keeps_both_lora_and_qlora_for_comparison -q
```

Expected before comparison coverage:

- Test fails if an application paper stays in top 2.

- [x] (2026-06-28 16:17Z) **Step 3: Implement comparison coverage**

In `agent/research/ranking/features.py`, add:

```python
    comparison_target_match = 0.0
    canonical_ids = {_normalize_arxiv_id(arxiv_id) for arxiv_id in getattr(plan, "canonical_arxiv_ids", [])}
    if len(canonical_ids) > 1 and _normalize_arxiv_id(candidate.arxiv_id) in canonical_ids:
        comparison_target_match = 1.0
```

Add to breakdown:

```python
        "comparison_target_match": comparison_target_match,
```

Add to score:

```python
        + 0.8 * comparison_target_match
```

- [x] (2026-06-28 16:17Z) **Step 4: Run focused tests**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_candidate_ranking.py -q
```

Expected:

```text
all tests passed
```

- [x] (2026-06-28 16:17Z) **Step 5: Commit**

```bash
git add agent/research/ranking/features.py tests/research/test_candidate_ranking.py
git commit -m "feat(research): rank comparison target papers together"
```

Parent review adjustment: the original exact-order assertion was changed to a set assertion. Ranking should guarantee that both canonical comparison targets survive into the top results; presentation order can be handled later without biasing retrieval score.

---

## Task 6: Add Evidence Quality Metrics

**Files:**
- Modify: `agent/research/evals/metrics.py`
- Test: `tests/research/test_research_eval_metrics.py`
- Modify: `eval/research_diagnostics.py`

- [x] (2026-06-28 16:20Z) **Step 1: Add evidence coverage tests**

Append to `tests/research/test_research_eval_metrics.py`:

```python
from agent.research.evidence.models import EvidenceSpan
from agent.research.evals.metrics import evidence_term_recall


def test_evidence_term_recall_counts_expected_terms_across_quotes():
    evidence = [
        EvidenceSpan(paper_id="p1", title="T", url="u", quote="The Transformer uses self-attention.", score=0.9),
        EvidenceSpan(paper_id="p1", title="T", url="u", quote="It has encoder and decoder stacks.", score=0.8),
    ]

    assert evidence_term_recall(evidence, ["self-attention", "encoder", "decoder"]) == 1.0
    assert evidence_term_recall(evidence, ["self-attention", "missing"]) == 0.5
```

- [x] (2026-06-28 16:20Z) **Step 2: Run test to verify failure**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_research_eval_metrics.py::test_evidence_term_recall_counts_expected_terms_across_quotes -q
```

Expected before implementation:

```text
ImportError: cannot import name 'evidence_term_recall'
```

- [x] (2026-06-28 16:20Z) **Step 3: Implement metric**

Add to `agent/research/evals/metrics.py`:

```python
def evidence_term_recall(evidence: List[EvidenceSpan], expected_terms: Iterable[str]) -> float:
    terms = [term.lower() for term in expected_terms if term]
    if not terms:
        return 0.0
    joined = "\n".join(span.quote.lower() for span in evidence)
    hits = sum(1 for term in terms if term in joined)
    return hits / len(terms)
```

- [x] (2026-06-28 16:20Z) **Step 4: Include metric in diagnostics**

In `eval/research_diagnostics.py`, import:

```python
from agent.research.evals.metrics import evidence_term_recall
```

When evidence is retrieved, add:

```python
        evidence_term_coverage = evidence_term_recall(evidence, row.get("expected_terms", []))
        if expected and evidence_count > 0 and evidence_term_coverage == 0.0:
            stage = "weak_evidence"
```

Include in result:

```python
        "evidence_term_recall": evidence_term_coverage,
```

Initialize `evidence_term_coverage = 0.0` before evidence retrieval.

- [x] (2026-06-28 16:20Z) **Step 5: Run focused tests**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_research_eval_metrics.py tests/research/test_research_diagnostics.py -q
```

Expected:

```text
all tests passed
```

- [x] (2026-06-28 16:20Z) **Step 6: Commit**

```bash
git add agent/research/evals/metrics.py eval/research_diagnostics.py tests/research/test_research_eval_metrics.py tests/research/test_research_diagnostics.py
git commit -m "feat(research): measure evidence term coverage"
```

Parent review adjustment: `retrieve_evidence()` was moved out of the candidate loop so diagnostics build all chunks first and evaluate evidence once. Added a regression test to prevent partial-chunk `weak_evidence` stage drift.

---

## Task 7: Add Structured Claim-Grounded Synthesis Contract

**Files:**
- Modify: `agent/research/synthesis/claim_answer.py`
- Modify: `tests/research/test_claim_answer.py`

- [x] (2026-06-28 16:23Z) **Step 1: Add failing structured synthesis tests**

Extend existing `tests/research/test_claim_answer.py`:

```python
from agent.research.evidence.models import EvidenceSpan
from agent.research.synthesis.claim_answer import build_claim_grounded_prompt, validate_claim_citations


def test_claim_grounded_prompt_demands_claim_citation_pairs():
    evidence = [
        EvidenceSpan(
            paper_id="p1",
            title="Attention Is All You Need",
            url="https://arxiv.org/abs/1706.03762",
            quote="The Transformer is based solely on attention mechanisms.",
            score=0.9,
        )
    ]

    prompt = build_claim_grounded_prompt("Transformer paper có gì", evidence)

    assert "Every major claim must cite evidence IDs like [E1]" in prompt
    assert "Do not cite an evidence ID that is not listed" in prompt
    assert "[E1]" in prompt


def test_validate_claim_citations_rejects_uncited_claims():
    answer = "The Transformer uses attention mechanisms effectively. It removed recurrence. [E1]"

    result = validate_claim_citations(answer, allowed_ids={"E1"})

    assert result["valid"] is False
    assert result["uncited_claim_count"] >= 1


def test_validate_claim_citations_accepts_cited_claims():
    answer = "The Transformer uses attention [E1]. It removed recurrence [E1]."

    result = validate_claim_citations(answer, allowed_ids={"E1"})

    assert result["valid"] is True
```

- [x] (2026-06-28 16:23Z) **Step 2: Run tests to verify failure**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_claim_answer.py -q
```

Expected before implementation:

```text
ImportError: cannot import name 'validate_claim_citations'
```

- [x] (2026-06-28 16:23Z) **Step 3: Harden prompt**

Update `CLAIM_GROUNDED_TEMPLATE` in `agent/research/synthesis/claim_answer.py`:

```python
CLAIM_GROUNDED_TEMPLATE = """\
Answer the user's question using only the evidence below.

Rules:
- Every major claim must cite evidence IDs like [E1].
- Do not cite an evidence ID that is not listed.
- Do not group all citations at the end; place citations next to the claim they support.
- If the evidence is insufficient, say that the evidence is insufficient and list what is missing.
- Prefer the user's language.

Evidence:
{context}

Question: {question}
"""
```

- [x] (2026-06-28 16:23Z) **Step 4: Add citation validator**

Add to `agent/research/synthesis/claim_answer.py`:

```python
import re
from typing import Set


SENTENCE_RE = re.compile(r"[^.!?。！？]+[.!?。！？]?")
CITATION_RE = re.compile(r"\[(E\d+)\]")


def validate_claim_citations(answer: str, *, allowed_ids: Set[str]) -> dict:
    uncited_claim_count = 0
    invalid_ids = []
    for match in CITATION_RE.finditer(answer):
        if match.group(1) not in allowed_ids:
            invalid_ids.append(match.group(1))

    for sentence in SENTENCE_RE.findall(answer):
        stripped = sentence.strip()
        if not stripped:
            continue
        if len(stripped.split()) < 5:
            continue
        if "insufficient" in stripped.lower() or "chưa đủ" in stripped.lower():
            continue
        if not CITATION_RE.search(stripped):
            uncited_claim_count += 1

    return {
        "valid": not invalid_ids and uncited_claim_count == 0,
        "invalid_ids": invalid_ids,
        "uncited_claim_count": uncited_claim_count,
    }
```

- [x] (2026-06-28 16:23Z) **Step 5: Run focused tests**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_claim_answer.py -q
```

Expected:

```text
6 passed
```

- [x] (2026-06-28 16:23Z) **Step 6: Commit**

```bash
git add agent/research/synthesis/claim_answer.py tests/research/test_claim_answer.py
git commit -m "feat(research): validate claim-level citations"
```

Parent review adjustment: reused the existing claim-answer test module instead of creating a parallel structured-synthesis file. The validator threshold was corrected back to the planned >=5-word claim sentence rule, with the uncited test sentence lengthened accordingly.

---

## Task 8: Add Same-Context Model Attribution Eval

**Files:**
- Create: `eval/model_synthesis_eval.py`
- Create: `tests/research/test_model_synthesis_eval.py`

- [x] (2026-06-28 16:25Z) **Step 1: Add tests**

Create `tests/research/test_model_synthesis_eval.py`:

```python
from eval.model_synthesis_eval import grade_synthesis_output


def test_grade_synthesis_output_passes_claim_cited_answer():
    answer = "The Transformer uses self-attention [E1]. It removes recurrence [E1]."

    grade = grade_synthesis_output(answer, expected_terms=["self-attention", "recurrence"], allowed_ids={"E1"})

    assert grade["passes"] is True
    assert grade["term_recall"] == 1.0


def test_grade_synthesis_output_fails_missing_terms_or_citations():
    answer = "The Transformer is important."

    grade = grade_synthesis_output(answer, expected_terms=["self-attention"], allowed_ids={"E1"})

    assert grade["passes"] is False
```

- [x] (2026-06-28 16:25Z) **Step 2: Implement grader**

Create `eval/model_synthesis_eval.py`:

```python
from __future__ import annotations

from typing import Iterable, Set

from agent.research.synthesis.claim_answer import validate_claim_citations


def grade_synthesis_output(answer: str, *, expected_terms: Iterable[str], allowed_ids: Set[str]) -> dict:
    terms = [term.lower() for term in expected_terms if term]
    lowered = answer.lower()
    term_recall = 0.0 if not terms else sum(1 for term in terms if term in lowered) / len(terms)
    citation_grade = validate_claim_citations(answer, allowed_ids=allowed_ids)
    return {
        "passes": term_recall >= 0.8 and citation_grade["valid"],
        "term_recall": term_recall,
        "citation_grade": citation_grade,
    }
```

- [x] (2026-06-28 16:25Z) **Step 3: Run focused tests**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/research/test_model_synthesis_eval.py -q
```

Expected:

```text
3 passed
```

- [x] (2026-06-28 16:25Z) **Step 4: Manual model attribution run**

Use fixed evidence from the same paper and compare models by changing only `LLM_BACKEND`/model env values:

```bash
LLM_BACKEND=openrouter OPENROUTER_MODEL=xiaomi/mimo-v2-flash:free UV_CACHE_DIR=.uv-cache uv run python eval/model_synthesis_eval.py
LLM_BACKEND=openrouter OPENROUTER_MODEL=<stronger-model> UV_CACHE_DIR=.uv-cache uv run python eval/model_synthesis_eval.py
```

Expected decision rule:

- If current model fails fixed-context synthesis and stronger model passes, model upgrade is justified for synthesis only.
- If both fail, prompt/output contract is still weak.
- If both pass, retrieval/evidence is the bottleneck.

Implemented as a fixed-context CLI with `--answer` for deterministic local smoke tests. Direct live model comparison remains a manual operation because it depends on the chosen provider/model credentials.

- [x] (2026-06-28 16:25Z) **Step 5: Commit**

```bash
git add eval/model_synthesis_eval.py tests/research/test_model_synthesis_eval.py
git commit -m "eval(research): isolate model synthesis quality"
```

---

## Task 9: Run Live Diagnostics And Set Promotion Criteria

**Files:**
- Modify: `docs/research-workflow/CHECKLOG.md`

- [x] (2026-06-28 16:27Z) **Step 1: Run full research tests**

```bash
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/research -q
```

Expected:

- Research tests pass.

- [x] (2026-06-28 16:27Z) **Step 2: Run answer-quality diagnostics**

```bash
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 uv run python eval/research_diagnostics.py --dataset eval/answer_quality_golden_set.jsonl --top-k 10
```

Expected target before closing this plan:

- `transformer-original-vi`: `stage=passed`.
- `lora-qlora-comparison`: top 10 contains `2106.09685` and `2305.14314`, or report clearly says provider did not return one of them.
- `ros2-robotics-concept`: not `discovery_or_ranking_miss`; if weak, it must be `weak_evidence`.
- `no-evidence-personal`: no fabricated paper answer.

- [x] (2026-06-28 16:27Z) **Step 3: Run existing eval gate**

```bash
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 make eval-research
```

Expected:

```text
GATE VERDICT: PASS
```

- [x] (2026-06-28 16:27Z) **Step 4: Record decisions**

Append to `docs/research-workflow/CHECKLOG.md`:

```markdown
| 2026-06-28 | Answer-quality debugging is stage-first: discovery/ranking/evidence/synthesis/model are measured separately. | Manual UI failures showed wrong paper selection before model quality could be judged. Same-context model eval is required before upgrading synthesis models. | Implemented |
| 2026-06-28 | Canonical paper resolution handles seminal paper lookups and comparisons. | Queries like `Transformer paper có gì` and `compare LoRA and QLoRA papers` need canonical scholarly targets, not broad keyword search over incidental mentions. | Implemented |
```

Add verification row:

```markdown
| 2026-06-28 | Answer-quality diagnostics: `uv run pytest tests/research -q`; `uv run python eval/research_diagnostics.py --dataset eval/answer_quality_golden_set.jsonl --top-k 10`; `make eval-research` | Passed | Transformer and LoRA/QLoRA cases no longer fail as broad discovery misses; dry-run eval still passes. |
```

- [x] (2026-06-28 16:27Z) **Step 5: Commit**

```bash
git add docs/research-workflow/CHECKLOG.md
git commit -m "docs(research): record answer quality harness decisions"
```

---

## Task 10: Final Verification

**Files:**
- No new implementation files unless previous tasks require fixes.

- [x] (2026-06-28 16:31Z) **Step 1: Run backend full suite**

```bash
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q
```

Expected:

- Full suite passes. Baseline before this plan was `203 passed, 30 skipped, 22 warnings`.

- [x] (2026-06-28 16:31Z) **Step 2: Run frontend build**

```bash
cd web && npm run build
```

Expected:

- Next.js build passes.

- [x] (2026-06-28 16:31Z) **Step 3: Run eval dry-run**

```bash
UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 make eval-research
```

Expected:

```text
GATE VERDICT: PASS
```

- [x] (2026-06-28 16:31Z) **Step 4: Run whitespace check**

```bash
git diff --check
```

Expected:

- No output, exit 0.

- [x] (2026-06-28 16:31Z) **Step 5: Report residual risks**

Report these separately instead of hiding them:

- Live provider instability can still affect `make eval-research-gate`.
- Full-text/PDF fetching is not implemented by this plan unless a later task adds it explicitly.
- Canonical registry is intentionally curated; it must be maintained like a small scholarly knowledge base, not treated as a hardcoded test hack.
- Model upgrade is approved only if same-context model eval proves current synthesis model fails.

Final verification summary:

- `UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q` passed: 223 passed, 30 skipped, 22 warnings.
- `cd web && npm run build` passed.
- `UV_CACHE_DIR=.uv-cache PYTHONDONTWRITEBYTECODE=1 make eval-research` passed with `GATE VERDICT: PASS`.
- `git diff --check` passed with no output.

---

## Execution Notes

Recommended commit order:

1. Diagnostic dataset.
2. Diagnostic CLI.
3. Canonical registry.
4. Canonical discovery/ranking.
5. Comparison coverage ranking.
6. Evidence metrics.
7. Structured synthesis validation.
8. Same-context model eval.
9. CHECKLOG decisions.
10. Final verification.

Stop and ask before:

- Adding or committing API keys.
- Changing `LLM_BACKEND` defaults in `.env.example`.
- Replacing the default production model.
- Adding network-heavy full-text fetching to the hot path.
- Deleting legacy LangGraph or LlamaIndex code.

Success bar:

- Manual UI cases produce grounded answers with visible source cards.
- Diagnostic report distinguishes discovery/ranking/evidence/synthesis/model failures.
- `Transformer paper có gì` retrieves `1706.03762` as the canonical target.
- `compare LoRA and QLoRA papers` retrieves both `2106.09685` and `2305.14314`.
- Existing `make eval-research` remains green.
