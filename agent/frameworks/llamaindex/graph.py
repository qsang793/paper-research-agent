"""
LlamaIndex-based LangGraph for full integration.

This module provides a complete LangGraph implementation using
LlamaIndex components while maintaining compatibility with the existing interface.
"""

from __future__ import annotations

import time
from typing import Callable

from langgraph.graph import END, StateGraph

from agent.nodes import intent_node, route_node, search_node
from agent.frameworks.llamaindex.retrieve_node import retrieve_node_llamaindex
from agent.frameworks.llamaindex.rerank_node import rerank_node_llamaindex
from agent.frameworks.llamaindex.generate_node import generate_node_llamaindex
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


def create_llamaindex_graph() -> StateGraph:
    """
    Create and compile the LangGraph using LlamaIndex components.

    This is a drop-in replacement for create_graph() that uses:
    - retrieve_node_llamaindex (instead of retrieve_node)
    - rerank_node_llamaindex (instead of rerank_node)
    - generate_node_llamaindex (instead of generate_node)

    Other nodes (intent, route, search) remain the same.
    """
    graph = StateGraph(AgentState)

    # Nodes - using LlamaIndex versions for retrieve, rerank, generate
    # Node id avoids colliding with AgentState["intent"] on newer LangGraph.
    graph.add_node("classify_intent", _with_metrics("intent", intent_node))
    graph.add_node("route", _with_metrics("route", route_node))
    graph.add_node("search", _with_metrics("search", search_node))
    graph.add_node("retrieve", _with_metrics("retrieve", retrieve_node_llamaindex))
    graph.add_node("rerank", _with_metrics("rerank", rerank_node_llamaindex))
    graph.add_node("generate", _with_metrics("generate", generate_node_llamaindex))

    # Entry point
    graph.set_entry_point("classify_intent")

    # Flow: intent -> route -> conditional
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

    # After search -> retrieve -> rerank -> generate -> END
    graph.add_edge("search", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "generate")
    graph.add_edge("generate", END)

    return graph.compile()
