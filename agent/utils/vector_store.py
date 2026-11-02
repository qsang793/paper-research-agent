"""
Singleton vector store manager for ChromaDB.

Provides a single connection pool to ChromaDB to avoid creating
multiple clients for each query, reducing connection overhead.
"""

import logging
from typing import Optional
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Singleton vector store manager for ChromaDB.

    Ensures only one ChromaDB client instance exists per chroma_path,
    reusing connections across all nodes (route, retrieve, query_router).

    Usage:
        >>> store = VectorStore(chroma_path="./chroma")
        >>> collection = store.get_collection("knowledge_base")
        >>> results = collection.query(...)
    """
    _instances: dict[str, 'VectorStore'] = {}

    def __new__(cls, chroma_path: str = "./chroma"):
        """
        Create or return existing VectorStore instance for given path.

        Args:
            chroma_path: Path to ChromaDB data directory

        Returns:
            VectorStore instance (singleton per path)
        """
        if chroma_path not in cls._instances:
            instance = super().__new__(cls)
            # Use instance attributes (not class attributes) to avoid confusion
            instance._chroma_path = chroma_path
            instance._client: Optional[chromadb.PersistentClient] = None
            cls._instances[chroma_path] = instance
        return cls._instances[chroma_path]

    def _ensure_client(self):
        """Lazy initialization of ChromaDB client."""
        if self._client is None:
            try:
                self._client = chromadb.PersistentClient(
                    path=self._chroma_path,
                    settings=Settings(anonymized_telemetry=False)
                )
                logger.debug(f"Initialized ChromaDB client for path: {self._chroma_path}")
            except Exception as exc:
                logger.error(f"Failed to initialize ChromaDB client: {exc}")
                raise

    def get_collection(
        self,
        name: str = "knowledge_base",
        max_retries: int = 3,
        *,
        embedding_function=None,
        metadata: Optional[dict] = None,
    ):
        """
        Get or create ChromaDB collection with retry logic.

        Args:
            name: Collection name (default: "knowledge_base")
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            ChromaDB Collection instance

        Raises:
            RuntimeError: If connection fails after all retries
        """
        self._ensure_client()

        last_exception = None
        for attempt in range(max_retries):
            try:
                kwargs = {}
                if embedding_function is not None:
                    kwargs["embedding_function"] = embedding_function
                if metadata is not None:
                    kwargs["metadata"] = metadata
                return self._client.get_or_create_collection(name, **kwargs)
            except Exception as exc:
                last_exception = exc
                logger.warning(
                    f"Failed to get collection '{name}' (attempt {attempt + 1}/{max_retries}): {exc}"
                )
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1 * (attempt + 1))  # Linear backoff: 1s, 2s, 3s

        raise RuntimeError(
            f"Failed to get collection '{name}' after {max_retries} attempts: {last_exception}"
        )

    def delete_collection(self, name: str) -> None:
        """Delete a ChromaDB collection by name."""
        self._ensure_client()
        self._client.delete_collection(name)

    def get_client(self):
        """
        Get ChromaDB client instance.

        Returns:
            ChromaDB PersistentClient instance
        """
        self._ensure_client()
        return self._client

    @classmethod
    def reset(cls, chroma_path: Optional[str] = None):
        """
        Reset singleton instance(s) - useful for testing.

        Args:
            chroma_path: Specific path to reset, or None to reset all
        """
        if chroma_path:
            if chroma_path in cls._instances:
                del cls._instances[chroma_path]
        else:
            cls._instances.clear()
