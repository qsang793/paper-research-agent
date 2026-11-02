# LlamaIndex Migration Plan

**Branch**: `feature/llamaindex-migration`  
**Date**: 2026-01-XX  
**Status**: 📋 Planning

## 🎯 Migration Goals

Migrate from custom LangGraph-based RAG pipeline to LlamaIndex framework while:
- ✅ Maintaining existing functionality
- ✅ Preserving performance optimizations (Phase 1-2)
- ✅ Keeping custom routing logic (Adaptive RAG)
- ✅ Enabling incremental migration (not all-at-once)

## 📊 Current Architecture

### Current Stack
- **Orchestration**: LangGraph (agentic workflow)
- **Vector Store**: ChromaDB (via VectorStoreInterface)
- **Retrieval**: Custom hybrid (Dense + BM25 + RRF)
- **Re-ranking**: Cross-encoder (custom)
- **LLM**: Multiple backends (Ollama/Gemini/OpenRouter)

### Current Flow
```
intent → route → search → retrieve → rerank → generate
         (LangGraph nodes)
```

## 🏗️ Target Architecture with LlamaIndex

### LlamaIndex Stack
- **Orchestration**: LangGraph (keep) + LlamaIndex components
- **Vector Store**: LlamaIndex ChromaDB integration
- **Retrieval**: LlamaIndex retrievers (with custom hybrid support)
- **Re-ranking**: LlamaIndex rerankers (or keep custom)
- **LLM**: LlamaIndex LLM abstraction

### Target Flow
```
intent → route → search → [LlamaIndex Retriever] → rerank → generate
         (LangGraph)      (LlamaIndex)              (Custom/LlamaIndex)
```

## 📋 Migration Strategy

### Phase 1: Setup & Dependencies (Day 1)

**Tasks**:
- [ ] Install LlamaIndex packages
  ```bash
  pip install llama-index llama-index-vector-stores-chroma
  pip install llama-index-embeddings-sentence-transformers
  pip install llama-index-llms-ollama llama-index-llms-openai
  ```
- [ ] Create `agent/frameworks/llamaindex/` module
- [ ] Create compatibility layer between current and LlamaIndex
- [ ] Update `requirements.txt` or `requirements-api.txt`

**Deliverables**:
- LlamaIndex installed and tested
- Module structure created
- Basic compatibility layer

---

### Phase 2: Vector Store Integration (Day 2)

**Tasks**:
- [ ] Create `LlamaIndexChromaStore` wrapper
  - Wrap existing `ChromaVectorStore` with LlamaIndex interface
  - Or use LlamaIndex's native ChromaDB integration
- [ ] Create `LlamaIndexVectorStore` adapter
  - Implements our `VectorStoreInterface`
  - Uses LlamaIndex under the hood
- [ ] Test vector store operations (query, add, count)

**Deliverables**:
- LlamaIndex vector store working
- Can query existing ChromaDB data
- Backward compatible with current code

---

### Phase 3: Retriever Integration (Day 3-4)

**Tasks**:
- [ ] Create `LlamaIndexHybridRetriever`
  - Combines Dense (vector) + BM25 (keyword) retrieval
  - Uses LlamaIndex's retriever components
  - Maintains RRF (Reciprocal Rank Fusion) logic
- [ ] Create `HybridRetrieverNode` for LangGraph
  - Wraps LlamaIndex retriever
  - Maintains same interface as current `retrieve_node`
- [ ] Test retrieval quality (compare with current)
- [ ] Performance benchmarking

**Deliverables**:
- Hybrid retriever working with LlamaIndex
- Same or better retrieval quality
- Performance maintained or improved

---

### Phase 4: LLM Integration (Day 4-5)

**Tasks**:
- [ ] Create `LlamaIndexLLMWrapper`
  - Supports Ollama, Gemini, OpenRouter
  - Uses LlamaIndex's LLM abstraction
- [ ] Update `generate_node` to use LlamaIndex LLM
- [ ] Test streaming responses
- [ ] Test different LLM backends

**Deliverables**:
- LLM integration working
- Streaming support maintained
- All backends tested

---

### Phase 5: Re-ranking Integration (Day 5)

**Tasks**:
- [ ] Evaluate LlamaIndex rerankers vs current cross-encoder
- [ ] Option A: Use LlamaIndex reranker
- [ ] Option B: Keep custom reranker (wrapped in LlamaIndex interface)
- [ ] Test reranking quality

**Deliverables**:
- Re-ranking working (LlamaIndex or custom)
- Quality maintained or improved

---

### Phase 6: Full Integration & Testing (Day 6-7)

**Tasks**:
- [ ] Replace `retrieve_node` with LlamaIndex version
- [ ] Update `generate_node` with LlamaIndex LLM
- [ ] End-to-end testing
- [ ] Performance comparison
- [ ] Quality comparison (RAG metrics)
- [ ] Fix any regressions

**Deliverables**:
- Full LlamaIndex integration
- All tests passing
- Performance maintained
- Quality maintained or improved

---

## 🔄 Migration Approach

### Incremental Migration (Recommended)

**Strategy**: Migrate one component at a time, test, then move to next.

1. **Week 1**: Vector Store + Retriever
2. **Week 2**: LLM + Re-ranking
3. **Week 3**: Full integration + testing

### Parallel Implementation

Keep both implementations during migration:
- `agent/nodes/retrieve.py` (current)
- `agent/nodes/retrieve_llamaindex.py` (new)
- Switch via feature flag or config

---

## 📦 LlamaIndex Components to Use

### 1. Vector Store
```python
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index import VectorStoreIndex

# Create index from existing ChromaDB
vector_store = ChromaVectorStore(chroma_collection=existing_collection)
index = VectorStoreIndex.from_vector_store(vector_store)
```

