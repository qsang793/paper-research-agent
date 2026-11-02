from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from agent.memory.config import MemoryConfig
from api.internal_auth import require_internal_api_token
from api.routes import chat as chat_route

router = APIRouter(
    prefix="/api/memory",
    tags=["memory"],
    dependencies=[Depends(require_internal_api_token)],
)


@router.get("/features")
async def memory_features():
    config = MemoryConfig.from_env()
    backend, error = await asyncio.to_thread(_memory_store_status, config)
    return {
        "persistent_transcript_enabled": config.persistent_transcript_enabled,
        "session_summary_enabled": config.session_summary_enabled,
        "long_term_memory_enabled": config.long_term_memory_enabled,
        "research_memory_enabled": config.research_memory_enabled,
        "memory_store_backend": backend,
        "memory_store_error": error,
    }


@router.delete("/session/{session_id}")
async def delete_memory_session(session_id: str):
    try:
        local_deleted, persistent_deleted = await asyncio.to_thread(
            chat_route.delete_session_data, session_id
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Memory deletion failed") from exc
    if not local_deleted and not persistent_deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "deleted_local_session": local_deleted,
        "deleted_persistent_session": persistent_deleted,
    }


def _memory_store_status(config: MemoryConfig) -> tuple[str, str | None]:
    if not config.persistent_transcript_enabled:
        return "disabled", None
    store = chat_route._get_memory_store(config)
    if store is None:
        return "unavailable", chat_route.memory_store_error or "unknown initialization failure"
    return chat_route.memory_store_backend, None
