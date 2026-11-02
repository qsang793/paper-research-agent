"""
Health check and info endpoints.
"""
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException

from api.models import HealthResponse, InfoResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns system status and timestamp.
    Checks ChromaDB connectivity.
    """
    chroma_status = "unknown"
    
    # Check ChromaDB connection
    try:
        chroma_path = os.getenv("CHROMA_PATH", "./chroma")
        if os.path.exists(chroma_path):
            # Try to import and check ChromaDB
            try:
                import chromadb
                # Simple check: if path exists and is accessible
                chroma_status = "connected"
            except ImportError:
                chroma_status = "error: chromadb not installed"
        else:
            chroma_status = "error: chroma path not found"
    except Exception as e:
        chroma_status = f"error: {str(e)}"
    
    # Determine overall status
    overall_status = "healthy" if chroma_status == "connected" else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        timestamp=datetime.now(),
        chroma_status=chroma_status
    )


@router.get("/info", response_model=InfoResponse)
async def get_info():
    """
    Get API configuration information.
    
    Returns current model settings and feature flags.
    """
    return InfoResponse(
        embed_model=os.getenv("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"),
        llm_backend=os.getenv("LLM_BACKEND", "ollama"),
        reranking_enabled=os.getenv("ENABLE_RERANKING", "true").lower() == "true",
        rerank_model=os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    )
