"""
LlamaIndex-based retrieve node for LangGraph.

This module provides a retrieve_node implementation using LlamaIndex
retrievers while maintaining compatibility with the existing interface.
"""

import os
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from agent.state import AgentState
from agent.frameworks.llamaindex.retriever import LlamaIndexHybridRetriever
from agent.nodes.retrieve import _rrf_merge

DEFAULT_TOP_K = int(os.getenv("TOP_K", "6"))
DEFAULT_EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/e5-base-v2")


def retrieve_node_llamaindex(state: AgentState) -> AgentState:
    """
    LangGraph node: retrieve relevant snippets using LlamaIndex retrievers.
    
    This is a drop-in replacement for retrieve_node that uses LlamaIndex
    for dense retrieval while maintaining the same interface and behavior.
    
    Search source behavior (same as original):
    - arxiv: KB first (ChromaDB + BM25), use API results only if KB < min_threshold
    - tavily: Search results only (no KB)
    - mixed: RRF merge all sources (KB + search)
    """
    route_type = state.get("route_type", "search")
    search_source = state.get("search_source", "mixed")
    kb_confidence = state.get("kb_confidence", 0.5)
    chroma_path = state.get("chroma_path", "./chroma")
    embed_model = state.get("embed_model", DEFAULT_EMBED_MODEL)
    clean_dir = state.get("clean_dir", "./cache/clean")
    top_k = int(state.get("top_k", DEFAULT_TOP_K))
    search_results = state.get("search_results", [])
    
    # Minimum KB results before using API fallback (for arxiv mode)
    MIN_KB_THRESHOLD = 3

    # TAVILY mode: Search results only, no KB
    if search_source == "tavily":
        merged = []
        for snippet in search_results[:top_k]:
            metadata = {
                "source_url": snippet.get("abs_url"),
                "title": snippet.get("title"),
                "published_at": snippet.get("published_at"),
            }
            abstract_text = snippet.get("abstract") or snippet.get("summary") or snippet.get("title") or ""
            merged.append({
                "text": abstract_text,
                "metadata": metadata,
                "source": "tavily"
            })
        state["merged_snippets"] = merged  # type: ignore[assignment]
        return state

    # Get KB results using LlamaIndex hybrid retriever
    query_embedding = state.get("query_embedding")
    
    # Initialize LlamaIndex retriever
    hybrid_retriever = LlamaIndexHybridRetriever(
        chroma_path=chroma_path,
        embed_model=embed_model,
        clean_dir=clean_dir
    )
    
    # Parallelize Dense + BM25 retrieval
    with ThreadPoolExecutor(max_workers=2) as executor:
        dense_future = executor.submit(
            hybrid_retriever.dense_retrieve,
            state["query"],
            top_k=max(top_k * 2, 10),
            query_embedding=query_embedding
        )
        bm25_future = executor.submit(
            hybrid_retriever.bm25_retrieve,
            state["query"],
            top_k
        )
        
        dense_results = dense_future.result()
        bm25_results = bm25_future.result()
    
    # Count unique KB results
    kb_urls = set()
    for key, _, _ in dense_results:
        kb_urls.add(key)
    for key in bm25_results.keys():
        kb_urls.add(key)
    kb_count = len(kb_urls)

    # ARXIV mode: KB first, use ArXiv API results only if KB insufficient
    if search_source == "arxiv":
        if kb_count >= MIN_KB_THRESHOLD:
            merged = _rrf_merge(
                dense_results, 
                bm25_results, 
                [],
                k=top_k,
                kb_confidence=1.0,
                route_type="kb_only"
            )
        else:
            merged = _rrf_merge(
                dense_results, 
                bm25_results, 
                search_results,
                k=top_k,
                kb_confidence=kb_count / MIN_KB_THRESHOLD,
                route_type="both"
            )
        state["merged_snippets"] = merged  # type: ignore[assignment]
        return state

    # MIXED mode (default): RRF merge all sources
    if route_type == "search_only":
        merged = []
        for snippet in search_results[:top_k]:
            metadata = {
                "source_url": snippet.get("abs_url"),
                "title": snippet.get("title"),
                "published_at": snippet.get("published_at"),
            }
            abstract_text = snippet.get("abstract") or snippet.get("summary") or snippet.get("title") or ""
            merged.append({
                "text": abstract_text,
                "metadata": metadata,
                "source": "search"
            })
        state["merged_snippets"] = merged  # type: ignore[assignment]
        return state

    # Standard merge with all sources
    use_search = route_type in {"search", "both"}
    merged = _rrf_merge(
        dense_results, 
        bm25_results, 
        search_results if use_search else [], 
        k=top_k,
        kb_confidence=kb_confidence,
        route_type=route_type
    )

    state["merged_snippets"] = merged  # type: ignore[assignment]
    return state
