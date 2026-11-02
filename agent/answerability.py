from __future__ import annotations

import os
from enum import Enum
from typing import Dict, List

from agent.sources import sources_from_snippets
from agent.state import AgentState


class AnswerabilityReason(str, Enum):
    ANSWERABLE = "ANSWERABLE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    NO_KB_MATCH = "NO_KB_MATCH"
    NO_SEARCH_RESULTS = "NO_SEARCH_RESULTS"
    NO_PAPER_FOUND = "NO_PAPER_FOUND"
    NO_EVIDENCE_FOUND = "NO_EVIDENCE_FOUND"
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
    INFRA_ERROR = "INFRA_ERROR"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"


NO_ANSWER_MESSAGES = {
    AnswerabilityReason.OUT_OF_SCOPE.value: (
        "Cau hoi nay nam ngoai pham vi tro ly nghien cuu AI/ML. "
        "Hay hoi ve paper, model, RAG, LLM, retrieval, evaluation, hoac chu de AI lien quan."
    ),
    AnswerabilityReason.NO_KB_MATCH.value: (
        "Chua co nguon phu hop trong knowledge base de tra loi cau hoi nay."
    ),
    AnswerabilityReason.NO_SEARCH_RESULTS.value: (
        "Khong tim thay nguon web/arXiv du tin cay de tra loi cau hoi nay."
    ),
    AnswerabilityReason.NO_PAPER_FOUND.value: (
        "Khong tim thay paper phu hop de tra loi cau hoi nay."
    ),
    AnswerabilityReason.NO_EVIDENCE_FOUND.value: (
        "Da tim thay paper ung vien, nhung chua co evidence span du tin cay de tra loi."
    ),
    AnswerabilityReason.WEAK_EVIDENCE.value: (
        "Nguon tim duoc co do lien quan qua thap, nen toi khong tra loi de tranh bia dat."
    ),
    AnswerabilityReason.INFRA_ERROR.value: (
        "He thong truy xuat nguon dang gap loi, vui long thu lai sau."
    ),
    AnswerabilityReason.NEEDS_CLARIFICATION.value: (
        "Cau hoi hien chua du ro de truy xuat nguon chinh xac. Hay bo sung chu de, thoi gian, hoac loai nguon can tim."
    ),
}


def build_no_answer_message(reason: str) -> str:
    return NO_ANSWER_MESSAGES.get(reason, "Chua du nguon de tra loi cau hoi nay.")


def _top_rerank_score(snippets: List[Dict]) -> float | None:
    scores = [
        float(snippet["rerank_score"])
        for snippet in snippets
        if snippet.get("rerank_score") is not None
    ]
    return max(scores) if scores else None


def evaluate_answerability(state: AgentState) -> Dict:
    snippets = state.get("merged_snippets", []) or []
    memory_context = state.get("memory_context", "")
    route_type = state.get("route_type", "kb_only")
    search_results = state.get("search_results", []) or []
    error = state.get("error")

    if state.get("query_policy", {}).get("decision") == "out_of_scope":
        reason = AnswerabilityReason.OUT_OF_SCOPE.value
        return {
            "can_answer": False,
            "reason": reason,
            "evidence_count": 0,
            "top_score": None,
            "source_mix": [],
            "recommended_action": build_no_answer_message(reason),
        }

    if error:
        reason = AnswerabilityReason.INFRA_ERROR.value
        return {
            "can_answer": False,
            "reason": reason,
            "evidence_count": 0,
            "top_score": None,
            "source_mix": [],
            "recommended_action": build_no_answer_message(reason),
        }

    if not snippets and memory_context:
        return {
            "can_answer": True,
            "reason": AnswerabilityReason.ANSWERABLE.value,
            "evidence_count": 0,
            "top_score": None,
            "source_mix": ["memory"],
            "recommended_action": "",
        }

    if not snippets:
        reason = (
            AnswerabilityReason.NO_SEARCH_RESULTS.value
            if route_type in {"search", "search_only", "both"} and not search_results
            else AnswerabilityReason.NO_KB_MATCH.value
        )
        return {
            "can_answer": False,
            "reason": reason,
            "evidence_count": 0,
            "top_score": None,
            "source_mix": [],
            "recommended_action": build_no_answer_message(reason),
        }

    top_score = _top_rerank_score(snippets)
    min_rerank_score = float(os.getenv("ANSWERABILITY_MIN_RERANK_SCORE", "-8.0"))
    if top_score is not None and top_score < min_rerank_score:
        reason = AnswerabilityReason.WEAK_EVIDENCE.value
        return {
            "can_answer": False,
            "reason": reason,
            "evidence_count": len(snippets),
            "top_score": top_score,
            "source_mix": sorted({s.get("source", "kb") for s in snippets}),
            "recommended_action": build_no_answer_message(reason),
        }

    return {
        "can_answer": True,
        "reason": AnswerabilityReason.ANSWERABLE.value,
        "evidence_count": len(snippets),
        "top_score": top_score,
        "source_mix": sorted({s.get("source", "kb") for s in snippets}),
        "recommended_action": "",
    }


def answerability_node(state: AgentState) -> AgentState:
    result = evaluate_answerability(state)
    state["answerability"] = result  # type: ignore[assignment]
    state["sources"] = sources_from_snippets(state.get("merged_snippets", []) or [])  # type: ignore[assignment]
    if not result["can_answer"]:
        state["no_answer_message"] = build_no_answer_message(result["reason"])  # type: ignore[assignment]
    return state
