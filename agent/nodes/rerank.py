"""
Re-ranking node for Stage 3 - improve retrieval precision.

Uses cross-encoder to re-score retrieved snippets based on relevance to query.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List

from sentence_transformers import CrossEncoder

from agent.state import AgentState

logger = logging.getLogger(__name__)

DEFAULT_RERANK_MODEL = os.getenv(
    "RERANK_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2"  # Fast & accurate for RAG
    # Alternatives: BAAI/bge-reranker-base, mixedbread-ai/mxbai-rerank-base-v1
)
DEFAULT_RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "6"))
DEFAULT_RERANK_THRESHOLD = float(os.getenv("RERANK_THRESHOLD", "0.0"))  # 0.0 = disable filtering, only reorder
DEFAULT_RERANK_SCORE_DROP = float(os.getenv("RERANK_SCORE_DROP", "999.0"))  # 999 = disable dynamic cutoff
DEFAULT_RERANK_MAX_TEXT_LENGTH = int(os.getenv("RERANK_MAX_TEXT_LENGTH", "400"))  # Shorter text for better rerank quality
ENABLE_RERANKING = os.getenv("ENABLE_RERANKING", "true").lower() == "true"

# Global cache for cross-encoder model
_RERANK_MODEL_CACHE = None


def _get_rerank_model() -> CrossEncoder:
    """Get or create cached cross-encoder model."""
    global _RERANK_MODEL_CACHE
    if _RERANK_MODEL_CACHE is None:
        logger.info(f"Loading re-ranking model: {DEFAULT_RERANK_MODEL}")
        _RERANK_MODEL_CACHE = CrossEncoder(DEFAULT_RERANK_MODEL)
    return _RERANK_MODEL_CACHE


def clear_rerank_cache():
    """
    Clear rerank model cache (useful for cleanup on shutdown).
    
    Properly cleans up CrossEncoder model which may use multiprocessing
    internally, preventing resource leaks on shutdown.
    """
    global _RERANK_MODEL_CACHE
    if _RERANK_MODEL_CACHE is not None:
        # Clear reference to allow garbage collection
        # CrossEncoder model will be cleaned up by Python GC
        _RERANK_MODEL_CACHE = None
        logger.debug("Rerank model cache cleared")


def _prepare_rerank_text(snippet: Dict, max_length: int = DEFAULT_RERANK_MAX_TEXT_LENGTH) -> str:
    """
    Prepare text for reranking by creating a focused summary.
    
    Strategy:
    - Include title if available
    - Include first portion of text (most relevant for definitions)
    - Keep total length <= max_length for better rerank quality
    
    This helps MiniLM-L6 reranker focus on key information rather than long chunks.
    """
    title = snippet.get("metadata", {}).get("title", "")
    text = snippet.get("text", "")
    
    # Build focused text: title + first portion
    parts = []
    if title:
        parts.append(title)
    
    # Take first portion of text (most relevant for "what is" queries)
    if text:
        # Remove extra whitespace
        text_clean = " ".join(text.split())
        # Take first max_length chars (or less if title takes space)
        title_len = len(title) if title else 0
        available_len = max(0, max_length - title_len - 10)  # Reserve 10 for separator
        if available_len > 0:
            text_portion = text_clean[:available_len]
            parts.append(text_portion)
    
    result = "\n".join(parts).strip()
    return result[:max_length]  # Final safety limit


def _rerank_snippets(
    query: str,
    snippets: List[Dict],
    top_k: int = DEFAULT_RERANK_TOP_K,
    threshold: float = DEFAULT_RERANK_THRESHOLD,
    score_drop: float = DEFAULT_RERANK_SCORE_DROP,
    max_text_length: int = DEFAULT_RERANK_MAX_TEXT_LENGTH
) -> List[Dict]:
    """
    Re-rank snippets using cross-encoder model with precision filtering.
    
    Args:
        query: User query
        snippets: List of retrieved snippets (from retrieve_node)
        top_k: Maximum number of snippets to return
        threshold: Minimum score to keep a snippet (default: 0.3)
        score_drop: Max score drop from best result for dynamic cutoff (default: 0.3)
        
    Returns:
        Filtered and sorted snippets by cross-encoder relevance score
        
    Filtering Strategy:
        1. Score all snippets with cross-encoder
        2. Remove snippets with score < threshold (absolute filter)
        3. Apply dynamic cutoff: stop when score drops > score_drop from top score
        4. Return at most top_k results
    """
    if not snippets:
        return []
    
    if not ENABLE_RERANKING:
        logger.info("Re-ranking disabled, returning original snippets")
        return snippets[:top_k]
    
    # Extract and prepare text for scoring
    # Use focused text (title + first portion) for better rerank quality
    pairs = []
    empty_text_count = 0
    for snippet in snippets:
        # Prepare focused text for reranking (title + first portion)
        rerank_text = _prepare_rerank_text(snippet, max_text_length)
        
        if not rerank_text or len(rerank_text.strip()) == 0:
            empty_text_count += 1
            logger.warning(f"[Rerank] Empty text in snippet: {snippet.get('metadata', {}).get('title', 'N/A')[:50]}")
            # Fallback to original text if prepared text is empty
            rerank_text = snippet.get("text", "")[:max_text_length]
        
        pairs.append([query, rerank_text])
    
    if empty_text_count > 0:
        logger.warning(f"[Rerank] Found {empty_text_count} snippets with empty text out of {len(snippets)}")
    
    logger.info(f"[Rerank] Scoring {len(pairs)} query-snippet pairs...")
    logger.debug(f"[Rerank] Query: '{query[:100]}...'")
    logger.debug(f"[Rerank] Sample snippet text lengths: {[len(p[1]) for p in pairs[:3]]}")
    
    # Score all pairs
    try:
        model = _get_rerank_model()
        scores = model.predict(pairs, show_progress_bar=False)
        
        # Log raw scores for debugging
        score_list = [float(s) for s in scores]
        logger.info(f"[Rerank] Raw scores from cross-encoder: {score_list[:5]}")
        logger.info(f"[Rerank] Score range: min={min(score_list):.4f}, max={max(score_list):.4f}, mean={sum(score_list)/len(score_list):.4f}")
        
        # IMPORTANT: Cross-encoder scores from ms-marco-MiniLM-L-6-v2 are raw logits
        # Score interpretation:
        # - Positive scores (> 0): Relevant
        # - Negative scores (< 0): Not relevant
        # - Typical range: -10 to +10 for ms-marco models
        # 
        # If ALL scores are negative, it means cross-encoder thinks nothing is relevant
        # This could be:
        # 1. Snippets truly not relevant to query
        # 2. Snippets have empty/missing text
        # 3. Query-snippet format issue
        
        min_score = min(score_list)
        max_score = max(score_list)
        score_range = max_score - min_score if max_score != min_score else 1.0
        
        # Check if all scores are negative (nothing relevant)
        all_negative = all(s < 0 for s in score_list)
        if all_negative:
            logger.warning(f"[Rerank] ⚠️ ALL {len(score_list)} scores are NEGATIVE (not relevant)!")
            logger.warning("[Rerank] This suggests snippets don't match query well, or text extraction failed")
            logger.warning(f"[Rerank] Score range: {min_score:.4f} to {max_score:.4f}")
        
        # Attach scores to snippets (keep raw scores for ranking)
        scored_snippets = []
        for snippet, raw_score in zip(snippets, scores):
            snippet_copy = snippet.copy()
            raw_score_float = float(raw_score)
            snippet_copy["rerank_score"] = raw_score_float
            # Also store normalized score for threshold comparison
            normalized_score = (raw_score_float - min_score) / score_range if score_range > 0 else 0.0
            snippet_copy["rerank_score_normalized"] = normalized_score
            scored_snippets.append(snippet_copy)
            # Log first few scores for debugging
            if len(scored_snippets) <= 3:
                text_preview = snippet.get("text", "")[:100] if snippet.get("text") else "EMPTY"
                logger.debug(f"[Rerank] Snippet {len(scored_snippets)}: raw={raw_score_float:.4f}, normalized={normalized_score:.4f}, text='{text_preview}...'")
        
        # Sort by raw score descending (raw scores are better for ranking)
        scored_snippets.sort(key=lambda x: x.get("rerank_score", -999.0), reverse=True)
        
        # Filter by threshold
        # Strategy based on user feedback:
        # 1. If threshold = 0.0 → disable filtering (only reorder)
        # 2. If all scores negative → disable threshold (use top-k anyway)
        # 3. If top score very low → fallback to pre-rerank order
        filtered_snippets = []
        
        # Check if threshold filtering is disabled (threshold = 0.0 or negative)
        threshold_disabled = threshold <= 0.0
        
        # Check if score_drop is disabled (score_drop >= 999)
        score_drop_disabled = score_drop >= 999.0
        
        logger.info(f"[Rerank] Filtering: threshold_disabled={threshold_disabled}, all_negative={all_negative}, threshold={threshold}, score_drop={score_drop}")
        
        if threshold_disabled:
            # Threshold disabled → only reorder, don't filter
            logger.info(f"[Rerank] Threshold filtering disabled (threshold={threshold:.2f}), using top-{top_k} by rerank score")
            filtered_snippets = scored_snippets[:top_k]
        elif all_negative:
            # All scores negative → cross-encoder says nothing is relevant
            # But we still need to return something, so use top-k by raw score
            logger.warning(f"[Rerank] All scores negative → disabling threshold filter, using top-{top_k} by raw score")
            filtered_snippets = scored_snippets[:top_k]
        else:
            # Some scores positive → apply threshold if enabled
            top_raw = scored_snippets[0].get("rerank_score", 0.0)
            top_normalized = scored_snippets[0].get("rerank_score_normalized", 0.0)
            
            # Fallback: If top score is very low (even if positive), disable filtering
            # This handles "broad query" case where scores are low but snippets are still useful
            if top_raw < 0.5 and top_normalized < 0.3:
                logger.info(f"[Rerank] Top score low (raw={top_raw:.4f}, normalized={top_normalized:.4f}) → disabling threshold, using top-{top_k}")
                filtered_snippets = scored_snippets[:top_k]
            else:
                # Normal threshold filtering
                for s in scored_snippets:
                    raw_score = s.get("rerank_score", -999.0)
                    normalized_score = s.get("rerank_score_normalized", 0.0)
                    # For positive scores, use normalized threshold
                    # For negative scores, only keep if very close to 0 (borderline relevant)
                    if raw_score > 0:
                        # Positive = relevant, use normalized threshold
                        if normalized_score >= threshold:
                            filtered_snippets.append(s)
                    elif raw_score > -2.0:
                        # Negative but close to 0 (borderline), use normalized threshold
                        if normalized_score >= threshold:
                            filtered_snippets.append(s)
                
                if not filtered_snippets:
                    logger.warning(f"[Rerank] All {len(scored_snippets)} snippets below threshold {threshold} (normalized).")
                    logger.warning(f"[Rerank] Top raw score: {top_raw:.4f}, normalized: {top_normalized:.4f}")
                    logger.warning(f"[Rerank] Fallback: Returning top-{min(top_k, len(scored_snippets))} snippets despite low scores")
                    filtered_snippets = scored_snippets[:top_k]
        
        # Safety check: if filtered_snippets is empty, fallback to scored_snippets
        if not filtered_snippets:
            logger.warning(f"[Rerank] filtered_snippets is empty, falling back to top-{top_k} scored_snippets")
            filtered_snippets = scored_snippets[:top_k]
        
        # Apply dynamic cutoff (score drop) - only if enabled
        if not filtered_snippets:
            logger.warning(f"[Rerank] No snippets available after filtering, returning empty list")
            return []
        
        top_raw_score = filtered_snippets[0].get("rerank_score", 0.0)
        top_normalized_score = filtered_snippets[0].get("rerank_score_normalized", 0.0)
        final_snippets = []
        
        logger.info(f"[Rerank] Before dynamic cutoff: filtered_snippets={len(filtered_snippets)}, score_drop_disabled={score_drop_disabled}")
        if score_drop_disabled:
            # Score drop disabled → return all filtered snippets up to top_k
            final_snippets = filtered_snippets[:top_k]
            logger.info(f"[Rerank] Score drop disabled, returning all {len(final_snippets)} filtered snippets")
        else:
            # Apply dynamic cutoff
            for snippet in filtered_snippets[:top_k]:
                raw_score = snippet.get("rerank_score", 0.0)
                normalized_score = snippet.get("rerank_score_normalized", 0.0)
                # Use normalized score drop for threshold comparison
                if top_normalized_score - normalized_score > score_drop:
                    logger.info(f"[Rerank] Dynamic cutoff: normalized score dropped from {top_normalized_score:.4f} to {normalized_score:.4f}")
                    break
                final_snippets.append(snippet)
        
        # Log filtering stats
        logger.info(
            f"[Rerank] Re-ranking: {len(snippets)} -> {len(filtered_snippets)} (threshold) "
            f"-> {len(final_snippets)} (dynamic). Top raw score: {top_raw_score:.4f}, normalized: {top_normalized_score:.4f}"
        )
        
        return final_snippets
        
    except Exception as exc:
        logger.error(f"Re-ranking failed: {exc}. Returning original order.")
        return snippets[:top_k]


def rerank_node(state: AgentState) -> AgentState:
    """
    LangGraph node: re-rank merged snippets using cross-encoder with precision filtering.
    
    Improvements (Stage 4):
    - Absolute threshold filtering (RERANK_THRESHOLD, default 0.0 = disabled)
    - Dynamic cutoff when score drops significantly (RERANK_SCORE_DROP, default 999 = disabled)
    - Better precision: removes low-quality chunks that passed BM25/semantic search
    - Focused text preparation: title + first portion for better rerank quality
    
    Note: Threshold filtering is disabled by default (0.0) to handle "broad queries" 
    like "what is RAG?" where cross-encoder scores may be low but snippets are still useful.
    """
    snippets = state.get("merged_snippets", []) or []
    query = state["query"]
    top_k = int(state.get("top_k", DEFAULT_RERANK_TOP_K))
    threshold = float(state.get("rerank_threshold", DEFAULT_RERANK_THRESHOLD))
    score_drop = float(state.get("rerank_score_drop", DEFAULT_RERANK_SCORE_DROP))
    max_text_length = int(state.get("rerank_max_text_length", DEFAULT_RERANK_MAX_TEXT_LENGTH))
    
    logger.info(f"[Rerank Node] Query: '{query[:100]}...'")
    logger.info(f"[Rerank Node] Input snippets: {len(snippets)}, Top K: {top_k}, Threshold: {threshold}")
    
    if len(snippets) == 0:
        logger.warning("[Rerank Node] No snippets to re-rank")
        return state
    
    # Re-rank snippets with filtering
    logger.info(f"[Rerank Node] Starting reranking với threshold={threshold:.2f}, score_drop={score_drop:.2f}, max_text_length={max_text_length}")
    reranked_snippets = _rerank_snippets(
        query, 
        snippets, 
        top_k=top_k,
        threshold=threshold,
        score_drop=score_drop,
        max_text_length=max_text_length
    )
    
    logger.info(f"[Rerank Node] Reranked snippets: {len(reranked_snippets)} (from {len(snippets)} input)")
    if reranked_snippets:
        top_score = reranked_snippets[0].get("rerank_score", 0.0)
        logger.info(f"[Rerank Node] Top rerank score: {top_score:.4f}")
        logger.info(f"[Rerank Node] ✅ Returning {len(reranked_snippets)} snippets to generate_node")
    else:
        logger.error(f"[Rerank Node] ❌ ERROR: reranked_snippets is EMPTY! This will cause 'Chưa đủ nguồn'")
        logger.error(f"[Rerank Node] Input snippets count: {len(snippets)}")
        logger.error(f"[Rerank Node] Threshold: {threshold}, Score drop: {score_drop}")
        # Fallback: return original snippets if rerank returns empty
        logger.warning(f"[Rerank Node] Fallback: Using original {len(snippets)} snippets")
        reranked_snippets = snippets[:top_k]
    
    # Update state with re-ranked snippets
    state["merged_snippets"] = reranked_snippets  # type: ignore[assignment]
    
    # Store re-ranking metadata for debugging
    if reranked_snippets:
        state["rerank_applied"] = True  # type: ignore[assignment]
        state["rerank_top_score"] = reranked_snippets[0].get("rerank_score", 0.0)  # type: ignore[assignment]
        state["rerank_count"] = len(reranked_snippets)  # type: ignore[assignment]
    
    return state
