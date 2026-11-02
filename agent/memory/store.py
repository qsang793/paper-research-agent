from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import replace
from typing import Protocol

from agent.memory.models import (
    ChatMessageRecord,
    ChatSessionRecord,
    MemoryItemRecord,
    MessageRole,
    MessageSourceRecord,
    SessionSummaryRecord,
    new_id,
    now_ts,
)


_MEMORY_SEARCH_STOPWORDS = frozenset(
    {
        "and",
        "are",
        "for",
        "that",
        "the",
        "this",
        "was",
        "were",
        "with",
        "you",
        "your",
    }
)


def _copy_session(session: ChatSessionRecord) -> ChatSessionRecord:
    return replace(session)


def _copy_message(message: ChatMessageRecord) -> ChatMessageRecord:
    return replace(message, metadata=copy.deepcopy(message.metadata))


def _copy_source(source: MessageSourceRecord) -> MessageSourceRecord:
    return replace(source, metadata=copy.deepcopy(source.metadata))


def _copy_summary(summary: SessionSummaryRecord) -> SessionSummaryRecord:
    return replace(summary)


def _copy_memory_item(item: MemoryItemRecord) -> MemoryItemRecord:
    return replace(item, metadata=copy.deepcopy(item.metadata))


def _has_valid_memory_owner(item: MemoryItemRecord, sessions: dict[str, ChatSessionRecord]) -> bool:
    if item.scope == "session":
        if item.session_id is None:
            return False
        session = sessions.get(item.session_id)
        return bool(session and session.deleted_at is None)
    if item.scope == "user":
        return item.user_id is not None
    return True


def _same_memory_owner(left: MemoryItemRecord, right: MemoryItemRecord) -> bool:
    if left.scope != right.scope:
        return False
    if left.scope == "session":
        return left.session_id is not None and left.session_id == right.session_id
    if left.scope == "user":
        return left.user_id is not None and left.user_id == right.user_id
    return left.session_id == right.session_id and left.user_id == right.user_id


