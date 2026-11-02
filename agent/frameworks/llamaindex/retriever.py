"""
LlamaIndex Retriever Integration.

This module provides LlamaIndex-based retrievers that can be used
as alternatives to the current custom hybrid retriever.
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import llama_index
    # Try importing retrievers (may vary by version)
    try:
        from llama_index.retrievers import VectorIndexRetriever
    except ImportError:
        try:
            from llama_index.core.retrievers import VectorIndexRetriever
        except ImportError:
            VectorIndexRetriever = None
    
    try:
        from llama_index.core import QueryBundle
    except ImportError:
        try:
            from llama_index import QueryBundle
        except ImportError:
            QueryBundle = None
    
    try:
        from llama_index import VectorStoreIndex
    except ImportError:
        try:
            from llama_index.core import VectorStoreIndex
        except ImportError:
            VectorStoreIndex = None
    
    LLAMAINDEX_RETRIEVER_AVAILABLE = (
        VectorIndexRetriever is not None and 
        QueryBundle is not None and
        VectorStoreIndex is not None
    )
    
    if not LLAMAINDEX_RETRIEVER_AVAILABLE:
        logger.warning("LlamaIndex retrievers not fully available")
except ImportError:
    LLAMAINDEX_RETRIEVER_AVAILABLE = False
    VectorIndexRetriever = None
    QueryBundle = None
    VectorStoreIndex = None
    logger.warning("LlamaIndex not installed")

from agent.frameworks.llamaindex.vector_store import LlamaIndexChromaStore
from agent.utils import get_bm25_index


class LlamaIndexHybridRetriever:
    """
    Hybrid retriever combining LlamaIndex vector retriever with BM25.
    
    This class provides a hybrid retrieval approach:
    - Dense retrieval: LlamaIndex VectorIndexRetriever
    - Keyword retrieval: BM25 (reusing existing implementation)
    - Results can be merged using RRF (Reciprocal Rank Fusion)
    
    Usage:
        >>> retriever = LlamaIndexHybridRetriever(
        ...     chroma_path="./chroma",
        ...     embed_model="intfloat/e5-base-v2"
        ... )
        >>> results = retriever.retrieve("machine learning", top_k=5)
    """
    
    def __init__(
        self,
        chroma_path: str = "./chroma",
        collection_name: str = "knowledge_base",
        embed_model: str = "intfloat/e5-base-v2",
        clean_dir: str = "./cache/clean"
    ):
        """
        Initialize hybrid retriever.
        
        Args:
            chroma_path: Path to ChromaDB data directory
            collection_name: Name of the ChromaDB collection
            embed_model: Embedding model name
            clean_dir: Directory for BM25 corpus
        """
        if not LLAMAINDEX_RETRIEVER_AVAILABLE:
            raise ImportError(
                "LlamaIndex retrievers not available. "
                "Install with: pip install llama-index"
            )
        
        self.chroma_path = chroma_path
        self.collection_name = collection_name
        self.embed_model = embed_model
        self.clean_dir = clean_dir
        
        # Initialize LlamaIndex store and index
        self._llamaindex_store = LlamaIndexChromaStore(
            chroma_path=chroma_path,
            collection_name=collection_name
        )
        self._index: Optional[VectorStoreIndex] = None
        self._vector_retriever: Optional[VectorIndexRetriever] = None
    
    def _get_vector_retriever(self, top_k: int = 6) -> VectorIndexRetriever:
        """Get or create vector retriever."""
        if self._vector_retriever is None or getattr(self._vector_retriever, 'similarity_top_k', None) != top_k:
            if self._index is None:
                # Get embedding model for index creation
                try:
                    from agent.utils.embeddings import get_embed_model
                    embed_model_instance = get_embed_model(self.embed_model)
                    # LlamaIndex needs embedding function, not model directly
                    # For now, use default embedding from index
                    self._index = self._llamaindex_store.get_index()
                except Exception as e:
                    logger.warning(f"Could not set embedding model, using default: {e}")
                    self._index = self._llamaindex_store.get_index()
            
            self._vector_retriever = VectorIndexRetriever(
                index=self._index,
                similarity_top_k=top_k
            )
        return self._vector_retriever
    
    def dense_retrieve(
        self,
        query: str,
        top_k: int = 6,
        query_embedding: Optional[List[float]] = None
    ) -> List[Tuple[str, Dict[str, str], float]]:
        """
        Dense retrieval using LlamaIndex VectorIndexRetriever.
        
        Args:
            query: Query text
            top_k: Number of results to return
            query_embedding: Optional pre-computed query embedding
            
        Returns:
            List of (key, doc_dict, distance) tuples
        """
        try:
            retriever = self._get_vector_retriever(top_k=top_k)
            
            # Use LlamaIndex retriever
            query_bundle = QueryBundle(query_str=query)
            nodes = retriever.retrieve(query_bundle)
            
            results: List[Tuple[str, Dict[str, str], float]] = []
            for node in nodes:
                # Extract metadata from node
                metadata = node.metadata or {}
                key = metadata.get("source_url") or metadata.get("title") or ""
                if not key:
                    continue
                
                # Get distance/score (LlamaIndex uses score, convert to distance)
                score = node.score or 0.0
                distance = 1.0 - score  # Convert similarity to distance
                
                doc_dict = {
                    "text": node.text or "",
                    "metadata": metadata
                }
                results.append((key, doc_dict, float(distance)))
            
            return results
        except Exception as exc:
            logger.error(f"LlamaIndex dense retrieval failed: {exc}")
            return []
    
    def bm25_retrieve(self, query: str, top_k: int) -> Dict[str, Dict]:
        """
        BM25 retrieval (reusing existing implementation).
        
        Args:
            query: Query text
            top_k: Number of results to return
            
        Returns:
            Dictionary mapping keys to document dicts
        """
        # Reuse existing BM25 implementation
        bm25, records = get_bm25_index(self.clean_dir)
        if bm25 is None or not records:
            return {}
        
        scores = bm25.get_scores(query.lower().split())
        paired = sorted(zip(scores, records), key=lambda x: x[0], reverse=True)
        results: Dict[str, Dict] = {}
        
        for score, record in paired[:top_k * 2]:
            meta = record.get("metadata", {})
            key = meta.get("source_url") or meta.get("title") or ""
            if not key:
                continue
            results[key] = {
                "text": record.get("text", ""),
                "metadata": meta,
                "score": float(score),
            }
        return results
    
    def retrieve(
        self,
        query: str,
        top_k: int = 6,
        query_embedding: Optional[List[float]] = None,
        use_bm25: bool = True
    ) -> Dict[str, List]:
        """
        Hybrid retrieval combining dense and BM25.
        
        Args:
            query: Query text
            top_k: Number of results to return
            query_embedding: Optional pre-computed query embedding
            use_bm25: Whether to include BM25 results
            
        Returns:
            Dictionary with "dense" and "bm25" results
        """
        dense_results = self.dense_retrieve(query, top_k=top_k, query_embedding=query_embedding)
        
        if use_bm25:
            bm25_results = self.bm25_retrieve(query, top_k=top_k)
        else:
            bm25_results = {}
        
        return {
            "dense": dense_results,
            "bm25": bm25_results
        }
