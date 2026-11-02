"""
Phase 5: Test LlamaIndex Reranker Integration.

Tests:
1. LlamaIndexReranker basic functionality
2. Compare với current rerank_node
3. Test different reranking modes
4. Quality comparison
"""

import pytest
import os
from typing import Dict, List

# Check if LlamaIndex reranker is available
try:
    from agent.frameworks.llamaindex import LlamaIndexReranker, rerank_node_llamaindex
    from agent.frameworks.llamaindex.reranker import LLAMAINDEX_RERANKER_AVAILABLE
    LLAMAINDEX_RERANKER_AVAILABLE_TEST = LLAMAINDEX_RERANKER_AVAILABLE
except ImportError:
    LLAMAINDEX_RERANKER_AVAILABLE_TEST = False

from agent.nodes.rerank import rerank_node
from agent.state import AgentState


def create_test_snippets() -> List[Dict]:
    """Create test snippets for reranking."""
    return [
        {
            "text": "Machine learning is a subset of artificial intelligence that focuses on algorithms.",
            "metadata": {
                "title": "ML Basics",
                "source_url": "https://example.com/ml"
            },
            "score_dense": 0.8
        },
        {
            "text": "Deep learning uses neural networks with multiple layers to learn complex patterns.",
            "metadata": {
                "title": "Deep Learning",
                "source_url": "https://example.com/dl"
            },
            "score_dense": 0.7
        },
        {
            "text": "Natural language processing enables computers to understand human language.",
            "metadata": {
                "title": "NLP",
                "source_url": "https://example.com/nlp"
            },
            "score_dense": 0.6
        },
        {
            "text": "Computer vision allows machines to interpret and understand visual information.",
            "metadata": {
                "title": "Computer Vision",
                "source_url": "https://example.com/cv"
            },
            "score_dense": 0.5
        },
        {
            "text": "Reinforcement learning is about learning through interaction with an environment.",
            "metadata": {
                "title": "RL",
                "source_url": "https://example.com/rl"
            },
            "score_dense": 0.4
        }
    ]


def test_llamaindex_reranker_cross_encoder():
    """Test LlamaIndexReranker với cross-encoder mode (default)."""
    reranker = LlamaIndexReranker(
        mode="cross_encoder",
        top_n=3,
        threshold=0.3,
        score_drop=0.3
    )
    
    query = "What is machine learning?"
    snippets = create_test_snippets()
    
    # Rerank
    reranked = reranker.rerank(query, snippets)
    
    assert isinstance(reranked, list)
    assert len(reranked) <= 3  # top_n
    assert len(reranked) > 0
    
    # Check that snippets have rerank_score
    for snippet in reranked:
        assert "rerank_score" in snippet
        assert snippet["rerank_score"] >= 0.0
    
    # Check ordering (should be sorted by rerank_score descending)
    scores = [s.get("rerank_score", 0.0) for s in reranked]
    assert scores == sorted(scores, reverse=True)
    
    print(f"✅ Cross-encoder reranking returned {len(reranked)} snippets")


def test_rerank_node_llamaindex_basic():
    """Test rerank_node_llamaindex với basic state."""
    snippets = create_test_snippets()
    
    state: AgentState = {
        "query": "What is machine learning?",
        "merged_snippets": snippets,
        "top_k": 3,
        "rerank_threshold": 0.3,
        "rerank_score_drop": 0.3,
        "rerank_mode": "cross_encoder"
    }
    
    # Run rerank_node_llamaindex
    result_state = rerank_node_llamaindex(state)
    
    # Check results
    assert "merged_snippets" in result_state
    reranked = result_state["merged_snippets"]
    assert isinstance(reranked, list)
    assert len(reranked) <= 3
    
    # Check metadata
    if reranked:
        assert result_state.get("rerank_applied") is True
        assert "rerank_top_score" in result_state
        assert "rerank_count" in result_state
    
    print(f"✅ rerank_node_llamaindex returned {len(reranked)} snippets")


