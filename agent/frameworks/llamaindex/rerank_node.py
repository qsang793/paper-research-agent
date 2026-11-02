"""
LlamaIndex-based rerank node for LangGraph.

This module provides a rerank_node implementation using LlamaIndex
rerankers while maintaining compatibility with the existing interface.
"""

import logging
import os
from typing import Dict, List

from agent.state import AgentState
from agent.frameworks.llamaindex.reranker import LlamaIndexReranker

logger = logging.getLogger(__name__)

DEFAULT_RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "6"))
DEFAULT_RERANK_THRESHOLD = float(os.getenv("RERANK_THRESHOLD", "0.3"))
DEFAULT_RERANK_SCORE_DROP = float(os.getenv("RERANK_SCORE_DROP", "0.3"))
ENABLE_RERANKING = os.getenv("ENABLE_RERANKING", "true").lower() == "true"


def rerank_node_llamaindex(state: AgentState) -> AgentState:
    """
    LangGraph node: re-rank merged snippets using LlamaIndex rerankers.
    
    This is a drop-in replacement for rerank_node that uses LlamaIndex
    rerankers while maintaining the same interface and behavior.
    
    Supports:
    - LlamaIndex LLMRerank (LLM-based)
    - LlamaIndex SimilarityPostprocessor (similarity-based)
    - Fallback to cross-encoder (current implementation)
    """
    snippets = state.get("merged_snippets", []) or []
    query = state["query"]
    top_k = int(state.get("top_k", DEFAULT_RERANK_TOP_K))
    threshold = float(state.get("rerank_threshold", DEFAULT_RERANK_THRESHOLD))
    score_drop = float(state.get("rerank_score_drop", DEFAULT_RERANK_SCORE_DROP))
    
    # Get reranker mode from state or env
    rerank_mode = state.get("rerank_mode") or os.getenv("RERANK_MODE", "cross_encoder")
    
    if not snippets:
        logger.warning("No snippets to re-rank")
        return state
    
    if not ENABLE_RERANKING:
        logger.info("Re-ranking disabled, returning original snippets")
        state["merged_snippets"] = snippets[:top_k]  # type: ignore[assignment]
        return state
    
    # Get LLM for LLMRerank mode if needed
    llm = None
    if rerank_mode == "llm":
        try:
            from agent.frameworks.llamaindex.llm import LlamaIndexLLMWrapper
            llm_backend = state.get("llm_backend") or os.getenv("LLM_BACKEND", "openrouter")
            llm = LlamaIndexLLMWrapper(backend=llm_backend)
        except Exception as exc:
            logger.warning(f"Could not initialize LLM for reranking: {exc}. Using cross-encoder.")
            rerank_mode = "cross_encoder"
    
    # Initialize reranker
    reranker = LlamaIndexReranker(
        mode=rerank_mode,
        top_n=top_k,
        threshold=threshold,
        score_drop=score_drop,
        llm=llm
    )
    
    # Re-rank snippets
    try:
        reranked_snippets = reranker.rerank(query, snippets)
    except Exception as exc:
        logger.error(f"Re-ranking failed: {exc}. Returning original order.")
        reranked_snippets = snippets[:top_k]
    
    # Update state with re-ranked snippets
    state["merged_snippets"] = reranked_snippets  # type: ignore[assignment]
    
    # Store re-ranking metadata for debugging
    if reranked_snippets:
        state["rerank_applied"] = True  # type: ignore[assignment]
        state["rerank_top_score"] = reranked_snippets[0].get("rerank_score", 0.0)  # type: ignore[assignment]
        state["rerank_count"] = len(reranked_snippets)  # type: ignore[assignment]
        state["rerank_mode"] = rerank_mode  # type: ignore[assignment]
    
    return state
