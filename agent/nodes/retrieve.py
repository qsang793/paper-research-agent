from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

from agent.state import AgentState
from agent.stores import ChromaVectorStore
from agent.utils import embed_query, get_bm25_index

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = int(os.getenv("TOP_K", "6"))
DEFAULT_EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/e5-base-v2")


def _dense_retrieve(
    query: str, 
    vector_store: ChromaVectorStore, 
    embed_model: str, 
    n: int,
    query_embedding: Optional[List[float]] = None
) -> List[Tuple[str, Dict[str, str], float]]:
    """Dense retrieval using VectorStoreInterface."""
    try:
        # Use cached embedding if available, otherwise compute
        # embed_query handles E5 prefix ("query:") automatically
        if query_embedding is None:
            query_embedding = embed_query(embed_model, query)

        res = vector_store.query(
            query_embedding=query_embedding,
            top_k=n,
            include=["documents", "metadatas", "distances"],
        )
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        distances = (res.get("distances") or [[]])[0]

        results: List[Tuple[str, Dict[str, str], float]] = []
        for doc, meta, dist in zip(docs, metas, distances):
            meta = meta or {}
            key = meta.get("source_url") or meta.get("title") or ""
            if not key:
                continue
            results.append((key, {"text": doc, "metadata": meta}, float(dist)))
        return results
    except Exception as exc:
        import logging
        logging.error(f"Dense retrieval failed: {exc}")
        return []  # Return empty list on failure


def _bm25_retrieve(query: str, clean_dir: str, top_k: int) -> Dict[str, Dict]:
    """BM25 retrieval using cached corpus."""
    # Use cached BM25 index
    bm25, records = get_bm25_index(clean_dir)
    if bm25 is None or not records:
        return {}
    scores = bm25.get_scores(query.lower().split())
    paired = sorted(zip(scores, records), key=lambda x: x[0], reverse=True)
    results: Dict[str, Dict] = {}
    for score, record in paired[: top_k * 2]:
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


def _rrf_merge(
    dense: List[Tuple[str, Dict[str, str], float]], 
    bm25: Dict[str, Dict], 
    search_snippets: List[Dict], 
    k: int,
    kb_confidence: float = 0.5,
    route_type: str = "search",
    query: str = ""  # Query string for definition query detection
) -> List[Dict]:
    """
    Reciprocal Rank Fusion with adaptive source weighting.
    
    Args:
        kb_confidence: 0.0-1.0, how relevant KB is to query
        route_type: "kb_only", "search", "search_only", "both"
    
    Weighting Strategy:
        - kb_only: KB sources get full weight, search gets 0
        - search_only: Search gets full weight, KB gets 0
        - search/both: Dynamic weighting based on kb_confidence
          * kb_weight = kb_confidence
          * search_weight = 1.0 (search always valued in these modes)
    """
    scores: Dict[str, float] = {}
    documents: Dict[str, Dict] = {}
    k_rrf = int(os.getenv("RRF_K", "60"))
    
    # Determine source weights based on routing decision
    if route_type == "kb_only":
        kb_weight = 1.0
        search_weight = 0.0
    elif route_type == "search_only":
        kb_weight = 0.0
        search_weight = 1.0
    else:  # "search" or "both"
        # Adaptive: low KB confidence → prioritize search results
        kb_weight = kb_confidence
        search_weight = 1.0  # Search always fully weighted when requested
        
        # Boost search weight for definition queries ("what is X")
        # These queries benefit more from ArXiv abstracts than KB chunks
        query_lower = query.lower()
        if any(qword in query_lower for qword in ["what is", "what are", "define", "meaning of"]):
            # Increase search weight for definition queries
            search_weight = 1.2  # 20% boost
            logger.debug(f"[RRF Merge] Definition query detected, boosting search weight to {search_weight}")

    # Dense results (convert distance to similarity)
    for position, (key, doc, dist) in enumerate(dense, start=1):
        score = 1.0 - dist
        rrf_score = kb_weight * (1.0 / (k_rrf + position))
        scores[key] = scores.get(key, 0.0) + rrf_score
        documents.setdefault(key, doc)
        documents[key]["score_dense"] = float(score)

    # BM25 results
    for position, (key, record) in enumerate(bm25.items(), start=1):
        rrf_score = kb_weight * (1.0 / (k_rrf + position))
        scores[key] = scores.get(key, 0.0) + rrf_score
        doc = {
            "text": record.get("text", ""),
            "metadata": record.get("metadata", {}),
        }
        documents.setdefault(key, doc)
        documents[key]["score_bm25"] = record.get("score")

    # Search snippets (if any)
    for position, snippet in enumerate(search_snippets, start=1):
        key = snippet.get("abs_url") or snippet.get("pdf_url") or snippet.get("title")
        if not key:
            continue
        rrf_score = search_weight * (1.0 / (k_rrf + position))
        scores[key] = scores.get(key, 0.0) + rrf_score
        metadata = {
            "source_url": snippet.get("abs_url"),
            "title": snippet.get("title"),
            "published_at": snippet.get("published_at"),
        }
        # Use abstract from arXiv API XML (parsed in search_arxiv)
        # Fallback to summary or title if abstract not available
        abstract_text = snippet.get("abstract") or snippet.get("summary") or snippet.get("title") or ""
        documents.setdefault(key, {
            "text": abstract_text,
            "metadata": metadata,
        })
        documents[key]["source"] = "search"

    top_keys = [key for key, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:k]]
    merged: List[Dict] = []
    for key in top_keys:
        doc = documents.get(key)
        if not doc:
            continue
        # Ensure text field exists and is not empty
        if not doc.get("text") or len(doc.get("text", "").strip()) == 0:
            logger.warning(f"[RRF Merge] Skipping document with empty text: {key[:50]}")
            continue
        merged.append(doc)
    
    logger.info(f"[RRF Merge] Merged {len(merged)} snippets (from {len(top_keys)} candidates)")
    return merged


