from agent.memory.config import MemoryConfig
from agent.memory.models import MemoryItemRecord
from agent.memory.profile import get_user_profile_memories, merge_memory_items
from agent.memory.store import InMemoryMemoryStore
from api.chat_orchestrator import ResearchChatWorkflow


def test_profile_memory_does_not_require_query_token_overlap():
    store = InMemoryMemoryStore()
    store.upsert_memory_item(
        MemoryItemRecord(
            id="profile-1",
            scope="user",
            text="User prefers concise technical answers.",
            user_id="u1",
        )
    )
    workflow = ResearchChatWorkflow(
        inject_memory_context_fn=lambda query, memory: (query, ""),
        run_preview_fn=lambda *args, **kwargs: {},
        memory_store=store,
        memory_config=MemoryConfig(
            persistent_transcript_enabled=True,
            long_term_memory_enabled=True,
            research_memory_enabled=True,
        ),
    )

    context = workflow.build_memory_context(
        "Explain retrieval augmented generation.",
        session_id="new-thread",
        user_id="u1",
        memory=None,
    )

    assert "User prefers concise technical answers." in context


def test_profile_memory_is_user_isolated():
    store = InMemoryMemoryStore()
    store.upsert_memory_item(
        MemoryItemRecord(
            id="profile-u1",
            scope="user",
            text="User prefers concise technical answers.",
            user_id="u1",
        )
    )

    assert get_user_profile_memories(store, "u2", limit=5) == []


def test_profile_and_relevant_memory_merge_deduplicates_by_id():
    item = MemoryItemRecord(
        id="same",
        scope="user",
        text="User prefers concise technical answers.",
        user_id="u1",
    )

    merged = merge_memory_items([item], [item], limit=5)

    assert [value.id for value in merged] == ["same"]
