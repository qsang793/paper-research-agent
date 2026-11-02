"""
LlamaIndex-based pipeline for full integration.

This module provides a complete pipeline implementation using
LlamaIndex components while maintaining compatibility with the existing interface.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict, Optional

from agent.frameworks.llamaindex.graph import create_llamaindex_graph
from agent.memory import ConversationMemory
from agent.state import AgentState
from agent.memory import inject_memory_context
from agent.pipeline import _default_state


@lru_cache(maxsize=1)
def _get_llamaindex_graph():
    return create_llamaindex_graph()


def run_llamaindex_pipeline(
    query: str,
    *,
    chroma_path: str = "./chroma",
    embed_model: str | None = None,
    llm_backend: str | None = None,
    clean_dir: str | None = None,
    top_k: int | None = None,
    memory: Optional[ConversationMemory] = None,
    search_source: str = "mixed",
) -> Dict:
    """
    Execute the LlamaIndex-based LangGraph pipeline for a given query.
    
    This is a drop-in replacement for run_agent_graph() that uses
    LlamaIndex components (retrieve, rerank, generate nodes).
    
    Args:
        query: User query
        chroma_path: Path to ChromaDB
        embed_model: Embedding model name
        llm_backend: LLM backend ("ollama", "gemini", or "openrouter")
        clean_dir: Directory with clean JSON files for BM25
        top_k: Number of top results to retrieve
        memory: Optional conversation memory instance
        search_source: Search source: 'arxiv', 'tavily', or 'mixed'
    
    Returns:
        Dictionary with pipeline results including answer, citations, metrics, etc.
    """
    graph = _get_llamaindex_graph()
    
    # Inject memory context if available
    enhanced_query, memory_context_str = inject_memory_context(query, memory)
    
    state = _default_state(
        enhanced_query,  # Use enhanced query with memory context
        chroma_path=chroma_path,
        embed_model=embed_model,
        llm_backend=llm_backend,
        clean_dir=clean_dir,
        top_k=top_k,
        memory_context=memory_context_str,
        search_source=search_source,
    )
    
    result = graph.invoke(state)
    
    # Save to memory after successful generation
    if memory and result.get("answer"):
        citations = result.get("citations", [])
        # Use original query (not enhanced) as key
        memory.add(query, result["answer"], citations)
    
    return dict(result)
