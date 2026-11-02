from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from typing import Callable, Dict, Iterable, List, Mapping

from agent.research.discovery.arxiv_provider import search_arxiv_papers
from agent.research.discovery.models import PaperCandidate, normalize_title
from agent.research.discovery.openalex_provider import search_openalex_papers
from agent.research.discovery.semantic_scholar_provider import search_semantic_scholar_papers
from agent.research.query_plan import QueryPlan, plan_research_query


ProviderFn = Callable[[QueryPlan, int], List[PaperCandidate]]

DEFAULT_PROVIDERS: Dict[str, ProviderFn] = {
    "arxiv": search_arxiv_papers,
    "semantic_scholar": search_semantic_scholar_papers,
    "openalex": search_openalex_papers,
}


def _title_similar(left: str, right: str, threshold: float = 0.92) -> bool:
    if not left or not right:
        return False
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio() >= threshold


def _normalize_arxiv_id(value: str | None) -> str:
    return re.sub(r"v\d+$", "", (value or "").strip().lower())


def _merge_into(target: PaperCandidate, source: PaperCandidate) -> PaperCandidate:
    for attr in ["arxiv_id", "doi", "semantic_scholar_id", "openalex_id", "pdf_url", "source_url", "venue", "year", "published_at"]:
        if not getattr(target, attr) and getattr(source, attr):
            setattr(target, attr, getattr(source, attr))
    if not target.abstract and source.abstract:
        target.abstract = source.abstract
    for author in source.authors:
        if author not in target.authors:
            target.authors.append(author)
    for category in source.categories:
        if category not in target.categories:
            target.categories.append(category)
    for provider in source.source_providers or [source.source_provider]:
        if provider and provider not in target.source_providers:
            target.source_providers.append(provider)
    if source.citation_count and (not target.citation_count or source.citation_count > target.citation_count):
        target.citation_count = source.citation_count
    return target


def merge_duplicate_candidates(candidates: Iterable[PaperCandidate]) -> List[PaperCandidate]:
    merged: List[PaperCandidate] = []
    identity_index: Dict[str, PaperCandidate] = {}

    for candidate in candidates:
        identities = candidate.identity_values()
        existing = None
        for identity in identities:
            if identity in identity_index:
                existing = identity_index[identity]
                break
        if existing is None:
            for item in merged:
                if _title_similar(item.title, candidate.title):
                    existing = item
                    break

        if existing is None:
            merged.append(candidate)
            for identity in identities:
                identity_index[identity] = candidate
            continue

        _merge_into(existing, candidate)
        for identity in existing.identity_values():
            identity_index[identity] = existing

    return merged


def score_discovery_candidate(plan: QueryPlan, candidate: PaperCandidate) -> tuple[float, Dict[str, float]]:
    haystack = f"{candidate.title} {candidate.abstract}".lower()
    requested_arxiv_ids = {_normalize_arxiv_id(arxiv_id) for arxiv_id in plan.arxiv_ids}
    canonical_ids = {_normalize_arxiv_id(arxiv_id) for arxiv_id in getattr(plan, "canonical_arxiv_ids", [])}
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
    entity_hits = sum(1 for entity in plan.entities if entity.lower() in haystack)
    entity_match = entity_hits / max(len(plan.entities), 1)
    alias_total = sum(len(values) for values in plan.aliases.values())
    alias_hits = sum(
        1
        for aliases in plan.aliases.values()
        for alias in aliases
        if alias.lower() in haystack
    )
    alias_match = alias_hits / max(alias_total, 1) if alias_total else 0.0
    category_match = 1.0 if set(plan.categories).intersection(candidate.categories) else 0.0
    recency = 0.0
    if candidate.year:
        recency = max(0.0, min(1.0, (candidate.year - 2018) / 8.0))
    # Authority signal: log-scaled citation count, matched to ranking.features so
    # the discovery gate and production reranker agree. Seminal papers are old
    # (low recency) but heavily cited, so this is what surfaces them by name.
    citation_signal = min(1.0, math.log10((candidate.citation_count or 0) + 1) / 4.0)
    provider_rank = 1.0 / max(candidate.provider_rank, 1) if candidate.provider_rank else 0.0

    breakdown = {
        "identifier_match": identifier_match,
        "canonical_match": canonical_match,
        "entity_match": entity_match,
        "alias_match": alias_match,
        "category_match": category_match,
        "recency": recency,
        "citation_signal": citation_signal,
        "provider_rank": provider_rank,
    }
    score = (
        0.33 * entity_match
        + 0.19 * alias_match
        + 0.18 * category_match
        + 0.04 * recency
        + 0.18 * citation_signal
        + 0.08 * provider_rank
        + 1.2 * canonical_match
        + 1.0 * identifier_match
    )
    return score, breakdown


def discover_papers(
    query: str | QueryPlan,
    *,
    providers: Mapping[str, ProviderFn] | None = None,
    provider_names: List[str] | None = None,
    max_results: int = 20,
) -> List[PaperCandidate]:
    plan = query if isinstance(query, QueryPlan) else plan_research_query(query)
    provider_map = dict(providers or DEFAULT_PROVIDERS)
    names = provider_names or list(provider_map.keys())
    candidates: List[PaperCandidate] = []
    for name in names:
        provider = provider_map.get(name)
        if not provider:
            continue
        try:
            candidates.extend(provider(plan, max_results))
        except TypeError:
            candidates.extend(provider(plan, max_results=max_results))  # type: ignore[misc]

    unique = merge_duplicate_candidates(candidates)
    for candidate in unique:
        score, breakdown = score_discovery_candidate(plan, candidate)
        candidate.score = score
        candidate.score_breakdown.update(breakdown)
    return sorted(unique, key=lambda item: item.score, reverse=True)[:max_results]
