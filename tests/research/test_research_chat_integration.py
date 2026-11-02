import asyncio
import json
import threading

import pytest
from fastapi.testclient import TestClient

from agent.memory.store import InMemoryMemoryStore
from agent.query_router import RouteResult, RouteType
from api.main import app
from api.models import ChatRequest
from api.routes import chat as chat_route
from api.routes.chat import chat_stream, sessions


_MEMORY_ENV_KEYS = [
    "PERSISTENT_TRANSCRIPT_ENABLED",
    "SESSION_SUMMARY_ENABLED",
    "LONG_TERM_MEMORY_ENABLED",
    "RESEARCH_MEMORY_ENABLED",
    "CONVERSATIONAL_MEMORY_ENABLED",
    "MEMORY_DATABASE_URL",
    "MEMORY_RECENT_MESSAGE_LIMIT",
    "MEMORY_MAX_CONTEXT_CHARS",
]


class _MemoryEntry:
    def __init__(self, query, answer):
        self.query = query
        self.answer = answer


class _FakeMemory:
    def __init__(self):
        self.add_calls = []
        self.thread_ids = {}

    def get_recent(self, n=5):
        self.thread_ids["get_recent"] = threading.get_ident()
        return [_MemoryEntry("Earlier topic", "Earlier answer about RAG limitations.")]

    def search_similar(self, query, top_k=2):
        self.thread_ids["search_similar"] = threading.get_ident()
        return [_MemoryEntry("Related topic", "Prior answer about GraphRAG.")]

    def add(self, query, answer, citations):
        self.thread_ids["add"] = threading.get_ident()
        self.add_calls.append({"query": query, "answer": answer, "citations": citations})


class _RagRouter:
    def __init__(self, standalone_query="GraphRAG limitations"):
        self.standalone_query = standalone_query
        self.contexts = []

    def route(self, query, *, conversation_context=""):
        self.contexts.append(conversation_context)
        return RouteResult(
            route_type=RouteType.RAG,
            intent="research_follow_up",
            confidence=0.9,
            standalone_query=self.standalone_query,
        )

    def get_llm_prompt(self, query, intent):
        return query


class _StaticRouter:
    def route(self, query, *, conversation_context=""):
        return RouteResult(
            route_type=RouteType.STATIC,
            intent="greeting",
            confidence=1.0,
            response="Hello from static route",
            standalone_query=query,
        )


class _OutOfScopeRouter:
    def route(self, query, *, conversation_context=""):
        return RouteResult(
            route_type=RouteType.OUT_OF_SCOPE,
            intent="outside_research_scope",
            confidence=0.98,
            standalone_query=query,
        )


class _LlmRouter:
    def __init__(self, memory_write=None):
        self.memory_write = memory_write
        self.contexts = []

    def route(self, query, *, conversation_context=""):
        self.contexts.append(conversation_context)
        return RouteResult(
            route_type=RouteType.LLM_ONLY,
            intent="conversation",
            confidence=0.95,
            standalone_query=query,
            memory_write=self.memory_write,
        )

    def get_llm_prompt(self, query, intent):
        return f"fallback prompt: {query}"


@pytest.fixture(autouse=True)
def clean_chat_route_state(monkeypatch):
    for key in _MEMORY_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(chat_route, "memory_store", None)
    monkeypatch.setattr(chat_route, "memory_store_backend", "disabled")
    monkeypatch.setattr(chat_route, "memory_store_error", None)
    sessions.clear()
    yield
    monkeypatch.setattr(chat_route, "memory_store", None)
    sessions.clear()


def _preview(answer="Research workflow answer", can_answer=True):
    return {
        "answer": answer,
        "citations": [
            {
                "title": "ROS 2 paper",
                "authors": ["A. Researcher"],
                "url": "https://example.test/ros2",
                "arxiv_id": "2306.17157",
                "relevance_score": 0.91,
                "snippet": "ROS 2 is used in robotics research.",
            }
        ],
        "answerability": {"can_answer": can_answer},
    }


