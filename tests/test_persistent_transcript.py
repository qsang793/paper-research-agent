import pytest

from agent.memory.config import MemoryConfig
from agent.memory.models import MemoryItemRecord, SessionSummaryRecord
from agent.memory.store import InMemoryMemoryStore
from api.chat_orchestrator import ResearchChatWorkflow
from api.routes import chat as chat_route


_MEMORY_ENV_KEYS = [
    "PERSISTENT_TRANSCRIPT_ENABLED",
    "SESSION_SUMMARY_ENABLED",
    "LONG_TERM_MEMORY_ENABLED",
    "RESEARCH_MEMORY_ENABLED",
    "MEMORY_DATABASE_URL",
    "MEMORY_RECENT_MESSAGE_LIMIT",
    "MEMORY_MAX_CONTEXT_CHARS",
]


@pytest.fixture(autouse=True)
def clean_memory_route_state(monkeypatch):
    for key in _MEMORY_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(chat_route, "memory_store", None)
    yield
    monkeypatch.setattr(chat_route, "memory_store", None)


def _preview(
    query,
    top_k=5,
    providers=None,
    generate=True,
    question=None,
    memory_context="",
):
    return {
        "answer": "Research answer still returns.",
        "answerability": {"can_answer": True},
        "citations": [
            {
                "title": "RAG paper",
                "url": "https://arxiv.org/abs/2005.11401",
                "source_type": "paper",
                "relevance_score": 1.0,
            }
        ],
    }


def _workflow(store, config, preview_fn=_preview):
    def inject(query, memory):
        return f"{query}\nlegacy enhanced blob", "legacy context only"

    return ResearchChatWorkflow(
        inject_memory_context_fn=inject,
        run_preview_fn=preview_fn,
        memory_store=store,
        memory_config=config,
    )


def test_research_workflow_persists_transcript_and_sources():
    store = InMemoryMemoryStore()
    workflow = _workflow(
        store,
        MemoryConfig(persistent_transcript_enabled=True),
    )

    response = workflow.run_chat_response(
        "What is RAG?",
        session_id="s1",
        top_k=5,
        memory=None,
        start_time=0.0,
        research_query="retrieval augmented generation",
        memory_context="",
        now_fn=lambda: 1.0,
    )

    messages = store.get_recent_messages("s1", limit=10)
    assert response.answer == "Research answer still returns."
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "What is RAG?"
    assert messages[1].content == "Research answer still returns."
    sources = store.get_message_sources(messages[1].id)
    assert [(source.title, source.url) for source in sources] == [
        ("RAG paper", "https://arxiv.org/abs/2005.11401")
    ]


def test_persistent_context_is_built_but_not_inserted_into_retrieval_query():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    store.append_message("s1", "user", "Earlier question about RAG.")
    store.append_message("s1", "assistant", "Earlier answer mentions Lewis 2020.")
    store.upsert_session_summary(
        SessionSummaryRecord(session_id="s1", summary="Prior summary references Lewis 2020.")
    )
    store.upsert_memory_item(
        MemoryItemRecord(
            id="mem1",
            scope="user",
            text="User prefers comparison tables.",
            user_id="u1",
        )
    )
    calls = []

    def preview(
        query,
        *,
        top_k,
        providers,
        generate,
        question=None,
        memory_context="",
    ):
        calls.append((query, question, memory_context))
        return _preview(query, top_k, providers, generate, question, memory_context)

    workflow = _workflow(
        store,
        MemoryConfig(
            persistent_transcript_enabled=True,
            session_summary_enabled=True,
            long_term_memory_enabled=True,
            research_memory_enabled=True,
        ),
        preview,
    )

    context = workflow.build_memory_context(
        "What about comparison tables?",
        session_id="s1",
        user_id="u1",
        memory=None,
    )
    workflow.run_chat_response(
        "What about comparison tables?",
        session_id="s1",
        user_id="u1",
        top_k=5,
        memory=None,
        start_time=0.0,
        research_query="RAG comparison methods",
        memory_context=context,
        now_fn=lambda: 1.0,
    )

    query, question, memory_context = calls[0]
    assert query == "RAG comparison methods"
    assert question == "What about comparison tables?"
    assert "SESSION SUMMARY" in memory_context
    assert "Prior summary references Lewis 2020." in memory_context
    assert "Earlier answer mentions Lewis 2020." in memory_context
    assert "User prefers comparison tables." in memory_context
    assert "Prior summary references Lewis 2020." not in query


