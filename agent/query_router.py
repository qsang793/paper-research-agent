"""Canonical structured router for chat and research requests.

Natural-language understanding lives here. Downstream policy code only maps the
validated decision to execution behavior; it must not maintain phrase lists or
intent examples.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent.generator import call_gemini, call_ollama, call_openrouter

logger = logging.getLogger(__name__)


class RouteType(str, Enum):
    """High-level interaction route."""

    STATIC = "static"
    LLM_ONLY = "llm_only"
    RAG = "rag"
    OUT_OF_SCOPE = "out_of_scope"


FreshnessNeed = Literal["none", "current", "mixed"]


@dataclass(frozen=True)
class RouteResult:
    """Validated routing result consumed by query policy and compatibility code."""

    route_type: RouteType
    response: Optional[str] = None
    intent: str = "unknown"
    confidence: float = 0.0
    standalone_query: str = ""
    freshness: FreshnessNeed = "none"
    memory_write: Optional[str] = None
    memory_key: Optional[str] = None


class _RouterDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    route_type: RouteType = RouteType.RAG
    intent: str = "research"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    standalone_query: str = ""
    freshness: FreshnessNeed = "none"
    response: Optional[str] = None
    memory_write: Optional[str] = None
    memory_key: Optional[str] = None

    @field_validator("intent", "standalone_query")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("response", "memory_write", "memory_key")
    @classmethod
    def _strip_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    def to_result(self, fallback_query: str) -> RouteResult:
        standalone_query = self.standalone_query or fallback_query.strip()
        route_type = self.route_type
        response = self.response if route_type == RouteType.STATIC else None
        if route_type == RouteType.STATIC and not response:
            # A static route without an answer would create an empty response.
            route_type = RouteType.LLM_ONLY
        memory_write = self.memory_write
        return RouteResult(
            route_type=route_type,
            response=response,
            intent=self.intent or route_type.value,
            confidence=self.confidence,
            standalone_query=standalone_query,
            freshness=self.freshness,
            memory_write=memory_write,
            memory_key=self.memory_key if memory_write else None,
        )


ROUTER_PROMPT = """You are the routing layer for an AI research assistant.
Current UTC date: {current_date}

Return ONLY one JSON object matching this schema:
{{
  "route_type": "static" | "llm_only" | "rag" | "out_of_scope",
  "intent": "short semantic label",
  "confidence": 0.0,
  "standalone_query": "self-contained version of the latest request",
  "freshness": "none" | "current" | "mixed",
  "response": "direct answer only for static, otherwise null",
  "memory_write": "one concise durable user fact only when explicitly requested, otherwise null",
  "memory_key": "stable lowercase snake_case semantic slot for overwriteable memory, otherwise null"
}}

Routing policy:
- static: greetings, thanks, farewells, acknowledgements, and other trivial turns that can be answered directly by this routing call. Put the complete short reply in response, in the user's language.
- llm_only: conversational/meta/help/reasoning requests that do not require research evidence.
- rag: AI/ML/scientific-research questions that benefit from paper discovery, retrieval, evidence, or citations.
- out_of_scope: requests clearly outside the product's AI/ML/scientific-research scope.
- freshness=current when the answer depends mainly on current/latest/recent information relative to the runtime date above.
- freshness=mixed when both established background and current evidence matter.
- standalone_query must resolve pronouns and follow-up references from conversation context. It must contain only the self-contained research/request text, never the transcript, summary, or memory sections.
- memory_write must be null unless the user explicitly asks the assistant to remember a durable preference or fact. Write a concise user-centric fact. Never store credentials, secrets, authentication tokens, or other highly sensitive data.
- memory_key must be null when memory_write is null. When the durable fact is a profile/preference value that a later explicit user update should replace, return a stable semantic slot name in lowercase snake_case. For additive durable facts that can coexist, return null.
- Do not infer a durable memory merely because a fact appears in the conversation.

Conversation context (context only; do not copy it into standalone_query):
{conversation_context}

Latest user request:
{query}
"""


def _call_router(prompt: str, backend: str, model: str | None = None) -> str:
    if backend == "openrouter":
        return call_openrouter(prompt, model=model, temperature=0.0)
    if backend == "gemini":
        return call_gemini(prompt, model=model, temperature=0.0)
    return call_ollama(prompt, model=model, temperature=0.0)


def _parse_router_response(raw: str, fallback_query: str) -> RouteResult:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    candidates = [text]
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        extracted = text[first_brace : last_brace + 1]
        if extracted != text:
            candidates.append(extracted)

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
            decision = _RouterDecision.model_validate(payload)
            return decision.to_result(fallback_query)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    raise ValueError("router returned invalid structured output")


class StructuredQueryRouter:
    """LLM-backed router with a conservative research fallback."""

    def __init__(self, chroma_path: str = "./chroma", enabled: bool = True):
        # chroma_path remains accepted for call-site compatibility; intent routing no
        # longer creates an embedding collection inside the knowledge-base database.
        self.chroma_path = chroma_path
        self.enabled = enabled

    def route(self, query: str, *, conversation_context: str = "") -> RouteResult:
        query_stripped = query.strip()
        if not self.enabled:
            return RouteResult(
                route_type=RouteType.RAG,
                intent="router_disabled",
                standalone_query=query_stripped,
            )
        if not query_stripped:
            return RouteResult(
                route_type=RouteType.RAG,
                intent="empty",
                standalone_query=query_stripped,
            )

        backend = os.getenv("ROUTER_BACKEND", os.getenv("LLM_BACKEND", "openrouter")).strip().lower()
        model = os.getenv("ROUTER_MODEL") or None
        max_context_chars = max(0, int(os.getenv("ROUTER_CONTEXT_MAX_CHARS", "8000")))
        bounded_context = (conversation_context or "")[-max_context_chars:]
        prompt = ROUTER_PROMPT.format(
            current_date=datetime.now(timezone.utc).date().isoformat(),
            conversation_context=bounded_context or "(none)",
            query=query_stripped,
        )

        try:
            raw = _call_router(prompt, backend, model)
            return _parse_router_response(raw, query_stripped)
        except Exception as exc:
            logger.warning("Structured router failed; using conservative research fallback: %s", exc)
            return RouteResult(
                route_type=RouteType.RAG,
                intent="router_fallback",
                confidence=0.0,
                standalone_query=query_stripped,
                freshness="mixed",
            )

    def get_llm_prompt(self, query: str, intent: str = "chat") -> str:
        del intent
        return (
            "You are an AI research assistant. Respond naturally and concisely to "
            "the user's conversational request. Do not invent research citations.\n\n"
            f"User request: {query}"
        )


_router_instance: Optional[StructuredQueryRouter] = None


def get_router() -> StructuredQueryRouter:
    """Return the process-level canonical router."""
    global _router_instance
    if _router_instance is None:
        enabled = os.getenv("QUERY_ROUTER_ENABLED", "true").lower() == "true"
        _router_instance = StructuredQueryRouter(
            chroma_path=os.getenv("CHROMA_PATH", "./chroma"),
            enabled=enabled,
        )
    return _router_instance