def _collect_stream(response):
    chunks = []

    async def collect():
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    asyncio.run(collect())
    return "".join(chunks)


def _stream_delta_text(stream_text: str) -> str:
    text = []
    for line in stream_text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = json.loads(line.removeprefix("data: "))
        if payload.get("type") == "text-delta":
            text.append(payload.get("delta", ""))
    return "".join(text)


def test_chat_uses_standalone_query_for_research_and_context_only_for_continuity(monkeypatch):
    router = _RagRouter("GraphRAG limitations compared with RAG")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: router)
    sessions["research-session"] = _FakeMemory()
    preview_calls = []

    def fake_research_preview(
        query,
        *,
        top_k=5,
        providers=None,
        generate=None,
        question=None,
        memory_context="",
    ):
        preview_calls.append(
            {
                "query": query,
                "top_k": top_k,
                "providers": providers,
                "generate": generate,
                "question": question,
                "memory_context": memory_context,
            }
        )
        return _preview()

    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_research_preview)
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        json={
            "query": "What about GraphRAG?",
            "session_id": "research-session",
            "mode": "search",
            "search_source": "research",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Research workflow answer"
    call = preview_calls[0]
    assert call["query"] == "GraphRAG limitations compared with RAG"
    assert call["question"] == "What about GraphRAG?"
    assert call["memory_context"]
    assert "Earlier answer about RAG limitations" in call["memory_context"]
    assert "Earlier answer about RAG limitations" not in call["query"]
    assert router.contexts[0] == call["memory_context"]


def test_chat_static_query_bypasses_research_workflow(monkeypatch):
    monkeypatch.setattr("api.routes.chat.get_router", lambda: _StaticRouter())
    monkeypatch.setattr(
        "api.routes.chat.run_research_preview",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("static route should not call research workflow")
        ),
    )

    response = TestClient(app).post("/api/chat", json={"query": "hello"})

    assert response.status_code == 200
    assert response.json()["answer"] == "Hello from static route"
    assert response.json()["citations"] == []


def test_out_of_scope_decision_is_router_driven_and_persisted(monkeypatch):
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: _OutOfScopeRouter())

    response = TestClient(app).post(
        "/api/chat",
        json={"query": "book a hotel", "session_id": "s1"},
    )

    assert response.status_code == 200
    messages = chat_route.memory_store.get_recent_messages("s1", limit=10)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "book a hotel"
    assert messages[1].content == response.json()["answer"]


def test_llm_only_turn_receives_persistent_conversation_context(monkeypatch):
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_MEMORY_ENABLED", "true")
    monkeypatch.setenv("CONVERSATIONAL_MEMORY_ENABLED", "true")
    router = _LlmRouter()
    monkeypatch.setattr("api.routes.chat.get_router", lambda: router)
    store = InMemoryMemoryStore()
    store.ensure_session("s1")
    store.append_message("s1", "user", "Earlier question")
    store.append_message("s1", "assistant", "Earlier answer")
    monkeypatch.setattr(chat_route, "memory_store", store)
    prompts = []

    async def fake_collect_simple_llm(prompt):
        prompts.append(prompt)
        return "I remember the previous turn."

    monkeypatch.setattr(chat_route, "_collect_simple_llm", fake_collect_simple_llm)

    response = TestClient(app).post(
        "/api/chat",
        json={"query": "What did we discuss?", "session_id": "s1"},
    )

    assert response.status_code == 200
    assert "Earlier answer" in router.contexts[0]
    assert "Earlier answer" in prompts[0]
    assert "What did we discuss?" in prompts[0]


