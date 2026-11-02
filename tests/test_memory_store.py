from pathlib import Path

import pytest

from agent.memory.models import (
    ChatMessageRecord,
    MemoryItemRecord,
    MessageSourceRecord,
    SessionSummaryRecord,
)
from agent.memory.store import InMemoryMemoryStore


def _normalized_sql(sql: str) -> str:
    return " ".join(sql.lower().split())


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


def test_ensure_session_rejects_conflicting_active_user_owner():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")

    with pytest.raises(ValueError):
        store.ensure_session("s1", user_id="u2")


def test_in_memory_store_soft_deletes_session():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id=None)
    store.append_message(session_id="s1", role="user", content="hello")

    assert store.delete_session("s1") is True
    assert store.get_recent_messages("s1", limit=10) == []
    assert store.delete_session("missing") is False


def test_recreated_deleted_session_starts_clean():
    store = InMemoryMemoryStore()
    message = store.append_message(session_id="s1", role="assistant", content="old")
    store.add_message_sources(
        message.id,
        [
            MessageSourceRecord(
                message_id=message.id,
                title="Old paper",
                url="https://example.com/old",
            )
        ],
    )
    store.upsert_session_summary(SessionSummaryRecord(session_id="s1", summary="old summary"))
    store.upsert_memory_item(
        MemoryItemRecord(
            id="mem1",
            scope="session",
            text="old session memory",
            session_id="s1",
        )
    )

    assert store.delete_session("s1") is True
    store.ensure_session("s1", user_id="u1")

    assert store.get_recent_messages("s1", limit=10) == []
    assert store.get_session_summary("s1") is None
    assert store.get_message_sources(message.id) == []
    assert store.search_memory_items("session memory", session_id="s1", user_id=None, limit=10) == []


def test_metadata_mutation_does_not_leak_into_store_reads():
    store = InMemoryMemoryStore()
    message = store.append_message(session_id="s1", role="user", content="hello")
    message.metadata["mutated"] = True

    source = MessageSourceRecord(
        message_id=message.id,
        title="Source",
        url="https://example.com/source",
        metadata={"rank": 1},
    )
    store.add_message_sources(message.id, [source])
    source.metadata["rank"] = 2
    read_source = store.get_message_sources(message.id)[0]
    read_source.metadata["rank"] = 3

    memory = store.upsert_memory_item(
        MemoryItemRecord(
            id="mem1",
            scope="session",
            text="stable metadata memory",
            session_id="s1",
            metadata={"kind": "fact"},
        )
    )
    memory.metadata["kind"] = "mutated"

    assert store.get_recent_messages("s1", limit=10)[0].metadata == {}
    assert store.get_message_sources(message.id)[0].metadata == {"rank": 1}
    assert store.search_memory_items("metadata memory", session_id="s1", user_id=None, limit=10)[0].metadata == {
        "kind": "fact"
    }


def test_nested_metadata_mutation_does_not_leak_into_store_reads():
    store = InMemoryMemoryStore()
    message = store.append_message(session_id="s1", role="assistant", content="hello")

    source = MessageSourceRecord(
        message_id=message.id,
        title="Nested source",
        url="https://example.com/nested",
        metadata={"outer": {"nested": "source"}},
    )
    store.add_message_sources(message.id, [source])
    source.metadata["outer"]["nested"] = "input-mutated"
    read_source = store.get_message_sources(message.id)[0]
    read_source.metadata["outer"]["nested"] = "read-mutated"

    memory = MemoryItemRecord(
        id="mem1",
        scope="session",
        text="nested memory metadata",
        session_id="s1",
        metadata={"outer": {"nested": "memory"}},
    )
    returned_memory = store.upsert_memory_item(memory)
    memory.metadata["outer"]["nested"] = "input-mutated"
    returned_memory.metadata["outer"]["nested"] = "returned-mutated"
    read_memory = store.search_memory_items("nested memory", session_id="s1", user_id=None, limit=10)[0]
    read_memory.metadata["outer"]["nested"] = "read-mutated"

    assert store.get_message_sources(message.id)[0].metadata == {"outer": {"nested": "source"}}
    assert store.search_memory_items("nested memory", session_id="s1", user_id=None, limit=10)[0].metadata == {
        "outer": {"nested": "memory"}
    }


