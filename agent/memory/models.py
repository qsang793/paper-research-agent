from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


MessageRole = Literal["user", "assistant", "system", "tool"]
MemoryStatus = Literal["active", "superseded"]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def now_ts() -> int:
    return int(time.time())


@dataclass(frozen=True)
class ChatSessionRecord:
    id: str
    user_id: str | None = None
    created_at: int = field(default_factory=now_ts)
    updated_at: int = field(default_factory=now_ts)
    deleted_at: int | None = None


@dataclass(frozen=True)
class ChatMessageRecord:
    id: str
    session_id: str
    role: MessageRole
    content: str
    created_at: int = field(default_factory=now_ts)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MessageSourceRecord:
    message_id: str
    title: str
    url: str
    source_type: str = "source"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionSummaryRecord:
    session_id: str
    summary: str
    source_message_id: str | None = None
    updated_at: int = field(default_factory=now_ts)


@dataclass(frozen=True)
class MemoryItemRecord:
    id: str
    scope: Literal["session", "user", "project", "research_topic"]
    text: str
    session_id: str | None = None
    user_id: str | None = None
    source_message_id: str | None = None
    confidence: float = 1.0
    privacy_class: Literal["normal", "sensitive"] = "normal"
    memory_key: str | None = None
    status: MemoryStatus = "active"
    superseded_by_id: str | None = None
    superseded_at: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: int = field(default_factory=now_ts)
    updated_at: int = field(default_factory=now_ts)
