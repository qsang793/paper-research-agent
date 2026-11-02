# Production Research Workflow

This folder tracks the production-grade redesign of the research-paper
assistant. The goal is to move from a rigid demo-style RAG flow to a measured
research retrieval system with RAG as the final synthesis layer.

## Read Order

1. [ARCHITECTURE.md](./ARCHITECTURE.md) - current architecture and boundaries.
2. [ROADMAP.md](./ROADMAP.md) - phase sequence and acceptance gates.
3. [CHECKLOG.md](./CHECKLOG.md) - decisions, assumptions, and handoff notes.
4. [LEGACY_RETIREMENT_PLAN.md](./LEGACY_RETIREMENT_PLAN.md) - completed plan for
   making `agent/research/` canonical and archiving stale docs.
5. [Historical production adoption plan](../superpowers/plans/2026-05-31-research-workflow-production-adoption.md) - original rollout plan, kept for provenance.
6. Phase specs:
   - [PHASE_1_PAPER_DISCOVERY.md](./PHASE_1_PAPER_DISCOVERY.md)
   - [PHASE_2_PAPER_INDEXING.md](./PHASE_2_PAPER_INDEXING.md)
   - [PHASE_3_RETRIEVAL_RANKING.md](./PHASE_3_RETRIEVAL_RANKING.md)
   - [PHASE_4_EVIDENCE_SYNTHESIS.md](./PHASE_4_EVIDENCE_SYNTHESIS.md)
   - [PHASE_5_EVAL_OBSERVABILITY.md](./PHASE_5_EVAL_OBSERVABILITY.md)

## Why This Exists

The historical custom LangGraph pipeline was useful as a RAG baseline, but it
was too rigid for serious paper discovery:

- Query expansion is hand-coded around a few abbreviations.
- ArXiv search is treated like keyword lookup instead of scholarly discovery.
- Local KB retrieval, external paper search, and answer synthesis are coupled.
- Ranking is not measured against research-specific quality targets.
- Evaluation is not yet the main engineering loop.

## Production Principle

Do not optimize "RAG" in isolation. Optimize the research workflow:

```text
query understanding
-> scholarly paper discovery
-> candidate normalization and deduplication
-> metadata/full-text acquisition
-> multi-index retrieval and reranking
-> evidence extraction
-> claim-grounded synthesis
-> evaluation and observability
```

## External References

- Anthropic Contextual Retrieval:
  https://www.anthropic.com/research/contextual-retrieval
- Microsoft GraphRAG:
  https://microsoft.github.io/graphrag/
- Weaviate hybrid search:
  https://docs.weaviate.io/weaviate/concepts/search/hybrid-search
- Qdrant hybrid queries:
  https://qdrant.tech/documentation/search/hybrid-queries/
- Semantic Scholar API:
  https://www.semanticscholar.org/product/api
- OpenAlex Works API:
  https://docs.openalex.org/api-entities/works
- Ragas metrics:
  https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- Arize Phoenix:
  https://arize.com/docs/phoenix
