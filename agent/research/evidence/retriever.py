from __future__ import annotations

import re
from dataclasses import replace
from typing import Iterable, List

from agent.research.evidence.models import EvidenceSpan
from agent.research.evidence.extractor import extract_evidence_spans
from agent.research.indexing.contextual_chunks import ContextualChunk


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _score(query: str, text: str) -> float:
    query_tokens = _tokens(query)
    text_tokens = _tokens(text)
    overlap = len(query_tokens.intersection(text_tokens)) / max(len(query_tokens), 1)
    compact_bonus = 0.25 if _compact(query).strip() and _compact(query)[:4] in _compact(text) else 0.0
    return min(1.0, overlap + compact_bonus)


def retrieve_evidence(
    query: str,
    chunks: Iterable[ContextualChunk],
    *,
    paper_ids: List[str] | None = None,
    top_k: int = 5,
) -> List[EvidenceSpan]:
    allowed = set(paper_ids or [])
    selected_chunks: List[ContextualChunk] = []
    for chunk in chunks:
        if allowed and chunk.paper_id not in allowed:
            continue
        score = _score(query, chunk.text)
        if score <= 0:
            continue
        selected_chunks.append(replace(chunk, score=max(score, chunk.score)))
    spans = extract_evidence_spans(selected_chunks, query=query)
    return sorted(spans, key=lambda span: span.score, reverse=True)[:top_k]
