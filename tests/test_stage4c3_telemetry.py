from __future__ import annotations

import asyncio
import json

from agent.memory.config import MemoryConfig
from agent.memory.models import MemoryItemRecord
from agent.memory.store import InMemoryMemoryStore
from agent.query_router import RouteResult, RouteType
from agent.research.observability import ResearchTrace
from api.chat_orchestrator import ResearchChatWorkflow
from api.telemetry import (
    RequestTelemetry,
    RequestTelemetryMiddleware,
    bind_request_telemetry,
    get_request_telemetry,
    route_request,
)


def test_telemetry_payload_excludes_raw_memory_and_user_content():
    telemetry = RequestTelemetry(enabled=False)
    item = MemoryItemRecord(
        id="mem_opaque",
        scope="user",
        text="SECRET MEMORY TEXT must never enter generic telemetry",
        user_id="user-private-id",
        memory_key="answer_style",
    )
    telemetry.record_memory_selection([item], context_chars=123)

    payload = json.dumps(telemetry.to_dict())
    assert "SECRET MEMORY TEXT" not in payload
    assert "user-private-id" not in payload
    assert "mem_opaque" in payload
    assert "answer_style" in payload
    assert telemetry.memory_lookup_count == 1


def test_route_request_records_decision_without_query_or_context_content():
    class FakeRouter:
        def route(self, query: str, *, conversation_context: str = "") -> RouteResult:
            assert query == "raw private query"
            assert conversation_context == "raw private memory context"
            return RouteResult(
                route_type=RouteType.LLM_ONLY,
                intent="chat",
                confidence=0.91,
                standalone_query=query,
                freshness="none",
            )

    telemetry = RequestTelemetry(enabled=False)
    with bind_request_telemetry(telemetry):
        _, policy = route_request(
            FakeRouter(),
            "raw private query",
            conversation_context="raw private memory context",
            mode="auto",
        )

    payload = json.dumps(telemetry.to_dict())
    assert policy.decision.value == "chat"
    assert telemetry.route_decision == "chat"
    assert telemetry.router_confidence == 0.91
    assert telemetry.router_latency_ms is not None
    assert "raw private query" not in payload
    assert "raw private memory context" not in payload


def test_research_trace_carries_safe_request_identity():
    trace = ResearchTrace(
        context={
            "trace_id": "trace-1",
            "router_strategy_id": "router-a",
            "memory_strategy_id": "memory-a",
            "research_strategy_id": "research-a",
        }
    )
    with trace.span("discovery", providers=["arxiv"]):
        pass

    metrics = trace.to_metrics()
    assert metrics["trace_context"]["trace_id"] == "trace-1"
    assert metrics["trace_context"]["research_strategy_id"] == "research-a"
    assert metrics["spans"][0]["name"] == "discovery"


def test_memory_context_records_only_selected_memory_identity():
    store = InMemoryMemoryStore()
    store.ensure_session("session-1", user_id="user-1")
    item = store.upsert_memory_item(
        MemoryItemRecord(
            id="mem-selected",
            scope="user",
            text="User prefers detailed technical answers.",
            user_id="user-1",
            memory_key="answer_style",
        )
    )
    workflow = ResearchChatWorkflow(
        inject_memory_context_fn=lambda query, memory: (query, ""),
        run_preview_fn=lambda query, **kwargs: {},
        memory_store=store,
        memory_config=MemoryConfig(
            persistent_transcript_enabled=True,
            long_term_memory_enabled=True,
            research_memory_enabled=True,
        ),
    )
    telemetry = RequestTelemetry(enabled=False)
    with bind_request_telemetry(telemetry):
        context = workflow.build_memory_context(
            "What answer style does the user prefer?",
            session_id="session-1",
            user_id="user-1",
            memory=None,
        )

    assert item.text in context
    assert telemetry.selected_memories == [
        {"id": "mem-selected", "scope": "user", "memory_key": "answer_style"}
    ]
    assert item.text not in json.dumps(telemetry.to_dict())


def test_research_workflow_receives_trace_context_and_records_outcome():
    captured = {}

    def preview(query: str, **kwargs):
        captured.update(kwargs)
        return {
            "answer": "answer",
            "citations": [],
            "answerability": {"can_answer": True},
            "metrics": {
                "latency_summary": {"discovery": {"count": 1, "p50_ms": 2, "p95_ms": 2, "max_ms": 2}}
            },
        }

    workflow = ResearchChatWorkflow(
        inject_memory_context_fn=lambda query, memory: (query, ""),
        run_preview_fn=preview,
        memory_store=None,
        memory_config=MemoryConfig(),
    )
    telemetry = RequestTelemetry(enabled=False, trace_id="trace-research")
    with bind_request_telemetry(telemetry):
        result = workflow.run_stream_preview(
            "question",
            session_id="session-1",
            top_k=3,
            memory=None,
        )

    assert result["answer"] == "answer"
    assert captured["trace_context"]["trace_id"] == "trace-research"
    assert telemetry.research_latency_summary["discovery"]["p50_ms"] == 2
    assert telemetry.answerability is True
    assert telemetry.status == "success"


def test_asgi_middleware_keeps_trace_across_stream_and_adds_header():
    seen = []
    sent = []

    async def app(scope, receive, send):
        telemetry = get_request_telemetry()
        assert telemetry is not None
        seen.append(telemetry.trace_id)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"one", "more_body": True})
        await asyncio.sleep(0)
        assert get_request_telemetry() is telemetry
        seen.append(telemetry.trace_id)
        await send({"type": "http.response.body", "body": b"two", "more_body": False})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    middleware = RequestTelemetryMiddleware(app)
    asyncio.run(
        middleware(
            {"type": "http", "method": "GET", "path": "/test", "headers": []},
            receive,
            send,
        )
    )

    start = next(message for message in sent if message["type"] == "http.response.start")
    headers = dict(start["headers"])
    assert b"x-request-id" in headers
    assert headers[b"x-request-id"].decode("ascii") == seen[0] == seen[1]
    assert get_request_telemetry() is None
