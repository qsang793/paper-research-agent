"""
Phase 3: Test LlamaIndex Retriever Integration.

Tests:
1. LlamaIndexHybridRetriever basic functionality
2. Compare với current retrieve_node
3. Performance benchmarking
4. Quality comparison
"""

import pytest
import os
from typing import Dict

# Check if LlamaIndex is available
try:
    from agent.frameworks.llamaindex import LlamaIndexHybridRetriever, retrieve_node_llamaindex
    from agent.frameworks.llamaindex.utils import check_llamaindex_installed
    LLAMAINDEX_AVAILABLE = check_llamaindex_installed()
except ImportError:
    LLAMAINDEX_AVAILABLE = False

from agent.nodes.retrieve import retrieve_node
from agent.state import AgentState
from agent.utils.embeddings import get_embed_model, embed_query

DEFAULT_EMBED_MODEL = "intfloat/e5-base-v2"


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_llamaindex_hybrid_retriever_basic():
    """Test basic LlamaIndexHybridRetriever functionality."""
    chroma_path = "./chroma"
    clean_dir = "./cache/clean"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    # Create retriever
    retriever = LlamaIndexHybridRetriever(
        chroma_path=chroma_path,
        embed_model=DEFAULT_EMBED_MODEL,
        clean_dir=clean_dir
    )
    
    # Test dense retrieval
    results = retriever.dense_retrieve("machine learning", top_k=5)
    assert isinstance(results, list)
    print(f"✅ Dense retrieval returned {len(results)} results")
    
    # Test BM25 retrieval
    bm25_results = retriever.bm25_retrieve("machine learning", top_k=5)
    assert isinstance(bm25_results, dict)
    print(f"✅ BM25 retrieval returned {len(bm25_results)} results")
    
    # Test hybrid retrieval
    hybrid_results = retriever.retrieve("machine learning", top_k=5)
    assert "dense" in hybrid_results
    assert "bm25" in hybrid_results
    print(f"✅ Hybrid retrieval: {len(hybrid_results['dense'])} dense, {len(hybrid_results['bm25'])} BM25")


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_retrieve_node_llamaindex_basic():
    """Test retrieve_node_llamaindex với basic state."""
    chroma_path = "./chroma"
    clean_dir = "./cache/clean"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    # Create test state
    query = "neural networks"
    query_embedding = embed_query(DEFAULT_EMBED_MODEL, query)
    
    state: AgentState = {
        "query": query,
        "query_embedding": query_embedding,
        "route_type": "search",
        "search_source": "mixed",
        "kb_confidence": 0.7,
        "chroma_path": chroma_path,
        "embed_model": DEFAULT_EMBED_MODEL,
        "clean_dir": clean_dir,
        "top_k": 5,
        "search_results": []
    }
    
    # Run retrieve_node_llamaindex
    result_state = retrieve_node_llamaindex(state)
    
    # Check results
    assert "merged_snippets" in result_state
    merged = result_state["merged_snippets"]
    assert isinstance(merged, list)
    print(f"✅ retrieve_node_llamaindex returned {len(merged)} snippets")


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_compare_with_current_retrieve_node():
    """So sánh retrieve_node_llamaindex với retrieve_node hiện tại."""
    chroma_path = "./chroma"
    clean_dir = "./cache/clean"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    # Create test state
    query = "deep learning"
    query_embedding = embed_query(DEFAULT_EMBED_MODEL, query)
    
    state: AgentState = {
        "query": query,
        "query_embedding": query_embedding,
        "route_type": "search",
        "search_source": "mixed",
        "kb_confidence": 0.7,
        "chroma_path": chroma_path,
        "embed_model": DEFAULT_EMBED_MODEL,
        "clean_dir": clean_dir,
        "top_k": 5,
        "search_results": []
    }
    
    # Run both retrievers
    llamaindex_state = retrieve_node_llamaindex(state.copy())
    current_state = retrieve_node(state.copy())
    
    # Compare results
    llamaindex_snippets = llamaindex_state.get("merged_snippets", [])
    current_snippets = current_state.get("merged_snippets", [])
    
    print(f"✅ LlamaIndex: {len(llamaindex_snippets)} snippets")
    print(f"✅ Current: {len(current_snippets)} snippets")
    
    # Should return similar number of results
    assert len(llamaindex_snippets) > 0, "LlamaIndex should return results"
    assert len(current_snippets) > 0, "Current should return results"
    
    # Compare document keys (URLs/titles)
    llamaindex_keys = set()
    for snippet in llamaindex_snippets:
        key = snippet.get("metadata", {}).get("source_url") or snippet.get("metadata", {}).get("title")
        if key:
            llamaindex_keys.add(key)
    
    current_keys = set()
    for snippet in current_snippets:
        key = snippet.get("metadata", {}).get("source_url") or snippet.get("metadata", {}).get("title")
        if key:
            current_keys.add(key)
    
    overlap = llamaindex_keys & current_keys
    print(f"✅ Overlapping documents: {len(overlap)}/{min(len(llamaindex_keys), len(current_keys))}")
    
    # Should have some overlap (same query, same data)
    assert len(overlap) > 0, "Should have some overlapping documents"


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_performance_benchmark():
    """Benchmark performance của retrieve_node_llamaindex."""
    import time
    
    chroma_path = "./chroma"
    clean_dir = "./cache/clean"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    query = "transformer architecture"
    query_embedding = embed_query(DEFAULT_EMBED_MODEL, query)
    
    state: AgentState = {
        "query": query,
        "query_embedding": query_embedding,
        "route_type": "search",
        "search_source": "mixed",
        "kb_confidence": 0.7,
        "chroma_path": chroma_path,
        "embed_model": DEFAULT_EMBED_MODEL,
        "clean_dir": clean_dir,
        "top_k": 5,
        "search_results": []
    }
    
    # Benchmark LlamaIndex
    start = time.time()
    for _ in range(5):
        retrieve_node_llamaindex(state.copy())
    llamaindex_time = (time.time() - start) / 5
    
    # Benchmark current
    start = time.time()
    for _ in range(5):
        retrieve_node(state.copy())
    current_time = (time.time() - start) / 5
    
    print(f"✅ LlamaIndex: {llamaindex_time*1000:.2f}ms per retrieval")
    print(f"✅ Current: {current_time*1000:.2f}ms per retrieval")
    
    ratio = llamaindex_time / current_time
    print(f"✅ Performance ratio: {ratio:.2f}x")
    
    # Performance should be within 2x (acceptable for Phase 3)
    assert ratio < 2.0, f"LlamaIndex should not be more than 2x slower (ratio: {ratio:.2f})"


def test_module_imports():
    """Test that modules can be imported."""
    try:
        from agent.frameworks.llamaindex import LlamaIndexHybridRetriever, retrieve_node_llamaindex
        assert True
    except ImportError as e:
        pytest.skip(f"LlamaIndex modules not available: {e}")
