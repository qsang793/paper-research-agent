from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from agent.research.canonical_papers import resolve_canonical_papers


TECHNICAL_ALIASES: Dict[str, List[str]] = {
    "ROS2": ["ROS 2", "Robot Operating System 2"],
    "RAG": ["retrieval augmented generation", "retrieval-augmented generation"],
    "LLM": ["large language model", "large language models"],
    "GNN": ["graph neural network", "graph neural networks"],
    "QLORA": ["QLoRA", "quantized low-rank adaptation"],
    "LORA": ["LoRA", "low-rank adaptation"],
}

CATEGORY_HINTS: Dict[str, List[str]] = {
    "robot": ["cs.RO"],
    "robotics": ["cs.RO"],
    "ros2": ["cs.RO"],
    "ros 2": ["cs.RO"],
    "robot operating system 2": ["cs.RO"],
    "retrieval": ["cs.IR", "cs.CL"],
    "rag": ["cs.IR", "cs.CL"],
    "rerank": ["cs.IR"],
    "reranking": ["cs.IR"],
    "llm": ["cs.CL", "cs.AI"],
    "language model": ["cs.CL"],
    "graph neural": ["cs.LG"],
    "gnn": ["cs.LG"],
    "benchmark": ["cs.SE", "cs.LG"],
}

FILLER_TERMS = {
    "là",
    "gì",
    "trong",
    "về",
    "cho",
    "tôi",
    "la",
    "gi",
    "ve",
    "what",
    "is",
    "are",
    "the",
    "a",
    "an",
    "please",
    "explain",
    "define",
    # English function words: never topical, must not become required AND terms.
    "and",
    "or",
    "of",
    "for",
    "to",
    "in",
    "on",
    "with",
    "by",
    "from",
    "as",
    "at",
    "how",
    "does",
    "do",
    "can",
    "you",
    "me",
    "give",
    "tell",
    "that",
    "this",
    "used",
    "use",
    "using",
}

LOOKUP_TERMS = {"paper", "papers", "summary", "summarize", "about"}

# Words that describe the request, not the topic. Kept as keywords but excluded
# from entities so they are never AND-ed into provider queries — e.g. asking for
# the "original BERT paper" must not require the word "original", which the
# seminal paper's text does not contain.
META_TERMS = {
    "original",
    "explained",
    "overview",
    "introduction",
    "intro",
    "compare",
    "comparison",
    "versus",
    "vs",
    "recent",
    "latest",
    "best",
    "detailed",
    "comprehensive",
}
ARXIV_ID_RE = re.compile(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b")
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9.+-]*|\d{4}\.\d{4,5}(?:v\d+)?")


@dataclass(frozen=True)
class QueryPlan:
    original_query: str
    normalized_query: str
    entities: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    aliases: Dict[str, List[str]] = field(default_factory=dict)
    categories: List[str] = field(default_factory=list)
    arxiv_ids: List[str] = field(default_factory=list)
    canonical_arxiv_ids: List[str] = field(default_factory=list)
    canonical_titles: List[str] = field(default_factory=list)
    uses_llm: bool = False


def _canonical_token(token: str) -> str:
    token = token.strip()
    lookup = token.lower()
    for canonical in TECHNICAL_ALIASES:
        if lookup == canonical.lower():
            return canonical
        if lookup in {alias.lower() for alias in TECHNICAL_ALIASES[canonical]}:
            return canonical
    return token


def _unique(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _category_hints(text: str, entities: List[str]) -> List[str]:
    haystack = " ".join([text, *entities]).lower()
    categories: List[str] = []
    for phrase, hinted_categories in CATEGORY_HINTS.items():
        if phrase in haystack:
            categories.extend(hinted_categories)
    return _unique(categories)


def _normalize_arxiv_id(value: str) -> str:
    return re.sub(r"v\d+$", "", value.strip(), flags=re.IGNORECASE)


def plan_research_query(query: str) -> QueryPlan:
    """Build a deterministic research query plan without LLM calls."""
    cleaned = query.strip().rstrip("?!.")
    arxiv_ids = [_normalize_arxiv_id(match.group(0)) for match in ARXIV_ID_RE.finditer(cleaned)]
    token_source = cleaned
    for filler in sorted(FILLER_TERMS, key=len, reverse=True):
        token_source = re.sub(rf"\b{re.escape(filler)}\b", " ", token_source, flags=re.IGNORECASE)

    tokens = TOKEN_RE.findall(token_source)
    entities: List[str] = []
    keywords: List[str] = []
    for token in tokens:
        lower = token.lower()
        canonical = _normalize_arxiv_id(token) if ARXIV_ID_RE.fullmatch(token) else _canonical_token(token)
        if lower in FILLER_TERMS:
            continue
        keywords.append(canonical)
        if (lower in LOOKUP_TERMS or lower in META_TERMS) and canonical not in arxiv_ids:
            continue
        entities.append(canonical)

    entities = _unique(entities)
    keywords = _unique(keywords)
    aliases = {
        entity: TECHNICAL_ALIASES[entity]
        for entity in entities
        if entity in TECHNICAL_ALIASES
    }
    categories = _category_hints(cleaned, entities)
    normalized_query = " ".join(entities or keywords).strip()
    canonical_matches = resolve_canonical_papers(query)
    canonical_arxiv_ids = [paper.arxiv_id for paper in canonical_matches]
    canonical_titles = [paper.title for paper in canonical_matches]

    return QueryPlan(
        original_query=query,
        normalized_query=normalized_query or cleaned,
        entities=entities,
        keywords=keywords,
        aliases=aliases,
        categories=categories,
        arxiv_ids=arxiv_ids,
        canonical_arxiv_ids=canonical_arxiv_ids,
        canonical_titles=canonical_titles,
        uses_llm=False,
    )