def test_add_message_sources_rejects_mismatched_message_id():
    store = InMemoryMemoryStore()

    with pytest.raises(ValueError):
        store.add_message_sources(
            "m1",
            [
                MessageSourceRecord(
                    message_id="m2",
                    title="Wrong message",
                    url="https://example.com/wrong",
                )
            ],
        )


def test_get_recent_messages_non_positive_limit_returns_empty():
    store = InMemoryMemoryStore()
    store.append_message(session_id="s1", role="user", content="hello")

    assert store.get_recent_messages("s1", limit=0) == []
    assert store.get_recent_messages("s1", limit=-1) == []


def test_memory_search_ignores_empty_low_signal_and_non_positive_limit():
    store = InMemoryMemoryStore()
    store.ensure_session("s1")
    store.upsert_memory_item(
        MemoryItemRecord(
            id="mem1",
            scope="session",
            text="User studies retrieval augmented generation",
            session_id="s1",
        )
    )

    assert store.search_memory_items("", session_id="s1", user_id=None, limit=10) == []
    assert store.search_memory_items("   ", session_id="s1", user_id=None, limit=10) == []
    assert store.search_memory_items("a to of", session_id="s1", user_id=None, limit=10) == []
    assert store.search_memory_items("retrieval", session_id="s1", user_id=None, limit=0) == []
    assert store.search_memory_items("retrieval", session_id="s1", user_id=None, limit=-1) == []


def test_memory_search_ignores_stopwords_but_keeps_useful_tokens():
    store = InMemoryMemoryStore()
    store.ensure_session("s1")
    store.upsert_memory_item(
        MemoryItemRecord(
            id="mem1",
            scope="session",
            text="The user needs comparison tables for retrieval systems.",
            session_id="s1",
        )
    )

    assert store.search_memory_items("the and for", session_id="s1", user_id=None, limit=10) == []
    assert [
        item.id for item in store.search_memory_items("comparison tables", session_id="s1", user_id=None, limit=10)
    ] == ["mem1"]


def test_memory_search_filters_from_record_ownership_side():
    store = InMemoryMemoryStore()
    store.ensure_session("s1")
    store.upsert_memory_item(
        MemoryItemRecord(
            id="global",
            scope="project",
            text="comparison tables global",
        )
    )
    store.upsert_memory_item(
        MemoryItemRecord(
            id="user",
            scope="user",
            text="comparison tables user",
            user_id="u1",
        )
    )
    store.upsert_memory_item(
        MemoryItemRecord(
            id="session",
            scope="session",
            text="comparison tables session",
            session_id="s1",
        )
    )

    assert [
        item.id for item in store.search_memory_items("comparison", session_id=None, user_id=None, limit=10)
    ] == ["global"]
    assert [
        item.id for item in store.search_memory_items("comparison", session_id="s1", user_id="u1", limit=10)
    ] == ["global", "user", "session"]


def test_session_memory_search_enforces_parent_session_user_owner():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    store.upsert_memory_item(
        MemoryItemRecord(
            id="session",
            scope="session",
            text="comparison tables session",
            session_id="s1",
        )
    )

    assert store.search_memory_items("comparison", session_id="s1", user_id=None, limit=10) == []
    assert store.search_memory_items("comparison", session_id="s1", user_id="u2", limit=10) == []
    assert [item.id for item in store.search_memory_items("comparison", session_id="s1", user_id="u1", limit=10)] == [
        "session"
    ]


