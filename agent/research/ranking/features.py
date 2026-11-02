from __future__ import annotations

import math
import re
from typing import Dict

from agent.research.discovery.models import PaperCandidate
from agent.research.query_plan import QueryPlan


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _contains_term(haystack: str, term: str) -> bool:
    return term.lower() in haystack.lower() or _compact(term) in _compact(haystack)


def _normalize_arxiv_id(value: str | None) -> str:
    return re.sub(r"v\d+$", "", (value or "").strip().lower())


def lexical_score(plan: QueryPlan, candidate: PaperCandidate) -> float:
    query_terms = _tokens(plan.normalized_query)
    text_terms = _tokens(f"{candidate.title} {candidate.abstract}")
    if not query_terms:
        return 0.0
    return len(query_terms.intersection(text_terms)) / len(query_terms)


def score_candidate(plan: QueryPlan, candidate: PaperCandidate) -> tuple[float, Dict[str, float]]:
    haystack = f"{candidate.title} {candidate.abstract}"
    requested_arxiv_ids = {_normalize_arxiv_id(arxiv_id) for arxiv_id in plan.arxiv_ids}
    canonical_arxiv_ids = [_normalize_arxiv_id(arxiv_id) for arxiv_id in getattr(plan, "canonical_arxiv_ids", [])]
    canonical_ids = set(canonical_arxiv_ids)
    canonical_titles = {title.lower() for title in getattr(plan, "canonical_titles", [])}
    identifier_match = (
        1.0
        if requested_arxiv_ids and _normalize_arxiv_id(candidate.arxiv_id) in requested_arxiv_ids
        else 0.0
    )
    canonical_match = (
        1.0
        if (canonical_ids and _normalize_arxiv_id(candidate.arxiv_id) in canonical_ids)
        or (candidate.title and candidate.title.lower() in canonical_titles)
        else 0.0
    )
    comparison_target_match = 0.0
    if len(canonical_arxiv_ids) > 1:
        candidate_canonical_id = _normalize_arxiv_id(candidate.arxiv_id)
        if candidate_canonical_id in canonical_ids:
            comparison_target_match = 1.0
    entity_match = sum(1 for entity in plan.entities if _contains_term(haystack, entity)) / max(len(plan.entities), 1)
    alias_count = sum(len(aliases) for aliases in plan.aliases.values())
    alias_match = (
        sum(1 for aliases in plan.aliases.values() for alias in aliases if _contains_term(haystack, alias))
        / max(alias_count, 1)
        if alias_count
        else 0.0
    )
    category_match = 1.0 if set(plan.categories).intersection(candidate.categories) else 0.0
    recency = max(0.0, min(1.0, ((candidate.year or 2018) - 2018) / 8.0))
    citation_signal = min(1.0, math.log10((candidate.citation_count or 0) + 1) / 4.0)
    provider_rank = 1.0 / max(candidate.provider_rank, 1) if candidate.provider_rank else 0.0
    lexical = lexical_score(plan, candidate)
    dense_score = candidate.score_breakdown.get("dense_score", 0.0)
    rerank_score = candidate.score_breakdown.get("rerank_score", 0.0)

    breakdown = {
        "identifier_match": identifier_match,
        "canonical_match": canonical_match,
        "comparison_target_match": comparison_target_match,
        "entity_match": entity_match,
        "alias_match": alias_match,
        "lexical_score": lexical,
        "dense_score": dense_score,
        "category_match": category_match,
        "recency": recency,
        "citation_signal": citation_signal,
        "provider_rank": provider_rank,
        "rerank_score": rerank_score,
    }
    score = (
        0.24 * entity_match
        + 0.18 * alias_match
        + 0.18 * lexical
        + 0.12 * category_match
        + 0.08 * recency
        + 0.08 * citation_signal
        + 0.07 * provider_rank
        + 0.05 * dense_score
        + 0.10 * max(rerank_score, 0.0)
        + 1.2 * canonical_match
        + 0.8 * comparison_target_match
        + 1.0 * identifier_match
    )
    return score, breakdown
