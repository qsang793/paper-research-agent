from fastapi.testclient import TestClient

from api.main import app


def test_research_preview_endpoint_returns_disabled_when_feature_flag_off(monkeypatch):
    monkeypatch.setenv("RESEARCH_WORKFLOW_ENABLED", "false")
    client = TestClient(app)

    response = client.post("/api/research/preview", json={"query": "ROS2 trong robotics là gì"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Research workflow preview is disabled"
    assert response.headers["x-request-id"]


def test_research_preview_endpoint_returns_evidence_when_enabled(monkeypatch):
    monkeypatch.setenv("RESEARCH_WORKFLOW_ENABLED", "true")
    captured = {}

    def fake_preview(query, top_k=5, providers=None, trace_context=None):
        captured["trace_context"] = trace_context
        return {
            "answer": "Preview answer",
            "citations": [{"title": "ROS 2 paper", "url": "https://example.test"}],
            "evidence": [{"paper_id": "p1", "quote": "ROS 2 is middleware."}],
            "answerability": {"can_answer": True, "reason": "ANSWERABLE"},
            "metrics": {"paper_count": 1},
        }

    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_preview)
    client = TestClient(app)

    response = client.post("/api/research/preview", json={"query": "ROS2 trong robotics là gì", "top_k": 3})

    assert response.status_code == 200
    assert response.json()["evidence"][0]["paper_id"] == "p1"
    assert captured["trace_context"] is not None
    assert response.headers["x-request-id"] == captured["trace_context"]["trace_id"]