def test_compare_with_current_rerank_node():
    """So sánh rerank_node_llamaindex với rerank_node hiện tại."""
    snippets = create_test_snippets()
    
    state: AgentState = {
        "query": "What is deep learning?",
        "merged_snippets": snippets.copy(),
        "top_k": 3,
        "rerank_threshold": 0.3,
        "rerank_score_drop": 0.3
    }
    
    # Run both rerankers
    llamaindex_state = rerank_node_llamaindex(state.copy())
    current_state = rerank_node(state.copy())
    
    # Compare results
    llamaindex_snippets = llamaindex_state.get("merged_snippets", [])
    current_snippets = current_state.get("merged_snippets", [])
    
    print(f"✅ LlamaIndex: {len(llamaindex_snippets)} snippets")
    print(f"✅ Current: {len(current_snippets)} snippets")
    
    # Both should return results
    assert len(llamaindex_snippets) > 0, "LlamaIndex should return results"
    assert len(current_snippets) > 0, "Current should return results"
    
    # Compare document keys (URLs/titles)
    llamaindex_keys = []
    for snippet in llamaindex_snippets:
        key = snippet.get("metadata", {}).get("source_url") or snippet.get("metadata", {}).get("title")
        if key:
            llamaindex_keys.append(key)
    
    current_keys = []
    for snippet in current_snippets:
        key = snippet.get("metadata", {}).get("source_url") or snippet.get("metadata", {}).get("title")
        if key:
            current_keys.append(key)
    
    overlap = set(llamaindex_keys) & set(current_keys)
    print(f"✅ Overlapping documents: {len(overlap)}/{min(len(llamaindex_keys), len(current_keys))}")
    
    # Should have some overlap (same query, same data, same mode)
    assert len(overlap) > 0, "Should have some overlapping documents"


def test_reranker_modes():
    """Test different reranker modes."""
    query = "What is neural network?"
    snippets = create_test_snippets()
    
    # Test cross-encoder mode (should always work)
    reranker = LlamaIndexReranker(mode="cross_encoder", top_n=3)
    reranked = reranker.rerank(query, snippets)
    assert len(reranked) > 0
    print(f"✅ Cross-encoder mode: {len(reranked)} snippets")
    
    # Test similarity mode (if available)
    if LLAMAINDEX_RERANKER_AVAILABLE_TEST:
        try:
            reranker_sim = LlamaIndexReranker(mode="similarity", top_n=3)
            reranked_sim = reranker_sim.rerank(query, snippets)
            assert len(reranked_sim) > 0
            print(f"✅ Similarity mode: {len(reranked_sim)} snippets")
        except Exception as e:
            print(f"⚠️ Similarity mode not available: {e}")
    
    # Test LLM mode (requires LLM, may not be available)
    # Skip for now as it requires LLM setup


def test_performance_benchmark():
    """Benchmark performance của rerank_node_llamaindex."""
    import time
    
    snippets = create_test_snippets()
    
    state: AgentState = {
        "query": "What is artificial intelligence?",
        "merged_snippets": snippets,
        "top_k": 3,
        "rerank_threshold": 0.3,
        "rerank_score_drop": 0.3,
        "rerank_mode": "cross_encoder"
    }
    
    # Benchmark LlamaIndex
    start = time.time()
    for _ in range(5):
        rerank_node_llamaindex(state.copy())
    llamaindex_time = (time.time() - start) / 5
    
    # Benchmark current
    start = time.time()
    for _ in range(5):
        rerank_node(state.copy())
    current_time = (time.time() - start) / 5
    
    print(f"✅ LlamaIndex: {llamaindex_time*1000:.2f}ms per rerank")
    print(f"✅ Current: {current_time*1000:.2f}ms per rerank")
    
    ratio = llamaindex_time / current_time if current_time > 0 else 0
    print(f"✅ Performance ratio: {ratio:.2f}x")
    
    # Performance should be within 2x (acceptable for Phase 5)
    assert ratio < 2.0, f"LlamaIndex should not be more than 2x slower (ratio: {ratio:.2f})"


def test_module_imports():
    """Test that modules can be imported."""
    try:
        from agent.frameworks.llamaindex import LlamaIndexReranker, rerank_node_llamaindex
        assert True
    except ImportError as e:
        pytest.skip(f"LlamaIndex reranker modules not available: {e}")
