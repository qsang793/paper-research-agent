"""
Shared embedding utilities for all nodes.

Provides cached embedding model loading to avoid duplicate initialization
across different nodes (route, retrieve, query_router, etc.).
"""

from typing import List

from sentence_transformers import SentenceTransformer

# Global cache for embedding models (shared across all nodes)
# Using simple dict cache instead of lru_cache to avoid redundancy
_EMBED_MODEL_CACHE = {}


def get_embed_model(model_name: str) -> SentenceTransformer:
    """
    Get or create cached embedding model (shared across all nodes).
    
    This function ensures that embedding models are loaded only once
    and reused across the entire application, reducing memory usage
    and initialization overhead.
    
    Args:
        model_name: Model name (e.g., "sentence-transformers/all-MiniLM-L6-v2")
        
    Returns:
        Cached SentenceTransformer instance
        
    Example:
        >>> model = get_embed_model("sentence-transformers/all-MiniLM-L6-v2")
        >>> embeddings = model.encode(["hello world"])
    """
    if model_name not in _EMBED_MODEL_CACHE:
        _EMBED_MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _EMBED_MODEL_CACHE[model_name]


def clear_embed_cache():
    """Clear embedding model cache (useful for testing or memory management)."""
    global _EMBED_MODEL_CACHE
    _EMBED_MODEL_CACHE.clear()


def _is_e5_model(model_name: str) -> bool:
    """E5 models require "query:"/"passage:" instruction prefixes."""
    return "e5" in model_name.lower()


def embed_query(model_name: str, query: str) -> List[float]:
    """
    Embed a single query string into a dense vector.

    For E5 models the required "query: " instruction prefix is added
    automatically (mirrors E5EmbeddingFunction in agent/query_router.py); other
    models (e.g. MiniLM) are encoded as-is. Returns a normalized vector.
    """
    model = get_embed_model(model_name)
    text = f"query: {query}" if _is_e5_model(model_name) else query
    embedding = model.encode([text], normalize_embeddings=True)
    return embedding[0].tolist()


def embed_with_prefix(
    model_name: str, texts: List[str], prefix: str = "passage:"
) -> List[List[float]]:
    """
    Embed a list of texts, applying an E5 instruction prefix when relevant.

    `prefix` (e.g. "passage:") is prepended to each text for E5 models so that
    document embeddings match how queries are embedded; non-E5 models encode the
    raw text. Returns one normalized vector per input text.
    """
    model = get_embed_model(model_name)
    if _is_e5_model(model_name):
        prepared = [f"{prefix} {text}" for text in texts]
    else:
        prepared = list(texts)
    embeddings = model.encode(prepared, normalize_embeddings=True)
    return [vec.tolist() for vec in embeddings]
