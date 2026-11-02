from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass(frozen=True)
class MemoryConfig:
    persistent_transcript_enabled: bool = False
    session_summary_enabled: bool = False
    long_term_memory_enabled: bool = False
    research_memory_enabled: bool = False
    conversational_memory_enabled: bool = False
    database_url: str | None = None
    recent_message_limit: int = 8
    max_context_chars: int = 12000

    @classmethod
    def from_env(cls) -> "MemoryConfig":
        return cls(
            persistent_transcript_enabled=_env_bool("PERSISTENT_TRANSCRIPT_ENABLED"),
            session_summary_enabled=_env_bool("SESSION_SUMMARY_ENABLED"),
            long_term_memory_enabled=_env_bool("LONG_TERM_MEMORY_ENABLED"),
            research_memory_enabled=_env_bool("RESEARCH_MEMORY_ENABLED"),
            conversational_memory_enabled=_env_bool("CONVERSATIONAL_MEMORY_ENABLED"),
            database_url=os.getenv("MEMORY_DATABASE_URL") or None,
            recent_message_limit=_env_int("MEMORY_RECENT_MESSAGE_LIMIT", 8),
            max_context_chars=_env_int("MEMORY_MAX_CONTEXT_CHARS", 12000),
        )