def test_delete_session_immediately_hides_child_records():
    store = InMemoryMemoryStore()
    message = store.append_message(session_id="s1", role="assistant", content="old")
    store.add_message_sources(
        message.id,
        [
            MessageSourceRecord(
                message_id=message.id,
                title="Old source",
                url="https://example.com/old",
            )
        ],
    )
    store.upsert_session_summary(SessionSummaryRecord(session_id="s1", summary="old summary"))
    store.upsert_memory_item(
        MemoryItemRecord(
            id="mem1",
            scope="session",
            text="old session memory",
            session_id="s1",
        )
    )

    assert store.delete_session("s1") is True

    assert store.get_message_sources(message.id) == []
    assert store.get_session_summary("s1") is None
    assert store.search_memory_items("session memory", session_id="s1", user_id=None, limit=10) == []


def test_child_writes_require_existing_active_parents():
    store = InMemoryMemoryStore()

    with pytest.raises(ValueError):
        store.add_message_sources(
            "missing",
            [
                MessageSourceRecord(
                    message_id="missing",
                    title="Orphan source",
                    url="https://example.com/orphan",
                )
            ],
        )
    with pytest.raises(ValueError):
        store.upsert_session_summary(SessionSummaryRecord(session_id="missing", summary="orphan"))

    message = store.append_message(session_id="s1", role="assistant", content="old")
    assert store.delete_session("s1") is True

    with pytest.raises(ValueError):
        store.add_message_sources(
            message.id,
            [
                MessageSourceRecord(
                    message_id=message.id,
                    title="Deleted source",
                    url="https://example.com/deleted",
                )
            ],
        )
    with pytest.raises(ValueError):
        store.upsert_session_summary(SessionSummaryRecord(session_id="s1", summary="deleted"))


def test_memory_item_upsert_requires_scope_owners():
    store = InMemoryMemoryStore()

    with pytest.raises(ValueError):
        store.upsert_memory_item(
            MemoryItemRecord(
                id="session-missing-owner",
                scope="session",
                text="comparison tables session",
            )
        )
    with pytest.raises(ValueError):
        store.upsert_memory_item(
            MemoryItemRecord(
                id="user-missing-owner",
                scope="user",
                text="comparison tables user",
            )
        )


def test_memory_item_source_message_id_must_exist():
    store = InMemoryMemoryStore()
    store.ensure_session("s1")

    with pytest.raises(ValueError):
        store.upsert_memory_item(
            MemoryItemRecord(
                id="mem1",
                scope="session",
                text="comparison tables session",
                session_id="s1",
                source_message_id="missing",
            )
        )


def test_memory_item_source_message_id_requires_active_session():
    store = InMemoryMemoryStore()
    message = store.append_message(session_id="s1", role="assistant", content="old")
    assert store.delete_session("s1") is True

    with pytest.raises(ValueError):
        store.upsert_memory_item(
            MemoryItemRecord(
                id="mem1",
                scope="project",
                text="comparison tables project",
                source_message_id=message.id,
            )
        )


def test_session_memory_item_source_message_id_must_match_session():
    store = InMemoryMemoryStore()
    message = store.append_message(session_id="s1", role="assistant", content="source")
    store.ensure_session("s2")

    with pytest.raises(ValueError):
        store.upsert_memory_item(
            MemoryItemRecord(
                id="mem1",
                scope="session",
                text="comparison tables session",
                session_id="s2",
                source_message_id=message.id,
            )
        )


def test_memory_item_source_message_id_accepts_same_active_session():
    store = InMemoryMemoryStore()
    message = store.append_message(session_id="s1", role="assistant", content="source")

    memory = store.upsert_memory_item(
        MemoryItemRecord(
            id="mem1",
            scope="session",
            text="comparison tables session",
            session_id="s1",
            source_message_id=message.id,
        )
    )

    assert memory.source_message_id == message.id


