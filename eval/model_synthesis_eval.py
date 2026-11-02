from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.research.evidence.models import EvidenceSpan
from agent.research.synthesis.claim_answer import generate_claim_grounded_answer, validate_claim_citations

FIXED_EVIDENCE = [
    EvidenceSpan(
        paper_id="1706.03762",
        title="Attention Is All You Need",
        url="https://arxiv.org/abs/1706.03762",
        quote=(
            "The Transformer uses stacked self-attention and omits recurrence and convolutions "
            "in both encoder and decoder stacks."
        ),
        score=1.0,
        claim="The Transformer removes recurrence.",
        section_title="Abstract",
    )
]
FIXED_EXPECTED_TERMS = ["self-attention", "recurrence"]
FIXED_ALLOWED_IDS = {"E1"}
FIXED_QUESTION = "What are the key technical characteristics of the Transformer architecture?"


def grade_synthesis_output(
    answer: str, *, expected_terms: Iterable[str], allowed_ids: Set[str]
) -> dict:
    terms = [term.lower() for term in expected_terms if term.strip()]
    lowered = answer.lower()
    term_recall = 0.0 if not terms else sum(1 for term in terms if term in lowered) / len(terms)
    citation_grade = validate_claim_citations(answer, allowed_ids=allowed_ids)
    return {
        "passes": term_recall >= 0.8 and citation_grade["valid"],
        "term_recall": term_recall,
        "citation_grade": citation_grade,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate same-context synthesis output quality.")
    parser.add_argument(
        "--answer",
        help="Answer text to grade directly (skip generation for smoke tests).",
    )
    parser.add_argument(
        "--backend",
        help="Backend used by generate_claim_grounded_answer when --answer is not provided.",
    )
    return parser


def _run_evaluation(answer: str | None, backend: str | None) -> tuple[str, dict]:
    final_answer = answer
    if final_answer is None:
        final_answer = generate_claim_grounded_answer(
            FIXED_QUESTION,
            FIXED_EVIDENCE,
            backend=backend,
        )
    grade = grade_synthesis_output(
        final_answer,
        expected_terms=FIXED_EXPECTED_TERMS,
        allowed_ids=FIXED_ALLOWED_IDS,
    )
    return final_answer, grade


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    answer, grade = _run_evaluation(args.answer, args.backend)
    print(
        json.dumps(
            {
                "question": FIXED_QUESTION,
                "answer": answer,
                "grade": grade,
            },
            ensure_ascii=False,
        )
    )
    return 0 if grade["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
