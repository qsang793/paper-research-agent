from __future__ import annotations

import contextvars
import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

from agent.query_policy import decide_query_policy

logger = logging.getLogger(__name__)
_current_telemetry: contextvars.ContextVar[RequestTelemetry | None] = contextvars.ContextVar(
    "request_telemetry",
    default=None,
)


@dataclass
class RequestTelemetry:
    """Vendor-neutral, content-free telemetry for one HTTP request.

    This object intentionally stores decisions, strategy identifiers, opaque
    record IDs, and timing metadata only. Raw queries, answers, memory text,
    credentials, and user/session identifiers do not belong in this envelope.
    """

    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    router_strategy_id: str = field(
        default_factory=lambda: os.getenv("ROUTER_STRATEGY_ID", "structured-router-v1")
    )
    memory_strategy_id: str = field(
        default_factory=lambda: os.getenv("MEMORY_STRATEGY_ID", "keyed-supersession-v1")
    )
    research_strategy_id: str = field(
        default_factory=lambda: os.getenv("RESEARCH_STRATEGY_ID", "paper-research-v1")
    )
    enabled: bool = field(
        default_factory=lambda: os.getenv("REQUEST_TELEMETRY_ENABLED", "true").lower() == "true"
    )
    started_at: float = field(default_factory=time.perf_counter, repr=False)
    http_status: int | None = None
    router_backend: str | None = None
    router_model: str | None = None
    route_decision: str | None = None
    freshness: str | None = None
    router_confidence: float | None = None
    router_fallback: bool = False
    router_latency_ms: float | None = None
    memory_lookup_count: int = 0
    selected_memories: list[dict[str, str | None]] = field(default_factory=list)
    memory_context_chars: int = 0
    research_latency_summary: dict[str, Any] = field(default_factory=dict)
    answerability: bool | None = None
    citation_count: int = 0
    status: str = "in_progress"
    error_type: str | None = None
    _emitted: bool = field(default=False, init=False, repr=False)

    def record_router(self, route_result: Any, policy: Any, *, latency_ms: float) -> None:
        self.router_backend = os.getenv("ROUTER_BACKEND", os.getenv("LLM_BACKEND", "openrouter"))
        self.router_model = os.getenv("ROUTER_MODEL") or os.getenv("OPENROUTER_MODEL") or os.getenv("GENAI_MODEL") or os.getenv("LLM_MODEL")
        decision = getattr(policy, "decision", None)
        self.route_decision = getattr(decision, "value", decision) or getattr(
            getattr(route_result, "route_type", None), "value", None
        )
        self.freshness = getattr(route_result, "freshness", None)
        self.router_confidence = float(getattr(route_result, "confidence", 0.0))
        self.router_fallback = getattr(route_result, "intent", "") in {
            "router_fallback",
            "router_disabled",
        }
        self.router_latency_ms = round(max(0.0, latency_ms), 3)

    def record_memory_selection(self, items: Iterable[Any], *, context_chars: int = 0) -> None:
        selected = []
        for item in items:
            selected.append(
                {
                    "id": str(getattr(item, "id", "")) or None,
                    "scope": str(getattr(item, "scope", "")) or None,
                    "memory_key": getattr(item, "memory_key", None),
                }
            )
        self.selected_memories = selected[:20]
        self.memory_lookup_count = len(selected)
        self.memory_context_chars = max(0, int(context_chars))

    def record_research_metrics(self, metrics: dict[str, Any] | None) -> None:
        payload = metrics or {}
        latency = payload.get("latency_summary")
        if isinstance(latency, dict):
            self.research_latency_summary = latency

    def complete(self, *, answerability: bool | None = None, citation_count: int = 0) -> None:
        self.status = "success"
        self.answerability = answerability
        self.citation_count = max(0, int(citation_count))

    def fail(self, exc: BaseException) -> None:
        self.status = "error"
        self.error_type = type(exc).__name__

    def mark_http_status(self, status_code: int) -> None:
        self.http_status = int(status_code)
        if self.status == "in_progress" and status_code >= 400:
            self.status = "error"

    def research_context(self) -> dict[str, str]:
        return {
            "trace_id": self.trace_id,
            "router_strategy_id": self.router_strategy_id,
            "memory_strategy_id": self.memory_strategy_id,
            "research_strategy_id": self.research_strategy_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "router_strategy_id": self.router_strategy_id,
            "memory_strategy_id": self.memory_strategy_id,
            "research_strategy_id": self.research_strategy_id,
            "http_status": self.http_status,
            "router_backend": self.router_backend,
            "router_model": self.router_model,
            "route_decision": self.route_decision,
            "freshness": self.freshness,
            "router_confidence": self.router_confidence,
            "router_fallback": self.router_fallback,
            "router_latency_ms": self.router_latency_ms,
            "memory_lookup_count": self.memory_lookup_count,
            "selected_memories": self.selected_memories,
            "memory_context_chars": self.memory_context_chars,
            "research_latency_summary": self.research_latency_summary,
            "answerability": self.answerability,
            "citation_count": self.citation_count,
            "status": self.status,
            "error_type": self.error_type,
            "request_duration_ms": round((time.perf_counter() - self.started_at) * 1000, 3),
        }

    def emit_once(self, target_logger: Any = logger) -> None:
        if self._emitted or not self.enabled:
            return
        self._emitted = True
        try:
            target_logger.info(
                "request_telemetry %s",
                json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True),
            )
        except Exception:
            # Telemetry must never affect request correctness.
            return


def get_request_telemetry() -> RequestTelemetry | None:
    return _current_telemetry.get()


@contextmanager
def bind_request_telemetry(telemetry: RequestTelemetry) -> Iterator[RequestTelemetry]:
    """Temporarily bind telemetry to the current context (useful for tests/tasks)."""
    token = _current_telemetry.set(telemetry)
    try:
        yield telemetry
    finally:
        _current_telemetry.reset(token)


def route_request(query_router: Any, query: str, *, conversation_context: str, mode: str):
    """Route one request and record router timing/decision without changing policy."""
    started = time.perf_counter()
    route_result = query_router.route(query, conversation_context=conversation_context)
    latency_ms = (time.perf_counter() - started) * 1000
    policy = decide_query_policy(query, mode=mode, route_result=route_result)
    telemetry = get_request_telemetry()
    if telemetry:
        telemetry.record_router(route_result, policy, latency_ms=latency_ms)
    return route_result, policy


class RequestTelemetryMiddleware:
    """ASGI middleware that provides one trace context across streaming responses."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        telemetry = RequestTelemetry()
        token = _current_telemetry.set(telemetry)

        async def send_with_telemetry(message: dict) -> None:
            try:
                if message.get("type") == "http.response.start":
                    status = int(message.get("status", 200))
                    telemetry.mark_http_status(status)
                    headers = list(message.get("headers") or [])
                    if not any(key.lower() == b"x-request-id" for key, _ in headers):
                        headers.append((b"x-request-id", telemetry.trace_id.encode("ascii")))
                    message["headers"] = headers
                elif message.get("type") == "http.response.body" and not message.get("more_body", False):
                    if telemetry.status == "in_progress":
                        telemetry.status = "success" if (telemetry.http_status or 200) < 400 else "error"
                    telemetry.emit_once()
            finally:
                await send(message)

        try:
            await self.app(scope, receive, send_with_telemetry)
        except Exception as exc:
            telemetry.fail(exc)
            telemetry.emit_once()
            raise
        finally:
            _current_telemetry.reset(token)
