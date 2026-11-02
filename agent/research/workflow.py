from __future__ import annotations

import os
from typing import Any, Dict, List

from agent.research.discovery.service import discover_papers
from agent.research.evidence.extractor import extract_evidence_spans
from agent.research.evidence.retriever import retrieve_evidence
from agent.research.indexing.contextual_chunks import ContextualChunk, create_contextual_chunks
from agent.research.indexing.paper_store import PaperStore
from agent.research.indexing.section_parser import parse_paper_text
from agent.research.observability import ResearchTrace
from agent.research.query_plan import plan_research_query
from agent.research.ranking.reranker import rank_candidates
from agent.research.synthesis.claim_answer import assess_evidence_answerability, generate_claim_grounded_answer


def _provider_names(providers: List[str] | None) -> List[str]:
    if providers:
        return providers
    configured = os.getenv("RESEARCH_DISCOVERY_PROVIDERS", "arxiv,semantic_scholar,openalex")
    return [item.strip() for item in configured.split(",") if item.strip()]


def _deterministic_preview_answer(evidence_count: int, paper_count: int) -> str:
    if paper_count == 0:
        return "Khong tim thay paper phu hop cho cau hoi nay."
    if evidence_count == 0:
        return "Da tim thay paper ung vien, nhung chua co evidence span du manh de tra loi."
    return f"Da tim thay {evidence_count} evidence span tu {paper_count} paper ung vien."


def run_research_preview(
    query: str,
    *,
    top_k: int = 5,
    providers: List[str] | None = None,
    generate: bool | None = None,
    question: str | None = None,
    memory_context: str = "",
    trace_context: Dict[str, Any] | None = None,
) -> Dict:
    """Run research using a clean retrieval query and separate synthesis context.

    `query` is the standalone retrieval query used for discovery, ranking, and
    evidence retrieval. `question` is the user's latest conversational wording;
    `memory_context` is available only to synthesis and never to source search.
    `trace_context` contains content-free request/strategy identifiers only.
    """
    trace = ResearchTrace(context=dict(trace_context or {}))
    research_question = (question or query).strip()
    plan = plan_research_query(query)

    with trace.span("discovery", providers=_provider_names(providers)):
        candidates = discover_papers(plan, provider_names=_provider_names(providers), max_results=max(top_k * 3, 10))
    with trace.span("candidate_ranking", candidates=len(candidates)):
        ranked = rank_candidates(plan, candidates, top_k=top_k)

    store = PaperStore()
    chunks: List[ContextualChunk] = []
    with trace.span("paper_indexing", papers=len(ranked)):
        for candidate in ranked:
            paper = store.upsert_candidate(candidate)
            parsed = parse_paper_text(candidate.abstract, candidate=candidate)
            chunks.extend(create_contextual_chunks(paper, parsed))

    with trace.span("evidence_retrieval", chunks=len(chunks)):
        evidence = retrieve_evidence(query, chunks, paper_ids=[paper.paper_id for paper in store.all()], top_k=top_k)
        if not evidence:
            evidence = extract_evidence_spans(chunks, query=query)[:top_k]

    generate_enabled = (
        generate
        if generate is not None
        else os.getenv("RESEARCH_PREVIEW_GENERATE", "false").lower() == "true"
    )
    answerability = assess_evidence_answerability(evidence, paper_count=len(ranked))
    with trace.span("synthesis", can_answer=answerability["can_answer"]):
        if answerability["can_answer"] and generate_enabled:
            answer = generate_claim_grounded_answer(
                research_question,
                evidence,
                memory_context=memory_context,
            )
        else:
            answer = _deterministic_preview_answer(len(evidence), len(ranked))

    citations = []
    for candidate in ranked:
        citations.append(
            {
                "title": candidate.title,
                "url": candidate.source_url,
                "authors": candidate.authors,
                "arxiv_id": candidate.arxiv_id,
                "relevance_score": candidate.score,
                "snippet": candidate.abstract[:300],
            }
        )

    metrics = trace.to_metrics()
    metrics.update({
        "paper_count": len(ranked),
        "evidence_count": len(evidence),
        "retrieval_query": query,
    })
    return {
        "answer": answer,
        "citations": citations,
        "evidence": [
            {
                "claim": span.claim,
                "paper_id": span.paper_id,
                "title": span.title,
                "url": span.url,
                "quote": span.quote,
                "score": span.score,
                "section_title": span.section_title,
            }
            for span in evidence
        ],
        "answerability": answerability,
        "metrics": metrics,
    }
