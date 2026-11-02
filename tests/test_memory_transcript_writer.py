from agent.memory.config import MemoryConfig
from agent.memory.store import InMemoryMemoryStore
from agent.memory.transcript import ChatTranscriptWriter


def test_transcript_writer_persists_source_free_turn():
    store = InMemoryMemoryStore()
    writer = ChatTranscriptWriter(
        store,
        MemoryConfig(persistent_transcript_enabled=True),
    )

    result = writer.persist_turn(
        session_id="s1",
        user_id=None,
        query="hi",
        answer="Hello from static route",
        sources=[],
    )

    messages = store.get_recent_messages("s1", limit=10)

    assert result.persisted is True
    assert result.user_message_id == messages[0].id
    assert result.assistant_message_id == messages[1].id
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "hi"
    assert messages[1].content == "Hello from static route"


def test_transcript_writer_persists_router_memory_as_user_scope():
    store = InMemoryMemoryStore()
    writer = ChatTranscriptWriter(
        store,
        MemoryConfig(
            persistent_transcript_enabled=True,
            long_term_memory_enabled=True,
        ),
    )

    result = writer.persist_turn(
        session_id="s1",
        user_id="u1",
        query="Please remember my preference.",
        answer="I will remember that.",
        sources=[],
        memory_write="User prefers concise technical answers.",
    )
    store.ensure_session("s2", user_id="u1")
    memories = store.search_memory_items(
        "concise technical answers",
        session_id="s2",
        user_id="u1",
        limit=5,
    )

    assert result.persisted is True
    assert len(memories) == 1
    assert memories[0].scope == "user"
    assert memories[0].session_id is None


def test_transcript_writer_does_not_infer_memory_without_router_candidate():
    store = InMemoryMemoryStore()
    writer = ChatTranscriptWriter(
        store,
        MemoryConfig(
            persistent_transcript_enabled=True,
            long_term_memory_enabled=True,
        ),
    )

    writer.persist_turn(
        session_id="s1",
        user_id="u1",
        query="I prefer comparison tables.",
        answer="Noted.",
        sources=[],
        memory_write=None,
    )

    assert store.search_memory_items(
        "comparison tables",
        session_id="s1",
        user_id="u1",
        limit=5,
    ) == []


def test_transcript_writer_keeps_answer_available_when_store_fails():
    class FailingStore:
        def ensure_session(self, session_id, user_id=None):
            raise RuntimeError("memory unavailable")

    writer = ChatTranscriptWriter(
        FailingStore(),
        MemoryConfig(persistent_transcript_enabled=True),
    )

    result = writer.persist_turn(
        session_id="s1",
        user_id=None,
        query="hello",
        answer="answer",
        sources=[],
    )

    assert result.persisted is False
    assert "memory unavailable" in (result.error or "")