class MemoryStore(Protocol):
    def ensure_session(self, session_id: str, user_id: str | None = None) -> ChatSessionRecord: ...
    def append_message(self, session_id: str, role: MessageRole, content: str) -> ChatMessageRecord: ...
    def get_recent_messages(self, session_id: str, limit: int) -> list[ChatMessageRecord]: ...
    def add_message_sources(self, message_id: str, sources: list[MessageSourceRecord]) -> None: ...
    def get_message_sources(self, message_id: str) -> list[MessageSourceRecord]: ...
    def get_session_summary(self, session_id: str) -> SessionSummaryRecord | None: ...
    def upsert_session_summary(self, summary: SessionSummaryRecord) -> None: ...
    def upsert_memory_item(self, item: MemoryItemRecord) -> MemoryItemRecord: ...
    def replace_active_memory_item(self, item: MemoryItemRecord) -> MemoryItemRecord: ...
    def search_memory_items(self, query: str, session_id: str | None, user_id: str | None, limit: int) -> list[MemoryItemRecord]: ...
    def get_user_memory_items(self, user_id: str, limit: int) -> list[MemoryItemRecord]: ...
    def delete_session(self, session_id: str) -> bool: ...


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self.sessions: dict[str, ChatSessionRecord] = {}
        self.messages: dict[str, list[ChatMessageRecord]] = defaultdict(list)
        self.message_sessions: dict[str, str] = {}
        self.sources: dict[str, list[MessageSourceRecord]] = defaultdict(list)
        self.summaries: dict[str, SessionSummaryRecord] = {}
        self.memory_items: dict[str, MemoryItemRecord] = {}

    def ensure_session(self, session_id: str, user_id: str | None = None) -> ChatSessionRecord:
        existing = self.sessions.get(session_id)
        if existing and existing.deleted_at is None:
            if existing.user_id is not None and user_id is not None and existing.user_id != user_id:
                raise ValueError("active session belongs to a different user")
            return _copy_session(existing)
        if existing and existing.deleted_at is not None:
            self._clear_session_data(session_id)
        session = ChatSessionRecord(id=session_id, user_id=user_id)
        self.sessions[session_id] = session
        return _copy_session(session)

    def append_message(self, session_id: str, role: MessageRole, content: str) -> ChatMessageRecord:
        self.ensure_session(session_id)
        message = ChatMessageRecord(
            id=new_id("msg"),
            session_id=session_id,
            role=role,
            content=content,
        )
        self.messages[session_id].append(_copy_message(message))
        self.message_sessions[message.id] = session_id
        current = self.sessions[session_id]
        self.sessions[session_id] = ChatSessionRecord(
            id=current.id,
            user_id=current.user_id,
            created_at=current.created_at,
            updated_at=now_ts(),
            deleted_at=current.deleted_at,
        )
        return _copy_message(message)

    def get_recent_messages(self, session_id: str, limit: int) -> list[ChatMessageRecord]:
        if limit <= 0:
            return []
        session = self.sessions.get(session_id)
        if not session or session.deleted_at is not None:
            return []
        return [_copy_message(message) for message in self.messages.get(session_id, [])[-limit:]]

    def add_message_sources(self, message_id: str, sources: list[MessageSourceRecord]) -> None:
        session_id = self.message_sessions.get(message_id)
        session = self.sessions.get(session_id) if session_id else None
        if not session or session.deleted_at is not None:
            raise ValueError("message source parent message must exist in an active session")
        for source in sources:
            if source.message_id != message_id:
                raise ValueError("message source message_id must match message_id")
        self.sources[message_id].extend(_copy_source(source) for source in sources)

    def get_message_sources(self, message_id: str) -> list[MessageSourceRecord]:
        return [_copy_source(source) for source in self.sources.get(message_id, [])]

    def get_session_summary(self, session_id: str) -> SessionSummaryRecord | None:
        summary = self.summaries.get(session_id)
        return _copy_summary(summary) if summary else None

    def upsert_session_summary(self, summary: SessionSummaryRecord) -> None:
        session = self.sessions.get(summary.session_id)
        if not session or session.deleted_at is not None:
            raise ValueError("session summary parent session must exist and be active")
        self.summaries[summary.session_id] = _copy_summary(summary)

    def upsert_memory_item(self, item: MemoryItemRecord) -> MemoryItemRecord:
        self._validate_memory_item(item)
        stored = _copy_memory_item(item)
        self.memory_items[item.id] = stored
        return _copy_memory_item(stored)

    def replace_active_memory_item(self, item: MemoryItemRecord) -> MemoryItemRecord:
        """Persist an active keyed memory and supersede older active values.

        Historical rows stay in storage. Existing retrieval APIs only expose
        active items, so callers get one current value while audit/history can
        still inspect superseded records.
        """
        self._validate_memory_item(item)
        if not item.memory_key:
            return self.upsert_memory_item(item)
        if item.status != "active":
            raise ValueError("replacement memory item must be active")

        timestamp = item.updated_at
        for item_id, existing in list(self.memory_items.items()):
            if item_id == item.id:
                continue
            if existing.status != "active":
                continue
            if existing.memory_key != item.memory_key:
                continue
            if not _same_memory_owner(existing, item):
                continue
            self.memory_items[item_id] = replace(
                existing,
                status="superseded",
                superseded_by_id=item.id,
                superseded_at=timestamp,
                updated_at=timestamp,
            )

        stored = _copy_memory_item(item)
        self.memory_items[item.id] = stored
        return _copy_memory_item(stored)

    def search_memory_items(
        self,
        query: str,
        session_id: str | None,
        user_id: str | None,
        limit: int,
    ) -> list[MemoryItemRecord]:
        if limit <= 0:
            return []
        query_tokens = [
            token
            for token in query.strip().lower().split()
            if len(token) >= 3 and token not in _MEMORY_SEARCH_STOPWORDS
        ]
        if not query_tokens:
            return []
        matches = []
        for item in self.memory_items.values():
            if item.status != "active":
                continue
            if not _has_valid_memory_owner(item, self.sessions):
                continue
            if not self._has_valid_memory_source(item):
                continue
            if item.scope == "session":
                parent_session = self.sessions.get(item.session_id) if item.session_id else None
                if not parent_session or parent_session.deleted_at is not None:
                    continue
                if parent_session.user_id is not None and parent_session.user_id != user_id:
                    continue
            if item.session_id is not None and item.session_id != session_id:
                continue
            if item.user_id is not None and item.user_id != user_id:
                continue
            item_text = item.text.lower()
            if any(token in item_text for token in query_tokens):
                matches.append(_copy_memory_item(item))
        matches.sort(key=lambda item: item.updated_at, reverse=True)
        return matches[:limit]

    def get_user_memory_items(self, user_id: str, limit: int) -> list[MemoryItemRecord]:
        """Return bounded active user-scoped profile memories without query matching."""
        if not user_id or limit <= 0:
            return []
        matches = [
            _copy_memory_item(item)
            for item in self.memory_items.values()
            if item.scope == "user"
            and item.status == "active"
            and item.user_id == user_id
            and _has_valid_memory_owner(item, self.sessions)
            and self._has_valid_memory_source(item)
        ]
        matches.sort(key=lambda item: item.updated_at, reverse=True)
        return matches[:limit]

    def delete_session(self, session_id: str) -> bool:
        current = self.sessions.get(session_id)
        if not current or current.deleted_at is not None:
            return False
        self.sessions[session_id] = ChatSessionRecord(
            id=current.id,
            user_id=current.user_id,
            created_at=current.created_at,
            updated_at=now_ts(),
            deleted_at=now_ts(),
        )
        self._clear_session_data(session_id)
        return True

    def _validate_memory_item(self, item: MemoryItemRecord) -> None:
        if not _has_valid_memory_owner(item, self.sessions):
            raise ValueError("memory item scope requires a valid owner")
        if item.status not in {"active", "superseded"}:
            raise ValueError("invalid memory item status")
        if item.status == "active" and (item.superseded_by_id or item.superseded_at):
            raise ValueError("active memory item cannot contain supersession metadata")
        if item.status == "superseded" and not item.superseded_by_id:
            raise ValueError("superseded memory item requires superseded_by_id")
        self._validate_memory_source_message(item)

    def _clear_session_data(self, session_id: str) -> None:
        self.messages.pop(session_id, None)
        deleted_message_ids = set()
        for message_id, message_session_id in list(self.message_sessions.items()):
            if message_session_id == session_id:
                deleted_message_ids.add(message_id)
                self.sources.pop(message_id, None)
                self.message_sessions.pop(message_id, None)
        self.summaries.pop(session_id, None)
        self.memory_items = {
            item_id: item
            for item_id, item in self.memory_items.items()
            if item.session_id != session_id and item.source_message_id not in deleted_message_ids
        }

    def _validate_memory_source_message(self, item: MemoryItemRecord) -> None:
        if item.source_message_id is None:
            return

        source_context = self._active_source_context(item.source_message_id)
        if source_context is None:
            raise ValueError("memory item source_message_id must refer to a message in an active session")
        source_session_id, source_session = source_context
        if item.session_id is not None and item.session_id != source_session_id:
            raise ValueError("memory item source_message_id must belong to the same session")
        if item.scope == "session" and item.session_id == source_session_id:
            return
        if source_session.user_id is not None and item.user_id != source_session.user_id:
            raise ValueError("memory item source_message_id belongs to a different user")

    def _has_valid_memory_source(self, item: MemoryItemRecord) -> bool:
        if item.source_message_id is None:
            return True
        source_context = self._active_source_context(item.source_message_id)
        if source_context is None:
            return False
        source_session_id, source_session = source_context
        if item.session_id is not None and item.session_id != source_session_id:
            return False
        if item.scope == "session" and item.session_id == source_session_id:
            return True
        return source_session.user_id is None or item.user_id == source_session.user_id

    def _active_source_context(self, source_message_id: str) -> tuple[str, ChatSessionRecord] | None:
        source_session_id = self.message_sessions.get(source_message_id)
        source_session = self.sessions.get(source_session_id) if source_session_id else None
        if (
            source_session_id is None
            or not source_session
            or source_session.deleted_at is not None
            or not any(message.id == source_message_id for message in self.messages.get(source_session_id, []))
        ):
            return None
        return source_session_id, source_session
