from __future__ import annotations

import logging
import json
import os
from pathlib import Path
from typing import List

import requests

from agent.research.discovery.models import PaperCandidate, normalize_doi
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

OPENALEX_WORKS_URL = "https://api.openalex.org/works"


def _default_cache_key_ttl() -> float:
    return _float_env("RESEARCH_OPENALEX_CACHE_TTL_SECONDS", 86400.0)


def _default_cache_path() -> Path | None:
    return _default_cache_dir("RESEARCH_OPENALEX_CACHE_DIR", ".cache/research/openalex")


def _default_retry_count() -> int:
    return _int_env("RESEARCH_OPENALEX_MAX_RETRIES", 3)


def _default_backoff_base() -> float:
    return _float_env("RESEARCH_OPENALEX_BACKOFF_BASE_SECONDS", 1.0)


def _default_backoff_max() -> float:
    return _float_env("RESEARCH_OPENALEX_BACKOFF_MAX_SECONDS", 60.0)


def _default_min_interval() -> float:
    return _float_env("RESEARCH_OPENALEX_MIN_INTERVAL_SECONDS", 1.0)


def _abstract_from_inverted_index(index: dict | None) -> str:
    if not index:
        return ""
    positioned = []
    for word, positions in index.items():
        for position in positions:
            positioned.append((int(position), word))
    return " ".join(word for _, word in sorted(positioned))


def _openalex_id(value: str | None) -> str | None:
    if not value:
        return None
    return value.rstrip("/").rsplit("/", 1)[-1]


def normalize_openalex_work(item: dict, provider_rank: int = 0) -> PaperCandidate:
    primary_location = item.get("primary_location") or {}
    authors = [
        ((authorship.get("author") or {}).get("display_name") or "")
        for authorship in item.get("authorships", []) or []
    ]
    authors = [author for author in authors if author]
    concepts = [
        concept.get("display_name")
        for concept in item.get("concepts", []) or []
        if concept.get("display_name")
    ]

    return PaperCandidate(
        title=item.get("display_name") or item.get("title") or "",
        abstract=_abstract_from_inverted_index(item.get("abstract_inverted_index")),
        authors=authors,
        year=item.get("publication_year"),
        published_at=item.get("publication_date"),
        source_provider="openalex",
        source_url=primary_location.get("landing_page_url") or item.get("id") or "",
        pdf_url=primary_location.get("pdf_url"),
        doi=normalize_doi(item["doi"]) if item.get("doi") else None,
        openalex_id=_openalex_id(item.get("id")),
        categories=concepts,
        venue=((primary_location.get("source") or {}).get("display_name")),
        citation_count=item.get("cited_by_count"),
        provider_rank=provider_rank,
    )


def search_openalex_papers(
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
    params = {
        "search": plan.normalized_query,
        "per-page": max_results,
        "sort": "relevance_score:desc",
    }
    api_key = os.getenv("OPENALEX_API_KEY")
    if api_key:
        params["api_key"] = api_key
    cache_dir_path = Path(cache_dir) if cache_dir is not None else _default_cache_path()
    ttl_seconds = _default_cache_key_ttl() if cache_ttl_seconds is None else cache_ttl_seconds
    retries = _default_retry_count() if max_retries is None else max_retries
    backoff_base = _default_backoff_base() if backoff_base_seconds is None else backoff_base_seconds
    backoff_max = _default_backoff_max() if backoff_max_seconds is None else backoff_max_seconds
    min_interval = _default_min_interval() if min_interval_seconds is None else min_interval_seconds
    cached = _read_cached_response(cache_dir_path, params, ttl_seconds)
    payload_text: str | None = cached

    try:
        if payload_text is None:
            payload_text = fetch_provider_json(
                OPENALEX_WORKS_URL,
                params=params,
                headers={"User-Agent": "ai-research-agent/0.1"},
                timeout=timeout,
                provider_name="OpenAlex",
                max_retries=retries,
                base_backoff_seconds=backoff_base,
                max_backoff_seconds=backoff_max,
                min_interval_seconds=min_interval,
                pacing_key="openalex",
            )
            if payload_text is None:
                return []
            payload = json.loads(payload_text)
            _write_cached_response(cache_dir_path, params, payload_text, ttl_seconds)
        else:
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                logger.warning("Ignoring invalid cached OpenAlex response")
                payload_text = None
                payload_text = fetch_provider_json(
                    OPENALEX_WORKS_URL,
                    params=params,
                    headers={"User-Agent": "ai-research-agent/0.1"},
                    timeout=timeout,
                    provider_name="OpenAlex",
                    max_retries=retries,
                    base_backoff_seconds=backoff_base,
                    max_backoff_seconds=backoff_max,
                    min_interval_seconds=min_interval,
                    pacing_key="openalex",
                )
                if payload_text is None:
                    return []
                payload = json.loads(payload_text)
                _write_cached_response(cache_dir_path, params, payload_text, ttl_seconds)
        return [
            normalize_openalex_work(item, provider_rank=rank)
            for rank, item in enumerate(payload.get("results", []) or [], start=1)
        ]
    except (json.JSONDecodeError, ValueError, TypeError, requests.RequestException) as exc:
        logger.warning("OpenAlex search failed: %s", exc)
        return []
