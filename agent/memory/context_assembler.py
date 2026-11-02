from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from agent.memory.models import ChatMessageRecord, MemoryItemRecord, SessionSummaryRecord


_TrackedKind = Literal["message", "memory"]


@dataclass(frozen=True)
class AssembledContext:
    text: str
    included_message_ids: list[str]
    included_memory_ids: list[str]
    truncated: bool = False


class ContextAssembler:
    def __init__(self, max_chars: int = 12000) -> None:
        self.max_chars = max_chars

    def assemble(
        self,
        *,
        query: str,
        recent_messages: list[ChatMessageRecord],
        summary: SessionSummaryRecord | None,
        memories: list[MemoryItemRecord],
    ) -> AssembledContext:
        parts: list[str] = []
        section_end_lengths: list[int] = []
        tracked_lines: list[tuple[_TrackedKind, str, int]] = []
        length = 0

        def append(text: str, *, kind: _TrackedKind | None = None, item_id: str | None = None) -> None:
            nonlocal length
            parts.append(text)
            length += len(text)
            if kind and item_id:
                tracked_lines.append((kind, item_id, length))

        append("## SESSION SUMMARY\n")
        append(
            _json_record(
                type="session_summary",
                content=summary.summary.strip() if summary and summary.summary.strip() else "(none)",
            )
        )
        append("\n\n")
        section_end_lengths.append(length)

        append("## LONG-TERM MEMORY\n")
        if memories:
            for index, memory in enumerate(memories):
                memory_text = _json_record(
                    type="memory_item",
                    id=memory.id,
                    scope=memory.scope,
                    content=memory.text,
                )
                append(
                    memory_text,
                    kind="memory",
                    item_id=memory.id,
                )
                section_end_lengths.append(length)
                if index < len(memories) - 1:
                    append("\n")
        else:
            append("(none)")
        append("\n\n")
        section_end_lengths.append(length)

        append("## RECENT CONVERSATION\n")
        if recent_messages:
            for index, message in enumerate(recent_messages):
                message_text = _json_record(
                    type="message",
                    id=message.id,
                    role=message.role,
                    content=message.content,
                )
                append(
                    message_text,
                    kind="message",
                    item_id=message.id,
                )
                section_end_lengths.append(length)
                if index < len(recent_messages) - 1:
                    append("\n")
        else:
            append("(none)")
        append("\n\n")
        section_end_lengths.append(length)

        current_question_start = length
        append("## CURRENT QUESTION\n")
        append(_json_record(type="current_question", content=query))

        full_text = "".join(parts)
        max_chars = max(0, self.max_chars)
        truncated = len(full_text) > max_chars
        included_prefix_length = len(full_text)
        if truncated:
            current_question = full_text[current_question_start:]
            if len(current_question) >= max_chars:
                included_prefix_length = 0
                text = current_question
            else:
                separator = "\n\n"
                prefix_budget = max_chars - len(separator) - len(current_question)
                included_prefix_length = max(
                    (section_end for section_end in section_end_lengths if section_end <= prefix_budget),
                    default=0,
                )
                prefix = full_text[:included_prefix_length].rstrip()
                text = f"{prefix}{separator}{current_question}" if prefix else current_question
        else:
            text = full_text

        included_message_ids = [
            item_id for kind, item_id, end in tracked_lines if kind == "message" and end <= included_prefix_length
        ]
        included_memory_ids = [
            item_id for kind, item_id, end in tracked_lines if kind == "memory" and end <= included_prefix_length
        ]

        return AssembledContext(
            text=text,
            included_message_ids=included_message_ids,
            included_memory_ids=included_memory_ids,
            truncated=truncated,
        )


def _json_record(**fields: str) -> str:
    content = fields["content"]
    return json.dumps({**fields, "chars": len(content)}, sort_keys=True)
