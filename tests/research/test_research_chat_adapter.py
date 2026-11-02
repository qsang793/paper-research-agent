import json

from agent.research.chat_adapter import (
    research_preview_to_chat_response,
    research_preview_to_source_events,
    stream_research_text_events,
)


def test_research_preview_to_chat_response_matches_chat_shape():
    preview = {
        "answer": "ROS 2 is middleware.",
        "citations": [
            {
                "title": "ROS 2 paper",
                "authors": ["Ada"],
                "url": "https://example.test/ros2",
                "arxiv_id": "2306.17157",
                "relevance_score": 0.91,
                "snippet": "ROS 2 middleware.",
            }
        ],
        "answerability": {"can_answer": True, "reason": "ANSWERABLE"},
        "evidence": [{"paper_id": "p1", "quote": "ROS 2 middleware."}],
        "metrics": {"paper_count": 1, "evidence_count": 1},
    }

    response = research_preview_to_chat_response(preview, session_id="s1", response_time_ms=12.5)

    assert response.answer == "ROS 2 is middleware."
    assert response.session_id == "s1"
    assert response.citations[0].arxiv_id == "2306.17157"


def test_research_preview_to_chat_response_clamps_relevance_scores():
    preview = {
        "citations": [
            {"title": "High score", "url": "https://example.test/high", "relevance_score": 1.7},
            {"title": "Low score", "url": "https://example.test/low", "relevance_score": -0.2},
        ]
    }

    response = research_preview_to_chat_response(preview, session_id="s1", response_time_ms=12.5)

    assert response.citations[0].relevance_score == 1.0
    assert response.citations[1].relevance_score == 0.0


def test_research_preview_to_source_events_keeps_ui_stream_contract():
    preview = {
        "citations": [
            {"title": "ROS 2 paper", "url": "https://example.test/ros2"},
            {"url": "https://example.test/unknown"},
            {"title": "No URL", "url": ""},
        ]
    }

    events = research_preview_to_source_events(preview)

    assert events == [
        {
            "type": "source-url",
            "sourceId": "research_source_0",
            "url": "https://example.test/ros2",
            "title": "ROS 2 paper",
        },
        {
            "type": "source-url",
            "sourceId": "research_source_1",
            "url": "https://example.test/unknown",
            "title": "Unknown",
        },
    ]


def test_stream_research_text_events_emits_vercel_ui_message_protocol():
    events = list(stream_research_text_events("msg1", "text1", "hello"))
    payloads = [json.loads(item.removeprefix("data: ").strip()) for item in events]

    assert payloads[0]["type"] == "start"
    assert payloads[1]["type"] == "text-start"
    assert payloads[2] == {"type": "text-delta", "id": "text1", "delta": "hello"}
    assert payloads[3]["type"] == "text-end"
    assert payloads[4] == {"type": "finish", "finishReason": "stop"}
