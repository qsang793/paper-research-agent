from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

import numpy as np

from agent.state import AgentState
from agent.stores import ChromaVectorStore
from agent.utils import embed_query

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = float(os.getenv("KB_CONFIDENCE_THRESHOLD", "0.6"))  # Lowered from 0.7 for more lenient routing
DEFAULT_EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/e5-base-v2")


def _compute_kb_confidence(
    query: str,
    chroma_path: str,
    embed_model: str,
    k: int = 6,
    max_retries: int = 3,
    query_embedding: Optional[List[float]] = None,
) -> Tuple[float, List[dict], Optional[List[float]]]:
    """
    Retrieve from Chroma and compute KB confidence based on relevance.
    
    Uses similarity threshold to filter relevant documents and combines
    average similarity with relevance ratio for better confidence estimation.
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            logger.info(f"[KB Confidence] Attempt {attempt + 1}/{max_retries} for query: '{query[:50]}...'")
            
            # Use ChromaVectorStore interface
            vector_store = ChromaVectorStore(chroma_path, collection_name="knowledge_base")
            
            # Check if collection is empty
            collection_count = vector_store.count()
            logger.info(f"[KB Confidence] ChromaDB collection count: {collection_count}")
            if collection_count == 0:
                logger.warning("[KB Confidence] Collection is empty, returning 0.0 confidence")
                return 0.0, [], None

            # Use cached embedding if available, otherwise compute
            # embed_query handles E5 prefix ("query:") automatically
            if query_embedding is None:
                logger.debug("[KB Confidence] Computing query embedding...")
                query_embedding = embed_query(embed_model, query)
                logger.debug(f"[KB Confidence] Query embedding computed, dimension: {len(query_embedding)}")
            else:
                logger.debug(f"[KB Confidence] Using cached query embedding, dimension: {len(query_embedding)}")

            logger.debug(f"[KB Confidence] Querying ChromaDB với top_k={k}...")
            result = vector_store.query(
                query_embedding=query_embedding,
                top_k=k,
                include=["documents", "metadatas", "distances", "embeddings"],
            )

            docs = (result.get("documents") or [[]])[0]
            logger.info(f"[KB Confidence] Retrieved {len(docs)} documents from ChromaDB")
            
            # Use len() instead of 'if not' to avoid issues with numpy arrays
            if len(docs) == 0:
                logger.warning("[KB Confidence] No documents retrieved, returning 0.0 confidence")
                return 0.0, [], None

            # Get embeddings for cosine similarity calculation
            doc_embeddings = (result.get("embeddings") or [[]])[0]
            logger.debug(f"[KB Confidence] Doc embeddings type: {type(doc_embeddings)}, length: {len(doc_embeddings) if hasattr(doc_embeddings, '__len__') else 'N/A'}")
            
            # Check if embeddings are available (handle both list and numpy array)
            # Use len() instead of 'if not' to avoid numpy array boolean ambiguity
            if len(doc_embeddings) == 0:
                logger.warning("[KB Confidence] No embeddings in result, computing from documents...")
                # Fallback: if embeddings not available, compute from documents
                # Note: Documents in ChromaDB should already have "passage:" prefix if using E5
                from agent.utils import embed_with_prefix
                doc_embeddings = embed_with_prefix(embed_model, docs, prefix="passage:")
                logger.info(f"[KB Confidence] Computed {len(doc_embeddings)} embeddings from documents")
            
            # Ensure doc_embeddings is a list (not numpy array) for iteration
            if isinstance(doc_embeddings, np.ndarray):
                logger.debug("[KB Confidence] Converting numpy array to list...")
                # Convert numpy array to list of arrays
                doc_embeddings = [doc_embeddings[i] for i in range(len(doc_embeddings))]
            
            # Compute cosine similarity directly from embeddings
            query_emb = np.array(query_embedding, dtype=np.float32)
            query_norm = float(np.linalg.norm(query_emb))
            logger.debug(f"[KB Confidence] Query norm: {query_norm:.4f}")
            
            # Relevance threshold: only consider docs with similarity > threshold (lowered for better recall)
            RELEVANCE_THRESHOLD = float(os.getenv("KB_RELEVANCE_THRESHOLD", "0.3"))
            logger.debug(f"[KB Confidence] Relevance threshold: {RELEVANCE_THRESHOLD}")
            
            similarities = []
            relevant_count = 0
            
            for doc_emb in doc_embeddings:
                # Skip None values
                if doc_emb is None:
                    continue
                
                # Convert to numpy array if not already
                if not isinstance(doc_emb, np.ndarray):
                    doc_emb_array = np.array(doc_emb, dtype=np.float32)
                else:
                    doc_emb_array = np.asarray(doc_emb, dtype=np.float32)
                
                doc_norm = float(np.linalg.norm(doc_emb_array))
                
                # Cosine similarity: dot product / (norm1 * norm2)
                # Ensure both norms are scalars (not arrays) for comparison
                if query_norm > 0.0 and doc_norm > 0.0:
                    similarity = float(np.dot(query_emb, doc_emb_array) / (query_norm * doc_norm))
                else:
                    similarity = 0.0
                
                # Clamp to [0, 1] range
                similarity = max(0.0, min(1.0, float(similarity)))
                similarities.append(similarity)
                
                if float(similarity) >= RELEVANCE_THRESHOLD:
                    relevant_count += 1

            if len(similarities) == 0:
                logger.warning("[KB Confidence] No similarities computed, returning 0.0 confidence")
                return 0.0, [], None

            # Confidence based on BOTH average similarity AND relevance ratio
            avg_similarity = sum(similarities) / len(similarities)
            relevance_ratio = relevant_count / len(similarities)
            
            logger.info(f"[KB Confidence] Similarities: avg={avg_similarity:.4f}, relevant={relevant_count}/{len(similarities)} (ratio={relevance_ratio:.4f})")
            
            # Combine metrics: need both high similarity AND high relevance count
            # relevance_ratio adds 0-50% boost to base similarity
            confidence = avg_similarity * (0.5 + 0.5 * relevance_ratio)
            
            # Penalize if no relevant docs found
            if relevant_count == 0:
                confidence = min(confidence, 0.2)  # Cap at 0.2 if nothing relevant
                logger.warning("[KB Confidence] No relevant docs found, capping confidence at 0.2")

            logger.info(f"[KB Confidence] Final confidence: {confidence:.4f} (threshold: {CONFIDENCE_THRESHOLD})")

            metas = (result.get("metadatas") or [[]])[0]
            snippets = [
                {"text": doc, "metadata": meta, "similarity": sim}
                for doc, meta, sim in zip(docs, metas, similarities)
            ]
            
            logger.info(f"[KB Confidence] Returning {len(snippets)} snippets")

            return confidence, snippets, query_embedding
            
        except Exception as exc:
            last_exception = exc
            logger.warning(
                f"[KB Confidence] Computation failed (attempt {attempt + 1}/{max_retries}): {exc}",
                exc_info=True  # Include full traceback
            )
            if attempt < max_retries - 1:
                import time
                time.sleep(1 * (attempt + 1))
    
    # All retries failed - return low confidence
    logger.error(f"[KB Confidence] Failed after {max_retries} attempts: {last_exception}", exc_info=True)
    return 0.0, [], None


def route_node(state: AgentState) -> AgentState:
    """
    LangGraph node: decide route_type based on intent and KB confidence.
    
    Routing Strategy (Adaptive RAG):
    - High confidence (>=0.7): kb_only - use KB retrieval exclusively
    - Medium confidence (0.3-0.7): search - external search + weighted KB merge
    - Low confidence (<0.3): search_only - external search only, skip KB retrieval
    """
    chroma_path = state.get("chroma_path", "./chroma")
    embed_model = state.get("embed_model", DEFAULT_EMBED_MODEL)

    # Check if query embedding already cached in state
    query_embedding = state.get("query_embedding")

    confidence, kb_snippets, computed_embedding = _compute_kb_confidence(
        state["query"], chroma_path, embed_model, query_embedding=query_embedding
    )
    
    # Cache embedding in state for reuse in retrieve_node
    if computed_embedding is not None:
        state["query_embedding"] = computed_embedding  # type: ignore[assignment]

    state["kb_confidence"] = confidence  # type: ignore[assignment]
    state["kb_snippets"] = kb_snippets  # type: ignore[assignment]

    intent = state.get("intent", "known")

    # Adaptive routing based on KB confidence tiers
    if intent == "fresh":
        # Fresh intent always needs external search
        route = "search_only" if confidence < 0.3 else "search"
    elif intent == "known":
        if confidence >= CONFIDENCE_THRESHOLD:
            route = "kb_only"
        elif confidence >= 0.3:
            route = "search"  # Hybrid: search + weighted KB
        else:
            route = "search_only"  # Skip KB retrieval
    else:  # mixed or unknown
        if confidence >= CONFIDENCE_THRESHOLD:
            route = "both"
        elif confidence >= 0.3:
            route = "search"
        else:
            route = "search_only"

    state["route_type"] = route  # type: ignore[assignment]
    return state