def test_owner_bound_source_message_cannot_create_global_memory():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    message = store.append_message(session_id="s1", role="assistant", content="private source")

    with pytest.raises(ValueError):
        store.upsert_memory_item(
            MemoryItemRecord(
                id="global-from-private-source",
                scope="project",
                text="comparison tables project",
                source_message_id=message.id,
            )
        )
    with pytest.raises(ValueError):
        store.upsert_memory_item(
            MemoryItemRecord(
                id="wrong-user-from-private-source",
                scope="user",
                text="comparison tables user",
                user_id="u2",
                source_message_id=message.id,
            )
        )

    assert store.search_memory_items("comparison", session_id=None, user_id=None, limit=10) == []
    assert store.search_memory_items("comparison", session_id=None, user_id="u2", limit=10) == []


def test_delete_session_hides_memory_items_sourced_from_deleted_messages():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    message = store.append_message(session_id="s1", role="assistant", content="private source")
    store.upsert_memory_item(
        MemoryItemRecord(
            id="user-from-source",
            scope="user",
            text="comparison tables user",
            user_id="u1",
            source_message_id=message.id,
        )
    )

    assert [item.id for item in store.search_memory_items("comparison", session_id=None, user_id="u1", limit=10)] == [
        "user-from-source"
    ]

    assert store.delete_session("s1") is True

    assert store.search_memory_items("comparison", session_id=None, user_id="u1", limit=10) == []


def test_memory_search_ignores_malformed_scoped_items():
    store = InMemoryMemoryStore()
    store.memory_items["session-missing-owner"] = MemoryItemRecord(
        id="session-missing-owner",
        scope="session",
        text="comparison tables session",
    )
    store.memory_items["user-missing-owner"] = MemoryItemRecord(
        id="user-missing-owner",
        scope="user",
        text="comparison tables user",
    )

    assert store.search_memory_items("comparison", session_id=None, user_id=None, limit=10) == []


def test_valid_scoped_memory_items_require_matching_identity():
    store = InMemoryMemoryStore()
    store.ensure_session("s1")
    store.upsert_memory_item(
        MemoryItemRecord(
            id="session",
            scope="session",
            text="comparison tables session",
            session_id="s1",
        )
    )
    store.upsert_memory_item(
        MemoryItemRecord(
            id="user",
            scope="user",
            text="comparison tables user",
            user_id="u1",
        )
    )

    assert store.search_memory_items("comparison", session_id=None, user_id=None, limit=10) == []
    assert [item.id for item in store.search_memory_items("comparison", session_id="s1", user_id=None, limit=10)] == [
        "session"
    ]
    assert [item.id for item in store.search_memory_items("comparison", session_id=None, user_id="u1", limit=10)] == [
        "user"
    ]


def test_postgres_store_exposes_schema_sql_without_connection():
    from agent.memory.postgres_store import SCHEMA_SQL

    assert "CREATE TABLE IF NOT EXISTS chat_sessions" in SCHEMA_SQL
    assert "CREATE TABLE IF NOT EXISTS chat_messages" in SCHEMA_SQL
    assert "CREATE TABLE IF NOT EXISTS message_sources" in SCHEMA_SQL
    assert "CREATE TABLE IF NOT EXISTS session_summaries" in SCHEMA_SQL
    assert "CREATE TABLE IF NOT EXISTS memory_items" in SCHEMA_SQL


def test_postgres_schema_protects_source_message_provenance_without_connection():
    from agent.memory.postgres_store import SCHEMA_SQL

    sql = _normalized_sql(SCHEMA_SQL)

    assert "position bigserial unique" in sql
    assert "on chat_messages(session_id, position)" in sql
    assert "constraint chat_messages_role_check" in sql
    assert "role in ('user', 'assistant', 'system', 'tool')" in sql
    assert "constraint memory_items_scope_check" in sql
    assert "scope in ('session', 'user', 'project', 'research_topic')" in sql
    assert "constraint memory_items_privacy_class_check" in sql
    assert "privacy_class in ('normal', 'sensitive')" in sql
    assert "message_id text not null references chat_messages(id) on delete cascade" in sql
    assert "source_message_id text references chat_messages(id) on delete cascade" in sql
    assert "constraint memory_items_scope_owner" in sql
    assert "scope <> 'session' or session_id is not null" in sql
    assert "scope <> 'user' or user_id is not null" in sql


