# Phase 3: Retrieval And Ranking

## Goal

Replace brittle retrieval heuristics with a measurable hybrid retrieval and
ranking stack for paper-level and evidence-level search.

## Scope

### Create

- `agent/research/ranking/features.py`
- `agent/research/ranking/reranker.py`
- `agent/research/evidence/retriever.py`
- `tests/research/test_candidate_ranking.py`
- `tests/research/test_evidence_retriever.py`

### Modify

- Current `agent/nodes/retrieve.py` only after the new retriever passes isolated
  tests.

## Retrieval Layers

Use two retrieval levels:

1. **Paper-level retrieval**: find the right papers.
2. **Evidence-level retrieval**: find the right spans inside those papers.

## Ranking Features

Use explicit score components:

```python
score_breakdown = {
    "entity_match": 0.0,
    "alias_match": 0.0,
    "lexical_score": 0.0,
    "dense_score": 0.0,
    "category_match": 0.0,
    "recency": 0.0,
    "citation_signal": 0.0,
    "provider_rank": 0.0,
    "rerank_score": 0.0,
}
```

Do not hide ranking logic in one opaque `score` field.

## Recommended Technical Direction

Short term:

- Keep current Chroma + BM25 baseline.
- Add explicit paper-level candidate reranking.
- Add score breakdown and eval logging.

Medium term:

- Evaluate Qdrant or Weaviate for native dense+sparse hybrid search.
- Consider late-interaction reranking for top candidates if latency budget
  allows.

## Implementation Tasks

### Task 1: Candidate ranking features

- [ ] Implement lexical/entity/category/recency feature functions.
- [ ] Add tests for acronym-heavy queries such as `ROS2 robotics`.
- [ ] Ensure score breakdown sums or combines deterministically.

### Task 2: Dense candidate scoring

- [ ] Score `query` against `title + abstract`.
- [ ] Cache embeddings by paper ID.
- [ ] Add tests with fake embeddings.

### Task 3: Cross-encoder reranking

- [ ] Rerank top candidates only, not every candidate.
- [ ] Preserve fallback when model is unavailable.
- [ ] Add tests that reranking changes order with fake scores.

### Task 4: Evidence retriever

- [ ] Retrieve chunks from selected papers.
- [ ] Rerank chunks against the query.
- [ ] Return `EvidenceSpan` candidates.

## Validation

```bash
uv run pytest tests/research/test_candidate_ranking.py tests/research/test_evidence_retriever.py -q
```

## Exit Criteria

- [ ] Candidate ranking is explainable.
- [ ] Exact technical terms and acronyms are handled better than dense-only.
- [ ] Evidence spans are retrieved from selected papers.
- [ ] A baseline eval shows improved retrieval quality over current search node.
