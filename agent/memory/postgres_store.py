from __future__ import annotations

import json
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

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


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    deleted_at BIGINT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    position BIGSERIAL UNIQUE,
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chat_messages_role_check CHECK (
        role IN ('user', 'assistant', 'system', 'tool')
    )
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
ON chat_messages(session_id, position);

CREATE TABLE IF NOT EXISTS message_sources (
    id BIGSERIAL PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_message_sources_message_id
ON message_sources(message_id);

CREATE TABLE IF NOT EXISTS session_summaries (
    session_id TEXT PRIMARY KEY REFERENCES chat_sessions(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    source_message_id TEXT REFERENCES chat_messages(id) ON DELETE SET NULL,
    updated_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    text TEXT NOT NULL,
    session_id TEXT REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id TEXT,
    source_message_id TEXT REFERENCES chat_messages(id) ON DELETE CASCADE,
    confidence DOUBLE PRECISION NOT NULL,
    privacy_class TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    CONSTRAINT memory_items_scope_check CHECK (
        scope IN ('session', 'user', 'project', 'research_topic')
    ),
    CONSTRAINT memory_items_privacy_class_check CHECK (
        privacy_class IN ('normal', 'sensitive')
    ),
    CONSTRAINT memory_items_scope_owner CHECK (
        (scope <> 'session' OR session_id IS NOT NULL)
        AND (scope <> 'user' OR user_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_memory_items_session_user
ON memory_items(session_id, user_id);

CREATE INDEX IF NOT EXISTS idx_memory_items_source_message
ON memory_items(source_message_id);

CREATE TABLE IF NOT EXISTS memory_item_lifecycle (
    memory_id TEXT PRIMARY KEY REFERENCES memory_items(id) ON DELETE CASCADE,
    memory_key TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    superseded_by_id TEXT,
    superseded_at BIGINT,
    CONSTRAINT memory_item_lifecycle_status_check CHECK (
        status IN ('active', 'superseded')
    ),
    CONSTRAINT memory_item_lifecycle_supersession_check CHECK (
        (status = 'active' AND superseded_by_id IS NULL AND superseded_at IS NULL)
        OR (status = 'superseded' AND superseded_by_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_memory_item_lifecycle_key_status
ON memory_item_lifecycle(memory_key, status);
"""


GET_RECENT_MESSAGES_SQL = """
SELECT m.id, m.session_id, m.role, m.content, m.created_at, m.metadata
FROM chat_messages AS m
JOIN chat_sessions AS s
  ON s.id = m.session_id
 AND s.deleted_at IS NULL
WHERE m.session_id = %s
ORDER BY m.position DESC
LIMIT %s
"""


ADD_MESSAGE_SOURCE_SQL = """
WITH source_input(message_id, title, url, source_type, metadata) AS (
    VALUES (%s, %s, %s, %s, %s::jsonb)
)
INSERT INTO message_sources (message_id, title, url, source_type, metadata)
SELECT source_input.message_id,
       source_input.title,
       source_input.url,
       source_input.source_type,
       source_input.metadata
FROM source_input
JOIN chat_messages AS source_message
  ON source_message.id = source_input.message_id
JOIN chat_sessions AS source_session
  ON source_session.id = source_message.session_id
 AND source_session.deleted_at IS NULL
RETURNING message_id
"""


GET_MESSAGE_SOURCES_SQL = """
SELECT src.message_id, src.title, src.url, src.source_type, src.metadata
FROM message_sources AS src
JOIN chat_messages AS source_message
  ON source_message.id = src.message_id
JOIN chat_sessions AS source_session
  ON source_session.id = source_message.session_id
 AND source_session.deleted_at IS NULL
WHERE src.message_id = %s
ORDER BY src.id ASC
"""


GET_SESSION_SUMMARY_SQL = """
SELECT summary.session_id,
       summary.summary,
       summary.source_message_id,
       summary.updated_at
FROM session_summaries AS summary
JOIN chat_sessions AS session_parent
  ON session_parent.id = summary.session_id
 AND session_parent.deleted_at IS NULL
LEFT JOIN chat_messages AS source_message
  ON source_message.id = summary.source_message_id
LEFT JOIN chat_sessions AS source_session
  ON source_session.id = source_message.session_id
WHERE summary.session_id = %s
  AND (
      summary.source_message_id IS NULL
      OR (
          source_message.session_id = summary.session_id
          AND source_session.deleted_at IS NULL
      )
  )
"""


UPSERT_SESSION_SUMMARY_SQL = """
WITH summary_input(session_id, summary, source_message_id, updated_at) AS (
    VALUES (%s, %s, %s, %s)
),
validated_summary AS (
    SELECT summary_input.session_id,
           summary_input.summary,
           summary_input.source_message_id,
           summary_input.updated_at
    FROM summary_input
    JOIN chat_sessions AS session_parent
      ON session_parent.id = summary_input.session_id
     AND session_parent.deleted_at IS NULL
    LEFT JOIN chat_messages AS source_message
      ON source_message.id = summary_input.source_message_id
    LEFT JOIN chat_sessions AS source_session
      ON source_session.id = source_message.session_id
    WHERE summary_input.source_message_id IS NULL
       OR (
           source_message.session_id = summary_input.session_id
           AND source_session.deleted_at IS NULL
       )
)
INSERT INTO session_summaries (session_id, summary, source_message_id, updated_at)
SELECT session_id, summary, source_message_id, updated_at
FROM validated_summary
ON CONFLICT (session_id) DO UPDATE
SET summary = EXCLUDED.summary,
    source_message_id = EXCLUDED.source_message_id,
    updated_at = EXCLUDED.updated_at
RETURNING session_id
"""


UPSERT_MEMORY_ITEM_SQL = """
WITH memory_input(
    id,
    scope,
    text,
    session_id,
    user_id,
    source_message_id,
    confidence,
    privacy_class,
    metadata,
    created_at,
    updated_at
) AS (
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
),
validated_memory AS (
    SELECT memory_input.id,
           memory_input.scope,
           memory_input.text,
           memory_input.session_id,
           memory_input.user_id,
           memory_input.source_message_id,
           memory_input.confidence,
           memory_input.privacy_class,
           memory_input.metadata,
           memory_input.created_at,
           memory_input.updated_at
    FROM memory_input
    LEFT JOIN chat_sessions AS parent_session
      ON parent_session.id = memory_input.session_id
    LEFT JOIN chat_messages AS source_message
      ON source_message.id = memory_input.source_message_id
    LEFT JOIN chat_sessions AS source_session
      ON source_session.id = source_message.session_id
    WHERE (
          memory_input.session_id IS NULL
          OR (
              parent_session.id IS NOT NULL
              AND parent_session.deleted_at IS NULL
          )
      )
      AND (
          memory_input.scope <> 'session'
          OR (
              memory_input.session_id IS NOT NULL
              AND parent_session.id IS NOT NULL
              AND parent_session.deleted_at IS NULL
          )
      )
      AND (memory_input.scope <> 'user' OR memory_input.user_id IS NOT NULL)
      AND (
          memory_input.source_message_id IS NULL
          OR (
              source_message.id IS NOT NULL
              AND source_session.deleted_at IS NULL
              AND (
                  memory_input.session_id IS NULL
                  OR source_message.session_id = memory_input.session_id
              )
              AND (
                  (
                      memory_input.scope = 'session'
                      AND source_message.session_id = memory_input.session_id
                  )
                  OR source_session.user_id IS NULL
                  OR memory_input.user_id = source_session.user_id
              )
          )
      )
)
INSERT INTO memory_items (
    id,
    scope,
    text,
    session_id,
    user_id,
    source_message_id,
    confidence,
    privacy_class,
    metadata,
    created_at,
    updated_at
)
SELECT id,
       scope,
       text,
       session_id,
       user_id,
       source_message_id,
       confidence,
       privacy_class,
       metadata,
       created_at,
       updated_at
FROM validated_memory
ON CONFLICT (id) DO UPDATE
SET scope = EXCLUDED.scope,
    text = EXCLUDED.text,
    session_id = EXCLUDED.session_id,
    user_id = EXCLUDED.user_id,
    source_message_id = EXCLUDED.source_message_id,
    confidence = EXCLUDED.confidence,
    privacy_class = EXCLUDED.privacy_class,
    metadata = EXCLUDED.metadata,
    updated_at = EXCLUDED.updated_at
RETURNING id, scope, text, session_id, user_id, source_message_id, confidence,
          privacy_class, metadata, created_at, updated_at
"""


UPSERT_MEMORY_LIFECYCLE_SQL = """
INSERT INTO memory_item_lifecycle (
    memory_id,
    memory_key,
    status,
    superseded_by_id,
    superseded_at
)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (memory_id) DO UPDATE
SET memory_key = EXCLUDED.memory_key,
    status = EXCLUDED.status,
    superseded_by_id = EXCLUDED.superseded_by_id,
    superseded_at = EXCLUDED.superseded_at
"""


SUPERSEDE_ACTIVE_MEMORY_ITEMS_SQL = """
WITH replacement(scope, session_id, user_id, memory_key, replacement_id, superseded_at) AS (
    VALUES (%s, %s, %s, %s, %s, %s)
)
UPDATE memory_item_lifecycle AS lifecycle
SET status = 'superseded',
    superseded_by_id = replacement.replacement_id,
    superseded_at = replacement.superseded_at
FROM memory_items AS existing, replacement
WHERE existing.id = lifecycle.memory_id
  AND lifecycle.status = 'active'
  AND lifecycle.memory_key = replacement.memory_key
  AND lifecycle.memory_id <> replacement.replacement_id
  AND existing.scope = replacement.scope
  AND existing.session_id IS NOT DISTINCT FROM replacement.session_id
  AND existing.user_id IS NOT DISTINCT FROM replacement.user_id
"""


SEARCH_MEMORY_ITEMS_SQL = """
WITH query_tokens(token) AS (
    SELECT unnest(%s::text[])
)
SELECT memory_items.id,
       memory_items.scope,
       memory_items.text,
       memory_items.session_id,
       memory_items.user_id,
       memory_items.source_message_id,
       memory_items.confidence,
       memory_items.privacy_class,
       lifecycle.memory_key,
       COALESCE(lifecycle.status, 'active') AS status,
       lifecycle.superseded_by_id,
       lifecycle.superseded_at,
       memory_items.metadata,
       memory_items.created_at,
       memory_items.updated_at
FROM memory_items
LEFT JOIN memory_item_lifecycle AS lifecycle
  ON lifecycle.memory_id = memory_items.id
LEFT JOIN chat_sessions AS parent_session
  ON parent_session.id = memory_items.session_id
LEFT JOIN chat_messages AS source_message
  ON source_message.id = memory_items.source_message_id
LEFT JOIN chat_sessions AS source_session
  ON source_session.id = source_message.session_id
WHERE EXISTS (
    SELECT 1
    FROM query_tokens
    WHERE memory_items.text ILIKE ('%%' || query_tokens.token || '%%') ESCAPE '\\'
)
  AND COALESCE(lifecycle.status, 'active') = 'active'
  AND (
      (
          memory_items.scope = 'session'
          AND memory_items.session_id IS NOT NULL
          AND parent_session.deleted_at IS NULL
          AND (parent_session.user_id IS NULL OR parent_session.user_id = %s)
      )
      OR (memory_items.scope = 'user' AND memory_items.user_id IS NOT NULL)
      OR memory_items.scope IN ('project', 'research_topic')
  )
  AND (
      memory_items.session_id IS NULL
      OR (%s::text IS NOT NULL AND memory_items.session_id = %s)
  )
  AND (
      memory_items.user_id IS NULL
      OR (%s::text IS NOT NULL AND memory_items.user_id = %s)
  )
  AND (
      memory_items.source_message_id IS NULL
      OR (
          source_message.id IS NOT NULL
          AND source_session.deleted_at IS NULL
          AND (
              memory_items.session_id IS NULL
              OR source_message.session_id = memory_items.session_id
          )
          AND (
              (
                  memory_items.scope = 'session'
                  AND source_message.session_id = memory_items.session_id
              )
              OR source_session.user_id IS NULL
              OR memory_items.user_id = source_session.user_id
          )
      )
  )
ORDER BY memory_items.updated_at DESC
LIMIT %s
"""


DELETE_SESSION_SQL = """
WITH target_session AS (
    UPDATE chat_sessions
    SET deleted_at = %s,
        updated_at = %s
    WHERE id = %s
      AND deleted_at IS NULL
    RETURNING id
),
deleted_messages AS (
    DELETE FROM chat_messages
    WHERE session_id IN (SELECT id FROM target_session)
    RETURNING id
),
deleted_summaries AS (
    DELETE FROM session_summaries
    WHERE session_id IN (SELECT id FROM target_session)
    RETURNING session_id
),
deleted_memory_items AS (
    DELETE FROM memory_items
    WHERE session_id IN (SELECT id FROM target_session)
       OR source_message_id IN (SELECT id FROM deleted_messages)
    RETURNING id
)
SELECT COUNT(*) AS deleted_count
FROM target_session
"""


_SELECT_SESSION_FOR_UPDATE_SQL = """
SELECT id, user_id, created_at, updated_at, deleted_at
FROM chat_sessions
WHERE id = %s
FOR UPDATE
"""


_INSERT_SESSION_SQL = """
INSERT INTO chat_sessions (id, user_id, created_at, updated_at, deleted_at)
VALUES (%s, %s, %s, %s, NULL)
ON CONFLICT (id) DO NOTHING
RETURNING id, user_id, created_at, updated_at, deleted_at
"""


_RECREATE_SESSION_SQL = """
UPDATE chat_sessions
SET user_id = %s,
    updated_at = %s,
    deleted_at = NULL
WHERE id = %s
RETURNING id, user_id, created_at, updated_at, deleted_at
"""


_TOUCH_SESSION_SQL = """
UPDATE chat_sessions
SET updated_at = %s
WHERE id = %s
  AND deleted_at IS NULL
"""


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _query_tokens(query: str) -> list[str]:
    return [
        _escape_like_token(token)
        for token in query.strip().lower().split()
        if len(token) >= 3 and token not in _MEMORY_SEARCH_STOPWORDS
    ]


def _escape_like_token(token: str) -> str:
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return dict(value) if isinstance(value, Mapping) else {}


def _validate_memory_lifecycle(item: MemoryItemRecord) -> None:
    if item.status not in {"active", "superseded"}:
        raise ValueError("invalid memory item status")
    if item.status == "active" and (item.superseded_by_id or item.superseded_at):
        raise ValueError("active memory item cannot contain supersession metadata")
    if item.status == "superseded" and not item.superseded_by_id:
        raise ValueError("superseded memory item requires superseded_by_id")


def _session_from_row(row: Mapping[str, Any]) -> ChatSessionRecord:
    return ChatSessionRecord(
        id=row["id"],
        user_id=row["user_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
    )


def _message_from_row(row: Mapping[str, Any]) -> ChatMessageRecord:
    return ChatMessageRecord(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
        metadata=_metadata(row),
    )


def _source_from_row(row: Mapping[str, Any]) -> MessageSourceRecord:
    return MessageSourceRecord(
        message_id=row["message_id"],
        title=row["title"],
        url=row["url"],
        source_type=row["source_type"],
        metadata=_metadata(row),
    )


def _summary_from_row(row: Mapping[str, Any]) -> SessionSummaryRecord:
    return SessionSummaryRecord(
        session_id=row["session_id"],
        summary=row["summary"],
        source_message_id=row["source_message_id"],
        updated_at=row["updated_at"],
    )


def _memory_item_from_row(row: Mapping[str, Any]) -> MemoryItemRecord:
    return MemoryItemRecord(
        id=row["id"],
        scope=row["scope"],
        text=row["text"],
        session_id=row["session_id"],
        user_id=row["user_id"],
        source_message_id=row["source_message_id"],
        confidence=row["confidence"],
        privacy_class=row["privacy_class"],
        memory_key=row.get("memory_key"),
        status=row.get("status") or "active",
        superseded_by_id=row.get("superseded_by_id"),
        superseded_at=row.get("superseded_at"),
        metadata=_metadata(row),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresMemoryStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def setup(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            conn.execute(SCHEMA_SQL)

    def ensure_session(self, session_id: str, user_id: str | None = None) -> ChatSessionRecord:
        timestamp = now_ts()
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            inserted = conn.execute(
                _INSERT_SESSION_SQL,
                (session_id, user_id, timestamp, timestamp),
            ).fetchone()
            if inserted:
                return _session_from_row(inserted)
            existing = conn.execute(_SELECT_SESSION_FOR_UPDATE_SQL, (session_id,)).fetchone()
            if existing and existing["deleted_at"] is None:
                if existing["user_id"] is not None and user_id is not None and existing["user_id"] != user_id:
                    raise ValueError("active session belongs to a different user")
                return _session_from_row(existing)
            if existing:
                self._clear_session_data(conn, session_id)
                row = conn.execute(_RECREATE_SESSION_SQL, (user_id, timestamp, session_id)).fetchone()
            else:
                raise ValueError("session insert failed without an existing row")
        return _session_from_row(row)

    def append_message(self, session_id: str, role: MessageRole, content: str) -> ChatMessageRecord:
        self.ensure_session(session_id)
        message = ChatMessageRecord(
            id=new_id("msg"),
            session_id=session_id,
            role=role,
            content=content,
        )
        with psycopg.connect(self.database_url) as conn:
            inserted = conn.execute(
                """
                INSERT INTO chat_messages (id, session_id, role, content, created_at, metadata)
                SELECT %s, s.id, %s, %s, %s, %s::jsonb
                FROM chat_sessions AS s
                WHERE s.id = %s
                  AND s.deleted_at IS NULL
                RETURNING id
                """,
                (
                    message.id,
                    role,
                    content,
                    message.created_at,
                    _json(message.metadata),
                    session_id,
                ),
            ).fetchone()
            if inserted is None:
                raise ValueError("message parent session must exist and be active")
            if conn.execute(_TOUCH_SESSION_SQL, (message.created_at, session_id)).rowcount != 1:
                raise ValueError("message parent session must exist and be active")
        return message

    def get_recent_messages(self, session_id: str, limit: int) -> list[ChatMessageRecord]:
        if limit <= 0:
            return []
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            rows = conn.execute(GET_RECENT_MESSAGES_SQL, (session_id, limit)).fetchall()
        return [_message_from_row(row) for row in reversed(rows)]

    def add_message_sources(self, message_id: str, sources: list[MessageSourceRecord]) -> None:
        with psycopg.connect(self.database_url) as conn:
            for source in sources:
                if source.message_id != message_id:
                    raise ValueError("message source message_id must match message_id")
                row = conn.execute(
                    ADD_MESSAGE_SOURCE_SQL,
                    (
                        source.message_id,
                        source.title,
                        source.url,
                        source.source_type,
                        _json(source.metadata),
                    ),
                ).fetchone()
                if row is None:
                    raise ValueError("message source parent message must exist in an active session")

    def get_message_sources(self, message_id: str) -> list[MessageSourceRecord]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            rows = conn.execute(GET_MESSAGE_SOURCES_SQL, (message_id,)).fetchall()
        return [_source_from_row(row) for row in rows]

    def get_session_summary(self, session_id: str) -> SessionSummaryRecord | None:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            row = conn.execute(GET_SESSION_SUMMARY_SQL, (session_id,)).fetchone()
        return _summary_from_row(row) if row else None

    def upsert_session_summary(self, summary: SessionSummaryRecord) -> None:
        with psycopg.connect(self.database_url) as conn:
            row = conn.execute(
                UPSERT_SESSION_SUMMARY_SQL,
                (
                    summary.session_id,
                    summary.summary,
                    summary.source_message_id,
                    summary.updated_at,
                ),
            ).fetchone()
            if row is None:
                raise ValueError("session summary parent session must exist and be active")

    def _upsert_memory_item_row(
        self,
        conn: psycopg.Connection[Any],
        item: MemoryItemRecord,
    ) -> Mapping[str, Any]:
        row = conn.execute(
            UPSERT_MEMORY_ITEM_SQL,
            (
                item.id,
                item.scope,
                item.text,
                item.session_id,
                item.user_id,
                item.source_message_id,
                item.confidence,
                item.privacy_class,
                _json(item.metadata),
                item.created_at,
                item.updated_at,
            ),
        ).fetchone()
        if row is None:
            raise ValueError("memory item scope requires a valid owner")
        return row

    def _upsert_memory_lifecycle(
        self,
        conn: psycopg.Connection[Any],
        item: MemoryItemRecord,
    ) -> None:
        conn.execute(
            UPSERT_MEMORY_LIFECYCLE_SQL,
            (
                item.id,
                item.memory_key,
                item.status,
                item.superseded_by_id,
                item.superseded_at,
            ),
        )

    def upsert_memory_item(self, item: MemoryItemRecord) -> MemoryItemRecord:
        _validate_memory_lifecycle(item)
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            row = self._upsert_memory_item_row(conn, item)
            self._upsert_memory_lifecycle(conn, item)
        merged = dict(row)
        merged.update(
            memory_key=item.memory_key,
            status=item.status,
            superseded_by_id=item.superseded_by_id,
            superseded_at=item.superseded_at,
        )
        return _memory_item_from_row(merged)

    def replace_active_memory_item(self, item: MemoryItemRecord) -> MemoryItemRecord:
        _validate_memory_lifecycle(item)
        if not item.memory_key:
            return self.upsert_memory_item(item)
        if item.status != "active":
            raise ValueError("replacement memory item must be active")

        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            row = self._upsert_memory_item_row(conn, item)
            self._upsert_memory_lifecycle(conn, item)
            conn.execute(
                SUPERSEDE_ACTIVE_MEMORY_ITEMS_SQL,
                (
                    item.scope,
                    item.session_id,
                    item.user_id,
                    item.memory_key,
                    item.id,
                    item.updated_at,
                ),
            )
        merged = dict(row)
        merged.update(
            memory_key=item.memory_key,
            status="active",
            superseded_by_id=None,
            superseded_at=None,
        )
        return _memory_item_from_row(merged)

    def search_memory_items(
        self,
        query: str,
        session_id: str | None,
        user_id: str | None,
        limit: int,
    ) -> list[MemoryItemRecord]:
        if limit <= 0:
            return []
        tokens = _query_tokens(query)
        if not tokens:
            return []
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            rows = conn.execute(
                SEARCH_MEMORY_ITEMS_SQL,
                (
                    tokens,
                    user_id,
                    session_id,
                    session_id,
                    user_id,
                    user_id,
                    limit,
                ),
            ).fetchall()
        return [_memory_item_from_row(row) for row in rows]

    def delete_session(self, session_id: str) -> bool:
        timestamp = now_ts()
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            row = conn.execute(DELETE_SESSION_SQL, (timestamp, timestamp, session_id)).fetchone()
        return bool(row and row["deleted_count"] > 0)

    def _clear_session_data(self, conn: psycopg.Connection[Any], session_id: str) -> None:
        conn.execute(
            """
            WITH deleted_messages AS (
                DELETE FROM chat_messages
                WHERE session_id = %s
                RETURNING id
            ),
            deleted_summaries AS (
                DELETE FROM session_summaries
                WHERE session_id = %s
                RETURNING session_id
            ),
            deleted_memory_items AS (
                DELETE FROM memory_items
                WHERE session_id = %s
                   OR source_message_id IN (SELECT id FROM deleted_messages)
                RETURNING id
            )
            SELECT 1
            """,
            (session_id, session_id, session_id),
        )
