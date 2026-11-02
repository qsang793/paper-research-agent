import asyncio
import json

from api.models import ChatRequest
from api.routes.chat import chat_stream, sessions


def test_chat_stream_uses_canonical_research_workflow(monkeypatch):
    asyncio.run(_run_chat_stream_test(monkeypatch))


async def _run_chat_stream_test(monkeypatch):
    calls = {"preview": 0}

    class FakeRouter:
        def route(self, query, *, conversation_context=""):
            from agent.query_router import RouteResult, RouteType

            assert conversation_context == ""
            return RouteResult(
                route_type=RouteType.RAG,
                intent="research",
                standalone_query="retrieval augmented generation",
            )

        def get_llm_prompt(self, query, intent):
            return query

    def fake_research_preview(
        query,
        *,
        top_k=5,
        providers=None,
        generate=None,
        question=None,
        memory_context="",
    ):
        calls["preview"] += 1
        assert query == "retrieval augmented generation"
        assert question == "What is RAG?"
        assert memory_context == ""
        return {
            "answer": "streamed research answer",
            "citations": [
                {
                    "title": "RAG paper",
                    "url": "https://example.com/rag",
                    "relevance_score": 0.9,
                }
            ],
            "answerability": {"can_answer": True},
        }

    monkeypatch.setattr("api.routes.chat.get_router", lambda: FakeRouter())
    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_research_preview)
    sessions.clear()

    response = await chat_stream(ChatRequest(query="What is RAG?"))
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    stream_text = "".join(chunks)
    assert calls == {"preview": 1}
    assert "streamed research answer" in stream_text
    assert '"type": "source-url"' in stream_text
    assert '"sourceId": "research_source_0"' in stream_text
    assert json.dumps("https://example.com/rag") in stream_text
    assert stream_text.count('"type": "finish"') == 1
