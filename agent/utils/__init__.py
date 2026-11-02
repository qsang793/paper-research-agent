"""
Shared utilities for agent nodes.

Provides:
- Cached embedding models (embeddings.py)
- Singleton vector store manager (vector_store.py)
- Cached BM25 indexes (bm25_cache.py)
"""

from agent.utils.embeddings import (
    get_embed_model,
    clear_embed_cache,
    embed_query,
    embed_with_prefix,
)
from agent.utils.vector_store import VectorStore
from agent.utils.bm25_cache import get_bm25_index, clear_bm25_cache

__all__ = [
    "get_embed_model",
    "clear_embed_cache",
    "embed_query",
    "embed_with_prefix",
    "VectorStore",
    "get_bm25_index",
    "clear_bm25_cache",
]
