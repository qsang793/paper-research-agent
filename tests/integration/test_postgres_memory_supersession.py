import os
import uuid

import pytest

from agent.memory.writer import MemoryWriter

DATABASE_URL = os.getenv("MEMORY_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="MEMORY_TEST_DATABASE_URL not configured",
)


def test_postgres_keyed_memory_supersedes_old_value_and_preserves_history():
    import psycopg
    from psycopg.rows import dict_row

    from agent.memory.postgres_store import PostgresMemoryStore

    store = PostgresMemoryStore(DATABASE_URL)
    store.setup()
    user_id = f"supersession-{uuid.uuid4().hex}"
    session_id = f"supersession-session-{uuid.uuid4().hex}"
    store.ensure_session(session_id, user_id=user_id)
    writer = MemoryWriter(store)

    old = writer.write_candidate(
        text="User prefers concise answers.",
        session_id=session_id,
        user_id=user_id,
        source_message_id=None,
        scope="user",
        memory_key="answer_style",
    )
    new = writer.write_candidate(
        text="User prefers detailed answers.",
        session_id=session_id,
        user_id=user_id,
        source_message_id=None,
        scope="user",
        memory_key="answer_style",
    )

    assert old is not None and new is not None
    active = store.search_memory_items("answers", session_id=session_id, user_id=user_id, limit=10)
    assert [item.id for item in active] == [new.id]
    assert active[0].memory_key == "answer_style"
    assert active[0].status == "active"

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT memory_id, memory_key, status, superseded_by_id, superseded_at
            FROM memory_item_lifecycle
            WHERE memory_id = ANY(%s::text[])
            ORDER BY memory_id
            """,
            ([old.id, new.id],),
        ).fetchall()

    by_id = {row["memory_id"]: row for row in rows}
    assert by_id[old.id]["status"] == "superseded"
    assert by_id[old.id]["superseded_by_id"] == new.id
    assert by_id[old.id]["superseded_at"] is not None
    assert by_id[new.id]["status"] == "active"
    assert by_id[new.id]["superseded_by_id"] is None


def test_postgres_supersession_is_user_isolated():
    from agent.memory.postgres_store import PostgresMemoryStore

    store = PostgresMemoryStore(DATABASE_URL)
    store.setup()
    writer = MemoryWriter(store)
    user_one = f"supersession-u1-{uuid.uuid4().hex}"
    user_two = f"supersession-u2-{uuid.uuid4().hex}"
    session_one = f"supersession-s1-{uuid.uuid4().hex}"
    session_two = f"supersession-s2-{uuid.uuid4().hex}"
    store.ensure_session(session_one, user_id=user_one)
    store.ensure_session(session_two, user_id=user_two)

    first = writer.write_candidate(
        text="User prefers concise answers.",
        session_id=session_one,
        user_id=user_one,
        source_message_id=None,
        scope="user",
        memory_key="answer_style",
    )
    second = writer.write_candidate(
        text="User prefers detailed answers.",
        session_id=session_two,
        user_id=user_two,
        source_message_id=None,
        scope="user",
        memory_key="answer_style",
    )

    assert first is not None and second is not None
    user_one_items = store.search_memory_items("answers", session_id=session_one, user_id=user_one, limit=10)
    user_two_items = store.search_memory_items("answers", session_id=session_two, user_id=user_two, limit=10)
    assert [item.id for item in user_one_items] == [first.id]
    assert [item.id for item in user_two_items] == [second.id]


def test_deleting_replacement_session_keeps_superseded_history_valid():
    import psycopg
    from psycopg.rows import dict_row

    from agent.memory.postgres_store import PostgresMemoryStore

    store = PostgresMemoryStore(DATABASE_URL)
    store.setup()
    writer = MemoryWriter(store)
    user_id = f"supersession-delete-{uuid.uuid4().hex}"
    old_session = f"supersession-old-{uuid.uuid4().hex}"
    new_session = f"supersession-new-{uuid.uuid4().hex}"
    store.ensure_session(old_session, user_id=user_id)
    store.ensure_session(new_session, user_id=user_id)
    old_source = store.append_message(old_session, "user", "Remember concise answers")
    new_source = store.append_message(new_session, "user", "Actually remember detailed answers")

    old = writer.write_candidate(
        text="User prefers concise answers.",
        session_id=old_session,
        user_id=user_id,
        source_message_id=old_source.id,
        scope="user",
        memory_key="answer_style",
    )
    new = writer.write_candidate(
        text="User prefers detailed answers.",
        session_id=new_session,
        user_id=user_id,
        source_message_id=new_source.id,
        scope="user",
        memory_key="answer_style",
    )
    assert old is not None and new is not None

    assert store.delete_session(new_session) is True
    assert store.search_memory_items("answers", session_id=old_session, user_id=user_id, limit=10) == []

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT lifecycle.status, lifecycle.superseded_by_id
            FROM memory_item_lifecycle AS lifecycle
            WHERE lifecycle.memory_id = %s
            """,
            (old.id,),
        ).fetchone()

    assert row is not None
    assert row["status"] == "superseded"
    assert row["superseded_by_id"] == new.id
