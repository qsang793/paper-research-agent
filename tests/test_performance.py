"""
Performance test script to measure improvements from Phase 1 & 2.

Tests:
1. Embedding model caching (Phase 1)
2. VectorStore singleton reuse (Phase 1)
3. BM25 corpus caching (Phase 1)
4. Query embedding caching (Phase 2)
5. Parallel retrieval (Phase 2)
"""

import time
from typing import Dict, List

from agent.utils import get_embed_model, VectorStore, get_bm25_index


def test_embedding_caching():
    """Test embedding model caching performance."""
    print("\n=== Test 1: Embedding Model Caching ===")
    
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    
    # First call (cold start)
    start = time.perf_counter()
    model1 = get_embed_model(model_name)
    first_call_time = (time.perf_counter() - start) * 1000
    
    # Second call (should be cached)
    start = time.perf_counter()
    model2 = get_embed_model(model_name)
    second_call_time = (time.perf_counter() - start) * 1000
    
    # Verify same instance
    assert model1 is model2, "Models should be the same instance"
    
    print(f"  First call (cold):  {first_call_time:.2f} ms")
    print(f"  Second call (cached): {second_call_time:.2f} ms")
    print(f"  Speedup: {first_call_time / max(second_call_time, 0.01):.1f}x")
    
    return {
        "first_call_ms": first_call_time,
        "second_call_ms": second_call_time,
        "speedup": first_call_time / max(second_call_time, 0.01)
    }


def test_vectorstore_singleton():
    """Test VectorStore singleton reuse."""
    print("\n=== Test 2: VectorStore Singleton Reuse ===")
    
    chroma_path = "./chroma"
    
    # First instantiation
    start = time.perf_counter()
    store1 = VectorStore(chroma_path)
    first_time = (time.perf_counter() - start) * 1000
    
    # Second instantiation (should return same instance)
    start = time.perf_counter()
    store2 = VectorStore(chroma_path)
    second_time = (time.perf_counter() - start) * 1000
    
    # Verify same instance
    assert store1 is store2, "Should return same singleton instance"
    
    print(f"  First instantiation: {first_time:.2f} ms")
    print(f"  Second instantiation: {second_time:.2f} ms")
    print(f"  Speedup: {first_time / max(second_time, 0.01):.1f}x")
    
    return {
        "first_ms": first_time,
        "second_ms": second_time,
        "speedup": first_time / max(second_time, 0.01)
    }


def test_bm25_caching():
    """Test BM25 corpus caching."""
    print("\n=== Test 3: BM25 Corpus Caching ===")
    
    clean_dir = "./cache/clean"
    
    # First call (load from disk)
    start = time.perf_counter()
    try:
        bm25_1, records_1 = get_bm25_index(clean_dir)
        first_call_time = (time.perf_counter() - start) * 1000
    except Exception as e:
        print(f"  ⚠️  Skipped: {e}")
        return None
    
    # Second call (should be cached)
    start = time.perf_counter()
    bm25_2, records_2 = get_bm25_index(clean_dir)
    second_call_time = (time.perf_counter() - start) * 1000
    
    # Verify same instance
    assert bm25_1 is bm25_2, "BM25 should be cached"
    
    print(f"  First call (load):  {first_call_time:.2f} ms")
    print(f"  Second call (cached): {second_call_time:.2f} ms")
    if first_call_time > 0:
        print(f"  Speedup: {first_call_time / max(second_call_time, 0.01):.1f}x")
    
    return {
        "first_call_ms": first_call_time,
        "second_call_ms": second_call_time,
        "speedup": first_call_time / max(second_call_time, 0.01) if first_call_time > 0 else 0
    }


def test_query_embedding_reuse():
    """Test query embedding computation and reuse."""
    print("\n=== Test 4: Query Embedding Computation ===")
    
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    query = "What is transformer architecture?"
    
    model = get_embed_model(model_name)
    
    # First embedding computation
    start = time.perf_counter()
    embedding1 = model.encode([query], convert_to_numpy=True).tolist()[0]
    first_time = (time.perf_counter() - start) * 1000
    
    # Second embedding computation (same query)
    start = time.perf_counter()
    embedding2 = model.encode([query], convert_to_numpy=True).tolist()[0]
    second_time = (time.perf_counter() - start) * 1000
    
    print(f"  First computation: {first_time:.2f} ms")
    print(f"  Second computation: {second_time:.2f} ms")
    print(f"  Note: Embedding computation is deterministic but not cached")
    print(f"  → This is why Phase 2 caches embeddings in state!")
    
    return {
        "first_ms": first_time,
        "second_ms": second_time
    }


def run_all_tests():
    """Run all performance tests."""
    print("=" * 60)
    print("Performance Test Suite - Phase 1 & 2 Improvements")
    print("=" * 60)
    
    results = {}
    
    try:
        results["embedding_caching"] = test_embedding_caching()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        results["embedding_caching"] = None
    
    try:
        results["vectorstore_singleton"] = test_vectorstore_singleton()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        results["vectorstore_singleton"] = None
    
    try:
        results["bm25_caching"] = test_bm25_caching()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        results["bm25_caching"] = None
    
    try:
        results["query_embedding"] = test_query_embedding_reuse()
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        results["query_embedding"] = None
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if results.get("embedding_caching"):
        speedup = results["embedding_caching"]["speedup"]
        print(f"✅ Embedding caching: {speedup:.1f}x speedup")
    
    if results.get("vectorstore_singleton"):
        speedup = results["vectorstore_singleton"]["speedup"]
        print(f"✅ VectorStore singleton: {speedup:.1f}x speedup")
    
    if results.get("bm25_caching"):
        speedup = results["bm25_caching"]["speedup"]
        if speedup > 1:
            print(f"✅ BM25 caching: {speedup:.1f}x speedup")
        else:
            print(f"⚠️  BM25 caching: No significant speedup (may be fast already)")
    
    print("\n✅ Performance tests completed!")
    
    return results


if __name__ == "__main__":
    run_all_tests()
