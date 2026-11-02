"""Conversation memory module for Stage 2 and production memory primitives."""

from .config import MemoryConfig
from .models import ChatMessageRecord, ChatSessionRecord, MemoryItemRecord, MessageSourceRecord, SessionSummaryRecord
from .store import InMemoryMemoryStore, MemoryStore

__all__ = [
    "ChatMessageRecord",
    "ChatSessionRecord",
    "ConversationEntry",
    "ConversationMemory",
    "InMemoryMemoryStore",
    "MemoryConfig",
    "MemoryItemRecord",
    "MemoryStore",
    "MessageSourceRecord",
    "SessionSummaryRecord",
    "inject_memory_context",
]


def __getattr__(name: str):
    if name in {"ConversationEntry", "ConversationMemory"}:
        from .conversation import ConversationEntry, ConversationMemory

        return {
            "ConversationEntry": ConversationEntry,
            "ConversationMemory": ConversationMemory,
        }[name]
    if name == "inject_memory_context":
        from .context import inject_memory_context

        return inject_memory_context
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
