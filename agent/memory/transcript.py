from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from agent.memory.config import MemoryConfig
from agent.memory.models import ChatSessionRecord, MessageSourceRecord, SessionSummaryRecord
from agent.memory.summarizer import build_deterministic_summary
from agent.memory.writer import MemoryWriter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PersistTurnResult:
    persisted: bool
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    error: str | None = None


class ChatTranscriptWriter:
    def __init__(self, store: Any | None, config: MemoryConfig) -> None:
        self._store = store
        self._config = config

    def persist_turn(
        self,
        *,
        session_id: str,
        user_id: str | None,
        query: str,
        answer: str,
        sources: list[dict],
        memory_write: str | None = None,
        memory_key: str | None = None,
    ) -> PersistTurnResult:
        if not self._store or not self._config.persistent_transcript_enabled:
            return PersistTurnResult(persisted=False)

        user_message_id: str | None = None
        assistant_message_id: str | None = None

        try:
            session = self._store.ensure_session(session_id=session_id, user_id=user_id)
            _raise_if_session_owner_mismatch(session, user_id)
            user_message = self._store.append_message(
                session_id=session_id,
                role="user",
                content=query,
            )
            user_message_id = user_message.id

            if not answer:
                self._write_long_term_memory(
                    memory_write,
                    memory_key,
                    session_id,
                    user_id,
                    user_message.id,
                )
                return PersistTurnResult(persisted=True, user_message_id=user_message_id)

            assistant_message = self._store.append_message(
                session_id=session_id,
                role="assistant",
                content=answer,
            )
            assistant_message_id = assistant_message.id

            self._store.add_message_sources(
                assistant_message.id,
                [
                    MessageSourceRecord(
                        message_id=assistant_message.id,
                        title=source.get("title") or "Untitled source",
                        url=source["url"],
                        source_type=source.get("source_type") or "paper",
                    )
                    for source in sources
                    if source.get("url")
                ],
            )

            self._update_session_summary(session_id, assistant_message.id)
            self._write_long_term_memory(
                memory_write,
                memory_key,
                session_id,
                user_id,
                user_message.id,
            )

            return PersistTurnResult(
                persisted=True,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
            )
        except Exception as exc:
            logger.warning("Failed to persist chat transcript", exc_info=True)
            return PersistTurnResult(
                persisted=False,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                error=f"{type(exc).__name__}: {exc}",
            )

    def _update_session_summary(self, session_id: str, source_message_id: str) -> None:
        if not self._config.session_summary_enabled:
            return
        previous = self._store.get_session_summary(session_id)
        messages = self._store.get_recent_messages(
            session_id,
            limit=self._config.recent_message_limit,
        )
        summary = build_deterministic_summary(
            previous.summary if previous else "",
            messages,
            max_chars=min(self._config.max_context_chars, 2000),
        )
        if not summary:
            return
        self._store.upsert_session_summary(
            SessionSummaryRecord(
                session_id=session_id,
                summary=summary,
                source_message_id=source_message_id,
            )
        )

    def _write_long_term_memory(
        self,
        memory_write: str | None,
        memory_key: str | None,
        session_id: str,
        user_id: str | None,
        source_message_id: str,
    ) -> None:
        if not self._config.long_term_memory_enabled or not memory_write:
            return
        MemoryWriter(self._store).write_candidate(
            text=memory_write,
            session_id=session_id,
            user_id=user_id,
            source_message_id=source_message_id,
            scope="user" if user_id else "session",
            memory_key=memory_key,
        )


def _raise_if_session_owner_mismatch(
    session: ChatSessionRecord,
    user_id: str | None,
) -> None:
    if session.user_id == user_id:
        return
    if session.user_id is None and user_id is None:
        return
    raise ValueError("active session belongs to a different user")
