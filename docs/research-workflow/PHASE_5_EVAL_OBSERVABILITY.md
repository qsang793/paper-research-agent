# Phase 5: Evaluation And Observability

## Goal

Make retrieval and answer quality measurable so production changes are evaluated
instead of judged by manual spot checks.

## Scope

### Create

- `agent/research/evals/datasets.py`
- `agent/research/evals/metrics.py`
- `eval/research_golden_set.jsonl`
- `eval/research_eval.py`
- `tests/research/test_research_eval_metrics.py`

### Modify

- `Makefile` to add a research eval command after the eval script exists.
- `CLAUDE.md` to document the eval command after it is stable.

## Golden Set Format

Use JSONL:

```json
{
  "id": "ros2-definition",
  "query": "ROS2 trong robotics là gì",
  "expected_papers": ["2306.17157", "2209.14030"],
  "expected_terms": ["ROS 2", "robotics", "middleware"],
  "task_type": "concept",
  "notes": "Should not fail because of Vietnamese filler words."
}
```

## Metrics

### Retrieval Metrics

- `paper_recall_at_k`
- `paper_precision_at_k`
- `evidence_precision_at_k`
- `provider_hit_rate`
- `dedup_rate`

### Answer Metrics

- faithfulness against evidence spans
- answer relevance
- citation support rate
- no-answer correctness

### Operational Metrics

- p50/p95 latency by provider
- p50/p95 latency by reranker/generator
- provider timeout/error rate
- no-answer rate by reason

## Implementation Tasks

### Task 1: Golden dataset

- [x] Add 50 initial queries across paper lookup, concept explanation, survey,
      recent papers, comparison, and benchmark extraction.
- [x] Include expected papers where known.
- [x] Add tests to validate JSONL schema.

### Task 2: Deterministic retrieval metrics

- [x] Implement recall@k, precision@k, MRR@k, and expected-paper hit ranks.
- [x] Add tests with synthetic candidate lists.
- [x] Make metrics independent of LLM calls.

### Task 3: Eval runner

- [x] Run discovery/retrieval over the golden set.
- [x] Write JSON report with per-query failures and failure stages.
- [x] Exit non-zero only when strict thresholds are configured.
- [x] Resume live reports safely using schema versioning.

### Task 4: Observability

- [x] Add trace spans around provider search, dedup, ranking, retrieval, and
      synthesis.
- [x] Add latency summaries with p50/p95/max per span name.
- [x] Add optional Phoenix flag reporting behind env flags.
- [x] Document local setup.

### Task 5: CI/Makefile integration

- [x] Add `make eval-research`, `make eval-research-live`, and
      `make eval-research-gate`.
- [x] Document when to run fast unit tests vs full evals.

## Validation

```bash
uv run pytest tests/research/test_research_eval_metrics.py -q
uv run python eval/research_eval.py --dataset eval/research_golden_set.jsonl --dry-run
```

## Exit Criteria

- [x] Retrieval quality has a baseline score.
- [x] New ranking changes can be compared against baseline.
- [x] Production misses have traceable failure stages.
- [x] Team can explain whether a failure came from discovery, retrieval,
      evidence, or synthesis.
