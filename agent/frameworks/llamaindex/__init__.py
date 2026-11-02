"""
LlamaIndex integration module.

This module provides LlamaIndex-based implementations that can be used
as alternatives or enhancements to the current custom RAG pipeline.

Components:
- VectorStore: LlamaIndex ChromaDB integration
- Retriever: Hybrid retriever with LlamaIndex
- LLM: LlamaIndex LLM abstraction
- Compatibility: Adapters to work with existing code
"""

__all__ = [
    "LlamaIndexChromaStore",
    "LlamaIndexVectorStoreAdapter",
    "LlamaIndexHybridRetriever",
    "LlamaIndexLLMWrapper",
    "LlamaIndexReranker",
    "retrieve_node_llamaindex",
    "generate_node_llamaindex",
    "rerank_node_llamaindex",
    "create_llamaindex_graph",
    "run_llamaindex_pipeline",
    "get_llamaindex_packages",
    "check_llamaindex_installed",
]

# Lazy imports to avoid errors if LlamaIndex is not installed
def _lazy_import():
    """Lazy import LlamaIndex components."""
    from agent.frameworks.llamaindex.vector_store import (
        LlamaIndexChromaStore,
        LlamaIndexVectorStoreAdapter,
    )
    from agent.frameworks.llamaindex.retriever import LlamaIndexHybridRetriever
    from agent.frameworks.llamaindex.llm import LlamaIndexLLMWrapper
    from agent.frameworks.llamaindex.reranker import LlamaIndexReranker
    from agent.frameworks.llamaindex.retrieve_node import retrieve_node_llamaindex
    from agent.frameworks.llamaindex.generate_node import generate_node_llamaindex
    from agent.frameworks.llamaindex.rerank_node import rerank_node_llamaindex
    from agent.frameworks.llamaindex.graph import create_llamaindex_graph
    from agent.frameworks.llamaindex.pipeline import run_llamaindex_pipeline
    from agent.frameworks.llamaindex.utils import get_llamaindex_packages, check_llamaindex_installed
    return {
        "LlamaIndexChromaStore": LlamaIndexChromaStore,
        "LlamaIndexVectorStoreAdapter": LlamaIndexVectorStoreAdapter,
        "LlamaIndexHybridRetriever": LlamaIndexHybridRetriever,
        "LlamaIndexLLMWrapper": LlamaIndexLLMWrapper,
        "LlamaIndexReranker": LlamaIndexReranker,
        "retrieve_node_llamaindex": retrieve_node_llamaindex,
        "generate_node_llamaindex": generate_node_llamaindex,
        "rerank_node_llamaindex": rerank_node_llamaindex,
        "create_llamaindex_graph": create_llamaindex_graph,
        "run_llamaindex_pipeline": run_llamaindex_pipeline,
        "get_llamaindex_packages": get_llamaindex_packages,
        "check_llamaindex_installed": check_llamaindex_installed,
    }

# Always available (no import needed)
from agent.frameworks.llamaindex.utils import get_llamaindex_packages, check_llamaindex_installed

# Lazy load other components
def __getattr__(name):
    """Lazy load LlamaIndex components."""
    if name in ["LlamaIndexChromaStore", "LlamaIndexVectorStoreAdapter", "LlamaIndexHybridRetriever", "LlamaIndexLLMWrapper", "LlamaIndexReranker", "retrieve_node_llamaindex", "generate_node_llamaindex", "rerank_node_llamaindex", "create_llamaindex_graph", "run_llamaindex_pipeline"]:
        components = _lazy_import()
        return components[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
