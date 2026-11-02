"""
LlamaIndex Reranker Integration.

This module provides LlamaIndex-based rerankers that can be used
as alternatives to the current custom cross-encoder reranker.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Try importing LlamaIndex rerankers
try:
    try:
        from llama_index.core.postprocessor import LLMRerank, SimilarityPostprocessor
    except ImportError:
        try:
            from llama_index.postprocessor import LLMRerank, SimilarityPostprocessor
        except ImportError:
            LLMRerank = None
            SimilarityPostprocessor = None
    
    try:
        from llama_index.postprocessor.rankgpt_rerank import RankGPTRerank
    except ImportError:
        try:
            from llama_index.core.postprocessor.rankgpt_rerank import RankGPTRerank
        except ImportError:
            RankGPTRerank = None
    
    LLAMAINDEX_RERANKER_AVAILABLE = (
        LLMRerank is not None or
        SimilarityPostprocessor is not None
    )
    
    if not LLAMAINDEX_RERANKER_AVAILABLE:
        logger.warning("LlamaIndex rerankers not fully available")
except ImportError:
    LLAMAINDEX_RERANKER_AVAILABLE = False
    LLMRerank = None
    SimilarityPostprocessor = None
    RankGPTRerank = None
    logger.warning("LlamaIndex not installed")

# Import current reranker for comparison
# Note: _rerank_snippets is not exported, so we'll use rerank_node logic
# or create a wrapper function


class LlamaIndexReranker:
    """
    Reranker wrapper that can use LlamaIndex rerankers or fallback to cross-encoder.
    
    Supports:
    - LlamaIndex LLMRerank (LLM-based reranking)
    - LlamaIndex SimilarityPostprocessor (similarity-based)
    - Fallback to current cross-encoder implementation
    
    Usage:
        >>> reranker = LlamaIndexReranker(mode="llm", top_n=5)
        >>> reranked = reranker.rerank(query, snippets)
    """
    
    def __init__(
        self,
        mode: str = "cross_encoder",  # "llm", "similarity", "cross_encoder"
        top_n: int = 6,
        threshold: float = 0.3,
        score_drop: float = 0.3,
        llm=None  # Optional LLM for LLMRerank
    ):
        """
        Initialize reranker.
        
        Args:
            mode: Reranking mode ("llm", "similarity", "cross_encoder")
            top_n: Number of results to return
            threshold: Minimum score threshold (for cross-encoder)
            score_drop: Max score drop for dynamic cutoff (for cross-encoder)
            llm: Optional LLM instance for LLMRerank mode
        """
        self.mode = mode.strip().lower()
        self.top_n = top_n
        self.threshold = threshold
        self.score_drop = score_drop
        self._llm = llm
        self._reranker = None
        
        # Initialize reranker based on mode
        if self.mode == "llm":
            if not LLAMAINDEX_RERANKER_AVAILABLE or LLMRerank is None:
                logger.warning("LLMRerank not available, falling back to cross-encoder")
                self.mode = "cross_encoder"
            elif self._llm is None:
                logger.warning("LLM not provided for LLMRerank, falling back to cross-encoder")
                self.mode = "cross_encoder"
            else:
                self._reranker = LLMRerank(top_n=top_n, llm=self._llm)
        elif self.mode == "similarity":
            if not LLAMAINDEX_RERANKER_AVAILABLE or SimilarityPostprocessor is None:
                logger.warning("SimilarityPostprocessor not available, falling back to cross-encoder")
                self.mode = "cross_encoder"
            else:
                self._reranker = SimilarityPostprocessor(similarity_cutoff=threshold)
        # cross_encoder mode uses current implementation (no initialization needed)
    
    def rerank(
        self,
        query: str,
        snippets: List[Dict],
    ) -> List[Dict]:
        """
        Re-rank snippets based on query relevance.
        
        Args:
            query: User query
            snippets: List of snippets to rerank
            
        Returns:
            Re-ranked and filtered snippets
        """
        if not snippets:
            return []
        
        # Use cross-encoder (current implementation) as default/fallback
        if self.mode == "cross_encoder":
            # Import here to avoid circular dependency
            from agent.nodes.rerank import _rerank_snippets
            return _rerank_snippets(
                query,
                snippets,
                top_k=self.top_n,
                threshold=self.threshold,
                score_drop=self.score_drop
            )
        
        # Use LlamaIndex rerankers
        if self.mode == "llm" and self._reranker is not None:
            try:
                # Convert snippets to LlamaIndex Node format
                from llama_index.core.schema import NodeWithScore, TextNode
                
                nodes = []
                for snippet in snippets:
                    text = snippet.get("text", "")
                    metadata = snippet.get("metadata", {})
                    node = TextNode(
                        text=text,
                        metadata=metadata
                    )
                    # Use existing score if available
                    score = snippet.get("rerank_score") or snippet.get("score_dense") or 0.0
                    nodes.append(NodeWithScore(node=node, score=score))
                
                # Create query bundle
                from llama_index.core import QueryBundle
                query_bundle = QueryBundle(query_str=query)
                
                # Rerank
                reranked_nodes = self._reranker.postprocess_nodes(
                    nodes,
                    query_bundle=query_bundle
                )
                
                # Convert back to snippet format
                reranked_snippets = []
                for node_with_score in reranked_nodes[:self.top_n]:
                    node = node_with_score.node
                    snippet = {
                        "text": node.text or "",
                        "metadata": node.metadata or {},
                        "rerank_score": float(node_with_score.score)
                    }
                    reranked_snippets.append(snippet)
                
                return reranked_snippets
                
            except Exception as exc:
                logger.error(f"LlamaIndex LLMRerank failed: {exc}. Falling back to cross-encoder.")
                from agent.nodes.rerank import _rerank_snippets
                return _rerank_snippets(
                    query,
                    snippets,
                    top_k=self.top_n,
                    threshold=self.threshold,
                    score_drop=self.score_drop
                )
        
        if self.mode == "similarity" and self._reranker is not None:
            try:
                # SimilarityPostprocessor works similarly
                from llama_index.core.schema import NodeWithScore, TextNode
                
                nodes = []
                for snippet in snippets:
                    text = snippet.get("text", "")
                    metadata = snippet.get("metadata", {})
                    node = TextNode(
                        text=text,
                        metadata=metadata
                    )
                    score = snippet.get("rerank_score") or snippet.get("score_dense") or 0.0
                    nodes.append(NodeWithScore(node=node, score=score))
                
                from llama_index.core import QueryBundle
                query_bundle = QueryBundle(query_str=query)
                
                reranked_nodes = self._reranker.postprocess_nodes(
                    nodes,
                    query_bundle=query_bundle
                )
                
                reranked_snippets = []
                for node_with_score in reranked_nodes[:self.top_n]:
                    node = node_with_score.node
                    snippet = {
                        "text": node.text or "",
                        "metadata": node.metadata or {},
                        "rerank_score": float(node_with_score.score)
                    }
                    reranked_snippets.append(snippet)
                
                return reranked_snippets
                
            except Exception as exc:
                logger.error(f"LlamaIndex SimilarityPostprocessor failed: {exc}. Falling back to cross-encoder.")
                from agent.nodes.rerank import _rerank_snippets
                return _rerank_snippets(
                    query,
                    snippets,
                    top_k=self.top_n,
                    threshold=self.threshold,
                    score_drop=self.score_drop
                )
        
        # Final fallback
        from agent.nodes.rerank import _rerank_snippets
        return _rerank_snippets(
            query,
            snippets,
            top_k=self.top_n,
            threshold=self.threshold,
            score_drop=self.score_drop
        )
