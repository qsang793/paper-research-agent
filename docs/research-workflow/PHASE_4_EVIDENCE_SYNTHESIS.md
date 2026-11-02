# Phase 4: Evidence Synthesis

## Goal

Generate answers from evidence spans with claim-level support, instead of
summarizing loosely from raw chunks.

## Scope

### Create

- `agent/research/evidence/extractor.py`
- `agent/research/synthesis/claim_answer.py`
- `tests/research/test_evidence_extractor.py`
- `tests/research/test_claim_answer.py`

### Modify

- `agent/answerability.py` only after evidence spans are available.
- `api/routes/chat.py` only when preview workflow is ready.

## Evidence Contract

Every generated answer should be traceable:

```text
Question: What is ROS 2 in robotics?

Claim:
  ROS 2 is middleware used to build distributed robotic systems.
Evidence:
  - Paper: ...
  - Span: ...
  - URL: ...
```

## Answer Shape

For the frontend and API, keep a compact answer but attach rich evidence:

```json
{
  "answer": "...",
  "citations": [...],
  "evidence": [
    {
      "claim": "...",
      "paper_id": "...",
      "title": "...",
      "url": "...",
      "quote": "...",
      "score": 0.91
    }
  ],
  "answerability": {
    "can_answer": true,
    "reason": "ANSWERABLE"
  }
}
```

## Implementation Tasks

### Task 1: Evidence span extraction

- [x] Convert retrieved chunks into smaller evidence spans.
- [x] Preserve paper title, section, URL, and score.
- [x] Add tests for metadata preservation.
- [x] Avoid fallback evidence when the query has no overlap with the chunk.

### Task 2: Claim-grounded prompt

- [x] Write a synthesis prompt that requires each major claim to cite evidence.
- [x] Add tests around prompt construction and generator handoff.
- [x] Keep provider calls behind `agent/generator.py`.

### Task 3: Evidence-aware answerability

- [x] Require minimum evidence count for paper-grounded answers.
- [x] Distinguish `NO_PAPER_FOUND`, `NO_EVIDENCE_FOUND`, and
      `WEAK_EVIDENCE`.
- [x] Add tests for no-answer outcomes.

### Task 4: Preview API

- [x] Add a non-default preview route or feature flag.
- [x] Return evidence metadata without breaking existing UI.
- [x] Add API contract tests.

## Validation

```bash
uv run pytest tests/research/test_evidence_extractor.py tests/research/test_evidence_retriever.py tests/research/test_claim_answer.py -q
```

## Exit Criteria

- [x] Answers are grounded in evidence spans.
- [x] No-answer reasons distinguish paper discovery vs evidence retrieval.
- [x] Existing chat stream protocol remains compatible.
