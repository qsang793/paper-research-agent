from __future__ import annotations

from typing import Iterable, List

from agent.research.discovery.models import PaperCandidate, normalize_doi
from agent.research.evidence.models import EvidenceSpan


def _candidate_ids(candidate: PaperCandidate) -> set[str]:
    ids = set()
    if candidate.arxiv_id:
        ids.add(candidate.arxiv_id.lower())
    if candidate.doi:
        ids.add(normalize_doi(candidate.doi))
    if candidate.semantic_scholar_id:
        ids.add(candidate.semantic_scholar_id)
    if candidate.openalex_id:
        ids.add(candidate.openalex_id)
    ids.add(candidate.stable_key().split(":", 1)[-1].lower())
    return ids


def _expected(expected_papers: Iterable[str]) -> set[str]:
    return {normalize_doi(item).lower() for item in expected_papers if item}


def paper_recall_at_k(candidates: List[PaperCandidate], expected_papers: Iterable[str], k: int = 10) -> float:
    expected = _expected(expected_papers)
    if not expected:
        return 0.0
    hits = 0
    for expected_id in expected:
        if any(expected_id in _candidate_ids(candidate) for candidate in candidates[:k]):
            hits += 1
    return hits / len(expected)


def paper_mrr_at_k(candidates: List[PaperCandidate], expected_papers: Iterable[str], k: int = 10) -> float:
    """Mean reciprocal rank of each expected paper within the top-k candidates.

    For a single-expected-paper query this is the standard reciprocal rank
    (1/rank, or 0 if absent from the top-k). Unlike precision@k it is not capped
    by k, so it remains a meaningful target for "find the seminal paper" queries.
    """
    expected = _expected(expected_papers)
    if not expected or k <= 0:
        return 0.0
    top = candidates[:k]
    total = 0.0
    for expected_id in expected:
        for rank, candidate in enumerate(top, start=1):
            if expected_id in _candidate_ids(candidate):
                total += 1.0 / rank
                break
    return total / len(expected)


def paper_hit_ranks_at_k(candidates: List[PaperCandidate], expected_papers: Iterable[str], k: int = 10) -> dict[str, int]:
    """Return 1-based ranks for expected papers found within the top-k candidates."""
    expected = _expected(expected_papers)
    if not expected or k <= 0:
        return {}
    ranks: dict[str, int] = {}
    for expected_id in expected:
        for rank, candidate in enumerate(candidates[:k], start=1):
            if expected_id in _candidate_ids(candidate):
                ranks[expected_id] = rank
                break
    return ranks


def paper_precision_at_k(candidates: List[PaperCandidate], expected_papers: Iterable[str], k: int = 10) -> float:
    expected = _expected(expected_papers)
    if not expected or k <= 0:
        return 0.0
    top = candidates[:k]
    if not top:
        return 0.0
    hits = sum(1 for candidate in top if _candidate_ids(candidate).intersection(expected))
    return hits / len(top)


def evidence_precision_at_k(evidence: List[EvidenceSpan], expected_terms: Iterable[str], k: int = 5) -> float:
    terms = [term.lower() for term in expected_terms if term]
    if not terms:
        return 0.0
    top = evidence[:k]
    if not top:
        return 0.0
    hits = sum(1 for span in top if any(term in span.quote.lower() for term in terms))
    return hits / len(top)


def evidence_term_recall(evidence: List[EvidenceSpan], expected_terms: Iterable[str]) -> float:
    terms = {term.lower() for term in expected_terms if term}
    if not terms:
        return 0.0
    joined = "\n".join(span.quote.lower() for span in evidence)
    hits = sum(1 for term in terms if term in joined)
    return hits / len(terms)


def provider_hit_rate(candidates: List[PaperCandidate], provider: str) -> float:
    if not candidates:
        return 0.0
    hits = sum(1 for candidate in candidates if provider in candidate.source_providers or candidate.source_provider == provider)
    return hits / len(candidates)


def dedup_rate(raw_count: int, deduped_count: int) -> float:
    if raw_count <= 0:
        return 0.0
    return max(0.0, (raw_count - deduped_count) / raw_count)
