from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from math import sqrt
from typing import Callable, Dict, List, Optional, Sequence, Set

from ingest.search import search_arxiv
from ingest.tavily_search import search_tavily
from agent.state import AgentState

logger = logging.getLogger(__name__)

DEFAULT_MULTI_QUERY_COUNT = int(os.getenv("MULTI_QUERY_COUNT", "4"))
DEFAULT_SEARCH_RESULTS = int(os.getenv("MULTI_QUERY_MAX_RESULTS", "5"))


def _parse_query_variations(text: str) -> List[str]:
    variations: List[str] = []
    for line in text.splitlines():
        cleaned = line.strip().lstrip("-*0123456789. ").strip()
        if cleaned:
            variations.append(cleaned)
    return variations


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = sqrt(sum(float(a) * float(a) for a in left))
    right_norm = sqrt(sum(float(b) * float(b) for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def dedup_queries(
    queries: List[str],
    *,
    threshold: float = 0.95,
    embedder: Optional[Callable[[List[str]], List[Sequence[float]]]] = None,
) -> List[str]:
    """Deduplicate query variations, optionally using embedding cosine similarity."""
    unique: List[str] = []
    seen: Set[str] = set()

    if not embedder:
        for query in queries:
            cleaned = query.strip()
            if cleaned and cleaned not in seen:
                unique.append(cleaned)
                seen.add(cleaned)
        return unique

    embeddings = embedder(queries)
    kept_embeddings: List[Sequence[float]] = []
    for query, embedding in zip(queries, embeddings):
        cleaned = query.strip()
        if not cleaned or cleaned in seen:
            continue
        if any(_cosine_similarity(embedding, kept) >= threshold for kept in kept_embeddings):
            continue
        unique.append(cleaned)
        seen.add(cleaned)
        kept_embeddings.append(embedding)
    return unique


def expand_query(
    question: str,
    max_variations: int = DEFAULT_MULTI_QUERY_COUNT,
    *,
    llm: Optional[Callable[[str], str]] = None,
    embedder: Optional[Callable[[List[str]], List[Sequence[float]]]] = None,
    dedup_threshold: float = 0.95,
) -> List[str]:
    """
    Generate query variations for multi-query search.

    Improvements:
    - Extract key terms from question words (what, how, why, etc.)
    - Expand common abbreviations (RAG, LLM, NLP)
    - Add year variations for recency
    """
    question = question.strip()
    variations: List[str] = []
    lower = question.lower()

    def add(text: str) -> None:
        cleaned = text.strip()
        if cleaned and cleaned not in variations:
            variations.append(cleaned)

    if llm:
        add(question)
        variations.extend(_parse_query_variations(llm(question)))
        return dedup_queries(
            variations,
            threshold=dedup_threshold,
            embedder=embedder,
        )[:max_variations]

    # Remove question words for cleaner search
    # Special handling for definition queries ("what is X")
    search_terms = question
    is_definition_query = False
    for qword in ["can you explain", "what is", "how does", "why", "what are", "explain", "define", "meaning of"]:
        if lower.startswith(qword):
            search_terms = question[len(qword):].strip()
            if qword in ["what is", "what are", "define", "meaning of"]:
                is_definition_query = True
            break

    # Remove trailing question mark and clean up
    search_terms = search_terms.rstrip("?").strip()

    # Add cleaned search terms first
    if search_terms and search_terms != question:
        add(search_terms)
    add(question)

    # Expand common abbreviations with synonyms
    if "rag" in lower:
        # Add full form
        expanded = search_terms.replace("RAG", "retrieval augmented generation")
        expanded = expanded.replace("rag", "retrieval augmented generation")
        add(expanded)
        # Add related terms
        add(f"{expanded} architecture")
        add(f"{expanded} framework")
        add(f"{expanded} system")

    if "llm" in lower:
        # Add full form
        expanded = search_terms.replace("LLM", "large language model")
        expanded = expanded.replace("llm", "large language model")
        add(expanded)
        # Add related terms
        add(f"{expanded} architecture")
        add(f"{expanded} applications")

    # Add year variations for recency
    if "2025" not in lower and "2024" not in lower:
        add(f"{search_terms} 2025")
        add(f"{search_terms} 2024")

    # For definition queries, add variations that help find definitions
    if is_definition_query:
        add(f"{search_terms} definition")
        add(f"{search_terms} overview")
        add(f"{search_terms} introduction")
        add(f"introduction to {search_terms}")

    return variations[:max_variations]


def _search_arxiv_only(query: str, max_results: int) -> List[Dict]:
    """Search ArXiv API only."""
    try:
        arxiv_results = search_arxiv(query, max_results)
        return [
            {**asdict(res), "source": "arxiv"}
            for res in arxiv_results
        ]
    except Exception as exc:
        logger.warning(f"ArXiv search failed for query '{query}': {exc}")
        return []


def _search_tavily_only(query: str, max_results: int) -> List[Dict]:
    """Search Tavily API only."""
    try:
        tavily_results = search_tavily(query, max_results)
        return [
            {
                "title": res.title,
                "abs_url": res.url,
                "pdf_url": None,
                "published_at": res.published_date,
                "authors": [],
                "primary_category": "web",
                "abstract": res.content,
                "source": "tavily",
                "score": res.score,
            }
            for res in tavily_results
        ]
    except Exception as exc:
        logger.warning(f"Tavily search failed for query '{query}': {exc}")
        return []


def _search_single(query: str, max_results: int, search_source: str = "mixed") -> List[Dict]:
    """
    Search based on search_source parameter.

    Args:
        query: Search query
        max_results: Max results per source
        search_source: 'arxiv', 'tavily', or 'mixed'

    Returns:
        List of search results
    """
    if search_source == "arxiv":
        return _search_arxiv_only(query, max_results)
    elif search_source == "tavily":
        return _search_tavily_only(query, max_results)
    else:  # mixed
        all_results = []
        all_results.extend(_search_arxiv_only(query, max_results))
        all_results.extend(_search_tavily_only(query, max_results))
        return all_results


def search_node(state: AgentState) -> AgentState:
    """LangGraph node: run multi-query search based on search_source."""
    max_queries = int(state.get("multi_query_count", DEFAULT_MULTI_QUERY_COUNT))
    max_results = int(state.get("multi_query_max_results", DEFAULT_SEARCH_RESULTS))
    search_source = state.get("search_source", "mixed")

    queries = expand_query(state["query"], max_variations=max_queries)
    all_results: List[Dict] = []

    with ThreadPoolExecutor(max_workers=len(queries) or 1) as executor:
        future_map = {
            executor.submit(_search_single, q, max_results, search_source): q
            for q in queries
        }
        for future in as_completed(future_map):
            all_results.extend(future.result())

    # Deduplicate by URL
    seen_urls: Set[str] = set()
    unique_results: List[Dict] = []

    # Sort to prioritize high-scored Tavily results, then ArXiv
    sorted_results = sorted(
        all_results,
        key=lambda x: (x.get("source") == "tavily" and x.get("score", 0) > 0.7, x.get("score", 0)),
        reverse=True
    )

    for item in sorted_results:
        url = item.get("abs_url") or item.get("pdf_url")
        if not url:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        unique_results.append(item)

    # Log source distribution
    arxiv_count = sum(1 for r in unique_results if r.get("source") == "arxiv")
    tavily_count = sum(1 for r in unique_results if r.get("source") == "tavily")
    logger.info(f"Search [{search_source}]: {arxiv_count} ArXiv + {tavily_count} Tavily = {len(unique_results)} total")

    state["expanded_queries"] = queries  # type: ignore[assignment]
    state["search_results"] = unique_results  # type: ignore[assignment]
    return state
