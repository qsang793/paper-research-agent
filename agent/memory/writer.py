from __future__ import annotations

import re
from typing import Literal

from agent.memory.models import MemoryItemRecord, new_id
from agent.memory.store import MemoryStore


SENSITIVE_TERMS = {
    "api key",
    "apikey",
    "password",
    "secret",
    "token",
    "private key",
}

MemoryScope = Literal["session", "user"]


class MemoryWriter:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def write_candidate(
        self,
        *,
        text: str,
        session_id: str | None,
        user_id: str | None,
        source_message_id: str | None,
        scope: MemoryScope = "session",
        memory_key: str | None = None,
    ) -> MemoryItemRecord | None:
        normalized = " ".join(text.strip().split())
        if not normalized:
            return None
        if _contains_sensitive_term(normalized):
            return None
        if scope == "user" and user_id is None:
            return None
        if session_id:
            try:
                self.store.ensure_session(session_id, user_id=user_id)
            except ValueError:
                return None
        elif scope == "session" or user_id is None:
            return None

        item_session_id = session_id if scope == "session" else None
        normalized_key = _normalize_memory_key(memory_key)
        existing = self.store.search_memory_items(
            normalized,
            session_id=item_session_id,
            user_id=user_id,
            limit=50,
        )
        for item in existing:
            if (
                item.scope == scope
                and item.memory_key == normalized_key
                and " ".join(item.text.strip().split()).casefold() == normalized.casefold()
            ):
                return item

        item = MemoryItemRecord(
            id=new_id("mem"),
            scope=scope,
            text=normalized,
            session_id=item_session_id,
            user_id=user_id,
            source_message_id=source_message_id,
            confidence=0.9 if scope == "user" else 0.8,
            privacy_class="normal",
            memory_key=normalized_key,
            status="active",
        )
        if normalized_key:
            return self.store.replace_active_memory_item(item)
        return self.store.upsert_memory_item(item)


def _normalize_memory_key(value: str | None) -> str | None:
    """Normalize a router-provided semantic key without inferring its meaning."""
    if value is None:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if not normalized:
        return None
    return normalized[:80]


def _contains_sensitive_term(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    padded = f" {normalized} "
    compact = normalized.replace(" ", "")
    for term in SENSITIVE_TERMS:
        normalized_term = re.sub(r"[^a-z0-9]+", " ", term).strip()
        if f" {normalized_term} " in padded:
            return True
        compact_term = normalized_term.replace(" ", "")
        if " " in normalized_term and compact_term in compact:
            return True
        if normalized_term == "apikey" and compact_term in compact:
            return True
    return False