def test_session_summary_updates_when_enabled():
    store = InMemoryMemoryStore()
    workflow = _workflow(
        store,
        MemoryConfig(
            persistent_transcript_enabled=True,
            session_summary_enabled=True,
        ),
    )

    workflow.run_chat_response(
        "What is RAG?",
        session_id="s1",
        top_k=5,
        memory=None,
        start_time=0.0,
        now_fn=lambda: 1.0,
    )

    summary = store.get_session_summary("s1")
    assert summary is not None
    assert "user: What is RAG?" in summary.summary
    assert "assistant: Research answer still returns." in summary.summary


def test_long_term_memory_requires_explicit_memory_write():
    store = InMemoryMemoryStore()
    workflow = _workflow(
        store,
        MemoryConfig(
            persistent_transcript_enabled=True,
            long_term_memory_enabled=True,
        ),
    )

    workflow.run_chat_response(
        "I prefer concise answers.",
        session_id="s1",
        user_id="u1",
        top_k=5,
        memory=None,
        start_time=0.0,
        memory_write=None,
        now_fn=lambda: 1.0,
    )
    assert store.search_memory_items(
        "concise answers",
        session_id="s1",
        user_id="u1",
        limit=5,
    ) == []

    workflow.run_chat_response(
        "Please remember my answer preference.",
        session_id="s1",
        user_id="u1",
        top_k=5,
        memory=None,
        start_time=0.0,
        memory_write="User prefers concise answers.",
        now_fn=lambda: 1.0,
    )
    store.ensure_session("s2", user_id="u1")
    memories = store.search_memory_items(
        "concise answers",
        session_id="s2",
        user_id="u1",
        limit=5,
    )
    assert len(memories) == 1
    assert memories[0].scope == "user"
    assert memories[0].session_id is None


def test_persistent_session_is_bound_to_user():
    store = InMemoryMemoryStore()
    workflow = _workflow(
        store,
        MemoryConfig(persistent_transcript_enabled=True),
    )

    workflow.run_chat_response(
        "What is RAG?",
        session_id="s1",
        user_id="u1",
        top_k=5,
        memory=None,
        start_time=0.0,
        now_fn=lambda: 1.0,
    )

    with pytest.raises(ValueError, match="different user"):
        store.ensure_session("s1", user_id="u2")


def test_user_memory_is_available_in_another_session_context():
    store = InMemoryMemoryStore()
    store.upsert_memory_item(
        MemoryItemRecord(
            id="mem-user-1",
            scope="user",
            text="User prefers compact tables.",
            user_id="u1",
        )
    )
    workflow = _workflow(
        store,
        MemoryConfig(
            persistent_transcript_enabled=True,
            long_term_memory_enabled=True,
            research_memory_enabled=True,
        ),
    )

    context = workflow.build_memory_context(
        "Can you use compact tables?",
        session_id="new-session",
        user_id="u1",
        memory=None,
    )

    assert "User prefers compact tables." in context


def test_context_from_different_user_session_is_not_exposed():
    store = InMemoryMemoryStore()
    store.ensure_session("s1", user_id="u1")
    store.append_message("s1", "user", "private prior question")
    store.append_message("s1", "assistant", "private prior answer")
    workflow = _workflow(
        store,
        MemoryConfig(
            persistent_transcript_enabled=True,
            research_memory_enabled=True,
        ),
    )

    context = workflow.build_memory_context(
        "What is RAG?",
        session_id="s1",
        user_id="u2",
        memory=None,
    )

    assert context == ""
    assert "private prior answer" not in context


def test_stream_preview_persists_transcript_with_sources():
    store = InMemoryMemoryStore()
    workflow = _workflow(
        store,
        MemoryConfig(persistent_transcript_enabled=True),
    )

    workflow.run_stream_preview(
        "Stream this answer",
        session_id="s1",
        top_k=5,
        user_id="u1",
        memory=None,
        research_query="clean research query",
        memory_context="context only",
    )

    messages = store.get_recent_messages("s1", limit=10)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "Stream this answer"
    assert messages[1].content == "Research answer still returns."
    sources = store.get_message_sources(messages[1].id)
    assert sources[0].url == "https://arxiv.org/abs/2005.11401"


def test_memory_store_factory_returns_none_by_default():
    assert chat_route._get_memory_store() is None


def test_memory_store_factory_uses_cached_in_memory_store_when_enabled(monkeypatch):
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")

    first = chat_route._get_memory_store()
    second = chat_route._get_memory_store()

    assert isinstance(first, InMemoryMemoryStore)
    assert second is first
