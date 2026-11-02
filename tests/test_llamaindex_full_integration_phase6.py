"""
Phase 6: Test Full LlamaIndex Integration.

Tests:
1. End-to-end pipeline với LlamaIndex components
2. Performance comparison (current vs LlamaIndex)
3. Quality comparison (answer quality, citations)
4. Compatibility check
"""

import pytest
import os
from typing import Dict

# Check if LlamaIndex is available
try:
    from agent.frameworks.llamaindex import run_llamaindex_pipeline
    from agent.frameworks.llamaindex.utils import check_llamaindex_installed
    LLAMAINDEX_AVAILABLE = check_llamaindex_installed()
except ImportError:
    LLAMAINDEX_AVAILABLE = False

from agent.pipeline import run_agent_graph


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_llamaindex_pipeline_basic():
    """Test basic LlamaIndex pipeline execution."""
    chroma_path = "./chroma"
    clean_dir = "./cache/clean"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    query = "What is machine learning?"
    
    # Run LlamaIndex pipeline
    result = run_llamaindex_pipeline(
        query,
        chroma_path=chroma_path,
        clean_dir=clean_dir,
        top_k=5,
        search_source="mixed"
    )
    
    # Check results
    assert "answer" in result
    assert isinstance(result["answer"], str)
    assert len(result["answer"]) > 0
    
    # Check metrics
    assert "metrics" in result
    metrics = result["metrics"]
    assert "nodes" in metrics
    
    print(f"✅ LlamaIndex pipeline returned answer: {len(result['answer'])} characters")
    print(f"✅ Metrics: {list(metrics.get('nodes', {}).keys())}")


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_compare_pipelines():
    """So sánh LlamaIndex pipeline với current pipeline."""
    chroma_path = "./chroma"
    clean_dir = "./cache/clean"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    query = "What is deep learning?"
    
    # Run both pipelines
    llamaindex_result = run_llamaindex_pipeline(
        query,
        chroma_path=chroma_path,
        clean_dir=clean_dir,
        top_k=5,
        search_source="mixed"
    )
    
    current_result = run_agent_graph(
        query,
        chroma_path=chroma_path,
        clean_dir=clean_dir,
        top_k=5,
        search_source="mixed"
    )
    
    # Compare answers
    llamaindex_answer = llamaindex_result.get("answer", "")
    current_answer = current_result.get("answer", "")
    
    print(f"✅ LlamaIndex answer: {len(llamaindex_answer)} characters")
    print(f"✅ Current answer: {len(current_answer)} characters")
    
    # Both should return answers
    assert len(llamaindex_answer) > 0, "LlamaIndex should return answer"
    assert len(current_answer) > 0, "Current should return answer"
    
    # Compare snippets count
    llamaindex_snippets = len(llamaindex_result.get("merged_snippets", []) or [])
    current_snippets = len(current_result.get("merged_snippets", []) or [])
    
    print(f"✅ LlamaIndex snippets: {llamaindex_snippets}")
    print(f"✅ Current snippets: {current_snippets}")
    
    # Compare citations
    llamaindex_citations = llamaindex_result.get("citations", [])
    current_citations = current_result.get("citations", [])
    
    print(f"✅ LlamaIndex citations: {len(llamaindex_citations)}")
    print(f"✅ Current citations: {len(current_citations)}")


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_performance_comparison():
    """Benchmark performance của LlamaIndex pipeline vs current."""
    import time
    
    chroma_path = "./chroma"
    clean_dir = "./cache/clean"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    query = "What is transformer architecture?"
    
    # Benchmark LlamaIndex (single run due to API costs)
    start = time.time()
    llamaindex_result = run_llamaindex_pipeline(
        query,
        chroma_path=chroma_path,
        clean_dir=clean_dir,
        top_k=5,
        search_source="mixed"
    )
    llamaindex_time = time.time() - start
    
    # Benchmark current (single run)
    start = time.time()
    current_result = run_agent_graph(
        query,
        chroma_path=chroma_path,
        clean_dir=clean_dir,
        top_k=5,
        search_source="mixed"
    )
    current_time = time.time() - start
    
    print(f"✅ LlamaIndex: {llamaindex_time*1000:.2f}ms")
    print(f"✅ Current: {current_time*1000:.2f}ms")
    
    ratio = llamaindex_time / current_time if current_time > 0 else 0
    print(f"✅ Performance ratio: {ratio:.2f}x")
    
    # Compare node-level metrics
    llamaindex_metrics = llamaindex_result.get("metrics", {}).get("nodes", {})
    current_metrics = current_result.get("metrics", {}).get("nodes", {})
    
    print("\nNode-level comparison:")
    for node in ["retrieve", "rerank", "generate"]:
        llamaindex_duration = llamaindex_metrics.get(node, {}).get("duration_ms", 0)
        current_duration = current_metrics.get(node, {}).get("duration_ms", 0)
        if llamaindex_duration > 0 and current_duration > 0:
            node_ratio = llamaindex_duration / current_duration
            print(f"  {node}: LlamaIndex={llamaindex_duration}ms, Current={current_duration}ms, Ratio={node_ratio:.2f}x")
    
    # Performance should be within 2x (acceptable for Phase 6)
    assert ratio < 2.0, f"LlamaIndex should not be more than 2x slower (ratio: {ratio:.2f})"


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_quality_comparison():
    """Compare answer quality between LlamaIndex và current pipeline."""
    chroma_path = "./chroma"
    clean_dir = "./cache/clean"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    query = "Explain neural networks"
    
    # Run both pipelines
    llamaindex_result = run_llamaindex_pipeline(
        query,
        chroma_path=chroma_path,
        clean_dir=clean_dir,
        top_k=5,
        search_source="mixed"
    )
    
    current_result = run_agent_graph(
        query,
        chroma_path=chroma_path,
        clean_dir=clean_dir,
        top_k=5,
        search_source="mixed"
    )
    
    # Compare answer quality metrics
    llamaindex_answer = llamaindex_result.get("answer", "")
    current_answer = current_result.get("answer", "")
    
    # Basic quality checks
    llamaindex_has_citations = "[" in llamaindex_answer and "]" in llamaindex_answer
    current_has_citations = "[" in current_answer and "]" in current_answer
    
    llamaindex_citation_count = llamaindex_result.get("citations_total", 0)
    current_citation_count = current_result.get("citations_total", 0)
    
    print(f"✅ LlamaIndex answer length: {len(llamaindex_answer)}")
    print(f"✅ Current answer length: {len(current_answer)}")
    print(f"✅ LlamaIndex has citations: {llamaindex_has_citations}")
    print(f"✅ Current has citations: {current_has_citations}")
    print(f"✅ LlamaIndex citation count: {llamaindex_citation_count}")
    print(f"✅ Current citation count: {current_citation_count}")
    
    # Both should have reasonable answers
    assert len(llamaindex_answer) > 50, "LlamaIndex answer should be substantial"
    assert len(current_answer) > 50, "Current answer should be substantial"


def test_module_imports():
    """Test that modules can be imported."""
    try:
        from agent.frameworks.llamaindex import run_llamaindex_pipeline, create_llamaindex_graph
        assert True
    except ImportError as e:
        pytest.skip(f"LlamaIndex pipeline modules not available: {e}")
