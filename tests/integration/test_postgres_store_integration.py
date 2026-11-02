"""Integration tests for PostgresMemoryStore against a real database.

Prerequisites:
    make compose-db
    export MEMORY_TEST_DATABASE_URL=postgresql://research:research@localhost:5432/research_memory
"""
import os
import uuid

import pytest

DATABASE_URL = os.getenv("MEMORY_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="MEMORY_TEST_DATABASE_URL not set; start Postgres via `make compose-db` first",
)


@pytest.fixture()
def store():
    from agent.memory.postgres_store import PostgresMemoryStore

    postgres_store = PostgresMemoryStore(DATABASE_URL)
    postgres_store.setup()
    return postgres_store


def _session_id() -> str:
    return f"it-{uuid.uuid4().hex}"


def test_setup_is_idempotent(store):
    store.setup()


def test_ensure_session_is_stable_across_calls(store):
    session_id = _session_id()
    first = store.ensure_session(session_id)
    second = store.ensure_session(session_id)

    assert first.id == session_id
    assert second.id == session_id


def test_transcript_roundtrip_orders_and_limits_messages(store):
    session_id = _session_id()
    store.ensure_session(session_id)
    for index in range(3):
        store.append_message(session_id, "user", f"question {index}")

    recent = store.get_recent_messages(session_id, limit=2)

    assert [message.content for message in recent] == ["question 1", "question 2"]
    assert all(message.session_id == session_id for message in recent)


def test_message_sources_roundtrip(store):
    from agent.memory.models import MessageSourceRecord

    session_id = _session_id()
    store.ensure_session(session_id)
    message = store.append_message(session_id, "assistant", "grounded answer")
    store.add_message_sources(
        message.id,
        [
            MessageSourceRecord(
                message_id=message.id,
                title="Paper",
                url="https://arxiv.org/abs/1234.5678",
            )
        ],
    )

    sources = store.get_message_sources(message.id)

    assert len(sources) == 1
    assert sources[0].url == "https://arxiv.org/abs/1234.5678"


def test_session_summary_upsert_overwrites_previous_summary(store):
    from agent.memory.models import SessionSummaryRecord

    session_id = _session_id()
    store.ensure_session(session_id)
    message = store.append_message(session_id, "assistant", "answer")
    store.upsert_session_summary(
        SessionSummaryRecord(session_id=session_id, summary="v1", source_message_id=message.id)
    )
    store.upsert_session_summary(
        SessionSummaryRecord(session_id=session_id, summary="v2", source_message_id=message.id)
    )

    summary = store.get_session_summary(session_id)

    assert summary is not None
    assert summary.summary == "v2"


def test_session_memory_item_upsert_and_search(store):
    from agent.memory.models import MemoryItemRecord, new_id

    session_id = _session_id()
    store.ensure_session(session_id)
    marker = uuid.uuid4().hex
    store.upsert_memory_item(
        MemoryItemRecord(
            id=new_id("mem"),
            scope="session",
            text=f"user studies retrieval marker {marker}",
            session_id=session_id,
        )
    )

    results = store.search_memory_items(marker, session_id=session_id, user_id=None, limit=5)

    assert len(results) == 1
    assert marker in results[0].text


def test_user_scoped_memory_is_recalled_across_sessions(store):
    from agent.memory.writer import MemoryWriter

    user_id = f"user-{uuid.uuid4().hex}"
    first_session = _session_id()
    second_session = _session_id()
    store.ensure_session(first_session, user_id=user_id)
    source = store.append_message(first_session, "user", "Remember my answer preference")
    marker = uuid.uuid4().hex

    item = MemoryWriter(store).write_candidate(
        text=f"User prefers concise technical answers marker {marker}",
        session_id=first_session,
        user_id=user_id,
        source_message_id=source.id,
        scope="user",
    )
    store.ensure_session(second_session, user_id=user_id)
    results = store.search_memory_items(
        marker,
        session_id=second_session,
        user_id=user_id,
        limit=5,
    )

    assert item is not None
    assert item.scope == "user"
    assert item.session_id is None
    assert [result.id for result in results] == [item.id]


def test_user_scoped_memory_is_not_visible_to_other_user(store):
    from agent.memory.models import MemoryItemRecord, new_id

    marker = uuid.uuid4().hex
    owner = f"owner-{uuid.uuid4().hex}"
    other = f"other-{uuid.uuid4().hex}"
    store.upsert_memory_item(
        MemoryItemRecord(
            id=new_id("mem"),
            scope="user",
            text=f"private preference {marker}",
            user_id=owner,
        )
    )
    other_session = _session_id()
    store.ensure_session(other_session, user_id=other)

    assert store.search_memory_items(
        marker,
        session_id=other_session,
        user_id=other,
        limit=5,
    ) == []


def test_delete_session_hides_all_session_data(store):
    from agent.memory.models import MemoryItemRecord, SessionSummaryRecord, new_id

    session_id = _session_id()
    store.ensure_session(session_id)
    message = store.append_message(session_id, "user", "delete me")
    store.upsert_session_summary(
        SessionSummaryRecord(session_id=session_id, summary="s", source_message_id=message.id)
    )
    store.upsert_memory_item(
        MemoryItemRecord(id=new_id("mem"), scope="session", text="fact to forget", session_id=session_id)
    )

    assert store.delete_session(session_id) is True
    assert store.get_recent_messages(session_id, limit=5) == []
    assert store.get_session_summary(session_id) is None
    assert store.search_memory_items("forget", session_id=session_id, user_id=None, limit=5) == []
    assert store.delete_session(session_id) is False
