# Research Workflow Architecture

## Current Production Chat Path

The active production chat path is the research workflow:

```text
api/routes/chat.py
-> agent/query_router.py
-> agent/query_policy.py
-> agent/research/workflow.py
-> agent/research/{query_plan,discovery,ranking,indexing,evidence,synthesis}
```

Static, out-of-scope, and LLM-only policies still bypass retrieval. Domain /
retrieval-backed queries use `agent/research/` through `/api/chat` and
`/api/chat/stream`.

## Target Components

```text
User query
  |
  v
Query Understanding
  - language detection
  - task type classification
  - entity and alias extraction
  - structured QueryPlan
  |
  v
Paper Discovery
  - ArXiv provider
  - Semantic Scholar provider
  - OpenAlex provider
  - provider health and retry policy
  |
  v
Candidate Normalization
  - PaperCandidate schema
  - DOI/arXiv/S2/OpenAlex ID mapping
  - title-similarity deduplication
  - source provenance
  |
  v
Candidate Ranking
  - lexical/entity score
  - metadata score
  - dense embedding score
  - citation/recency/domain boosts
  - explainable score breakdown
  |
  v
Paper Acquisition and Indexing
  - abstract-only fast path
  - PDF/full-text fetch where available
  - section-aware parsing
  - contextual chunks
  - metadata store and vector/sparse indexes
  |
  v
Evidence Retrieval
  - paper-level retrieval
  - section/chunk retrieval
  - reranking
  - evidence span extraction
  |
  v
Answer Synthesis
  - claim-grounded answer
  - citation support per claim
  - no-answer with reason codes
  |
  v
Evaluation and Observability
  - retrieval recall/precision
  - faithfulness
  - source coverage
  - latency and provider hit rate
```

## Proposed Module Layout

Keep new code behind a separate namespace until it is proven:

```text
agent/research/
  __init__.py
  query_plan.py
  discovery/
    __init__.py
    models.py
    arxiv_provider.py
    semantic_scholar_provider.py
    openalex_provider.py
    service.py
  ranking/
    __init__.py
    features.py
    reranker.py
  indexing/
    __init__.py
    paper_store.py
    section_parser.py
    contextual_chunks.py
  evidence/
    __init__.py
    retriever.py
    extractor.py
  synthesis/
    __init__.py
    claim_answer.py
  evals/
    __init__.py
    datasets.py
    metrics.py
```

Tests should mirror this structure:

```text
tests/research/
  test_query_plan.py
  test_arxiv_provider.py
  test_candidate_dedup.py
  test_candidate_ranking.py
  test_contextual_chunks.py
  test_evidence_extractor.py
  test_research_eval_metrics.py
```

## Data Boundaries

Use explicit schemas between layers. Avoid passing provider-specific dictionaries
through the system.

### QueryPlan

```python
@dataclass(frozen=True)
class QueryPlan:
    original_query: str
    language: str
    task_type: str  # concept | survey | compare | recent | paper_lookup
    entities: list[str]
    aliases: dict[str, list[str]]
    must_terms: list[str]
    optional_terms: list[str]
    categories: list[str]
    year_from: int | None
    year_to: int | None
    providers: list[str]
```

### PaperCandidate

```python
@dataclass(frozen=True)
class PaperCandidate:
    title: str
    abstract: str | None
    authors: list[str]
    published_at: str | None
    url: str
    pdf_url: str | None
    arxiv_id: str | None
    doi: str | None
    semantic_scholar_id: str | None
    openalex_id: str | None
    venue: str | None
    citation_count: int | None
    categories: list[str]
    provider: str
    score: float
    score_breakdown: dict[str, float]
```

### EvidenceSpan

```python
@dataclass(frozen=True)
class EvidenceSpan:
    paper_id: str
    title: str
    url: str
    section: str | None
    text: str
    quote: str | None
    score: float
    supports_claim: str | None
```

## Migration Status

1. Build `agent/research/` without touching the previous chat path. Done.
2. Expose an internal CLI/test harness first. Done.
3. Add an API preview route after discovery/ranking/evidence tests. Done.
4. Switch `/api/chat` and `/api/chat/stream` to the research workflow after live
   gates and smoke tests. Done.
5. Retire legacy LangGraph chat call sites. Done for chat routing; the legacy
   modules remain only for historical tests/comparison until Phase 4 docs/code
   cleanup decides whether to archive or delete them.

## Non-Goals

- Do not replace all of LangGraph immediately.
- Do not wire optional LlamaIndex migration work into production by default.
- Do not depend on a single paper source.
- Do not treat a good answer demo as evidence of retrieval quality.