def test_postgres_read_sql_excludes_deleted_sessions_without_connection():
    from agent.memory.postgres_store import (
        GET_MESSAGE_SOURCES_SQL,
        GET_RECENT_MESSAGES_SQL,
        GET_SESSION_SUMMARY_SQL,
        SEARCH_MEMORY_ITEMS_SQL,
    )

    for sql_text in [
        GET_RECENT_MESSAGES_SQL,
        GET_MESSAGE_SOURCES_SQL,
        GET_SESSION_SUMMARY_SQL,
        SEARCH_MEMORY_ITEMS_SQL,
    ]:
        sql = _normalized_sql(sql_text)
        assert "chat_sessions" in sql
        assert "deleted_at is null" in sql

    search_sql = _normalized_sql(SEARCH_MEMORY_ITEMS_SQL)
    assert "parent_session.deleted_at is null" in search_sql
    assert "source_session.deleted_at is null" in search_sql
    assert "escape '\\'" in search_sql

    recent_sql = _normalized_sql(GET_RECENT_MESSAGES_SQL)
    assert "order by m.position desc" in recent_sql

    # Guards against reverting d6046ee: nullable scope params must be cast to
    # ::text before the IS NOT NULL check, or Postgres can't infer their type.
    assert "%s::text IS NOT NULL" in SEARCH_MEMORY_ITEMS_SQL


def test_postgres_query_tokens_escape_like_wildcards_without_connection():
    from agent.memory.postgres_store import _query_tokens

    assert _query_tokens("100% recall foo_bar slash\\test") == [
        "100\\%",
        "recall",
        "foo\\_bar",
        "slash\\\\test",
    ]


def test_postgres_write_sql_validates_active_parents_without_connection():
    from agent.memory.postgres_store import (
        ADD_MESSAGE_SOURCE_SQL,
        _INSERT_SESSION_SQL,
        UPSERT_MEMORY_ITEM_SQL,
        UPSERT_SESSION_SUMMARY_SQL,
    )

    insert_session_sql = _normalized_sql(_INSERT_SESSION_SQL)
    assert "on conflict (id) do nothing" in insert_session_sql
    assert "returning id, user_id, created_at, updated_at, deleted_at" in insert_session_sql

    source_sql = _normalized_sql(ADD_MESSAGE_SOURCE_SQL)
    assert "join chat_sessions" in source_sql
    assert "deleted_at is null" in source_sql

    summary_sql = _normalized_sql(UPSERT_SESSION_SUMMARY_SQL)
    assert "source_message_id" in summary_sql
    assert "source_message.session_id = summary_input.session_id" in summary_sql
    assert "source_session.deleted_at is null" in summary_sql
    assert "deleted_at is null" in summary_sql

    memory_sql = _normalized_sql(UPSERT_MEMORY_ITEM_SQL)
    assert "source_message_id" in memory_sql
    assert "parent_session.id is not null" in memory_sql
    assert "memory_input.scope <> 'session' or" in memory_sql
    assert "source_message.session_id = memory_input.session_id" in memory_sql
    assert "source_session.user_id is null or memory_input.user_id = source_session.user_id" in memory_sql
    assert "deleted_at is null" in memory_sql


def test_postgres_delete_sql_hides_child_and_sourced_records_without_connection():
    from agent.memory.postgres_store import DELETE_SESSION_SQL

    sql = _normalized_sql(DELETE_SESSION_SQL)

    assert "update chat_sessions" in sql
    assert "deleted_at is null" in sql
    assert "delete from session_summaries" in sql
    assert "delete from memory_items" in sql
    assert "source_message_id in (select id from deleted_messages)" in sql
    assert "delete from chat_messages" in sql


def test_requirements_txt_includes_postgres_runtime_dependency():
    requirements = Path("requirements.txt").read_text()

    assert "psycopg==" in requirements
    assert "psycopg-binary==" in requirements
