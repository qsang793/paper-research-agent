from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class CanonicalPaper:
    key: str
    title: str
    arxiv_id: str
    aliases: tuple[str, ...]


CANONICAL_PAPERS: tuple[CanonicalPaper, ...] = (
    CanonicalPaper(
        key="transformer",
        title="Attention Is All You Need",
        arxiv_id="1706.03762",
        aliases=("transformer paper", "attention is all you need", "original transformer"),
    ),
    CanonicalPaper(
        key="lora",
        title="LoRA: Low-Rank Adaptation of Large Language Models",
        arxiv_id="2106.09685",
        aliases=("lora", "lora paper", "low-rank adaptation", "original lora"),
    ),
    CanonicalPaper(
        key="qlora",
        title="QLoRA: Efficient Finetuning of Quantized LLMs",
        arxiv_id="2305.14314",
        aliases=("qlora", "qlora paper", "quantized low-rank adaptation", "original qlora"),
    ),
    CanonicalPaper(
        key="bert",
        title="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        arxiv_id="1810.04805",
        aliases=("bert paper", "original bert"),
    ),
    CanonicalPaper(
        key="rag",
        title="Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        arxiv_id="2005.11401",
        aliases=("rag paper", "original rag", "retrieval augmented generation original"),
    ),
)


def _contains_lookup_intent(text: str) -> bool:
    lowered = text.lower()
    return any(
        term in lowered
        for term in ("paper", "papers", "summary", "có gì", "compare", "original", "explained")
    )


def _alias_hit(alias: str, lowered_query: str) -> bool:
    return f" {alias} " in f" {lowered_query} "


def resolve_canonical_papers(query: str) -> List[CanonicalPaper]:
    lowered = query.lower()

    if not _contains_lookup_intent(query):
        return []

    if "compare" in lowered and "lora" in lowered and "qlora" in lowered:
        return [
            _paper_for_key("lora"),
            _paper_for_key("qlora"),
        ]

    matches: List[CanonicalPaper] = []
    for paper in CANONICAL_PAPERS:
        if paper.key in lowered:
            matches.append(paper)
            continue
        if any(_alias_hit(alias, lowered) for alias in paper.aliases):
            matches.append(paper)

    return matches


def _paper_for_key(key: str) -> CanonicalPaper:
    for paper in CANONICAL_PAPERS:
        if paper.key == key:
            return paper
    raise KeyError(f"No canonical paper for key: {key}")
