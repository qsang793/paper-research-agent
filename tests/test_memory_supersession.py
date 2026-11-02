import json

import agent.query_router as query_router
from agent.memory.store import InMemoryMemoryStore
from agent.memory.writer import MemoryWriter
from agent.query_policy import decide_query_policy
from agent.query_router import StructuredQueryRouter


def _writer_with_user():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    return store, MemoryWriter(store)


def test_keyed_memory_supersedes_old_value_but_preserves_history():
    store, writer = _writer_with_user()

    old = writer.write_candidate(
        text="User prefers concise answers.",
        session_id="s1",
        user_id="u1",
        source_message_id=None,
        scope="user",
        memory_key="answer_style",
    )
    new = writer.write_candidate(
        text="User prefers detailed answers.",
        session_id="s1",
        user_id="u1",
        source_message_id=None,
        scope="user",
        memory_key="answer_style",
    )

    assert old is not None and new is not None
    active = store.search_memory_items("answers", session_id="s1", user_id="u1", limit=10)
    assert [item.id for item in active] == [new.id]
    assert store.memory_items[old.id].status == "superseded"
    assert store.memory_items[old.id].superseded_by_id == new.id
    assert store.memory_items[new.id].status == "active"


def test_different_memory_keys_remain_active_together():
    store, writer = _writer_with_user()
    style = writer.write_candidate(
        text="User prefers detailed answers.",
        session_id="s1",
        user_id="u1",
        source_message_id=None,
        scope="user",
        memory_key="answer_style",
    )
    language = writer.write_candidate(
        text="User prefers Vietnamese responses.",
        session_id="s1",
        user_id="u1",
        source_message_id=None,
        scope="user",
        memory_key="preferred_language",
    )

    assert style is not None and language is not None
    assert store.memory_items[style.id].status == "active"
    assert store.memory_items[language.id].status == "active"


def test_same_memory_key_never_supersedes_another_user():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    store.ensure_session("s2", user_id="u2")
    writer = MemoryWriter(store)
    first = writer.write_candidate(
        text="User prefers concise answers.",
        session_id="s1",
        user_id="u1",
        source_message_id=None,
        scope="user",
        memory_key="answer_style",
    )
    second = writer.write_candidate(
        text="User prefers detailed answers.",
        session_id="s2",
        user_id="u2",
        source_message_id=None,
        scope="user",
        memory_key="answer_style",
    )

    assert first is not None and second is not None
    assert store.memory_items[first.id].status == "active"
    assert store.memory_items[second.id].status == "active"


def test_unkeyed_memories_keep_additive_behavior():
    store, writer = _writer_with_user()
    first = writer.write_candidate(
        text="User follows GraphRAG research.",
        session_id="s1",
        user_id="u1",
        source_message_id=None,
        scope="user",
    )
    second = writer.write_candidate(
        text="User follows agentic RAG research.",
        session_id="s1",
        user_id="u1",
        source_message_id=None,
        scope="user",
    )

    assert first is not None and second is not None
    assert store.memory_items[first.id].status == "active"
    assert store.memory_items[second.id].status == "active"


def test_router_memory_key_is_propagated_only_with_memory_write(monkeypatch):
    responses = iter(
        [
            {
                "route_type": "llm_only",
                "intent": "remember_preference",
                "confidence": 0.99,
                "standalone_query": "Remember my answer preference",
                "freshness": "none",
                "response": None,
                "memory_write": "User prefers detailed answers.",
                "memory_key": "answer_style",
            },
            {
                "route_type": "llm_only",
                "intent": "chat",
                "confidence": 0.9,
                "standalone_query": "Explain the plan",
                "freshness": "none",
                "response": None,
                "memory_write": None,
                "memory_key": "answer_style",
            },
        ]
    )
    monkeypatch.setattr(
        query_router,
        "_call_router",
        lambda prompt, backend, model=None: json.dumps(next(responses)),
    )

    remembered = StructuredQueryRouter().route("Remember that I prefer detailed answers")
    policy = decide_query_policy("Remember that I prefer detailed answers", route_result=remembered)
    normal = StructuredQueryRouter().route("Explain the plan")

    assert remembered.memory_key == "answer_style"
    assert policy.memory_key == "answer_style"
    assert normal.memory_write is None
    assert normal.memory_key is None
