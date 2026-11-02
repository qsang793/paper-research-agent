"""
Model preloading utilities.

Provides functionality to preload models at startup to avoid cold start delays.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global flags to track preloading
_EMBED_MODEL_PRELOADED = False
_RERANK_MODEL_PRELOADED = False


def preload_embedding_model(model_name: Optional[str] = None) -> None:
    """
    Preload embedding model at startup.
    
    Args:
        model_name: Embedding model name (default from env)
    """
    global _EMBED_MODEL_PRELOADED
    if _EMBED_MODEL_PRELOADED:
        return
    
    try:
        model_name = model_name or os.getenv("EMBED_MODEL", "intfloat/e5-base-v2")
        logger.info(f"Preloading embedding model: {model_name}")
        from agent.utils.embeddings import get_embed_model
        get_embed_model(model_name)
        _EMBED_MODEL_PRELOADED = True
        logger.info("✅ Embedding model preloaded successfully")
    except Exception as exc:
        logger.error(f"Failed to preload embedding model: {exc}")


def preload_rerank_model(model_name: Optional[str] = None) -> None:
    """
    Preload rerank model at startup.
    
    Args:
        model_name: Rerank model name (default from env)
    """
    global _RERANK_MODEL_PRELOADED
    if _RERANK_MODEL_PRELOADED:
        return
    
    try:
        model_name = model_name or os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        logger.info(f"Preloading rerank model: {model_name}")
        from agent.nodes.rerank import _get_rerank_model
        _get_rerank_model()
        _RERANK_MODEL_PRELOADED = True
        logger.info("✅ Rerank model preloaded successfully")
    except Exception as exc:
        logger.error(f"Failed to preload rerank model: {exc}")


def preload_all_models() -> None:
    """
    Preload all models at startup based on env flags.
    
    Environment variables:
    - PRELOAD_EMBED_MODEL: "true" to preload embedding model
    - PRELOAD_RERANK_MODEL: "true" to preload rerank model
    """
    preload_embed = os.getenv("PRELOAD_EMBED_MODEL", "false").lower() == "true"
    preload_rerank = os.getenv("PRELOAD_RERANK_MODEL", "false").lower() == "true"
    
    if preload_embed:
        preload_embedding_model()
    
    if preload_rerank:
        preload_rerank_model()
    
    if not preload_embed and not preload_rerank:
        logger.info("Model preloading disabled (set PRELOAD_EMBED_MODEL or PRELOAD_RERANK_MODEL=true to enable)")
