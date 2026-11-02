from __future__ import annotations

from typing import Any

from agent.memory.models import MemoryItemRecord


def get_user_profile_memories(
    store: Any,
    user_id: str | None,
    *,
    limit: int = 5,
) -> list[MemoryItemRecord]:
    """Return bounded active durable user memories independent of query tokens."""
    if not store or not user_id or limit <= 0:
        return []

    getter = getattr(store, "get_user_memory_items", None)
    if callable(getter):
        return list(getter(user_id, limit))

    database_url = getattr(store, "database_url", None)
    if not database_url:
        return []

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        return []

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT item.id,
                   item.scope,
                   item.text,
                   item.session_id,
                   item.user_id,
                   item.source_message_id,
                   item.confidence,
                   item.privacy_class,
                   lifecycle.memory_key,
                   COALESCE(lifecycle.status, 'active') AS status,
                   lifecycle.superseded_by_id,
                   lifecycle.superseded_at,
                   item.metadata,
                   item.created_at,
                   item.updated_at
            FROM memory_items AS item
            LEFT JOIN memory_item_lifecycle AS lifecycle
              ON lifecycle.memory_id = item.id
            LEFT JOIN chat_messages AS source_message
              ON source_message.id = item.source_message_id
            LEFT JOIN chat_sessions AS source_session
              ON source_session.id = source_message.session_id
            WHERE item.scope = 'user'
              AND item.user_id = %s
              AND item.session_id IS NULL
              AND COALESCE(lifecycle.status, 'active') = 'active'
              AND (
                  item.source_message_id IS NULL
                  OR (
                      source_message.id IS NOT NULL
                      AND source_session.deleted_at IS NULL
                      AND (source_session.user_id IS NULL OR source_session.user_id = item.user_id)
                  )
              )
            ORDER BY item.updated_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()

    return [
        MemoryItemRecord(
            id=row["id"],
            scope=row["scope"],
            text=row["text"],
            session_id=row["session_id"],
            user_id=row["user_id"],
            source_message_id=row["source_message_id"],
            confidence=row["confidence"],
            privacy_class=row["privacy_class"],
            memory_key=row["memory_key"],
            status=row["status"],
            superseded_by_id=row["superseded_by_id"],
            superseded_at=row["superseded_at"],
            metadata=dict(row["metadata"] or {}),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


def merge_memory_items(
    profile_items: list[MemoryItemRecord],
    relevant_items: list[MemoryItemRecord],
    *,
    limit: int,
) -> list[MemoryItemRecord]:
    """Merge active profile and query-relevant memories without duplicates."""
    if limit <= 0:
        return []
    merged: list[MemoryItemRecord] = []
    seen: set[str] = set()
    for item in [*profile_items, *relevant_items]:
        if item.status != "active" or item.id in seen:
            continue
        seen.add(item.id)
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged
