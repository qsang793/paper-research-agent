# Production Memory Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace prototype in-process chat memory with production-ready session identity, persistent transcript storage, context assembly, summaries, and controlled long-term memory for the research agent.

**Architecture:** Keep `agent/research/` as the canonical production RAG path and introduce a narrow memory layer beside it. The first production milestone is durable transcript + stable `session_id`; summary and long-term memory are feature-flagged follow-ups so each step can be shipped and rolled back independently.

**Tech Stack:** Python 3.12, FastAPI, pytest, uv, Next.js App Router, Vercel AI SDK stream protocol, PostgreSQL + pgvector for production storage, in-memory fakes for deterministic tests.

---

## Context

Current memory behavior is prototype-level:

- `api/routes/chat.py` owns `sessions: Dict[str, ConversationMemory]`.
- `ConversationMemory` stores query/answer/citations/embedding in process memory and evicts after 50 entries.
- `agent/memory/context.py::inject_memory_context` appends the last 5 entries plus top-2 semantically similar entries to the query.
- The web streaming path uses `useChat` and the Next.js proxy in `web/src/app/api/chat/route.ts`; it forwards only the latest user message and currently does not provide a stable backend `session_id`.
- Production RAG is `agent/research/`; legacy LangGraph and optional LlamaIndex paths are not the API path.

Desired production behavior:

- Browser chat sessions have stable ids and "new chat" creates a new id.
- Backend persists raw transcript and source events outside process memory.
- Context assembly has explicit sections and token budgets instead of appending arbitrary text to the query.
- Session summaries keep long conversations usable without sending the full transcript.
- Long-term memory is scoped, inspectable, deletable, and opt-in via feature flag.
- Research facts remain grounded in sources and are not confused with user preference memory.

## File Structure

New files:

- `docs/adr/ADR-001-production-memory-context.md` - architecture decision and rollback policy.
- `agent/memory/config.py` - environment-backed memory feature flags and limits.
- `agent/memory/models.py` - dataclasses for sessions, messages, sources, summaries, memory items, and assembled context.
- `agent/memory/store.py` - `MemoryStore` protocol and `InMemoryMemoryStore` test/runtime fallback.
- `agent/memory/postgres_store.py` - PostgreSQL-backed implementation used behind feature flags.
- `agent/memory/context_assembler.py` - builds structured context from recent messages, summary, retrieved memories, and research evidence.
- `agent/memory/summarizer.py` - deterministic summary prompts and summary update wrapper.
- `agent/memory/writer.py` - extracts and persists long-term memory candidates after answers.
- `api/routes/memory.py` - user/session memory inspection and deletion endpoints.
- `tests/test_memory_config.py`
- `tests/test_memory_store.py`
- `tests/test_memory_context_assembler.py`
- `tests/test_memory_writer.py`
- `tests/test_session_identity.py`
- `tests/test_persistent_transcript.py`

Modified files:

- `.env.example` - add memory flags and Postgres connection settings without secrets.
- `agent/memory/__init__.py` - export new memory primitives without breaking existing imports.
- `api/routes/chat.py` - replace direct `sessions` usage behind feature flags and persist transcript.
- `api/chat_orchestrator.py` - accept context assembly/store collaborators and persist assistant outputs.
- `api/main.py` - include `api.routes.memory` router.
- `web/src/app/chat/page.tsx` - create and pass stable `session_id`.
- `web/src/app/api/chat/route.ts` - forward `session_id` and normalize AI SDK message content.
- `web/src/lib/api.ts` - expose memory/session request types if needed by UI.

Do not touch:

- `.env`, `.env.*`, credentials, API keys, or local cache data.
- `agent/frameworks/llamaindex/**` unless a later explicit framework migration plan is approved.
- Legacy LangGraph files except tests that prove current behavior is preserved.

---

## Task 1: Record Architecture Decision and Flags

**Files:**
- Create: `docs/adr/ADR-001-production-memory-context.md`
- Create: `agent/memory/config.py`
- Modify: `.env.example`
- Modify: `agent/memory/__init__.py`
- Test: `tests/test_memory_config.py`

- [x] **Step 1: Write the failing config tests**

Create `tests/test_memory_config.py`:

```python
from agent.memory.config import MemoryConfig


def test_memory_config_defaults_are_safe(monkeypatch):
    for key in [
        "PERSISTENT_TRANSCRIPT_ENABLED",
        "SESSION_SUMMARY_ENABLED",
        "LONG_TERM_MEMORY_ENABLED",
        "RESEARCH_MEMORY_ENABLED",
        "MEMORY_DATABASE_URL",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = MemoryConfig.from_env()

    assert config.persistent_transcript_enabled is False
    assert config.session_summary_enabled is False
    assert config.long_term_memory_enabled is False
    assert config.research_memory_enabled is False
    assert config.database_url is None
    assert config.recent_message_limit == 8
    assert config.max_context_chars == 12000


def test_memory_config_parses_enabled_flags(monkeypatch):
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setenv("SESSION_SUMMARY_ENABLED", "1")
    monkeypatch.setenv("LONG_TERM_MEMORY_ENABLED", "yes")
    monkeypatch.setenv("RESEARCH_MEMORY_ENABLED", "on")
    monkeypatch.setenv("MEMORY_DATABASE_URL", "postgresql://user:pass@localhost:5432/research")
    monkeypatch.setenv("MEMORY_RECENT_MESSAGE_LIMIT", "6")
    monkeypatch.setenv("MEMORY_MAX_CONTEXT_CHARS", "9000")

    config = MemoryConfig.from_env()

    assert config.persistent_transcript_enabled is True
    assert config.session_summary_enabled is True
    assert config.long_term_memory_enabled is True
    assert config.research_memory_enabled is True
    assert config.database_url == "postgresql://user:pass@localhost:5432/research"
    assert config.recent_message_limit == 6
    assert config.max_context_chars == 9000
```

- [x] **Step 2: Run the focused test and verify it fails**

Run:

```bash
uv run pytest tests/test_memory_config.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'agent.memory.config'
```

- [x] **Step 3: Implement memory config**

Create `agent/memory/config.py`:

```python
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
            database_url=os.getenv("MEMORY_DATABASE_URL") or None,
            recent_message_limit=_env_int("MEMORY_RECENT_MESSAGE_LIMIT", 8),
            max_context_chars=_env_int("MEMORY_MAX_CONTEXT_CHARS", 12000),
        )
```

Update `agent/memory/__init__.py`:

```python
"""Conversation memory module for Stage 2 and production memory primitives."""

from .config import MemoryConfig
from .conversation import ConversationEntry, ConversationMemory
from .context import inject_memory_context

__all__ = [
    "ConversationEntry",
    "ConversationMemory",
    "MemoryConfig",
    "inject_memory_context",
]
```

- [x] **Step 4: Add environment template entries**

Append to `.env.example` after the API server section:

```dotenv
# ----- Memory / Conversation Context -----

PERSISTENT_TRANSCRIPT_ENABLED=false
SESSION_SUMMARY_ENABLED=false
LONG_TERM_MEMORY_ENABLED=false
RESEARCH_MEMORY_ENABLED=false
MEMORY_DATABASE_URL=
MEMORY_RECENT_MESSAGE_LIMIT=8
MEMORY_MAX_CONTEXT_CHARS=12000
```

- [x] **Step 5: Add the ADR**

Create `docs/adr/ADR-001-production-memory-context.md`:

```markdown
# ADR-001: Production Memory Context
Date: 2026-06-29
Status: Proposed

## Context

The chat API currently keeps conversation memory in process-local Python dictionaries.
That loses context on restart, does not work across multiple workers, and makes
streaming web sessions depend on backend-generated ids that the frontend does not
persist.

## Decision

Use a custom memory layer with a narrow `MemoryStore` interface. PostgreSQL plus
pgvector is the production storage target. In-memory storage remains available for
tests and for feature-flagged rollback. The canonical research workflow remains
`agent/research/`; LangGraph and LlamaIndex are not introduced as production
orchestration dependencies in this decision.

The memory rollout is feature-flagged in this order:

1. Stable session id propagation.
2. Persistent transcript storage.
3. Context assembly and session summary.
4. Long-term scoped memory.
5. Research-specific memory.

## Consequences

**Positive:** durable sessions, multi-worker compatibility, explicit rollback,
clear test surfaces, and no framework lock-in for citation/privacy policy.

**Negative:** more local code than adopting a managed memory framework.

**Risks:** schema drift, prompt bloat, and privacy leakage. These are mitigated
through feature flags, memory provenance, deletion endpoints, evals, and avoiding
plaintext secret logging.
```

- [x] **Step 6: Run tests**

Run:

```bash
uv run pytest tests/test_memory_config.py -q
```

Expected:

```text
2 passed
```

- [x] **Step 7: Commit**

```bash
git add .env.example agent/memory/__init__.py agent/memory/config.py docs/adr/ADR-001-production-memory-context.md tests/test_memory_config.py
git commit -m "docs(memory): define production memory rollout"
```

---

## Task 2: Add Stable Session Identity to the Web Chat

**Files:**
- Modify: `web/src/app/chat/page.tsx`
- Modify: `web/src/app/api/chat/route.ts`
- Test: `tests/test_session_identity.py`

- [x] **Step 1: Add backend proxy regression tests**

Create `tests/test_session_identity.py`:

```python
from api.models import ChatRequest


def test_chat_request_accepts_session_id():
    request = ChatRequest(
        query="What is RAG?",
        session_id="chat-abc",
        mode="auto",
        top_k=6,
    )

    assert request.session_id == "chat-abc"
```

- [x] **Step 2: Run focused backend test**

Run:

```bash
uv run pytest tests/test_session_identity.py -q
```

Expected:

```text
1 passed
```

- [x] **Step 3: Add frontend session id helper**

In `web/src/app/chat/page.tsx`, add this helper above `export default function ChatPage()`:

```tsx
function createChatSessionId(): string {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID();
    }
    return `chat-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
```

- [x] **Step 4: Store and send session id**

In `web/src/app/chat/page.tsx`, inside `ChatPage`, add state near the existing `searchMode` state:

```tsx
const [chatSessionId, setChatSessionId] = useState<string>(() => createChatSessionId());
```

Update the `send` call body:

```tsx
return sendMessage(
    { role: "user", content: text },
    {
        body: {
            session_id: chatSessionId,
            mode: searchMode,
            search_source: searchMode === "search" ? "research" : undefined,
        },
    }
);
```

Update `handleNewChat` so it creates a new id:

```tsx
const handleNewChat = () => {
    const nextSessionId = createChatSessionId();
    setChatSessionId(nextSessionId);
    if (typeof chatHelpers.setMessages === "function") {
        chatHelpers.setMessages([]);
        setInput("");
        setIsSidebarOpen(false);
    } else {
        window.location.reload();
    }
};
```

- [x] **Step 5: Harden the Next.js proxy message extraction**

In `web/src/app/api/chat/route.ts`, add this helper above `POST`:

```ts
function getMessageText(message: any): string {
    if (typeof message?.content === "string") return message.content;
    if (Array.isArray(message?.parts)) {
        return message.parts
            .filter((part: any) => part?.type === "text")
            .map((part: any) => part.text || "")
            .join("");
    }
    return "";
}
```

Replace:

```ts
const query = lastMessage.content;
```

with:

```ts
const query = getMessageText(lastMessage);
```

Keep the request body spread so `session_id` is forwarded:

```ts
body: JSON.stringify({
    query: query,
    ...body
}),
```

- [x] **Step 6: Run verification**

Run:

```bash
uv run pytest tests/test_session_identity.py -q
cd web && npm run lint
```

Expected:

```text
1 passed
```

and `npm run lint` exits with status 0.

- [x] **Step 7: Commit**

```bash
git add tests/test_session_identity.py web/src/app/chat/page.tsx web/src/app/api/chat/route.ts
git commit -m "feat(chat): send stable session id from web client"
```

---

## Task 3: Add Memory Models and In-Memory Store

**Files:**
- Create: `agent/memory/models.py`
- Create: `agent/memory/store.py`
- Modify: `agent/memory/__init__.py`
- Test: `tests/test_memory_store.py`

- [x] **Step 1: Write failing store tests**

Create `tests/test_memory_store.py`:

```python
from agent.memory.models import ChatMessageRecord, MessageSourceRecord
from agent.memory.store import InMemoryMemoryStore


def test_in_memory_store_persists_messages_and_sources():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")

    user_message = store.append_message(
        session_id="s1",
        role="user",
        content="What is RAG?",
    )
    assistant_message = store.append_message(
        session_id="s1",
        role="assistant",
        content="RAG augments generation with retrieval.",
    )
    store.add_message_sources(
        assistant_message.id,
        [
            MessageSourceRecord(
                message_id=assistant_message.id,
                title="RAG paper",
                url="https://arxiv.org/abs/2005.11401",
                source_type="paper",
            )
        ],
    )

    messages = store.get_recent_messages("s1", limit=10)
    sources = store.get_message_sources(assistant_message.id)

    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "What is RAG?"
    assert sources[0].url == "https://arxiv.org/abs/2005.11401"
    assert user_message.id != assistant_message.id


def test_in_memory_store_soft_deletes_session():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id=None)
    store.append_message(session_id="s1", role="user", content="hello")

    assert store.delete_session("s1") is True
    assert store.get_recent_messages("s1", limit=10) == []
    assert store.delete_session("missing") is False
```

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_memory_store.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'agent.memory.models'
```

- [x] **Step 3: Add memory models**

Create `agent/memory/models.py`:

```python
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


MessageRole = Literal["user", "assistant", "system", "tool"]


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
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: int = field(default_factory=now_ts)
    updated_at: int = field(default_factory=now_ts)
```

- [x] **Step 4: Add the store protocol and in-memory adapter**

Create `agent/memory/store.py`:

```python
from __future__ import annotations

from collections import defaultdict
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


class MemoryStore(Protocol):
    def ensure_session(self, session_id: str, user_id: str | None = None) -> ChatSessionRecord: ...
    def append_message(self, session_id: str, role: MessageRole, content: str) -> ChatMessageRecord: ...
    def get_recent_messages(self, session_id: str, limit: int) -> list[ChatMessageRecord]: ...
    def add_message_sources(self, message_id: str, sources: list[MessageSourceRecord]) -> None: ...
    def get_message_sources(self, message_id: str) -> list[MessageSourceRecord]: ...
    def get_session_summary(self, session_id: str) -> SessionSummaryRecord | None: ...
    def upsert_session_summary(self, summary: SessionSummaryRecord) -> None: ...
    def upsert_memory_item(self, item: MemoryItemRecord) -> MemoryItemRecord: ...
    def search_memory_items(self, query: str, session_id: str | None, user_id: str | None, limit: int) -> list[MemoryItemRecord]: ...
    def delete_session(self, session_id: str) -> bool: ...


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self.sessions: dict[str, ChatSessionRecord] = {}
        self.messages: dict[str, list[ChatMessageRecord]] = defaultdict(list)
        self.sources: dict[str, list[MessageSourceRecord]] = defaultdict(list)
        self.summaries: dict[str, SessionSummaryRecord] = {}
        self.memory_items: dict[str, MemoryItemRecord] = {}

    def ensure_session(self, session_id: str, user_id: str | None = None) -> ChatSessionRecord:
        existing = self.sessions.get(session_id)
        if existing and existing.deleted_at is None:
            return existing
        session = ChatSessionRecord(id=session_id, user_id=user_id)
        self.sessions[session_id] = session
        return session

    def append_message(self, session_id: str, role: MessageRole, content: str) -> ChatMessageRecord:
        self.ensure_session(session_id)
        message = ChatMessageRecord(
            id=new_id("msg"),
            session_id=session_id,
            role=role,
            content=content,
        )
        self.messages[session_id].append(message)
        current = self.sessions[session_id]
        self.sessions[session_id] = ChatSessionRecord(
            id=current.id,
            user_id=current.user_id,
            created_at=current.created_at,
            updated_at=now_ts(),
            deleted_at=current.deleted_at,
        )
        return message

    def get_recent_messages(self, session_id: str, limit: int) -> list[ChatMessageRecord]:
        session = self.sessions.get(session_id)
        if not session or session.deleted_at is not None:
            return []
        return self.messages.get(session_id, [])[-limit:]

    def add_message_sources(self, message_id: str, sources: list[MessageSourceRecord]) -> None:
        self.sources[message_id].extend(sources)

    def get_message_sources(self, message_id: str) -> list[MessageSourceRecord]:
        return list(self.sources.get(message_id, []))

    def get_session_summary(self, session_id: str) -> SessionSummaryRecord | None:
        return self.summaries.get(session_id)

    def upsert_session_summary(self, summary: SessionSummaryRecord) -> None:
        self.summaries[summary.session_id] = summary

    def upsert_memory_item(self, item: MemoryItemRecord) -> MemoryItemRecord:
        self.memory_items[item.id] = item
        return item

    def search_memory_items(
        self,
        query: str,
        session_id: str | None,
        user_id: str | None,
        limit: int,
    ) -> list[MemoryItemRecord]:
        query_lower = query.lower()
        matches = []
        for item in self.memory_items.values():
            if session_id and item.session_id not in {None, session_id}:
                continue
            if user_id and item.user_id not in {None, user_id}:
                continue
            if query_lower in item.text.lower() or any(token in item.text.lower() for token in query_lower.split()):
                matches.append(item)
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
        return True
```

- [x] **Step 5: Export new primitives**

Update `agent/memory/__init__.py`:

```python
"""Conversation memory module for Stage 2 and production memory primitives."""

from .config import MemoryConfig
from .conversation import ConversationEntry, ConversationMemory
from .context import inject_memory_context
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
```

- [x] **Step 6: Run tests**

Run:

```bash
uv run pytest tests/test_memory_store.py tests/test_memory_config.py -q
```

Expected:

```text
4 passed
```

- [x] **Step 7: Commit**

```bash
git add agent/memory/__init__.py agent/memory/models.py agent/memory/store.py tests/test_memory_store.py
git commit -m "feat(memory): add store interface and in-memory adapter"
```

---

## Task 4: Add PostgreSQL Transcript Adapter Behind the Store Interface

**Files:**
- Create: `agent/memory/postgres_store.py`
- Modify: `pyproject.toml`
- Test: `tests/test_memory_store.py`

- [x] **Step 1: Add dependency**

In `pyproject.toml`, add this dependency to `[project].dependencies`:

```toml
"psycopg[binary]>=3.2.0,<4",
```

- [x] **Step 2: Add adapter construction test**

Append to `tests/test_memory_store.py`:

```python
def test_postgres_store_exposes_schema_sql_without_connection():
    from agent.memory.postgres_store import SCHEMA_SQL

    assert "CREATE TABLE IF NOT EXISTS chat_sessions" in SCHEMA_SQL
    assert "CREATE TABLE IF NOT EXISTS chat_messages" in SCHEMA_SQL
    assert "CREATE TABLE IF NOT EXISTS message_sources" in SCHEMA_SQL
    assert "CREATE TABLE IF NOT EXISTS session_summaries" in SCHEMA_SQL
    assert "CREATE TABLE IF NOT EXISTS memory_items" in SCHEMA_SQL
```

- [x] **Step 3: Run test to verify failure**

Run:

```bash
uv run pytest tests/test_memory_store.py::test_postgres_store_exposes_schema_sql_without_connection -q
```

Expected:

```text
ModuleNotFoundError: No module named 'agent.memory.postgres_store'
```

- [x] **Step 4: Implement schema SQL and adapter skeleton**

Create `agent/memory/postgres_store.py`:

```python
from __future__ import annotations

import json
from typing import Any

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


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    deleted_at BIGINT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
ON chat_messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS message_sources (
    id BIGSERIAL PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES chat_messages(id),
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_message_sources_message_id
ON message_sources(message_id);

CREATE TABLE IF NOT EXISTS session_summaries (
    session_id TEXT PRIMARY KEY REFERENCES chat_sessions(id),
    summary TEXT NOT NULL,
    source_message_id TEXT,
    updated_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    text TEXT NOT NULL,
    session_id TEXT,
    user_id TEXT,
    source_message_id TEXT,
    confidence DOUBLE PRECISION NOT NULL,
    privacy_class TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_items_session_user
ON memory_items(session_id, user_id);
"""


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


class PostgresMemoryStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def setup(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            conn.execute(SCHEMA_SQL)

    def ensure_session(self, session_id: str, user_id: str | None = None) -> ChatSessionRecord:
        timestamp = now_ts()
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions (id, user_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET updated_at = EXCLUDED.updated_at
                """,
                (session_id, user_id, timestamp, timestamp),
            )
            row = conn.execute("SELECT * FROM chat_sessions WHERE id = %s", (session_id,)).fetchone()
        return ChatSessionRecord(**row)

    def append_message(self, session_id: str, role: MessageRole, content: str) -> ChatMessageRecord:
        self.ensure_session(session_id)
        message = ChatMessageRecord(id=new_id("msg"), session_id=session_id, role=role, content=content)
        with psycopg.connect(self.database_url) as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (id, session_id, role, content, created_at, metadata)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (message.id, session_id, role, content, message.created_at, _json(message.metadata)),
            )
            conn.execute(
                "UPDATE chat_sessions SET updated_at = %s WHERE id = %s",
                (message.created_at, session_id),
            )
        return message

    def get_recent_messages(self, session_id: str, limit: int) -> list[ChatMessageRecord]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, role, content, created_at, metadata
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (session_id, limit),
            ).fetchall()
        return [ChatMessageRecord(**row) for row in reversed(rows)]

    def add_message_sources(self, message_id: str, sources: list[MessageSourceRecord]) -> None:
        with psycopg.connect(self.database_url) as conn:
            for source in sources:
                conn.execute(
                    """
                    INSERT INTO message_sources (message_id, title, url, source_type, metadata)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (message_id, source.title, source.url, source.source_type, _json(source.metadata)),
                )

    def get_message_sources(self, message_id: str) -> list[MessageSourceRecord]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            rows = conn.execute(
                """
                SELECT message_id, title, url, source_type, metadata
                FROM message_sources
                WHERE message_id = %s
                ORDER BY id ASC
                """,
                (message_id,),
            ).fetchall()
        return [MessageSourceRecord(**row) for row in rows]

    def get_session_summary(self, session_id: str) -> SessionSummaryRecord | None:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            row = conn.execute(
                "SELECT session_id, summary, source_message_id, updated_at FROM session_summaries WHERE session_id = %s",
                (session_id,),
            ).fetchone()
        return SessionSummaryRecord(**row) if row else None

    def upsert_session_summary(self, summary: SessionSummaryRecord) -> None:
        with psycopg.connect(self.database_url) as conn:
            conn.execute(
                """
                INSERT INTO session_summaries (session_id, summary, source_message_id, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE
                SET summary = EXCLUDED.summary,
                    source_message_id = EXCLUDED.source_message_id,
                    updated_at = EXCLUDED.updated_at
                """,
                (summary.session_id, summary.summary, summary.source_message_id, summary.updated_at),
            )

    def upsert_memory_item(self, item: MemoryItemRecord) -> MemoryItemRecord:
        with psycopg.connect(self.database_url) as conn:
            conn.execute(
                """
                INSERT INTO memory_items
                (id, scope, text, session_id, user_id, source_message_id, confidence, privacy_class, metadata, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET text = EXCLUDED.text,
                    confidence = EXCLUDED.confidence,
                    privacy_class = EXCLUDED.privacy_class,
                    metadata = EXCLUDED.metadata,
                    updated_at = EXCLUDED.updated_at
                """,
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
            )
        return item

    def search_memory_items(
        self,
        query: str,
        session_id: str | None,
        user_id: str | None,
        limit: int,
    ) -> list[MemoryItemRecord]:
        pattern = f"%{query}%"
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            rows = conn.execute(
                """
                SELECT id, scope, text, session_id, user_id, source_message_id, confidence,
                       privacy_class, metadata, created_at, updated_at
                FROM memory_items
                WHERE text ILIKE %s
                  AND (%s IS NULL OR session_id IS NULL OR session_id = %s)
                  AND (%s IS NULL OR user_id IS NULL OR user_id = %s)
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (pattern, session_id, session_id, user_id, user_id, limit),
            ).fetchall()
        return [MemoryItemRecord(**row) for row in rows]

    def delete_session(self, session_id: str) -> bool:
        timestamp = now_ts()
        with psycopg.connect(self.database_url) as conn:
            result = conn.execute(
                """
                UPDATE chat_sessions
                SET deleted_at = %s, updated_at = %s
                WHERE id = %s AND deleted_at IS NULL
                """,
                (timestamp, timestamp, session_id),
            )
        return result.rowcount > 0
```

- [x] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_memory_store.py -q
```

Expected:

```text
3 passed
```

- [x] **Step 6: Sync lockfile if dependency changed**

Run:

```bash
uv lock
```

Expected: `uv.lock` updates successfully.

- [x] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock agent/memory/postgres_store.py tests/test_memory_store.py
git commit -m "feat(memory): add postgres memory store"
```

---

## Task 5: Persist Transcript from Chat Routes

**Files:**
- Modify: `api/routes/chat.py`
- Modify: `api/chat_orchestrator.py`
- Test: `tests/test_persistent_transcript.py`
- Test: `tests/research/test_research_chat_integration.py`

- [x] **Step 1: Write transcript integration tests**

Create `tests/test_persistent_transcript.py`:

```python
from agent.memory.store import InMemoryMemoryStore
from api.chat_orchestrator import ResearchChatWorkflow


def test_research_workflow_persists_user_and_assistant_messages():
    store = InMemoryMemoryStore()

    def inject(query, memory):
        return query, ""

    def preview(query, top_k, providers, generate):
        return {
            "answer": "RAG combines retrieval and generation.",
            "answerability": {"can_answer": True},
            "sources": [
                {
                    "title": "RAG paper",
                    "url": "https://arxiv.org/abs/2005.11401",
                    "source_type": "paper",
                    "relevance_score": 1.0,
                }
            ],
        }

    workflow = ResearchChatWorkflow(
        inject_memory_context_fn=inject,
        run_preview_fn=preview,
        memory_store=store,
    )

    response = workflow.run_chat_response(
        "What is RAG?",
        session_id="s1",
        top_k=5,
        memory=None,
        start_time=0.0,
        now_fn=lambda: 1.0,
    )

    messages = store.get_recent_messages("s1", limit=10)
    assert response.answer == "RAG combines retrieval and generation."
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "What is RAG?"
    assert messages[1].content == "RAG combines retrieval and generation."
```

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_persistent_transcript.py -q
```

Expected:

```text
TypeError: ResearchChatWorkflow.__init__() got an unexpected keyword argument 'memory_store'
```

- [x] **Step 3: Update `ResearchChatWorkflow` constructor**

In `api/chat_orchestrator.py`, add `memory_store` to `__init__`:

```python
    def __init__(
        self,
        *,
        inject_memory_context_fn: Callable[..., tuple[str, str]],
        run_preview_fn: Callable[..., dict],
        to_chat_response_fn: Callable[..., Any] | None = None,
        to_source_events_fn: Callable[..., list[dict]] | None = None,
        memory_store: Any | None = None,
    ) -> None:
        self._inject_memory_context = inject_memory_context_fn
        self._run_preview = run_preview_fn
        self._to_chat_response = to_chat_response_fn or research_preview_to_chat_response
        self._to_source_events = to_source_events_fn or research_preview_to_source_events
        self._memory_store = memory_store
```

- [x] **Step 4: Persist messages inside non-streaming workflow**

In `api/chat_orchestrator.py::run_chat_response`, add user message persistence before `enhanced_query`:

```python
        if self._memory_store:
            self._memory_store.ensure_session(session_id)
            self._memory_store.append_message(
                session_id=session_id,
                role="user",
                content=query,
            )
```

Add assistant persistence after `response` is created:

```python
        if self._memory_store and response.answer:
            assistant_message = self._memory_store.append_message(
                session_id=session_id,
                role="assistant",
                content=response.answer,
            )
            self._memory_store.add_message_sources(
                assistant_message.id,
                [
                    MessageSourceRecord(
                        message_id=assistant_message.id,
                        title=citation.title,
                        url=citation.url,
                        source_type="paper",
                    )
                    for citation in response.citations
                    if citation.url
                ],
            )
```

Add import at top:

```python
from agent.memory.models import MessageSourceRecord
```

- [x] **Step 5: Add store factory in chat routes**

In `api/routes/chat.py`, add imports:

```python
from agent.memory import MemoryConfig
from agent.memory.store import InMemoryMemoryStore
from agent.memory.postgres_store import PostgresMemoryStore
```

Add module-level store cache below `sessions`:

```python
memory_store = None


def _get_memory_store():
    global memory_store
    config = MemoryConfig.from_env()
    if not config.persistent_transcript_enabled:
        return None
    if memory_store is not None:
        return memory_store
    if config.database_url:
        store = PostgresMemoryStore(config.database_url)
        store.setup()
    else:
        store = InMemoryMemoryStore()
    memory_store = store
    return memory_store
```

Update `_research_chat_workflow()`:

```python
def _research_chat_workflow() -> ResearchChatWorkflow:
    return ResearchChatWorkflow(
        inject_memory_context_fn=inject_memory_context,
        run_preview_fn=run_research_preview,
        memory_store=_get_memory_store(),
    )
```

- [x] **Step 6: Run tests**

Run:

```bash
uv run pytest tests/test_persistent_transcript.py tests/research/test_research_chat_integration.py -q
```

Expected: all tests pass.

- [x] **Step 7: Commit**

```bash
git add api/chat_orchestrator.py api/routes/chat.py tests/test_persistent_transcript.py
git commit -m "feat(memory): persist chat transcript behind flag"
```

---

## Task 6: Add Context Assembler and Session Summary

**Files:**
- Create: `agent/memory/context_assembler.py`
- Create: `agent/memory/summarizer.py`
- Modify: `api/chat_orchestrator.py`
- Test: `tests/test_memory_context_assembler.py`

- [x] **Step 1: Write context assembler tests** (completed 2026-07-03T07:41Z)

Create `tests/test_memory_context_assembler.py`:

```python
from agent.memory.context_assembler import ContextAssembler
from agent.memory.models import ChatMessageRecord, MemoryItemRecord, SessionSummaryRecord


def test_context_assembler_builds_ordered_sections():
    assembler = ContextAssembler(max_chars=1000)

    context = assembler.assemble(
        query="What did we conclude?",
        recent_messages=[
            ChatMessageRecord(id="m1", session_id="s1", role="user", content="What is RAG?"),
            ChatMessageRecord(id="m2", session_id="s1", role="assistant", content="RAG uses retrieval."),
        ],
        summary=SessionSummaryRecord(session_id="s1", summary="The session is about RAG."),
        memories=[
            MemoryItemRecord(id="mem1", scope="session", text="User is comparing RAG methods.", session_id="s1"),
        ],
    )

    assert "SESSION SUMMARY" in context.text
    assert "LONG-TERM MEMORY" in context.text
    assert "RECENT CONVERSATION" in context.text
    assert "CURRENT QUESTION" in context.text
    assert context.text.index("SESSION SUMMARY") < context.text.index("RECENT CONVERSATION")
    assert context.included_message_ids == ["m1", "m2"]
    assert context.included_memory_ids == ["mem1"]


def test_context_assembler_respects_character_budget():
    assembler = ContextAssembler(max_chars=160)

    context = assembler.assemble(
        query="Q",
        recent_messages=[
            ChatMessageRecord(id="m1", session_id="s1", role="assistant", content="A" * 300),
        ],
        summary=SessionSummaryRecord(session_id="s1", summary="S" * 300),
        memories=[],
    )

    assert len(context.text) <= 160
    assert context.truncated is True
```

- [x] **Step 2: Run tests to verify failure** (completed 2026-07-03T07:41Z)

Run:

```bash
uv run pytest tests/test_memory_context_assembler.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'agent.memory.context_assembler'
```

- [x] **Step 3: Implement context assembler** (completed 2026-07-03T07:41Z)

Create `agent/memory/context_assembler.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from agent.memory.models import ChatMessageRecord, MemoryItemRecord, SessionSummaryRecord


@dataclass(frozen=True)
class AssembledContext:
    text: str
    included_message_ids: list[str]
    included_memory_ids: list[str]
    truncated: bool = False


class ContextAssembler:
    def __init__(self, max_chars: int = 12000) -> None:
        self.max_chars = max_chars

    def assemble(
        self,
        *,
        query: str,
        recent_messages: list[ChatMessageRecord],
        summary: SessionSummaryRecord | None,
        memories: list[MemoryItemRecord],
    ) -> AssembledContext:
        sections: list[str] = []
        included_message_ids: list[str] = []
        included_memory_ids: list[str] = []

        if summary and summary.summary.strip():
            sections.append(f"## SESSION SUMMARY\n{summary.summary.strip()}")

        if memories:
            memory_lines = []
            for memory in memories:
                included_memory_ids.append(memory.id)
                memory_lines.append(f"- [{memory.scope}] {memory.text}")
            sections.append("## LONG-TERM MEMORY\n" + "\n".join(memory_lines))

        if recent_messages:
            message_lines = []
            for message in recent_messages:
                included_message_ids.append(message.id)
                message_lines.append(f"{message.role.upper()}: {message.content}")
            sections.append("## RECENT CONVERSATION\n" + "\n".join(message_lines))

        sections.append(f"## CURRENT QUESTION\n{query}")
        text = "\n\n".join(sections)
        truncated = False
        if len(text) > self.max_chars:
            text = text[: self.max_chars].rstrip()
            truncated = True

        return AssembledContext(
            text=text,
            included_message_ids=included_message_ids,
            included_memory_ids=included_memory_ids,
            truncated=truncated,
        )
```

- [x] **Step 4: Implement deterministic summarizer wrapper** (completed 2026-07-03T07:41Z)

Create `agent/memory/summarizer.py`:

```python
from __future__ import annotations

from agent.memory.models import ChatMessageRecord


def build_summary_prompt(previous_summary: str, messages: list[ChatMessageRecord]) -> str:
    lines = [
        "Update the session summary for a research assistant conversation.",
        "Keep durable research context, paper references, unresolved questions, and user constraints.",
        "Do not invent facts not present in the messages.",
        "",
        "Previous summary:",
        previous_summary or "(none)",
        "",
        "New messages:",
    ]
    for message in messages:
        lines.append(f"{message.role.upper()}: {message.content}")
    return "\n".join(lines)
```

- [x] **Step 5: Run focused tests** (completed 2026-07-03T07:41Z)

Run:

```bash
uv run pytest tests/test_memory_context_assembler.py -q
```

Expected:

```text
2 passed
```

- [x] **Step 6: Commit** (completed 2026-07-03T07:41Z)

```bash
git add agent/memory/context_assembler.py agent/memory/summarizer.py tests/test_memory_context_assembler.py
git commit -m "feat(memory): add structured context assembler"
```

Task 6 completion notes (2026-07-03T07:41Z):
- Implemented `ContextAssembler` and deterministic summary prompt builder.
- Context records use JSON serialization for untrusted summary, memory, message, and current-question content.
- Truncation includes only complete prior records and always preserves a complete current-question record, even when a too-small budget makes strict `max_chars` impossible.
- Validation: `uv run pytest tests/test_memory_context_assembler.py tests/test_memory_config.py tests/test_memory_store.py -q` -> 42 passed.
- Subagent gates: spec review passed; code-quality review approved.

---

## Task 7: Add Long-Term Memory Writer and Retrieval

**Files:**
- Create: `agent/memory/writer.py`
- Modify: `api/chat_orchestrator.py`
- Test: `tests/test_memory_writer.py`

- [x] **Step 1: Write memory writer tests** (completed 2026-07-03T07:56Z)

Create `tests/test_memory_writer.py`:

```python
from agent.memory.store import InMemoryMemoryStore
from agent.memory.writer import MemoryWriter


def test_memory_writer_stores_research_preference():
    store = InMemoryMemoryStore()
    writer = MemoryWriter(store)

    item = writer.write_candidate(
        text="User prefers answers with paper comparison tables.",
        session_id="s1",
        user_id="u1",
        source_message_id="m1",
    )

    assert item is not None
    results = store.search_memory_items("comparison tables", session_id="s1", user_id="u1", limit=5)
    assert [result.id for result in results] == [item.id]


def test_memory_writer_skips_sensitive_candidate():
    store = InMemoryMemoryStore()
    writer = MemoryWriter(store)

    item = writer.write_candidate(
        text="User password is hunter2.",
        session_id="s1",
        user_id="u1",
        source_message_id="m1",
    )

    assert item is None
    assert store.search_memory_items("password", session_id="s1", user_id="u1", limit=5) == []
```

- [x] **Step 2: Run tests to verify failure** (completed 2026-07-03T07:56Z)

Run:

```bash
uv run pytest tests/test_memory_writer.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'agent.memory.writer'
```

- [x] **Step 3: Implement memory writer** (completed 2026-07-03T07:56Z)

Create `agent/memory/writer.py`:

```python
from __future__ import annotations

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
    ) -> MemoryItemRecord | None:
        normalized = text.strip()
        if not normalized:
            return None
        lowered = normalized.lower()
        if any(term in lowered for term in SENSITIVE_TERMS):
            return None

        item = MemoryItemRecord(
            id=new_id("mem"),
            scope="session" if session_id else "user",
            text=normalized,
            session_id=session_id,
            user_id=user_id,
            source_message_id=source_message_id,
            confidence=0.8,
            privacy_class="normal",
        )
        return self.store.upsert_memory_item(item)
```

- [x] **Step 4: Run focused tests** (completed 2026-07-03T07:56Z)

Run:

```bash
uv run pytest tests/test_memory_writer.py -q
```

Expected:

```text
2 passed
```

- [x] **Step 5: Wire retrieval into future context assembly** (completed 2026-07-03T07:56Z)

In `api/chat_orchestrator.py`, do not call `MemoryWriter` yet. Add a short code comment near the assistant persistence block:

```python
# Long-term memory writing is intentionally added behind LONG_TERM_MEMORY_ENABLED
# after transcript persistence and context assembly are validated.
```

This keeps this task behavior-preserving while the writer test surface is established.

- [x] **Step 6: Commit** (completed 2026-07-03T07:56Z)

```bash
git add agent/memory/writer.py api/chat_orchestrator.py tests/test_memory_writer.py
git commit -m "feat(memory): add scoped memory writer"
```

Task 7 completion notes (2026-07-03T07:56Z):
- Implemented `MemoryWriter` with scoped session/user memory writes, sensitive candidate filtering, owner consistency checks, and no runtime write path yet.
- Added tests for preference storage/retrieval, sensitive terms with punctuation, avoiding research false positives like tokenization, session owner mismatch, and missing user owner.
- Validation: `uv run pytest tests/test_memory_writer.py tests/test_memory_store.py -q` -> 36 passed.
- Subagent gates: spec review passed; code-quality re-review approved after sensitive normalization and ownership fixes.

---

## Task 8: Add Memory Controls and Evaluation Gate

**Files:**
- Create: `api/routes/memory.py`
- Modify: `api/main.py`
- Create: `tests/test_memory_controls.py`
- Create: `eval/memory_eval.py`
- Create: `eval/memory_golden_set.jsonl`

- [x] **Step 1: Create memory eval dataset** (completed 2026-07-03T08:11Z)

Create `eval/memory_golden_set.jsonl`:

```jsonl
{"id":"follow-up-recent","turns":[{"role":"user","content":"Explain RAG using the Lewis 2020 paper."},{"role":"assistant","content":"RAG combines retrieval with generation and is introduced by Lewis et al. 2020."},{"role":"user","content":"What paper did we just discuss?"}],"expected_terms":["Lewis","2020","RAG"]}
{"id":"no-cross-session-leak","turns":[{"role":"user","content":"Remember that my research topic is LoRA."},{"role":"assistant","content":"I will use LoRA as the current research topic."}],"probe_session":"different-session","probe":"What is my research topic?","must_not_include":["LoRA"]}
```

- [x] **Step 2: Add controls route skeleton** (completed 2026-07-03T08:11Z)

Create `api/routes/memory.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agent.memory.config import MemoryConfig

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/features")
async def memory_features():
    config = MemoryConfig.from_env()
    return {
        "persistent_transcript_enabled": config.persistent_transcript_enabled,
        "session_summary_enabled": config.session_summary_enabled,
        "long_term_memory_enabled": config.long_term_memory_enabled,
        "research_memory_enabled": config.research_memory_enabled,
    }


@router.delete("/session/{session_id}")
async def delete_memory_session(session_id: str):
    raise HTTPException(
        status_code=501,
        detail="DB-backed memory deletion is enabled after persistent transcript rollout.",
    )
```

- [x] **Step 3: Include router** (completed 2026-07-03T08:11Z)

In `api/main.py`, import:

```python
from api.routes import memory
```

Register the router alongside existing routers:

```python
app.include_router(memory.router)
```

- [x] **Step 4: Add controls tests** (completed 2026-07-03T08:11Z)

Create `tests/test_memory_controls.py`:

```python
from fastapi.testclient import TestClient

from api.main import app


def test_memory_features_endpoint_reports_flags(monkeypatch):
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setenv("SESSION_SUMMARY_ENABLED", "false")
    monkeypatch.setenv("LONG_TERM_MEMORY_ENABLED", "false")
    monkeypatch.setenv("RESEARCH_MEMORY_ENABLED", "false")

    client = TestClient(app)
    response = client.get("/api/memory/features")

    assert response.status_code == 200
    assert response.json()["persistent_transcript_enabled"] is True
    assert response.json()["session_summary_enabled"] is False
```

- [x] **Step 5: Add deterministic eval loader** (completed 2026-07-03T08:11Z)

Create `eval/memory_eval.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


def load_memory_eval_rows(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


if __name__ == "__main__":
    rows = load_memory_eval_rows(Path("eval/memory_golden_set.jsonl"))
    print(f"loaded {len(rows)} memory eval rows")
```

- [x] **Step 6: Run tests and eval loader** (completed 2026-07-03T08:11Z)

Run:

```bash
uv run pytest tests/test_memory_controls.py -q
uv run python eval/memory_eval.py
```

Expected:

```text
1 passed
loaded 2 memory eval rows
```

- [x] **Step 7: Commit** (completed 2026-07-03T08:11Z)

```bash
git add api/main.py api/routes/memory.py eval/memory_eval.py eval/memory_golden_set.jsonl tests/test_memory_controls.py
git commit -m "feat(memory): add controls and eval seed"
```

Task 8 completion notes (2026-07-03T08:11Z):
- Added memory feature controls endpoint, deletion placeholder, memory eval seed, and deterministic eval loader.
- Validation: `uv run pytest tests/test_memory_controls.py tests/test_memory_config.py -q` -> 4 passed; `uv run python eval/memory_eval.py` -> loaded 2 memory eval rows.
- Subagent gates: spec review passed; code-quality review approved.

Final review remediation (2026-07-03T08:32Z):
- Replaced the deletion placeholder with a real `DELETE /api/memory/session/{session_id}` path that clears both process-local and persistent session data.
- Wired `RESEARCH_MEMORY_ENABLED`, `SESSION_SUMMARY_ENABLED`, and `LONG_TERM_MEMORY_ENABLED` into the chat runtime behind best-effort fallback guards.
- Added `memory_store_backend` to the memory features response so non-durable in-memory persistent mode is visible to operators.

---

## Execution Order

Execute tasks strictly in this order:

```text
Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5 -> Task 6 -> Task 7 -> Task 8
```

Task 2 can be implemented before Task 1 if needed, but do not wire persistence before Task 3.
Task 4 can be skipped in local-only development if PostgreSQL is not available, but Task 5 must still pass with `InMemoryMemoryStore`.

## Verification Matrix

After all tasks:

```bash
uv run pytest tests/test_memory_config.py tests/test_memory_store.py tests/test_session_identity.py tests/test_persistent_transcript.py tests/test_memory_context_assembler.py tests/test_memory_writer.py tests/test_memory_controls.py -q
uv run pytest tests/research/test_research_chat_integration.py tests/test_chat_streaming.py -q
uv run python eval/memory_eval.py
cd web && npm run lint
```

Before enabling production flags:

```bash
uv run pytest tests/ -q
make eval-research
```

## Rollback Strategy

- Disable `PERSISTENT_TRANSCRIPT_ENABLED` to return chat routes to the current in-process memory behavior.
- Disable `SESSION_SUMMARY_ENABLED` to bypass summaries and use recent messages only.
- Disable `LONG_TERM_MEMORY_ENABLED` to stop memory retrieval/writing while keeping transcript storage.
- Disable `RESEARCH_MEMORY_ENABLED` to prevent research trail injection while preserving normal RAG.
- If PostgreSQL setup fails, leave `MEMORY_DATABASE_URL` empty and use `InMemoryMemoryStore` only in non-production test environments.

## Self-Review

Spec coverage:

- Stable session id: Task 2.
- Persistent transcript: Tasks 3-5.
- Context assembly and summary: Task 6.
- Long-term memory writer/retrieval foundation: Task 7.
- User controls and eval seed: Task 8.
- Framework decision: explicitly deferred; this plan keeps the canonical research workflow and custom memory layer.

Placeholder scan:

- No task uses TBD/TODO/implement later.
- Code-changing steps include concrete code blocks.
- Verification commands and expected outcomes are listed per task.

Type consistency:

- `ChatMessageRecord`, `MessageSourceRecord`, `SessionSummaryRecord`, and `MemoryItemRecord` are defined in Task 3 before use in later tasks.
- `MemoryStore` method names are used consistently across in-memory, Postgres, writer, and orchestrator snippets.
