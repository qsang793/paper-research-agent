# LlamaIndex Integration

This module provides LlamaIndex-based implementations that can be used as alternatives or enhancements to the current custom RAG pipeline.

## Installation

Install required packages:

```bash
pip install llama-index llama-index-vector-stores-chroma
pip install llama-index-embeddings-sentence-transformers
pip install llama-index-llms-ollama llama-index-llms-openai
```

Or use the utility function:

```python
from agent.frameworks.llamaindex.utils import get_llamaindex_packages
packages = get_llamaindex_packages()
# Install with: pip install " ".join(packages)
```

## Components

### 1. Vector Store Integration

#### LlamaIndexChromaStore

Direct LlamaIndex ChromaDB integration:

```python
from agent.frameworks.llamaindex import LlamaIndexChromaStore

store = LlamaIndexChromaStore(chroma_path="./chroma")
index = store.get_index()
retriever = index.as_retriever(similarity_top_k=5)
```

#### LlamaIndexVectorStoreAdapter

Adapter that implements `VectorStoreInterface`:

```python
from agent.frameworks.llamaindex import LlamaIndexVectorStoreAdapter

adapter = LlamaIndexVectorStoreAdapter(chroma_path="./chroma")
results = adapter.query(query_embedding, top_k=5)
```

This adapter allows you to use LlamaIndex components while maintaining compatibility with existing code.

## Migration Strategy

### Phase 1: Setup ✅
- Install LlamaIndex packages
- Create module structure
- Create compatibility layer

### Phase 2: Vector Store (Next)
- Test LlamaIndex ChromaDB integration
- Compare with current implementation
- Benchmark performance

### Phase 3: Retriever (Future)
- Create hybrid retriever with LlamaIndex
- Integrate with LangGraph nodes
- Test retrieval quality

## Testing

Check if LlamaIndex is installed:

```python
from agent.frameworks.llamaindex.utils import check_llamaindex_installed

if check_llamaindex_installed():
    print("LlamaIndex is available")
    version = get_llamaindex_version()
    print(f"Version: {version}")
```

## Notes

- This module is **optional** - the current custom implementation works well
- LlamaIndex can be used incrementally for specific features
- Compatibility layer ensures no breaking changes
- Performance should be benchmarked before full migration
