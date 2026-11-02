"""
LlamaIndex ChromaDB vector store integration.

This module provides:
1. LlamaIndexChromaStore: Direct LlamaIndex ChromaDB integration
2. LlamaIndexVectorStoreAdapter: Adapter implementing VectorStoreInterface
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    # Try importing LlamaIndex core
    import llama_index
    # Try importing ChromaDB integration (may not exist for older versions)
    try:
        from llama_index.vector_stores.chroma import ChromaVectorStore as LlamaIndexChromaVectorStore
        try:
            from llama_index import VectorStoreIndex
        except ImportError:
            # For newer versions, might be in different location
            from llama_index.core import VectorStoreIndex
        LLAMAINDEX_CHROMA_AVAILABLE = True
    except ImportError:
        # For older versions, ChromaDB might be integrated differently
        try:
            from llama_index.vector_stores import ChromaVectorStore as LlamaIndexChromaVectorStore
            try:
                from llama_index import VectorStoreIndex
            except ImportError:
                from llama_index.core import VectorStoreIndex
            LLAMAINDEX_CHROMA_AVAILABLE = True
        except ImportError:
            LLAMAINDEX_CHROMA_AVAILABLE = False
            VectorStoreIndex = None  # Type hint fallback
            logger.warning(
                "LlamaIndex ChromaDB integration not available. "
                "For 0.11.15, ChromaDB may be integrated differently. "
                "Try: pip install llama-index[vector-stores-chroma] or upgrade LlamaIndex"
            )
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False
    LLAMAINDEX_CHROMA_AVAILABLE = False
    LlamaIndexChromaVectorStore = None
    VectorStoreIndex = None
    logger.warning(
        "LlamaIndex not installed. Install with: pip install llama-index"
    )

from agent.stores.base import VectorStoreInterface
from agent.utils.vector_store import VectorStore


class LlamaIndexChromaStore:
    """
    LlamaIndex ChromaDB vector store wrapper.
    
    This class wraps LlamaIndex's ChromaVectorStore to work with
    our existing ChromaDB setup.
    
    Usage:
        >>> store = LlamaIndexChromaStore(chroma_path="./chroma")
        >>> index = store.get_index(collection_name="knowledge_base")
        >>> retriever = index.as_retriever(similarity_top_k=5)
    """
    
    def __init__(self, chroma_path: str = "./chroma", collection_name: str = "knowledge_base"):
        """
        Initialize LlamaIndex ChromaDB store.
        
        Args:
            chroma_path: Path to ChromaDB data directory
            collection_name: Name of the ChromaDB collection
        """
        if not LLAMAINDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is not installed. Install with: pip install llama-index"
            )
        
        if not LLAMAINDEX_CHROMA_AVAILABLE:
            raise ImportError(
                "LlamaIndex ChromaDB integration not available. "
                "For version 0.11.15, try: pip install llama-index[vector-stores-chroma] "
                "or upgrade to a newer version of LlamaIndex"
            )
        
        self.chroma_path = chroma_path
        self.collection_name = collection_name
        
        # Use our existing VectorStore singleton to get ChromaDB client
        self._vector_store = VectorStore(chroma_path=chroma_path)
        self._chroma_client = self._vector_store.get_client()
        self._chroma_collection = self._vector_store.get_collection(collection_name)
        
        # Create LlamaIndex ChromaVectorStore
        self._llamaindex_store = LlamaIndexChromaVectorStore(
            chroma_collection=self._chroma_collection
        )
        self._index: Optional[VectorStoreIndex] = None
    
    def get_index(self, embedding_model=None):
        """
        Get or create LlamaIndex VectorStoreIndex.
        
        Args:
            embedding_model: Optional embedding model (uses default if None)
            
        Returns:
            VectorStoreIndex instance
        """
        if self._index is None:
            self._index = VectorStoreIndex.from_vector_store(
                vector_store=self._llamaindex_store,
                embed_model=embedding_model
            )
        return self._index
    
    def get_collection(self):
        """Get underlying ChromaDB collection."""
        return self._chroma_collection


class LlamaIndexVectorStoreAdapter(VectorStoreInterface):
    """
    Adapter that implements VectorStoreInterface using LlamaIndex.
    
    This allows us to use LlamaIndex components while maintaining
    compatibility with our existing code that expects VectorStoreInterface.
    
    Usage:
        >>> adapter = LlamaIndexVectorStoreAdapter(chroma_path="./chroma")
        >>> results = adapter.query(query_embedding, top_k=5)
    """
    
    def __init__(self, chroma_path: str = "./chroma", collection_name: str = "knowledge_base"):
        """
        Initialize adapter.
        
        Args:
            chroma_path: Path to ChromaDB data directory
            collection_name: Name of the ChromaDB collection
        """
        if not LLAMAINDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is not installed. Install with: pip install llama-index"
            )
        
        if not LLAMAINDEX_CHROMA_AVAILABLE:
            raise ImportError(
                "LlamaIndex ChromaDB integration not available. "
                "For version 0.11.15, try: pip install llama-index[vector-stores-chroma] "
                "or upgrade to a newer version of LlamaIndex"
            )
        
        self.chroma_path = chroma_path
        self.collection_name = collection_name
        
        # Use our existing VectorStore singleton
        self._vector_store = VectorStore(chroma_path=chroma_path)
        self._chroma_collection = self._vector_store.get_collection(collection_name)
        
        # Create LlamaIndex store
        self._llamaindex_store = LlamaIndexChromaVectorStore(
            chroma_collection=self._chroma_collection
        )
    
    def query(
        self,
        query_embedding: List[float],
        top_k: int,
        include: Optional[List[str]] = None
    ) -> Dict:
        """
        Query vector store using LlamaIndex.
        
        Args:
            query_embedding: Query vector embedding
            top_k: Number of results to return
            include: Fields to include (not used with LlamaIndex, kept for compatibility)
            
        Returns:
            Dictionary with query results in format:
            {
                "documents": List[str],
                "metadatas": List[Dict],
                "distances": List[float],
                "ids": List[str]
            }
        """
        # Use ChromaDB collection directly for query (simpler than LlamaIndex query)
        # This maintains compatibility with existing code
        results = self._chroma_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format results to match expected interface
        # ChromaDB returns results as lists of lists (one per query)
        documents = results.get("documents", [[]])
        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])
        ids = results.get("ids", [[]])
        
        return {
            "documents": documents[0] if documents else [],
            "metadatas": metadatas[0] if metadatas else [],
            "distances": distances[0] if distances else [],
            "ids": ids[0] if ids else [],
        }
    
    def add(
        self,
        documents: List[str],
        metadatas: List[Dict],
        ids: Optional[List[str]] = None
    ) -> None:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of document texts
            metadatas: List of metadata dictionaries
            ids: Optional list of document IDs
        """
        self._chroma_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def count(self) -> int:
        """
        Get total number of documents in the store.
        
        Returns:
            Total document count
        """
        return self._chroma_collection.count()
    
    def get_collection(self, name: str = "knowledge_base"):
        """
        Get or create a collection.
        
        Args:
            name: Collection name (default: "knowledge_base")
            
        Returns:
            Collection object
        """
        if name == self.collection_name:
            return self._chroma_collection
        return self._vector_store.get_collection(name)
