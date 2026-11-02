from __future__ import annotations

from agent.query_router import get_router
from agent.state import AgentState


def intent_node(state: AgentState) -> AgentState:
    """Compatibility node that derives legacy freshness fields from the canonical router.

    The production chat API and the legacy LangGraph pipeline share the same
    natural-language classifier and standalone-query semantics. This node does
    not maintain keyword/year rules.
    """
    original_query = state.get("original_query") or state["query"]
    result = get_router().route(
        original_query,
        conversation_context=state.get("memory_context", ""),
    )

    if result.freshness == "current":
        intent = "fresh"
    elif result.freshness == "mixed":
        intent = "mixed"
    else:
        intent = "known"

    standalone_query = result.standalone_query or original_query
    state["original_query"] = original_query
    state["standalone_query"] = standalone_query
    state["query"] = standalone_query
    state["freshness"] = result.freshness
    state["intent"] = intent  # type: ignore[assignment]
    state["intent_confidence"] = result.confidence  # type: ignore[assignment]
    return state
