import json

import agent.query_router as query_router
from agent.query_router import RouteType, StructuredQueryRouter


def test_freshness_is_model_structured_not_year_keyword_based(monkeypatch):
    prompts: list[str] = []

    def fake_call(prompt, backend, model=None):
        prompts.append(prompt)
        return json.dumps(
            {
                "route_type": "rag",
                "intent": "current_research",
                "confidence": 0.93,
                "standalone_query": "current retrieval augmented generation research",
                "freshness": "current",
                "response": None,
                "memory_write": None,
            }
        )

    monkeypatch.setattr(query_router, "_call_router", fake_call)
    result = StructuredQueryRouter().route("What is new in RAG right now?")

    assert result.route_type == RouteType.RAG
    assert result.freshness == "current"
    assert "Current UTC date:" in prompts[0]


def test_router_has_no_fixed_year_keyword_classifier():
    source = query_router.ROUTER_PROMPT
    assert "2024" not in source
    assert "2025" not in source
    assert not hasattr(query_router, "FRESH_KEYWORDS")
    assert not hasattr(query_router, "KNOWN_KEYWORDS")
