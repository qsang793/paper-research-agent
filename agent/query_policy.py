from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from agent.query_router import FreshnessNeed, RouteResult, RouteType


class QueryDecision(str, Enum):
    STATIC = "static"
    CHAT = "chat"
    OUT_OF_SCOPE = "out_of_scope"
    KB_ONLY = "kb_only"
    SEARCH_ONLY = "search_only"
    HYBRID = "hybrid"
    CLARIFY = "clarify"


class SourcePolicy(str, Enum):
    NONE = "none"
    KB = "kb"
    SEARCH = "search"
    HYBRID = "hybrid"


class AnswerPolicy(str, Enum):
    STATIC = "static"
    LLM = "llm"
    RAG = "rag"
    NO_ANSWER = "no_answer"
    CLARIFY = "clarify"


@dataclass(frozen=True)
class QueryPolicy:
    decision: QueryDecision
    reason: str
    confidence: float
    source_policy: SourcePolicy
    answer_policy: AnswerPolicy
    response: Optional[str] = None
    intent: str = "unknown"
    standalone_query: str = ""
    freshness: FreshnessNeed = "none"
    memory_write: Optional[str] = None
    memory_key: Optional[str] = None


def decide_query_policy(
    query: str,
    *,
    mode: str = "auto",
    route_result: RouteResult,
) -> QueryPolicy:
    """Map one structured router result plus explicit UI mode to execution policy.

    This layer intentionally contains no natural-language phrase lists. Manual
    modes are deterministic product controls; automatic language understanding
    belongs exclusively to the canonical query router.
    """
    normalized_mode = (mode or "auto").strip().lower()
    standalone_query = route_result.standalone_query or query.strip()
    common = {
        "confidence": route_result.confidence,
        "intent": route_result.intent,
        "standalone_query": standalone_query,
        "freshness": route_result.freshness,
        "memory_write": route_result.memory_write,
        "memory_key": route_result.memory_key,
    }

    if normalized_mode == "chat":
        return QueryPolicy(
            decision=QueryDecision.CHAT,
            reason="manual_chat_mode",
            source_policy=SourcePolicy.NONE,
            answer_policy=AnswerPolicy.LLM,
            **common,
        )

    if normalized_mode == "search":
        return QueryPolicy(
            decision=QueryDecision.HYBRID,
            reason="manual_search_mode",
            source_policy=SourcePolicy.HYBRID,
            answer_policy=AnswerPolicy.RAG,
            **common,
        )

    if route_result.route_type == RouteType.STATIC:
        return QueryPolicy(
            decision=QueryDecision.STATIC,
            reason=route_result.intent,
            source_policy=SourcePolicy.NONE,
            answer_policy=AnswerPolicy.STATIC,
            response=route_result.response,
            **common,
        )

    if route_result.route_type == RouteType.LLM_ONLY:
        return QueryPolicy(
            decision=QueryDecision.CHAT,
            reason=route_result.intent,
            source_policy=SourcePolicy.NONE,
            answer_policy=AnswerPolicy.LLM,
            **common,
        )

    if route_result.route_type == RouteType.OUT_OF_SCOPE:
        return QueryPolicy(
            decision=QueryDecision.OUT_OF_SCOPE,
            reason=route_result.intent or "outside_research_scope",
            source_policy=SourcePolicy.NONE,
            answer_policy=AnswerPolicy.NO_ANSWER,
            **common,
        )

    return QueryPolicy(
        decision=QueryDecision.HYBRID,
        reason=route_result.intent or "research",
        source_policy=SourcePolicy.HYBRID,
        answer_policy=AnswerPolicy.RAG,
        **common,
    )
