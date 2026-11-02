"""
FastAPI application entry point.
"""
from dotenv import load_dotenv

# Load environment variables before any api./agent. imports so module-level
# os.getenv() reads (e.g. SESSIONS_MAX in api.routes.chat) see .env values.
load_dotenv()

import os
import signal
import sys
import atexit
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from api.routes import chat, health, memory
from api.telemetry import RequestTelemetryMiddleware

# Fix HuggingFace tokenizers warning when using uvicorn --reload
# Set TOKENIZERS_PARALLELISM=false to avoid forking warnings
if os.getenv("TOKENIZERS_PARALLELISM") is None:
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


# Global flag to prevent double cleanup
_cleanup_done = False


def cleanup_resources():
    """
    Cleanup all resources to prevent resource leaks.
    
    This function is called on shutdown to ensure proper cleanup of:
    - ThreadPoolExecutor instances
    - ChromaDB connections
    - Embedding model caches
    - Multiprocessing resources
    - Other background resources
    
    Note: This function is idempotent - safe to call multiple times.
    """
    global _cleanup_done
    if _cleanup_done:
        return  # Already cleaned up
    
    _cleanup_done = True
    
    try:
        # Cleanup ChromaDB connections
        from agent.utils.vector_store import VectorStore
        VectorStore.reset()
        print("   ✅ ChromaDB connections closed")
    except Exception as e:
        print(f"   ⚠️  Error closing ChromaDB connections: {e}")
    
    try:
        # Cleanup embedding model caches
        from agent.utils.embeddings import clear_embed_cache
        clear_embed_cache()
        print("   ✅ Embedding model cache cleared")
    except Exception as e:
        print(f"   ⚠️  Error clearing embedding cache: {e}")
    
    try:
        # Cleanup rerank model cache
        from agent.nodes.rerank import clear_rerank_cache
        clear_rerank_cache()
        print("   ✅ Rerank model cache cleared")
    except Exception as e:
        print(f"   ⚠️  Error clearing rerank cache: {e}")
    
    try:
        # Cleanup multiprocessing resources (fixes semaphore leaks)
        import multiprocessing
        # Wait for any child processes to finish
        for child in multiprocessing.active_children():
            child.join(timeout=1.0)
        print("   ✅ Multiprocessing resources cleaned")
    except Exception as e:
        print(f"   ⚠️  Error cleaning multiprocessing: {e}")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print("\n🛑 Received shutdown signal, cleaning up resources...")
    cleanup_resources()
    sys.exit(0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup/shutdown.
    Can be used to initialize resources like ChromaDB connections.
    """
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register cleanup function to be called on exit
    atexit.register(cleanup_resources)
    
    # Startup
    print("🚀 Starting AI Research Agent API...")
    print(f"   - LLM Backend: {os.getenv('LLM_BACKEND', 'ollama')}")
    print(f"   - Embed Model: {os.getenv('EMBED_MODEL', 'default')}")
    print(f"   - ChromaDB Path: {os.getenv('CHROMA_PATH', './chroma')}")
    
    # Preload models if enabled
    preload_models = os.getenv("PRELOAD_MODELS", "false").lower() == "true"
    if preload_models:
        print("   - Preloading models...")
        try:
            from agent.utils.model_loader import preload_all_models
            preload_all_models()
        except Exception as e:
            print(f"   ⚠️  Model preloading failed: {e}")
    else:
        print("   - Model preloading disabled (set PRELOAD_MODELS=true to enable)")
    
    yield
    
    # Shutdown
    print("👋 Shutting down AI Research Agent API...")
    cleanup_resources()


# Create FastAPI app
app = FastAPI(
    title="AI Research Agent API",
    description="RAG-based research assistant API with arXiv integration",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend
import re
from fastapi import Request
from typing import List

def get_allowed_origins() -> List[str]:
    """Use explicit origins in production and local conveniences in development."""
    origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]

    if os.getenv("APP_ENV", "development").lower() == "production":
        return origins

    default_origins = [
        "http://localhost:3000",
        "https://*.vercel.app",
        "https://*.trycloudflare.com",  # Cloudflare Quick Tunnel
    ]

    for origin in default_origins:
        if origin not in origins:
            origins.append(origin)

    return origins

def is_origin_allowed(origin: str, allowed_origins: List[str]) -> bool:
    """Check if origin matches any allowed pattern (supports wildcards)."""
    if not origin:
        return False

    for allowed in allowed_origins:
        # Exact match
        if origin == allowed:
            return True

        # Wildcard pattern (e.g., https://*.trycloudflare.com)
        if "*" in allowed:
            pattern = allowed.replace(".", r"\.").replace("*", r"[a-z0-9-]+")
            if re.match(f"^{pattern}$", origin):
                return True

    return False

# Custom CORS middleware to support wildcard origins
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        allowed_origins = get_allowed_origins()

        # Handle preflight OPTIONS requests BEFORE routing
        if request.method == "OPTIONS":
            if origin and is_origin_allowed(origin, allowed_origins):
                return Response(
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                        "Access-Control-Allow-Headers": "*",
                        "Access-Control-Max-Age": "600",
                    }
                )
            else:
                # Origin not allowed
                return Response(status_code=403)

        # Process regular requests
        response = await call_next(request)

        # Add CORS headers to response if origin is allowed
        if origin and is_origin_allowed(origin, allowed_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            response.headers["Access-Control-Allow-Headers"] = "*"

        return response

app.add_middleware(CustomCORSMiddleware)
# Added after CORS so this ASGI middleware wraps the full HTTP/stream lifecycle.
app.add_middleware(RequestTelemetryMiddleware)

# Register routers
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(memory.router)


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "AI Research Agent API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_check": "/health"
    }