def test_router_memory_write_becomes_cross_session_user_memory(monkeypatch):
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setenv("LONG_TERM_MEMORY_ENABLED", "true")
    router = _LlmRouter(memory_write="User prefers concise technical answers.")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: router)

    async def fake_collect_simple_llm(prompt):
        return "I will remember that."

    monkeypatch.setattr(chat_route, "_collect_simple_llm", fake_collect_simple_llm)
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "query": "Please remember my answer preference.",
            "session_id": "s1",
            "user_id": "u1",
            "mode": "auto",
        },
    )

    assert response.status_code == 200
    store = chat_route.memory_store
    store.ensure_session("s2", user_id="u1")
    memories = store.search_memory_items(
        "concise technical answers",
        session_id="s2",
        user_id="u1",
        limit=5,
    )
    assert len(memories) == 1
    assert memories[0].scope == "user"
    assert memories[0].session_id is None


def test_research_path_binds_persistent_session_to_authenticated_user(monkeypatch):
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    router = _RagRouter("ROS2 robotics")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: router)
    monkeypatch.setattr(
        "api.routes.chat.run_research_preview",
        lambda *args, **kwargs: _preview(answer="Owned research answer"),
    )

    response = TestClient(app).post(
        "/api/chat",
        json={
            "query": "ROS2 in robotics",
            "session_id": "owned-session",
            "user_id": "user-1",
            "mode": "search",
        },
    )

    assert response.status_code == 200
    with pytest.raises(ValueError, match="different user"):
        chat_route.memory_store.ensure_session("owned-session", user_id="user-2")


def test_stream_research_uses_same_clean_query_boundary(monkeypatch):
    router = _RagRouter("GraphRAG limitations")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: router)
    sessions["stream-session"] = _FakeMemory()
    preview_calls = []

    def fake_research_preview(
        query,
        *,
        top_k=5,
        providers=None,
        generate=None,
        question=None,
        memory_context="",
    ):
        preview_calls.append((query, question, memory_context))
        return _preview(answer="Streamed research answer")

    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_research_preview)
    response = asyncio.run(
        chat_stream(
            ChatRequest(
                query="What about GraphRAG?",
                session_id="stream-session",
                mode="search",
                top_k=3,
            )
        )
    )
    stream_text = _collect_stream(response)

    assert preview_calls[0][0] == "GraphRAG limitations"
    assert preview_calls[0][1] == "What about GraphRAG?"
    assert preview_calls[0][2]
    assert preview_calls[0][2] not in preview_calls[0][0]
    assert "Streamed research answer" in stream_text
    assert '"type": "source-url"' in stream_text
    assert stream_text.count('"type": "finish"') == 1


def test_stream_no_answer_does_not_pollute_legacy_memory(monkeypatch):
    monkeypatch.setattr("api.routes.chat.get_router", lambda: _RagRouter("unknown paper"))
    memory = _FakeMemory()
    sessions["no-answer-session"] = memory
    monkeypatch.setattr(
        "api.routes.chat.run_research_preview",
        lambda *args, **kwargs: _preview(
            answer="Khong tim thay paper phu hop cho cau hoi nay.",
            can_answer=False,
        ),
    )

    response = asyncio.run(
        chat_stream(
            ChatRequest(
                query="unknown paper query",
                session_id="no-answer-session",
                mode="search",
            )
        )
    )
    stream_text = _collect_stream(response)

    assert "Khong tim thay paper phu hop cho cau hoi nay." in stream_text
    assert memory.add_calls == []


def test_stream_static_is_persisted(monkeypatch):
    monkeypatch.setenv("PERSISTENT_TRANSCRIPT_ENABLED", "true")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: _StaticRouter())

    response = asyncio.run(
        chat_stream(ChatRequest(query="hello", session_id="static-stream", mode="auto"))
    )
    stream_text = _collect_stream(response)

    assert _stream_delta_text(stream_text) == "Hello from static route"
    messages = chat_route.memory_store.get_recent_messages("static-stream", limit=10)
    assert [message.role for message in messages] == ["user", "assistant"]