def retrieve_node(state: AgentState) -> AgentState:
    """
    LangGraph node: retrieve relevant snippets based on search_source.
    
    Search source behavior:
    - arxiv: KB first (ChromaDB + BM25), use API results only if KB < min_threshold
    - tavily: Search results only (no KB)
    - mixed: RRF merge all sources (KB + search)
    """
    query = state.get("query", "")
    route_type = state.get("route_type", "search")
    search_source = state.get("search_source", "mixed")
    kb_confidence = state.get("kb_confidence", 0.5)
    chroma_path = state.get("chroma_path", "./chroma")
    embed_model = state.get("embed_model", DEFAULT_EMBED_MODEL)
    clean_dir = state.get("clean_dir", "./cache/clean")
    top_k = int(state.get("top_k", DEFAULT_TOP_K))
    search_results = state.get("search_results", [])
    
    logger.info(f"[Retrieve Node] Query: '{query[:100]}...'")
    logger.info(f"[Retrieve Node] Route type: {route_type}, Search source: {search_source}")
    logger.info(f"[Retrieve Node] KB confidence: {kb_confidence:.4f}, Top K: {top_k}")
    logger.info(f"[Retrieve Node] Search results count: {len(search_results)}")
    
    # Minimum KB results before using API fallback (for arxiv mode)
    MIN_KB_THRESHOLD = 3

    # TAVILY mode: Search results only, no KB
    if search_source == "tavily":
        logger.info("[Retrieve Node] TAVILY mode: Using search results only")
        merged = []
        for snippet in search_results[:top_k]:
            metadata = {
                "source_url": snippet.get("abs_url"),
                "title": snippet.get("title"),
                "published_at": snippet.get("published_at"),
            }
            abstract_text = snippet.get("abstract") or snippet.get("summary") or snippet.get("title") or ""
            merged.append({
                "text": abstract_text,
                "metadata": metadata,
                "source": "tavily"
            })
        logger.info(f"[Retrieve Node] TAVILY: Returning {len(merged)} snippets")
        state["merged_snippets"] = merged  # type: ignore[assignment]
        return state

    # Get KB results for arxiv and mixed modes
    # Reuse query embedding from state if available (computed in route_node)
    query_embedding = state.get("query_embedding")
    logger.debug(f"[Retrieve Node] Query embedding cached: {query_embedding is not None}")
    
    # Use ChromaVectorStore interface
    vector_store = ChromaVectorStore(chroma_path, collection_name="knowledge_base")
    logger.info(f"[Retrieve Node] ChromaDB collection count: {vector_store.count()}")
    
    # Parallelize Dense + BM25 retrieval for better performance
    logger.info("[Retrieve Node] Starting parallel retrieval (Dense + BM25)...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both retrieval tasks in parallel
        # Retrieve more candidates for better diversity (2-3x top_k)
        dense_future = executor.submit(
            _dense_retrieve,
            state["query"],
            vector_store,
            embed_model,
            max(top_k * 3, 15),  # Increased from 2x to 3x for better diversity
            query_embedding
        )
        bm25_future = executor.submit(
            _bm25_retrieve,
            state["query"],
            clean_dir,
            top_k
        )
        
        # Wait for both to complete
        dense_results = dense_future.result()
        bm25_results = bm25_future.result()
    
    logger.info(f"[Retrieve Node] Dense results: {len(dense_results)}, BM25 results: {len(bm25_results)}")
    
    # Count unique KB results
    kb_urls = set()
    for key, _, _ in dense_results:
        kb_urls.add(key)
    for key in bm25_results.keys():
        kb_urls.add(key)
    kb_count = len(kb_urls)
    logger.info(f"[Retrieve Node] Unique KB documents: {kb_count}")

    # ARXIV mode: Always include ArXiv API results, weight by KB confidence
    # Fix: Use confidence-based logic instead of count-based
    # This ensures ArXiv API results are never ignored, even if KB has many snippets
    if search_source == "arxiv":
        logger.info(f"[Retrieve Node] ARXIV mode: KB count={kb_count}, KB confidence={kb_confidence:.4f}")
        logger.info(f"[Retrieve Node] ARXIV: ArXiv API results available: {len(search_results)} papers")
        
        # Always include ArXiv API results, weight by KB confidence
        # High confidence (>= 0.6): KB primary (70%), ArXiv supplement (30%)
        # Medium confidence (0.3-0.6): Equal weight (50%)
        # Low confidence (< 0.3): ArXiv primary (70%), KB supplement (30%)
        if kb_confidence >= 0.6:
            kb_weight = 0.7
            logger.info("[Retrieve Node] ARXIV: High KB confidence, KB primary (70%), ArXiv supplement (30%)")
        elif kb_confidence >= 0.3:
            kb_weight = 0.5
            logger.info("[Retrieve Node] ARXIV: Medium KB confidence, equal weight (50%)")
        else:
            kb_weight = 0.3
            logger.info("[Retrieve Node] ARXIV: Low KB confidence, ArXiv primary (70%), KB supplement (30%)")
        
        # Always merge KB + ArXiv API results
        merged = _rrf_merge(
            dense_results, 
            bm25_results, 
            search_results,  # Always include ArXiv API results!
            k=top_k,
            kb_confidence=kb_weight,
            route_type="both",
            query=query
        )
        logger.info(f"[Retrieve Node] ARXIV: Returning {len(merged)} merged snippets (KB + ArXiv)")
        state["merged_snippets"] = merged  # type: ignore[assignment]
        return state

    # MIXED mode (default): RRF merge all sources
    # Also handles route_type-specific logic for backward compatibility
    if route_type == "search_only":
        merged = []
        for snippet in search_results[:top_k]:
            metadata = {
                "source_url": snippet.get("abs_url"),
                "title": snippet.get("title"),
                "published_at": snippet.get("published_at"),
            }
            abstract_text = snippet.get("abstract") or snippet.get("summary") or snippet.get("title") or ""
            merged.append({
                "text": abstract_text,
                "metadata": metadata,
                "source": "search"
            })
        state["merged_snippets"] = merged  # type: ignore[assignment]
        return state

    # Standard merge with all sources
    use_search = route_type in {"search", "both"}
    logger.info(f"[Retrieve Node] MIXED mode: use_search={use_search}, route_type={route_type}")
    merged = _rrf_merge(
        dense_results, 
        bm25_results, 
        search_results if use_search else [], 
        k=top_k,
        kb_confidence=kb_confidence,
        route_type=route_type,
        query=query
    )

    logger.info(f"[Retrieve Node] MIXED: Returning {len(merged)} merged snippets")
    if merged:
        logger.info(f"[Retrieve Node] Top snippet sources: {[m.get('metadata', {}).get('title', 'N/A')[:50] for m in merged[:3]]}")
    
    state["merged_snippets"] = merged  # type: ignore[assignment]
    return state

