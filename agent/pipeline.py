from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict, Optional

from agent.graph import create_graph, create_retrieval_graph
from agent.memory import ConversationMemory, inject_memory_context
from agent.state import AgentState


def _default_state(
    query: str,
    *,
    chroma_path: str,
    embed_model: str,
    llm_backend: str | None = None,
    clean_dir: str | None = None,
    top_k: int | None = None,
    memory_context: str = "",
    search_source: str = "mixed",
) -> AgentState:
    return AgentState(
        query=query,
        chroma_path=chroma_path,
        embed_model=embed_model,
        llm_backend=llm_backend or os.getenv("LLM_BACKEND", "ollama"),
        clean_dir=clean_dir or os.getenv("CLEAN_CACHE_DIR", "./cache/clean"),
        top_k=top_k or int(os.getenv("TOP_K", "6")),
        memory_context=memory_context,
        rerank_enabled=os.getenv("ENABLE_RERANKING", "true").lower() == "true",
        rerank_model=os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
        search_source=search_source,
    )


@lru_cache(maxsize=1)
def _get_graph():
    return create_graph()


@lru_cache(maxsize=1)
def _get_retrieval_graph():
    return create_retrieval_graph()


def _memory_context_only(query: str, memory: Optional[ConversationMemory]) -> str:
    """Return conversation context without turning it into retrieval text."""
    _, memory_context = inject_memory_context(query, memory)
    return memory_context


def run_agent_graph(
    query: str,
    *,
    chroma_path: str = "./chroma",
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    llm_backend: str | None = None,
    clean_dir: str | None = None,
    top_k: int | None = None,
    memory: Optional[ConversationMemory] = None,
    search_source: str = "mixed",
) -> Dict:
    """Execute the legacy LangGraph path with memory kept separate from retrieval."""
    graph = _get_graph()
    memory_context_str = _memory_context_only(query, memory)

    state = _default_state(
        query,
        chroma_path=chroma_path,
        embed_model=embed_model,
        llm_backend=llm_backend,
        clean_dir=clean_dir,
        top_k=top_k,
        memory_context=memory_context_str,
        search_source=search_source,
    )

    result = graph.invoke(state)

    if memory and result.get("answer"):
        citations = result.get("citations", [])
        memory.add(query, result["answer"], citations)

    return dict(result)


def run_agent_retrieval(
    query: str,
    *,
    chroma_path: str = "./chroma",
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    llm_backend: str | None = None,
    clean_dir: str | None = None,
    top_k: int | None = None,
    memory: Optional[ConversationMemory] = None,
    search_source: str = "mixed",
) -> Dict:
    """Run legacy routing/retrieval without contaminating the retrieval query."""
    graph = _get_retrieval_graph()
    memory_context_str = _memory_context_only(query, memory)
    state = _default_state(
        query,
        chroma_path=chroma_path,
        embed_model=embed_model,
        llm_backend=llm_backend,
        clean_dir=clean_dir,
        top_k=top_k,
        memory_context=memory_context_str,
        search_source=search_source,
    )
    result = graph.invoke(state)
    return dict(result)
