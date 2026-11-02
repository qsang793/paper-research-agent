from __future__ import annotations

import inspect
import logging
import os
import time
from typing import Any, Callable

from agent.memory.config import MemoryConfig
from agent.memory.context_assembler import ContextAssembler
from agent.memory.profile import get_user_profile_memories, merge_memory_items
from agent.memory.transcript import ChatTranscriptWriter, PersistTurnResult
from agent.research.chat_adapter import (
    research_preview_to_chat_response,
    research_preview_to_source_events,
)
from api.telemetry import get_request_telemetry

logger = logging.getLogger(__name__)


class SessionOwnerMismatch(ValueError):
    pass


class ResearchChatWorkflow:
    """Canonical adapter from conversation state to the research workflow."""

    def __init__(
        self,
        *,
        inject_memory_context_fn: Callable[..., tuple[str, str]],
        run_preview_fn: Callable[..., dict],
        to_chat_response_fn: Callable[..., Any] | None = None,
        to_source_events_fn: Callable[..., list[dict]] | None = None,
        memory_store: Any | None = None,
        memory_config: MemoryConfig | None = None,
    ) -> None:
        self._inject_memory_context = inject_memory_context_fn
        self._run_preview = run_preview_fn
        self._to_chat_response = to_chat_response_fn or research_preview_to_chat_response
        self._to_source_events = to_source_events_fn or research_preview_to_source_events
        self._memory_store = memory_store
        self._memory_config = memory_config or MemoryConfig()
        self._transcript_writer = ChatTranscriptWriter(memory_store, self._memory_config)

    def build_memory_context(
        self,
        query: str,
        *,
        session_id: str,
        user_id: str | None,
        memory: Any,
    ) -> str:
        """Build bounded conversation/profile context without mutating retrieval text."""
        telemetry = get_request_telemetry()
        if not self._memory_store or not self._memory_config.research_memory_enabled:
            _, context = self._inject_memory_context(query, memory)
            if telemetry:
                telemetry.record_memory_selection([], context_chars=len(context))
            return context

        try:
            session = self._memory_store.ensure_session(session_id, user_id=user_id)
            if _session_owner_mismatch(session.user_id, user_id):
                raise SessionOwnerMismatch("active session belongs to a different user")
            summary = (
                self._memory_store.get_session_summary(session_id)
                if self._memory_config.session_summary_enabled
                else None
            )
            recent_messages = self._memory_store.get_recent_messages(
                session_id,
                limit=self._memory_config.recent_message_limit,
            )

            memories = []
            if self._memory_config.long_term_memory_enabled:
                memory_limit = max(1, int(os.getenv("USER_PROFILE_MEMORY_LIMIT", "5")))
                relevant_memories = self._memory_store.search_memory_items(
                    query,
                    session_id=session_id,
                    user_id=user_id,
                    limit=memory_limit,
                )
                profile_memories = get_user_profile_memories(
                    self._memory_store,
                    user_id,
                    limit=memory_limit,
                )
                memories = merge_memory_items(
                    profile_memories,
                    relevant_memories,
                    limit=memory_limit,
                )

            assembled = ContextAssembler(max_chars=self._memory_config.max_context_chars).assemble(
                query=query,
                recent_messages=recent_messages,
                summary=summary,
                memories=memories,
            )
            if telemetry:
                telemetry.record_memory_selection(memories, context_chars=len(assembled.text))
            return assembled.text
        except Exception as exc:
            if _is_session_owner_error(exc):
                # Ownership mismatches must fail closed. Falling back to legacy
                # in-process memory here could expose context from a session that
                # belongs to another authenticated user.
                logger.warning(
                    "Skipped all memory context due to session ownership mismatch"
                )
                if telemetry:
                    telemetry.record_memory_selection([], context_chars=0)
                return ""
            logger.warning("Failed to assemble persistent memory context", exc_info=True)
            _, context = self._inject_memory_context(query, memory)
            if telemetry:
                telemetry.record_memory_selection([], context_chars=len(context))
            return context

    def _run_preview_compat(
        self,
        research_query: str,
        *,
        top_k: int,
        question: str,
        memory_context: str,
    ) -> dict:
        """Invoke preview adapters while keeping the retrieval query clean.

        Production `run_research_preview` accepts the Stage 4B question/context
        fields. Older injected test/dev adapters may expose the pre-4B signature;
        unsupported kwargs are omitted rather than folded into `research_query`.
        """
        telemetry = get_request_telemetry()
        kwargs: dict[str, Any] = {
            "top_k": top_k,
            "providers": None,
            "generate": True,
            "question": question,
            "memory_context": memory_context,
        }
        if telemetry:
            kwargs["trace_context"] = telemetry.research_context()
        try:
            signature = inspect.signature(self._run_preview)
        except (TypeError, ValueError):
            signature = None

        if signature is not None:
            accepts_kwargs = any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
            if not accepts_kwargs:
                kwargs = {
                    key: value
                    for key, value in kwargs.items()
                    if key in signature.parameters
                }

        return self._run_preview(research_query, **kwargs)

    def run_chat_response(
        self,
        query: str,
        *,
        session_id: str,
        top_k: int | None,
        memory: Any,
        start_time: float,
        user_id: str | None = None,
        research_query: str | None = None,
        memory_context: str | None = None,
        memory_write: str | None = None,
        memory_key: str | None = None,
        now_fn: Callable[[], float] = time.time,
    ) -> Any:
        resolved_context = (
            memory_context
            if memory_context is not None
            else self.build_memory_context(
                query,
                session_id=session_id,
                user_id=user_id,
                memory=memory,
            )
        )
        clean_research_query = (research_query or query).strip()
        preview = self._run_preview_compat(
            clean_research_query,
            top_k=top_k or 5,
            question=query,
            memory_context=resolved_context,
        )
        telemetry = get_request_telemetry()
        if telemetry:
            telemetry.record_research_metrics(preview.get("metrics"))
        response_time_ms = (now_fn() - start_time) * 1000
        response = self._to_chat_response(
            preview,
            session_id=session_id,
            response_time_ms=response_time_ms,
        )
        can_answer = (preview.get("answerability") or {}).get("can_answer", True)
        self._persist_transcript(
            session_id=session_id,
            user_id=user_id,
            query=query,
            answer=response.answer,
            sources=[
                {
                    "title": citation.title,
                    "url": citation.url,
                    "source_type": "paper",
                }
                for citation in response.citations
            ],
            memory_write=memory_write,
            memory_key=memory_key,
        )
        if memory and response.answer and can_answer:
            citation_urls = [citation.url for citation in response.citations if citation.url]
            memory.add(query, response.answer, citation_urls)
        if telemetry:
            telemetry.complete(answerability=bool(can_answer), citation_count=len(response.citations))
        return response

    def run_stream_preview(
        self,
        query: str,
        *,
        session_id: str,
        top_k: int | None,
        memory: Any,
        user_id: str | None = None,
        research_query: str | None = None,
        memory_context: str | None = None,
        memory_write: str | None = None,
        memory_key: str | None = None,
    ) -> dict:
        resolved_context = (
            memory_context
            if memory_context is not None
            else self.build_memory_context(
                query,
                session_id=session_id,
                user_id=user_id,
                memory=memory,
            )
        )
        clean_research_query = (research_query or query).strip()
        preview = self._run_preview_compat(
            clean_research_query,
            top_k=top_k or 5,
            question=query,
            memory_context=resolved_context,
        )
        telemetry = get_request_telemetry()
        if telemetry:
            telemetry.record_research_metrics(preview.get("metrics"))
        answer = preview.get("answer") or ""
        can_answer = (preview.get("answerability") or {}).get("can_answer", True)
        if memory and answer and can_answer:
            citation_urls = [
                event["url"]
                for event in self._to_source_events(preview)
                if event.get("url")
            ]
            memory.add(query, answer, citation_urls)
        source_events = self._to_source_events(preview)
        self._persist_transcript(
            session_id=session_id,
            user_id=user_id,
            query=query,
            answer=answer,
            sources=source_events,
            memory_write=memory_write,
            memory_key=memory_key,
        )
        if telemetry:
            telemetry.complete(answerability=bool(can_answer), citation_count=len(source_events))
        return preview

    def _persist_transcript(
        self,
        *,
        session_id: str,
        user_id: str | None = None,
        query: str,
        answer: str,
        sources: list[dict],
        memory_write: str | None = None,
        memory_key: str | None = None,
    ) -> PersistTurnResult:
        return self._transcript_writer.persist_turn(
            session_id=session_id,
            user_id=user_id,
            query=query,
            answer=answer,
            sources=sources,
            memory_write=memory_write,
            memory_key=memory_key,
        )


def _session_owner_mismatch(existing_user_id: str | None, requested_user_id: str | None) -> bool:
    if existing_user_id == requested_user_id:
        return False
    return existing_user_id is not None or requested_user_id is not None


def _is_session_owner_error(exc: BaseException) -> bool:
    if isinstance(exc, SessionOwnerMismatch):
        return True
    return isinstance(exc, ValueError) and "different user" in str(exc).casefold()
