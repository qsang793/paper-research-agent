from __future__ import annotations

import logging
import hashlib
import json
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List
from urllib.parse import urlparse

import requests

from agent.research.discovery.models import PaperCandidate
from agent.research.query_plan import QueryPlan

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
_last_arxiv_request_at: float | None = None
_arxiv_pacing_lock = threading.Lock()


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using %s", name, raw, default)
        return default


def _default_cache_dir() -> Path | None:
    raw = os.getenv("RESEARCH_ARXIV_CACHE_DIR", ".cache/research/arxiv").strip()
    return Path(raw) if raw else None


def _cache_key(params: dict) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_path(cache_dir: Path, params: dict) -> Path:
    return cache_dir / f"{_cache_key(params)}.xml"


def _read_cached_response(cache_dir: Path | None, params: dict, ttl_seconds: float) -> str | None:
    if cache_dir is None or ttl_seconds <= 0:
        return None
    path = _cache_path(cache_dir, params)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > ttl_seconds:
        return None
    return path.read_text(encoding="utf-8")


def _write_cached_response(cache_dir: Path | None, params: dict, text: str, ttl_seconds: float) -> None:
    if cache_dir is None or ttl_seconds <= 0:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_dir, params)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _pace_arxiv_request(min_interval_seconds: float) -> None:
    global _last_arxiv_request_at
    if min_interval_seconds <= 0:
        return
    with _arxiv_pacing_lock:
        now = time.monotonic()
        if _last_arxiv_request_at is not None:
            wait_seconds = min_interval_seconds - (now - _last_arxiv_request_at)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
                now += wait_seconds
        _last_arxiv_request_at = now


def _quote_term(term: str) -> str:
    if " " in term or "-" in term:
        return f'all:"{term}"'
    return f"all:{term}"


def _field_terms(field: str, term: str) -> List[str]:
    if " " in term or "-" in term:
        return [f'{field}:"{term}"']
    return [f"{field}:{term}"]


def build_arxiv_queries(plan: QueryPlan) -> List[str]:
    if plan.arxiv_ids:
        return [f"id:{arxiv_id}" for arxiv_id in plan.arxiv_ids]

    canonical_ids = [arxiv_id for arxiv_id in getattr(plan, "canonical_arxiv_ids", []) if arxiv_id]
    queries = [f"id:{arxiv_id}" for arxiv_id in canonical_ids]

    entities = plan.entities or plan.keywords or [plan.normalized_query]
    base = " AND ".join(_quote_term(entity) for entity in entities)
    if base:
        queries.append(base)

    expanded_parts = []
    for entity in entities:
        variants = [entity, *plan.aliases.get(entity, [])]
        expanded_parts.append("(" + " OR ".join(_quote_term(variant) for variant in variants) + ")")
    category_part = " OR ".join(f"cat:{category}" for category in plan.categories)
    if expanded_parts:
        expanded = " AND ".join(expanded_parts)
        if category_part:
            expanded = f"{expanded} AND ({category_part})"
        queries.append(expanded)

    title_abs_terms = []
    for entity in entities:
        for variant in [entity, *plan.aliases.get(entity, [])]:
            title_abs_terms.extend(_field_terms("ti", variant))
            title_abs_terms.extend(_field_terms("abs", variant))
    if title_abs_terms:
        queries.append(" OR ".join(title_abs_terms))

    seen = set()
    unique = []
    for query in queries:
        if query and query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _https(url: str | None) -> str:
    if not url:
        return ""
    return "https://" + url[len("http://") :] if url.startswith("http://") else url


def _arxiv_id_from_url(url: str) -> str | None:
    path = urlparse(url).path
    if "/abs/" not in path:
        return None
    raw = path.rsplit("/", 1)[-1]
    return re.sub(r"v\d+$", "", raw)


def parse_arxiv_atom(xml_text: str) -> List[PaperCandidate]:
    root = ET.fromstring(xml_text)
    candidates: List[PaperCandidate] = []
    for rank, entry in enumerate(root.findall("atom:entry", ATOM_NS), start=1):
        title = _clean_text(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
        abstract = _clean_text(entry.findtext("atom:summary", default="", namespaces=ATOM_NS))
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS) or None
        year = int(published[:4]) if published and published[:4].isdigit() else None
        authors = [
            _clean_text(author.findtext("atom:name", default="", namespaces=ATOM_NS))
            for author in entry.findall("atom:author", ATOM_NS)
        ]
        authors = [author for author in authors if author]

        abs_url = ""
        pdf_url = None
        for link in entry.findall("atom:link", ATOM_NS):
            rel = link.attrib.get("rel")
            title_attr = link.attrib.get("title")
            href = _https(link.attrib.get("href"))
            if rel == "alternate":
                abs_url = href
            if title_attr == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = href
        if not abs_url:
            abs_url = _https(entry.findtext("atom:id", default="", namespaces=ATOM_NS))

        arxiv_id = _arxiv_id_from_url(abs_url)
        categories = []
        primary = entry.find("arxiv:primary_category", ATOM_NS)
        if primary is not None and primary.attrib.get("term"):
            categories.append(primary.attrib["term"])
        for category in entry.findall("atom:category", ATOM_NS):
            term = category.attrib.get("term")
            if term and term not in categories:
                categories.append(term)

        candidates.append(
            PaperCandidate(
                title=title,
                abstract=abstract,
                authors=authors,
                year=year,
                published_at=published,
                source_provider="arxiv",
                source_url=abs_url,
                pdf_url=pdf_url,
                arxiv_id=arxiv_id,
                categories=categories,
                provider_rank=rank,
            )
        )
    return candidates


def search_arxiv_papers(
    plan: QueryPlan,
    max_results: int = 20,
    timeout: int = 15,
    *,
    min_interval_seconds: float | None = None,
    cache_dir: str | Path | None = None,
    cache_ttl_seconds: float | None = None,
) -> List[PaperCandidate]:
    queries = build_arxiv_queries(plan)
    headers = {"User-Agent": "ai-research-agent/0.1"}
    candidates: List[PaperCandidate] = []
    interval = (
        _float_env("RESEARCH_ARXIV_MIN_INTERVAL_SECONDS", 3.2)
        if min_interval_seconds is None
        else min_interval_seconds
    )
    ttl = (
        _float_env("RESEARCH_ARXIV_CACHE_TTL_SECONDS", 604800.0)
        if cache_ttl_seconds is None
        else cache_ttl_seconds
    )
    resolved_cache_dir = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
    for query in queries:
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        try:
            cached_candidates = None
            cached = _read_cached_response(resolved_cache_dir, params, ttl)
            if cached is not None:
                try:
                    cached_candidates = parse_arxiv_atom(cached)
                except Exception as exc:
                    logger.warning("Ignoring invalid cached arXiv response for query %r: %s", query, exc)
            if cached_candidates is not None:
                candidates.extend(cached_candidates)
            else:
                _pace_arxiv_request(interval)
                response = requests.get(
                    ARXIV_API,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
                response.raise_for_status()
                parsed = parse_arxiv_atom(response.text)
                _write_cached_response(resolved_cache_dir, params, response.text, ttl)
                candidates.extend(parsed)
        except Exception as exc:
            logger.warning("arXiv search failed for query %r: %s", query, exc)
        if len(candidates) >= max_results:
            break
    return candidates[:max_results]
