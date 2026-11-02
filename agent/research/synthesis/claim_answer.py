from __future__ import annotations

import re

from typing import Dict, List, Set

from agent.generator import generate_answer
from agent.research.evidence.models import EvidenceSpan


CLAIM_GROUNDED_TEMPLATE = """You are a research assistant.
Answer the user's question using only the evidence below for factual research claims.
Conversation context may be used only to resolve references, preferences, and continuity; it is not research evidence.
Every major factual claim must cite evidence IDs like [E1].
Do not cite an evidence ID that is not listed.
Do not group all citations at the end; place citations next to the claim they support.
If the evidence is insufficient, say that the evidence is insufficient and list what is missing.
Prefer the user's language.

Conversation context (not evidence):
{memory}

Evidence:
{context}

Question: {question}
Answer:
"""


def _evidence_context(evidence: List[EvidenceSpan]) -> str:
    context_lines = []
    for index, span in enumerate(evidence, start=1):
        context_lines.append(
            f"[E{index}] Paper: {span.title}\n"
            f"URL: {span.url}\n"
            f"Section: {span.section_title}\n"
            f"Claim candidate: {span.claim or span.quote}\n"
            f"Quote: {span.quote}"
        )
    return "\n\n".join(context_lines)


def build_claim_grounded_prompt(
    question: str,
    evidence: List[EvidenceSpan],
    *,
    memory_context: str = "",
) -> str:
    memory = memory_context.strip() or "(none)"
    return CLAIM_GROUNDED_TEMPLATE.format(
        context=_evidence_context(evidence),
        question=question,
        memory=memory,
    )


def validate_claim_citations(answer: str, *, allowed_ids: Set[str]) -> Dict:
    citation_pattern = re.compile(r"\[(E\d+)\]")
    invalid_ids: List[str] = []
    seen_invalid: Set[str] = set()

    for citation_id in citation_pattern.findall(answer):
        if citation_id not in allowed_ids and citation_id not in seen_invalid:
            invalid_ids.append(citation_id)
            seen_invalid.add(citation_id)

    sentence_parts = re.split(r"(?<=[.!?])\s+", answer.strip())
    uncited_claim_count = 0
    for part in sentence_parts:
        sentence = part.strip()
        if not sentence:
            continue

        lowered = sentence.lower()
        if "insufficient" in lowered or "chưa đủ" in lowered:
            continue

        if citation_pattern.search(sentence):
            continue

        word_count = len(re.findall(r"\b\w+\b", sentence, flags=re.UNICODE))
        if word_count >= 5:
            uncited_claim_count += 1

    return {
        "valid": not invalid_ids and uncited_claim_count == 0,
        "invalid_ids": invalid_ids,
        "uncited_claim_count": uncited_claim_count,
    }


def assess_evidence_answerability(
    evidence: List[EvidenceSpan],
    *,
    paper_count: int,
    min_evidence_count: int = 1,
    min_score: float = 0.2,
) -> Dict:
    if paper_count == 0:
        return {"can_answer": False, "reason": "NO_PAPER_FOUND", "evidence_count": 0}
    if len(evidence) < min_evidence_count:
        return {"can_answer": False, "reason": "NO_EVIDENCE_FOUND", "evidence_count": len(evidence)}
    top_score = max((span.score for span in evidence), default=0.0)
    if top_score < min_score:
        return {"can_answer": False, "reason": "WEAK_EVIDENCE", "evidence_count": len(evidence), "top_score": top_score}
    return {"can_answer": True, "reason": "ANSWERABLE", "evidence_count": len(evidence), "top_score": top_score}


def generate_claim_grounded_answer(
    question: str,
    evidence: List[EvidenceSpan],
    *,
    backend: str | None = None,
    memory_context: str = "",
) -> str:
    snippets = [
        {
            "text": (
                f"[E{index}]\n"
                f"Paper: {span.title}\n"
                f"Section: {span.section_title}\n"
                f"Claim candidate: {span.claim or span.quote}\n"
                f"Quote: {span.quote}"
            ),
            "metadata": {
                "title": span.title,
                "source_url": span.url,
                "paper_id": span.paper_id,
                "section_title": span.section_title,
            },
        }
        for index, span in enumerate(evidence, start=1)
    ]
    return generate_answer(
        question,
        snippets,
        prompt_template=CLAIM_GROUNDED_TEMPLATE,
        backend=backend,
        memory_context=memory_context,
    )
