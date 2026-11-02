# Production Research Workflow Roadmap

## Status

**Created:** 2026-05-31
**Status:** Production chat uses `agent/research/`; legacy chat routing retired in Phase 3
**Owner:** AI agent handoff plan

## Phase Overview

| Phase | Goal | Main Output | Must Pass Before Next Phase |
|---|---|---|---|
| 1 | Paper discovery | Provider-backed `PaperCandidate` list | Known paper queries return relevant candidates |
| 2 | Paper indexing | Section-aware paper store and contextual chunks | Indexed papers retain metadata and section context |
| 3 | Retrieval/ranking | Hybrid retrieval + candidate reranking | Recall@k and MRR@k improve over baseline |
| 4 | Evidence synthesis | Claim-grounded answer generation | Answers cite supporting evidence spans |
| 5 | Eval/observability | Regression suite + traces + metrics | CI catches retrieval/faithfulness regressions |

## Recommended Execution Order

### Phase 1: Paper Discovery

Implement first because current failures, including `ROS2 trong robotics là gì`
in ArXiv mode, are discovery failures before they are RAG failures.

Target behavior:

```text
Input: "ROS2 trong robotics là gì"
QueryPlan:
  entities: ["ROS2", "robotics"]
  aliases:
    ROS2: ["ROS 2", "Robot Operating System 2"]
  categories: ["cs.RO"]
Provider queries:
  arxiv:
    all:ROS2 AND all:robotics
    (all:ROS2 OR all:"ROS 2") AND (all:robotics OR cat:cs.RO)
Output:
  >= 3 relevant PaperCandidate items
```

### Phase 2: Paper Indexing

Once discovery returns good paper candidates, index paper metadata and text in a
paper-aware model. Abstract-only answers are useful, but production research
needs full-text when available.

### Phase 3: Retrieval And Ranking

Replace hard-coded RRF heuristics with a measured ranking stack. Keep the first
implementation simple and explainable: lexical/entity score + dense score +
metadata boosts + cross-encoder reranking.

### Phase 4: Evidence Synthesis

Answers should be composed from evidence spans, not raw chunks. The system
should be able to say which source supports each important claim.

### Phase 5: Eval And Observability

Make evaluation the control loop. Every retrieval or prompt change should be
compared to a baseline dataset.

## Production Acceptance Bar

Do not call the workflow production-ready until all are true:

- [x] Golden-set retrieval recall@10 is measured and beats current baseline.
- [ ] Candidate precision@5 is measured for paper discovery queries.
- [ ] No-answer reasons are tracked and reviewed.
- [ ] Answer faithfulness is measured on generated answers.
- [x] Each provider has timeout, retry, and health behavior.
- [x] Each answer can expose source candidates and evidence spans.
- [ ] p95 latency is tracked for discovery, retrieval, rerank, and generation.

Current implementation note: `/api/chat` and `/api/chat/stream` now use
`agent/research/` as the canonical retrieval-backed chat path. Static,
out-of-scope, and LLM-only policies still bypass retrieval. `/api/research/preview`
remains the dev-facing preview endpoint and is the only path gated by
`RESEARCH_WORKFLOW_ENABLED`.

## Feature Flags

Research workflow configuration:

```env
RESEARCH_DISCOVERY_PROVIDERS=arxiv,semantic_scholar,openalex
RESEARCH_ENABLE_FULLTEXT_FETCH=false
RESEARCH_ENABLE_GRAPH=false
RESEARCH_ENABLE_PHOENIX=false
```

## Suggested Commits

Keep commits small:

1. `docs: add production research workflow plan`
2. `feat(research): add query plan schema`
3. `feat(research): add arxiv discovery provider`
4. `feat(research): add paper candidate normalization`
5. `test(research): add paper discovery golden cases`
6. `feat(research): add candidate reranking`
7. `feat(research): add evidence span model`
