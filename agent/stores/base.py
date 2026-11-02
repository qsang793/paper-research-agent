"""
Abstract interface for vector stores.

This interface allows us to:
1. Easily swap vector databases (ChromaDB → Qdrant → Pinecone)
2. Mock vector stores for testing
3. Implement different strategies (local, cloud, hybrid)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class VectorStoreInterface(ABC):
    """
    Abstract interface for vector stores.
    
    All vector store implementations should inherit from this interface
    to ensure consistent API and enable easy migration.
    
    Example:
        >>> store = ChromaVectorStore(chroma_path="./chroma")
        >>> results = store.query(query_embedding, top_k=5)
        >>> store.add(documents=["doc1", "doc2"], metadatas=[{}, {}])
    """
    
    @abstractmethod
    def query(
        self, 
        query_embedding: List[float], 
        top_k: int,
        include: Optional[List[str]] = None
    ) -> Dict:
        """
        Query vector store for similar documents.
        
        Args:
            query_embedding: Query vector embedding
            top_k: Number of results to return
            include: Fields to include in results (e.g., ["documents", "metadatas", "distances"])
            
        Returns:
            Dictionary with query results. Format depends on implementation but should include:
            - "documents": List of document texts
            - "metadatas": List of metadata dicts
            - "distances": List of distance scores
            - "embeddings": Optional list of document embeddings
        """
        pass
    
    @abstractmethod
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
            ids: Optional list of document IDs (auto-generated if not provided)
        """
        pass
    
    @abstractmethod
    def count(self) -> int:
        """
        Get total number of documents in the store.
        
        Returns:
            Total document count
        """
        pass
    
    @abstractmethod
    def get_collection(self, name: str = "knowledge_base"):
        """
        Get or create a collection (for stores that support collections).
        
        Args:
            name: Collection name
            
        Returns:
            Collection object (implementation-specific)
        """
        pass
