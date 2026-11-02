"""
ChromaDB implementation of VectorStoreInterface.

Wraps ChromaDB with the standard interface to enable easy migration
and testing.
"""

from typing import Dict, List, Optional

from agent.stores.base import VectorStoreInterface
from agent.utils.vector_store import VectorStore


class ChromaVectorStore(VectorStoreInterface):
    """
    ChromaDB implementation of VectorStoreInterface.

    Uses the singleton VectorStore manager internally to ensure
    connection reuse and consistency.

    Example:
        >>> store = ChromaVectorStore(chroma_path="./chroma")
        >>> results = store.query(query_embedding, top_k=5)
        >>> store.add(documents=["doc1"], metadatas=[{}])
    """

    def __init__(self, chroma_path: str = "./chroma", collection_name: str = "knowledge_base"):
        """
        Initialize ChromaDB vector store.

        Args:
            chroma_path: Path to ChromaDB data directory
            collection_name: Name of the collection to use
        """
        self._vector_store = VectorStore(chroma_path)
        self._collection_name = collection_name
        self._chroma_path = chroma_path

    def query(
        self,
        query_embedding: List[float],
        top_k: int,
        include: Optional[List[str]] = None
    ) -> Dict:
        """
        Query ChromaDB collection for similar documents.

        Args:
            query_embedding: Query vector embedding
            top_k: Number of results to return
            include: Fields to include (default: ["documents", "metadatas", "distances"])

        Returns:
            Dictionary with ChromaDB query results
        """
        collection = self.get_collection()
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=include or ["documents", "metadatas", "distances"]
        )

    def add(
        self,
        documents: List[str],
        metadatas: List[Dict],
        ids: Optional[List[str]] = None
    ) -> None:
        """
        Add documents to ChromaDB collection.

        Args:
            documents: List of document texts
            metadatas: List of metadata dictionaries
            ids: Optional list of document IDs
        """
        collection = self.get_collection()
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def count(self) -> int:
        """
        Get total document count in collection.

        Returns:
            Number of documents in collection
        """
        collection = self.get_collection()
        return collection.count()

    def get_collection(
        self,
        name: Optional[str] = None,
        *,
        embedding_function=None,
        metadata: Optional[dict] = None,
    ):
        """
        Get or create ChromaDB collection.

        Args:
            name: Collection name (uses default if not provided)

        Returns:
            ChromaDB Collection instance
        """
        collection_name = name or self._collection_name
        return self._vector_store.get_collection(
            collection_name,
            embedding_function=embedding_function,
            metadata=metadata,
        )

    def delete_collection(self, name: Optional[str] = None) -> None:
        """Delete a collection through the shared ChromaDB client."""
        collection_name = name or self._collection_name
        self._vector_store.delete_collection(collection_name)
