from __future__ import annotations

import logging
import os
from typing import Dict, List

from agent.answerability import build_no_answer_message
from agent.citation_validator import validate_citation_sources
from agent.generator import generate_answer
from agent.sources import sources_from_snippets
from agent.state import AgentState

logger = logging.getLogger(__name__)


def generate_node(state: AgentState) -> AgentState:
    """
    LangGraph node: generate final answer from merged snippets using the
    configured LLM backend (Ollama/Gemini/OpenRouter) and validate citations.

    Supports memory-only generation when no snippets are available but
    memory context exists (e.g., for meta-questions about conversation history).
    Retrieval uses the standalone query while generation answers the original
    latest user wording, keeping conversation semantics separate from search text.
    """
    retrieval_query = state.get("standalone_query") or state.get("query", "")
    question = state.get("original_query") or retrieval_query
    snippets: List[Dict] = state.get("merged_snippets", []) or []
    memory_context = state.get("memory_context", "")
    answerability = state.get("answerability", {}) or {}

    logger.info(f"[Generate Node] Retrieval query: '{retrieval_query[:100]}...'")
    logger.info(f"[Generate Node] Original question: '{question[:100]}...'")
    logger.info(f"[Generate Node] Snippets count: {len(snippets)}")
    logger.info(f"[Generate Node] Memory context length: {len(memory_context)}")

    if answerability and not answerability.get("can_answer", True):
        reason = answerability.get("reason", "WEAK_EVIDENCE")
        state["answer"] = state.get("no_answer_message") or build_no_answer_message(reason)  # type: ignore[assignment]
        state["sources"] = state.get("sources", []) or []  # type: ignore[assignment]
        state["citations"] = []  # type: ignore[assignment]
        state["citations_ok"] = 0  # type: ignore[assignment]
        state["citations_total"] = 0  # type: ignore[assignment]
        state["citations_dead"] = []  # type: ignore[assignment]
        return state

    if snippets:
        logger.info(f"[Generate Node] Snippet sources: {[s.get('metadata', {}).get('title', 'N/A')[:50] for s in snippets[:3]]}")

    if not snippets and not memory_context:
        logger.warning("[Generate Node] No snippets and no memory context")
        state["answer"] = "Chua du nguon de tra loi cau hoi nay."
        state["sources"] = []  # type: ignore[assignment]
        state["citations"] = []  # type: ignore[assignment]
        state["citations_ok"] = 0  # type: ignore[assignment]
        state["citations_total"] = 0  # type: ignore[assignment]
        state["citations_dead"] = []  # type: ignore[assignment]
        return state

    llm_backend = state.get("llm_backend") or os.getenv("LLM_BACKEND", "ollama")
    logger.info(f"[Generate Node] Using LLM backend: {llm_backend}")
    logger.info(f"[Generate Node] Generating answer with {len(snippets)} snippets...")
    answer = generate_answer(
        question,
        snippets,
        backend=llm_backend,
        memory_context=memory_context,
    )
    logger.info(f"[Generate Node] Answer generated: {len(answer)} characters")
    state["answer"] = answer  # type: ignore[assignment]

    sources = state.get("sources") or sources_from_snippets(snippets)
    validation = validate_citation_sources(answer, sources)
    state["sources"] = validation.get("sources", sources)  # type: ignore[assignment]
    state["citations"] = validation.get("sources", sources)  # type: ignore[assignment]
    state["citations_ok"] = validation.get("ok", 0)  # type: ignore[assignment]
    state["citations_total"] = validation.get("total", 0)  # type: ignore[assignment]
    state["citations_dead"] = validation.get("dead", [])  # type: ignore[assignment]

    return state
