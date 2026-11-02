from __future__ import annotations

import logging
import json
import os
from pathlib import Path
from typing import List

import requests

from agent.research.discovery.models import PaperCandidate
from agent.research.query_plan import QueryPlan
from agent.research.discovery.http_provider import (
    _default_cache_dir,
    _float_env,
    _int_env,
    _read_cached_response,
    _write_cached_response,
    fetch_provider_json,
)

logger = logging.getLogger(__name__)

S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = ",".join(
    [
        "title",
        "abstract",
        "authors",
        "year",
        "publicationDate",
        "url",
        "externalIds",
        "citationCount",
        "venue",
        "openAccessPdf",
        "fieldsOfStudy",
        "s2FieldsOfStudy",
    ]
)


def _default_cache_key_ttl() -> float:
    return _float_env("RESEARCH_SEMANTIC_SCHOLAR_CACHE_TTL_SECONDS", 86400.0)


def _default_cache_path() -> Path | None:
    return _default_cache_dir("RESEARCH_SEMANTIC_SCHOLAR_CACHE_DIR", ".cache/research/semantic_scholar")


def _default_retry_count() -> int:
    return _int_env("RESEARCH_SEMANTIC_SCHOLAR_MAX_RETRIES", 3)


def _default_backoff_base() -> float:
    return _float_env("RESEARCH_SEMANTIC_SCHOLAR_BACKOFF_BASE_SECONDS", 1.0)


def _default_backoff_max() -> float:
    return _float_env("RESEARCH_SEMANTIC_SCHOLAR_BACKOFF_MAX_SECONDS", 60.0)


def _default_min_interval() -> float:
    return _float_env("RESEARCH_SEMANTIC_SCHOLAR_MIN_INTERVAL_SECONDS", 1.0)


def normalize_semantic_scholar_paper(item: dict, provider_rank: int = 0) -> PaperCandidate:
    external = item.get("externalIds") or {}
    authors = [
        author.get("name", "")
        for author in item.get("authors", []) or []
        if author.get("name")
    ]
    pdf = item.get("openAccessPdf") or {}
    fields = item.get("fieldsOfStudy") or []
    s2_fields = [entry.get("category") for entry in item.get("s2FieldsOfStudy", []) or []]
    categories = [field for field in [*fields, *s2_fields] if field]

    return PaperCandidate(
        title=item.get("title") or "",
        abstract=item.get("abstract") or "",
        authors=authors,
        year=item.get("year"),
        published_at=item.get("publicationDate"),
        source_provider="semantic_scholar",
        source_url=item.get("url") or "",
        pdf_url=pdf.get("url"),
        arxiv_id=external.get("ArXiv"),
        doi=external.get("DOI"),
        semantic_scholar_id=item.get("paperId"),
        categories=categories,
        venue=item.get("venue"),
        citation_count=item.get("citationCount"),
        provider_rank=provider_rank,
    )


def search_semantic_scholar_papers(
    plan: QueryPlan,
    max_results: int = 20,
    timeout: int = 15,
    *,
    cache_dir: str | Path | None = None,
    cache_ttl_seconds: float | None = None,
    max_retries: int | None = None,
    backoff_base_seconds: float | None = None,
    backoff_max_seconds: float | None = None,
    min_interval_seconds: float | None = None,
) -> List[PaperCandidate]:
    headers = {"User-Agent": "ai-research-agent/0.1"}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    params = {
        "query": plan.normalized_query,
        "limit": max_results,
        "fields": S2_FIELDS,
    }
    cache_dir_path = Path(cache_dir) if cache_dir is not None else _default_cache_path()
    ttl_seconds = (
        _default_cache_key_ttl() if cache_ttl_seconds is None else cache_ttl_seconds
    )
    retries = _default_retry_count() if max_retries is None else max_retries
    backoff_base = _default_backoff_base() if backoff_base_seconds is None else backoff_base_seconds
    backoff_max = _default_backoff_max() if backoff_max_seconds is None else backoff_max_seconds
    min_interval = _default_min_interval() if min_interval_seconds is None else min_interval_seconds
    cached = _read_cached_response(cache_dir_path, params, ttl_seconds)
    payload_text: str | None = cached
    try:
        if payload_text is not None:
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                logger.warning("Ignoring invalid cached Semantic Scholar response")
                payload_text = None
            else:
                return [
                    normalize_semantic_scholar_paper(item, provider_rank=rank)
                    for rank, item in enumerate(payload.get("data", []) or [], start=1)
                ]

        payload_text = fetch_provider_json(
            S2_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=timeout,
            provider_name="Semantic Scholar",
            max_retries=retries,
            base_backoff_seconds=backoff_base,
            max_backoff_seconds=backoff_max,
            min_interval_seconds=min_interval,
            pacing_key="semantic_scholar",
        )
        if payload_text is None:
            return []
        payload = json.loads(payload_text)
        _write_cached_response(cache_dir_path, params, payload_text, ttl_seconds)
        return [
            normalize_semantic_scholar_paper(item, provider_rank=rank)
            for rank, item in enumerate(payload.get("data", []) or [], start=1)
        ]
    except (json.JSONDecodeError, ValueError, TypeError, requests.RequestException) as exc:
        logger.warning("Semantic Scholar search failed: %s", exc)
        return []
