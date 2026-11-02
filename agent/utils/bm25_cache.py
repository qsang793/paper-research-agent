"""
Cached BM25 corpus loading.

Provides cached BM25 index to avoid reloading and parsing JSON files
from disk on every query, significantly improving retrieval performance.
"""

import hashlib
import json
import logging
import os
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


def _get_cache_key(clean_dir: str) -> str:
    """
    Generate cache key based on directory modification time.
    
    Cache is invalidated when directory contents change (new files added/removed).
    
    Args:
        clean_dir: Directory containing JSON files
        
    Returns:
        MD5 hash string as cache key
    """
    try:
        # Use directory mtime to detect changes
        mtime = os.path.getmtime(clean_dir)
        key_string = f"{clean_dir}_{mtime}"
        return hashlib.md5(key_string.encode()).hexdigest()
    except OSError:
        # Fallback to directory path if mtime unavailable
        return hashlib.md5(clean_dir.encode()).hexdigest()


@lru_cache(maxsize=2)
def _load_bm25_corpus(clean_dir: str, cache_key: str) -> Tuple[BM25Okapi, List[Dict]]:
    """
    Load BM25 corpus with caching (internal function).
    
    Args:
        clean_dir: Directory containing JSON files
        cache_key: Cache key (based on directory mtime)
        
    Returns:
        Tuple of (BM25Okapi instance, records list)
    """
    tokenized: List[List[str]] = []
    records: List[Dict] = []
    
    logger.info(f"Loading BM25 corpus from {clean_dir} (cache_key: {cache_key[:8]}...)")
    
    if not os.path.exists(clean_dir):
        logger.warning(f"BM25 corpus directory does not exist: {clean_dir}")
        return None, []
    
    file_count = 0
    for fp in os.listdir(clean_dir):
        if not fp.endswith(".json"):
            continue
        
        path = os.path.join(clean_dir, fp)
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            text = obj.get("text", "")
            metadata = obj.get("metadata", {})
            
            if not text.strip():
                continue
            
            tokenized.append(text.lower().split())
            records.append({"text": text, "metadata": metadata})
            file_count += 1
        except Exception as exc:
            logger.warning(f"Failed to load BM25 corpus file {path}: {exc}")
            continue
    
    if not tokenized:
        logger.warning(f"No valid documents found in BM25 corpus directory: {clean_dir}")
        return None, []
    
    logger.info(f"Loaded {file_count} documents into BM25 corpus")
    bm25 = BM25Okapi(tokenized)
    return bm25, records


def get_bm25_index(clean_dir: str) -> Tuple[Optional[BM25Okapi], List[Dict]]:
    """
    Get BM25 index with automatic cache key generation.
    
    This function automatically generates a cache key based on directory
    modification time, ensuring cache is invalidated when files change.
    
    Args:
        clean_dir: Directory containing JSON files for BM25 corpus
        
    Returns:
        Tuple of (BM25Okapi instance or None, records list)
        
    Example:
        >>> bm25, records = get_bm25_index("./cache/clean")
        >>> if bm25:
        ...     scores = bm25.get_scores(query.split())
    """
    cache_key = _get_cache_key(clean_dir)
    return _load_bm25_corpus(clean_dir, cache_key)


def clear_bm25_cache():
    """Clear BM25 corpus cache (useful for testing or forced reload)."""
    _load_bm25_corpus.cache_clear()
    logger.info("BM25 corpus cache cleared")
