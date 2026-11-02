from __future__ import annotations

import time
from typing import Callable

from langgraph.graph import END, StateGraph

from agent.nodes import answerability_node, generate_node, intent_node, route_node, search_node, retrieve_node, rerank_node
from agent.state import AgentState


def route_decision(state: AgentState) -> str:
    """Determine the next node after routing."""
    return state.get("route_type", "search")


def _record_metrics(state: AgentState, node: str, duration_ms: int) -> None:
    """Attach per-node metrics onto state."""
    metrics = state.get("metrics") or {}
    nodes = metrics.get("nodes") or {}
    entry = {"duration_ms": duration_ms}

    if node == "search":
        entry["expanded_queries"] = len(state.get("expanded_queries", []) or [])
        entry["search_results"] = len(state.get("search_results", []) or [])
    elif node == "retrieve":
        entry["snippets"] = len(state.get("merged_snippets", []) or [])
    elif node == "rerank":
        entry["reranked_snippets"] = len(state.get("kb_snippets", []) or [])
        entry["rerank_enabled"] = state.get("rerank_enabled", False)
    elif node == "generate":
        entry["citations_total"] = state.get("citations_total", 0)
        entry["citations_ok"] = state.get("citations_ok", 0)
    elif node == "answerability":
        answerability = state.get("answerability", {}) or {}
        entry["can_answer"] = answerability.get("can_answer")
        entry["reason"] = answerability.get("reason")

    nodes[node] = entry
    metrics["nodes"] = nodes
    # Summary counters for UI convenience
    metrics["expanded_queries_count"] = len(state.get("expanded_queries", []) or [])
    metrics["search_results_count"] = len(state.get("search_results", []) or [])
    metrics["snippets_count"] = len(state.get("merged_snippets", []) or [])
    state["metrics"] = metrics  # type: ignore[assignment]


def _with_metrics(node_name: str, fn: Callable[[AgentState], AgentState]) -> Callable[[AgentState], AgentState]:
    """Wrap a node function to measure duration and store metrics."""

    def wrapper(state: AgentState) -> AgentState:
        start = time.perf_counter()
        new_state = fn(state)
        duration_ms = int((time.perf_counter() - start) * 1000)
        _record_metrics(new_state, node_name, duration_ms)
        return new_state

    return wrapper


def _create_graph(*, include_generate: bool) -> StateGraph:
    """Create and compile the LangGraph for Stage 2."""
    graph = StateGraph(AgentState)

    # Nodes
    # Node id is "classify_intent" (not "intent") because LangGraph forbids a
    # node id that collides with an AgentState key — and AgentState has "intent".
    # The metrics label stays "intent" so metrics output is unchanged.
    graph.add_node("classify_intent", _with_metrics("intent", intent_node))
    graph.add_node("route", _with_metrics("route", route_node))
    graph.add_node("search", _with_metrics("search", search_node))
    graph.add_node("retrieve", _with_metrics("retrieve", retrieve_node))
    graph.add_node("rerank", _with_metrics("rerank", rerank_node))
    graph.add_node("check_answerability", _with_metrics("answerability", answerability_node))
    if include_generate:
        graph.add_node("generate", _with_metrics("generate", generate_node))

    # Entry point
    graph.set_entry_point("classify_intent")

    # Flow: classify_intent -> route -> conditional
    graph.add_edge("classify_intent", "route")
    graph.add_conditional_edges(
        "route",
        route_decision,
        {
            "kb_only": "retrieve",
            "search": "search",
            "search_only": "search",  # search_only still needs to run search node first
            "both": "search",
        },
    )

    # After search -> retrieve -> rerank -> answerability -> optional generate -> END
    graph.add_edge("search", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "check_answerability")
    if include_generate:
        graph.add_edge("check_answerability", "generate")
        graph.add_edge("generate", END)
    else:
        graph.add_edge("check_answerability", END)

    return graph.compile()


def create_graph() -> StateGraph:
    return _create_graph(include_generate=True)


def create_retrieval_graph() -> StateGraph:
    return _create_graph(include_generate=False)
