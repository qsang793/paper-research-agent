import json

import agent.query_router as query_router
from agent.query_router import RouteType, StructuredQueryRouter, get_router


def test_structured_router_returns_static_response(monkeypatch):
    monkeypatch.setattr(
        query_router,
        "_call_router",
        lambda prompt, backend, model=None: json.dumps(
            {
                "route_type": "static",
                "intent": "greeting",
                "confidence": 0.98,
                "standalone_query": "hello",
                "freshness": "none",
                "response": "Hello!",
                "memory_write": None,
            }
        ),
    )

    result = StructuredQueryRouter().route("hello")

    assert result.route_type == RouteType.STATIC
    assert result.response == "Hello!"
    assert result.intent == "greeting"
    assert result.confidence == 0.98


def test_router_uses_context_to_return_standalone_query(monkeypatch):
    prompts: list[str] = []

    def fake_call(prompt, backend, model=None):
        prompts.append(prompt)
        return json.dumps(
            {
                "route_type": "rag",
                "intent": "research_follow_up",
                "confidence": 0.94,
                "standalone_query": "GraphRAG disadvantages compared with RAG",
                "freshness": "none",
                "response": None,
                "memory_write": None,
            }
        )

    monkeypatch.setattr(query_router, "_call_router", fake_call)
    result = StructuredQueryRouter().route(
        "What about GraphRAG?",
        conversation_context="Previous discussion: disadvantages of RAG",
    )

    assert result.route_type == RouteType.RAG
    assert result.standalone_query == "GraphRAG disadvantages compared with RAG"
    assert "Previous discussion" in prompts[0]
    assert "What about GraphRAG?" in prompts[0]


def test_router_returns_explicit_memory_candidate(monkeypatch):
    monkeypatch.setattr(
        query_router,
        "_call_router",
        lambda prompt, backend, model=None: json.dumps(
            {
                "route_type": "llm_only",
                "intent": "remember_preference",
                "confidence": 0.97,
                "standalone_query": "Remember my answer preference",
                "freshness": "none",
                "response": None,
                "memory_write": "User prefers concise technical answers.",
            }
        ),
    )

    result = StructuredQueryRouter().route("Please remember that I prefer concise technical answers")

    assert result.memory_write == "User prefers concise technical answers."


def test_router_falls_back_to_research_when_output_is_invalid(monkeypatch):
    monkeypatch.setattr(query_router, "_call_router", lambda prompt, backend, model=None: "not-json")

    result = StructuredQueryRouter().route("Explain retrieval augmented generation")

    assert result.route_type == RouteType.RAG
    assert result.intent == "router_fallback"
    assert result.standalone_query == "Explain retrieval augmented generation"
    assert result.freshness == "mixed"


def test_disabled_router_is_conservative():
    result = StructuredQueryRouter(enabled=False).route("hello")

    assert result.route_type == RouteType.RAG
    assert result.intent == "router_disabled"


def test_static_without_response_is_promoted_to_llm_only(monkeypatch):
    monkeypatch.setattr(
        query_router,
        "_call_router",
        lambda prompt, backend, model=None: json.dumps(
            {
                "route_type": "static",
                "intent": "acknowledgement",
                "confidence": 0.9,
                "standalone_query": "okay",
                "freshness": "none",
                "response": None,
                "memory_write": None,
            }
        ),
    )

    result = StructuredQueryRouter().route("okay")

    assert result.route_type == RouteType.LLM_ONLY
    assert result.response is None


def test_router_module_no_longer_exposes_embedding_intent_dataset():
    assert not hasattr(query_router, "INTENT_EXAMPLES")
    assert not hasattr(query_router, "INTENT_COLLECTION_METADATA")
    assert not hasattr(query_router, "E5EmbeddingFunction")


def test_get_router_returns_singleton(monkeypatch):
    query_router._router_instance = None
    monkeypatch.setenv("QUERY_ROUTER_ENABLED", "false")

    first = get_router()
    second = get_router()

    assert first is second
    assert first.enabled is False
    query_router._router_instance = None
