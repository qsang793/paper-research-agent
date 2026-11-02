from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple

from agent.research.evidence.models import EvidenceSpan
from agent.research.indexing.contextual_chunks import ContextualChunk


_STOP_TERMS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
    "cau",
    "gi",
    "la",
    "trong",
}

_CONTEXT_PREFIXES = ("paper:", "authors:", "year:", "section:", "context:")


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _tokens(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 1 and token not in _STOP_TERMS
    ]


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    return [part.strip() for part in parts if part.strip()]


def _evidence_text(chunk: ContextualChunk) -> str:
    text = chunk.chunk_text or chunk.text
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(_CONTEXT_PREFIXES):
            continue
        lines.append(stripped)
    return " ".join(line for line in lines if line)


def _sentence_score(sentence: str, query_terms: Sequence[str]) -> float:
    if not query_terms:
        return 0.0
    sentence_tokens = set(_tokens(sentence))
    compact_sentence = _compact(sentence)
    matched_terms = {
        term
        for term in query_terms
        if term in sentence_tokens or (len(term) >= 3 and term in compact_sentence)
    }
    return len(matched_terms) / len(set(query_terms))


def _rank_sentences(sentences: Sequence[str], query_terms: Sequence[str]) -> List[Tuple[int, str, float]]:
    scored = [
        (index, sentence, _sentence_score(sentence, query_terms))
        for index, sentence in enumerate(sentences)
    ]
    return [item for item in sorted(scored, key=lambda item: item[2], reverse=True) if item[2] > 0]


def _trim_quote(sentences: Sequence[str], max_chars: int) -> str:
    quote = " ".join(sentence.strip() for sentence in sentences if sentence.strip()).strip()
    if len(quote) <= max_chars:
        return quote
    return quote[: max_chars - 1].rstrip() + "..."


def extract_evidence_spans(
    chunks: Iterable[ContextualChunk],
    *,
    query: str,
    max_spans_per_chunk: int = 2,
    min_sentence_score: float = 0.15,
    max_quote_chars: int = 700,
) -> List[EvidenceSpan]:
    query_terms = _tokens(query)
    spans: List[EvidenceSpan] = []
    for chunk in chunks:
        ranked = [
            item
            for item in _rank_sentences(_sentences(_evidence_text(chunk)), query_terms)
            if item[2] >= min_sentence_score
        ][:max_spans_per_chunk]
        if not ranked:
            continue
        ordered_sentences = [sentence for _, sentence, _ in sorted(ranked, key=lambda item: item[0])]
        quote = _trim_quote(ordered_sentences, max_quote_chars)
        if not quote:
            continue
        sentence_score = max(score for _, _, score in ranked)
        score = min(1.0, (sentence_score * 0.85) + (max(chunk.score, 0.0) * 0.15))
        spans.append(
            EvidenceSpan(
                claim=ordered_sentences[0],
                paper_id=chunk.paper_id,
                title=chunk.title,
                section_title=chunk.section_title,
                url=chunk.source_url,
                quote=quote,
                score=score,
                chunk_id=chunk.chunk_id,
            )
        )
    return sorted(spans, key=lambda span: span.score, reverse=True)
