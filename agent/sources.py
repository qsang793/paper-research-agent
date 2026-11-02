from __future__ import annotations

from typing import Dict, List


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def _score_from_snippet(snippet: Dict) -> float:
    if "relevance_score" in snippet:
        return _clamp_score(float(snippet.get("relevance_score") or 0.0))
    if "rerank_score_normalized" in snippet:
        return _clamp_score(float(snippet.get("rerank_score_normalized") or 0.0))
    if "similarity" in snippet:
        return _clamp_score(float(snippet.get("similarity") or 0.0))
    if "score_dense" in snippet:
        return _clamp_score(float(snippet.get("score_dense") or 0.0))
    if "rerank_score" in snippet:
        return 1.0 if float(snippet.get("rerank_score") or 0.0) > 0 else 0.0
    return 0.0


def source_from_snippet(snippet: Dict, index: int) -> Dict:
    metadata = snippet.get("metadata") or {}
    text = snippet.get("text") or snippet.get("document") or snippet.get("content") or ""
    url = metadata.get("source_url") or metadata.get("url") or snippet.get("url") or ""
    title = metadata.get("title") or snippet.get("title") or "Unknown"
    source_type = snippet.get("source") or metadata.get("source_type") or "kb"

    return {
        "id": f"source_{index}",
        "title": title,
        "url": url,
        "source_type": source_type,
        "score": _score_from_snippet(snippet),
        "relevance_score": _score_from_snippet(snippet),
        "snippet": text[:500],
        "published_at": metadata.get("published_at"),
        "alive_status": "unchecked",
        "authors": metadata.get("authors", []),
        "arxiv_id": metadata.get("arxiv_id"),
    }


def sources_from_snippets(snippets: List[Dict], *, include_empty_url: bool = False) -> List[Dict]:
    sources: List[Dict] = []
    for snippet in snippets:
        source = source_from_snippet(snippet, len(sources))
        if source["url"] or include_empty_url:
            sources.append(source)
    return sources
