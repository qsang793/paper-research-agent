"""
Vector store abstraction layer.

Provides interfaces and implementations for different vector databases
(ChromaDB, Qdrant, Pinecone, etc.) to enable easy migration and testing.
"""

from agent.stores.base import VectorStoreInterface
from agent.stores.chroma_store import ChromaVectorStore

__all__ = [
    "VectorStoreInterface",
    "ChromaVectorStore",
]