### 2. Retriever
```python
from llama_index.retrievers import VectorIndexRetriever
from llama_index.retrievers import BM25Retriever
from llama_index.retrievers import QueryFusionRetriever

# Hybrid retriever
vector_retriever = VectorIndexRetriever(index=index, similarity_top_k=6)
bm25_retriever = BM25Retriever.from_defaults(index=index, similarity_top_k=6)
hybrid_retriever = QueryFusionRetriever([vector_retriever, bm25_retriever])
```

### 3. LLM
```python
from llama_index.llms.ollama import Ollama
from llama_index.llms.openai import OpenAI
from llama_index.llms.gemini import Gemini

llm = Ollama(model="llama2", request_timeout=60.0)
```

### 4. Query Engine
```python
from llama_index.query_engine import RetrieverQueryEngine

query_engine = RetrieverQueryEngine.from_args(
    retriever=hybrid_retriever,
    llm=llm
)
```

---

## 🔍 Key Considerations

### What to Keep
- ✅ LangGraph orchestration (agentic workflow)
- ✅ Custom routing logic (Adaptive RAG)
- ✅ RRF merging logic (if LlamaIndex doesn't have equivalent)
- ✅ Performance optimizations (caching, parallelization)

### What to Migrate
- 🔄 Vector store operations → LlamaIndex
- 🔄 Retrieval logic → LlamaIndex retrievers
- 🔄 LLM calls → LlamaIndex LLM abstraction
- 🔄 Re-ranking → LlamaIndex rerankers (optional)

### What to Evaluate
- ⚠️ Hybrid retrieval: LlamaIndex vs custom RRF
- ⚠️ Re-ranking: LlamaIndex vs custom cross-encoder
- ⚠️ Performance: LlamaIndex overhead vs benefits
- ⚠️ Quality: Retrieval and generation quality

---

## 📊 Success Criteria

### Functional
- [ ] All existing features work
- [ ] Retrieval quality ≥ current
- [ ] Generation quality ≥ current
- [ ] All LLM backends supported

### Performance
- [ ] Latency ≤ current (or within 10%)
- [ ] Memory usage acceptable
- [ ] No significant regressions

### Code Quality
- [ ] Clean integration with LangGraph
- [ ] Maintainable code
- [ ] Good documentation
- [ ] Tests passing

---

## 🧪 Testing Plan

### Unit Tests
- [ ] Vector store operations
- [ ] Retriever operations
- [ ] LLM integration
- [ ] Re-ranking

### Integration Tests
- [ ] Full pipeline end-to-end
- [ ] Compare results with current implementation
- [ ] Performance benchmarks

### Quality Tests
- [ ] RAG metrics (Faithfulness, Answer Relevance)
- [ ] Retrieval precision/recall
- [ ] Generation quality

---

## 📝 Implementation Checklist

### Setup
- [ ] Install LlamaIndex
- [ ] Create module structure
- [ ] Create compatibility layer

### Vector Store
- [ ] Integrate ChromaDB with LlamaIndex
- [ ] Test query operations
- [ ] Test add operations

### Retriever
- [ ] Create hybrid retriever
- [ ] Integrate with LangGraph
- [ ] Test retrieval quality

### LLM
- [ ] Integrate LLM backends
- [ ] Test streaming
- [ ] Test all backends

### Re-ranking
- [ ] Evaluate rerankers
- [ ] Integrate chosen reranker
- [ ] Test quality

### Integration
- [ ] Full pipeline integration
- [ ] End-to-end testing
- [ ] Performance comparison
- [ ] Quality comparison

### Documentation
- [ ] Update architecture docs
- [ ] Update API docs
- [ ] Migration guide
- [ ] Performance report

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install llama-index llama-index-vector-stores-chroma
pip install llama-index-embeddings-sentence-transformers
pip install llama-index-llms-ollama
```

### 2. Create First Integration
```python
# agent/frameworks/llamaindex/vector_store.py
from llama_index.vector_stores.chroma import ChromaVectorStore
from agent.stores.base import VectorStoreInterface

class LlamaIndexChromaStore(VectorStoreInterface):
    """LlamaIndex wrapper for ChromaDB."""
    # Implementation
```

### 3. Test Integration
```python
# Test that it works with existing data
store = LlamaIndexChromaStore(chroma_path="./chroma")
results = store.query(query_embedding, top_k=5)
```

---

## 📚 Resources

- [LlamaIndex Documentation](https://docs.llamaindex.ai/)
- [LlamaIndex ChromaDB Integration](https://docs.llamaindex.ai/en/stable/module_guides/storing/vector_stores/)
- [LlamaIndex Retrievers](https://docs.llamaindex.ai/en/stable/module_guides/deploying/query_engine/)
- [Hybrid Retrieval Guide](https://docs.llamaindex.ai/en/stable/examples/retrievers/hybrid_retriever.html)

---

## ⚠️ Risks & Mitigation

### Risk 1: Performance Regression
- **Mitigation**: Benchmark at each step, compare with current
- **Rollback**: Keep current implementation as fallback

### Risk 2: Quality Regression
- **Mitigation**: Test with same queries, compare metrics
- **Rollback**: Feature flag to switch back

### Risk 3: Breaking Changes
- **Mitigation**: Incremental migration, test each component
- **Rollback**: Git branch, can revert easily

---

## 📅 Timeline

**Week 1**: Setup + Vector Store + Retriever  
**Week 2**: LLM + Re-ranking  
**Week 3**: Full Integration + Testing

**Total**: ~3 weeks for complete migration

---

**Next Steps**: Start with Phase 1 (Setup & Dependencies)
