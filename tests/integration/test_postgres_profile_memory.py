import os
import uuid

import pytest

from agent.memory.models import MemoryItemRecord, new_id
from agent.memory.profile import get_user_profile_memories

DATABASE_URL = os.getenv("MEMORY_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="MEMORY_TEST_DATABASE_URL not configured",
)


def test_postgres_profile_memory_is_cross_thread_and_user_isolated():
    from agent.memory.postgres_store import PostgresMemoryStore

    store = PostgresMemoryStore(DATABASE_URL)
    store.setup()
    user_id = f"profile-{uuid.uuid4().hex}"
    other_user = f"profile-other-{uuid.uuid4().hex}"
    marker = uuid.uuid4().hex
    store.upsert_memory_item(
        MemoryItemRecord(
            id=new_id("mem"),
            scope="user",
            text=f"User prefers concise answers {marker}",
            user_id=user_id,
        )
    )

    owner_items = get_user_profile_memories(store, user_id, limit=5)
    other_items = get_user_profile_memories(store, other_user, limit=5)

    assert any(marker in item.text for item in owner_items)
    assert all(marker not in item.text for item in other_items)
