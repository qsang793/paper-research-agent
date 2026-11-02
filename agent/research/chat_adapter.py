from __future__ import annotations

import json
from typing import Dict, Iterable, List

from api.models import ChatResponse, Citation


def _clamp_relevance_score(value: object) -> float:
    score = float(value or 0.0)
    return min(max(score, 0.0), 1.0)


def research_preview_to_chat_response(
    preview: Dict,
    *,
    session_id: str,
    response_time_ms: float,
) -> ChatResponse:
    citations = []
    for item in preview.get("citations", []) or []:
        citations.append(
            Citation(
                title=item.get("title") or "Unknown",
                authors=item.get("authors") or [],
                url=item.get("url") or "",
                arxiv_id=item.get("arxiv_id"),
                relevance_score=_clamp_relevance_score(item.get("relevance_score")),
                snippet=item.get("snippet"),
            )
        )
    return ChatResponse(
        answer=preview.get("answer") or "",
        citations=citations,
        session_id=session_id,
        response_time_ms=response_time_ms,
        tokens_used=None,
    )


def research_preview_to_source_events(preview: Dict) -> List[Dict]:
    events = []
    for index, citation in enumerate(preview.get("citations", []) or []):
        url = citation.get("url")
        if not url:
            continue
        events.append(
            {
                "type": "source-url",
                "sourceId": f"research_source_{index}",
                "url": url,
                "title": citation.get("title") or "Unknown",
            }
        )
    return events


def stream_research_text_events(message_id: str, text_id: str, answer: str) -> Iterable[str]:
    yield f'data: {json.dumps({"type": "start", "messageId": message_id})}\n\n'
    yield f'data: {json.dumps({"type": "text-start", "id": text_id})}\n\n'
    yield f'data: {json.dumps({"type": "text-delta", "id": text_id, "delta": answer})}\n\n'
    yield f'data: {json.dumps({"type": "text-end", "id": text_id})}\n\n'
    yield f'data: {json.dumps({"type": "finish", "finishReason": "stop"})}\n\n'
