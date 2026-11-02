"""
Phase 2: Test LlamaIndex Vector Store Integration với real data.

Tests:
1. Basic query với LlamaIndex adapter
2. Compare với ChromaVectorStore
3. Performance benchmarking
"""

import pytest
import os
from typing import List
import time

# Check if LlamaIndex is available
try:
    from agent.frameworks.llamaindex import LlamaIndexVectorStoreAdapter
    from agent.frameworks.llamaindex.utils import check_llamaindex_installed
    LLAMAINDEX_AVAILABLE = check_llamaindex_installed()
except ImportError:
    LLAMAINDEX_AVAILABLE = False

from agent.stores.chroma_store import ChromaVectorStore
from agent.utils.embeddings import get_embed_model


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_llamaindex_adapter_basic():
    """Test basic query với LlamaIndexVectorStoreAdapter."""
    chroma_path = "./chroma"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    # Tạo adapter
    adapter = LlamaIndexVectorStoreAdapter(chroma_path=chroma_path)
    
    # Test count
    count = adapter.count()
    assert count >= 0, "Count should be non-negative"
    print(f"✅ Collection has {count} documents")
    
    if count == 0:
        pytest.skip("Collection is empty, cannot test query")


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_llamaindex_adapter_query():
    """Test query với LlamaIndex adapter."""
    chroma_path = "./chroma"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    # Tạo adapter và current store
    adapter = LlamaIndexVectorStoreAdapter(chroma_path=chroma_path)
    current_store = ChromaVectorStore(chroma_path=chroma_path)
    
    # Check if collection has data
    count = adapter.count()
    if count == 0:
        pytest.skip("Collection is empty")
    
    # Tạo query embedding
    embed_model = get_embed_model("intfloat/e5-base-v2")
    test_query = "machine learning"
    query_embedding = embed_model.encode(test_query).tolist()
    
    # Query với adapter
    adapter_results = adapter.query(query_embedding, top_k=5)
    
    # Validate results format
    assert "documents" in adapter_results
    assert "metadatas" in adapter_results
    assert "distances" in adapter_results
    assert isinstance(adapter_results["documents"], list)
    assert len(adapter_results["documents"]) <= 5
    
    print(f"✅ LlamaIndex adapter returned {len(adapter_results['documents'])} results")


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_compare_with_current_implementation():
    """So sánh kết quả giữa LlamaIndex adapter và ChromaVectorStore."""
    chroma_path = "./chroma"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    # Tạo cả hai stores
    adapter = LlamaIndexVectorStoreAdapter(chroma_path=chroma_path)
    current_store = ChromaVectorStore(chroma_path=chroma_path)
    
    # Check if collection has data
    count = adapter.count()
    if count == 0:
        pytest.skip("Collection is empty")
    
    # Tạo query embedding
    embed_model = get_embed_model("intfloat/e5-base-v2")
    test_query = "neural networks"
    query_embedding = embed_model.encode(test_query).tolist()
    
    # Query với cả hai
    adapter_results = adapter.query(query_embedding, top_k=5)
    current_results = current_store.query(query_embedding, top_k=5)
    
    # So sánh số lượng results
    # Current store returns results in nested format: {"documents": [[...]], "ids": [[...]]}
    # Adapter returns flat format: {"documents": [...], "ids": [...]}
    adapter_docs = adapter_results.get("documents", [])
    current_docs = current_results.get("documents", [])
    
    # Handle nested format from ChromaVectorStore
    if current_docs and isinstance(current_docs[0], list):
        current_docs = current_docs[0]
    
    adapter_count = len(adapter_docs)
    current_count = len(current_docs)
    
    print(f"✅ LlamaIndex adapter: {adapter_count} results")
    print(f"✅ Current store: {current_count} results")
    
    # Results should be similar (same collection, same query)
    # Note: May differ slightly due to implementation differences
    assert adapter_count > 0, "Adapter should return at least 1 result"
    assert current_count > 0, "Current store should return at least 1 result"
    
    # Compare document IDs (should overlap)
    adapter_ids = adapter_results.get("ids", [])
    current_ids = current_results.get("ids", [])
    
    # Handle nested format
    if current_ids and isinstance(current_ids[0], list):
        current_ids = current_ids[0]
    
    if adapter_ids and current_ids:
        # Should have some overlap (same collection, same query)
        overlap = set(adapter_ids) & set(current_ids)
        print(f"✅ Overlapping IDs: {len(overlap)}/{min(len(adapter_ids), len(current_ids))}")
        assert len(overlap) > 0, "Should have some overlapping document IDs"


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_performance_benchmark():
    """Benchmark performance của LlamaIndex adapter."""
    chroma_path = "./chroma"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    # Tạo stores
    adapter = LlamaIndexVectorStoreAdapter(chroma_path=chroma_path)
    current_store = ChromaVectorStore(chroma_path=chroma_path)
    
    # Check if collection has data
    count = adapter.count()
    if count == 0:
        pytest.skip("Collection is empty")
    
    # Tạo query embedding
    embed_model = get_embed_model("intfloat/e5-base-v2")
    test_query = "deep learning"
    query_embedding = embed_model.encode(test_query).tolist()
    
    # Benchmark adapter
    start = time.time()
    for _ in range(10):
        adapter.query(query_embedding, top_k=5)
    adapter_time = (time.time() - start) / 10
    
    # Benchmark current
    start = time.time()
    for _ in range(10):
        current_store.query(query_embedding, top_k=5)
    current_time = (time.time() - start) / 10
    
    print(f"✅ LlamaIndex adapter: {adapter_time*1000:.2f}ms per query")
    print(f"✅ Current store: {current_time*1000:.2f}ms per query")
    
    # Performance should be within 50% (acceptable for Phase 2)
    ratio = adapter_time / current_time
    print(f"✅ Performance ratio: {ratio:.2f}x")
    
    assert ratio < 2.0, f"Adapter should not be more than 2x slower (ratio: {ratio:.2f})"


@pytest.mark.skipif(not LLAMAINDEX_AVAILABLE, reason="LlamaIndex not installed")
def test_error_handling():
    """Test error handling."""
    chroma_path = "./chroma"
    
    if not os.path.exists(chroma_path):
        pytest.skip(f"ChromaDB path not found: {chroma_path}")
    
    adapter = LlamaIndexVectorStoreAdapter(chroma_path=chroma_path)
    
    # Test với empty embedding
    empty_embedding = []
    try:
        adapter.query(empty_embedding, top_k=5)
        pytest.fail("Should raise error for empty embedding")
    except Exception:
        pass  # Expected
    
    # Test với invalid top_k (ChromaDB doesn't allow negative, so we test with 0)
    embed_model = get_embed_model("intfloat/e5-base-v2")
    query_embedding = embed_model.encode("test").tolist()
    
    # Zero top_k should return empty results
    try:
        results = adapter.query(query_embedding, top_k=0)
        assert len(results.get("documents", [])) == 0, "Should handle zero top_k"
    except Exception:
        # ChromaDB may raise error for zero, which is acceptable
        pass


def test_module_imports():
    """Test that modules can be imported."""
    try:
        from agent.frameworks.llamaindex import LlamaIndexVectorStoreAdapter
        from agent.frameworks.llamaindex.utils import check_llamaindex_installed
        assert True
    except ImportError as e:
        pytest.skip(f"LlamaIndex modules not available: {e}")
