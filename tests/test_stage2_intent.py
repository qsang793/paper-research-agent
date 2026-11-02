from agent.nodes import intent as intent_module
from agent.nodes.intent import intent_node
from agent.query_router import RouteResult, RouteType
from agent.state import AgentState


class _FakeRouter:
    def __init__(self, result: RouteResult):
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def route(self, query: str, *, conversation_context: str = ""):
        self.calls.append((query, conversation_context))
        return self.result


def _state(query: str, *, memory_context: str = "") -> AgentState:
    return {
        "query": query,
        "chroma_path": "./chroma",
        "embed_model": "intfloat/e5-base-v2",
        "memory_context": memory_context,
    }


def test_intent_node_maps_current_freshness(monkeypatch):
    router = _FakeRouter(
        RouteResult(
            route_type=RouteType.RAG,
            intent="latest_research",
            confidence=0.91,
            standalone_query="latest RAG research",
            freshness="current",
        )
    )
    monkeypatch.setattr(intent_module, "get_router", lambda: router)

    result = intent_node(_state("What is new in RAG?"))

    assert result["intent"] == "fresh"
    assert result["intent_confidence"] == 0.91
    assert result["query"] == "latest RAG research"


def test_intent_node_maps_mixed_freshness(monkeypatch):
    router = _FakeRouter(
        RouteResult(
            route_type=RouteType.RAG,
            confidence=0.88,
            standalone_query="RAG background and current research",
            freshness="mixed",
        )
    )
    monkeypatch.setattr(intent_module, "get_router", lambda: router)

    result = intent_node(_state("Compare classic RAG with current work"))

    assert result["intent"] == "mixed"
    assert result["intent_confidence"] == 0.88


def test_intent_node_maps_none_to_known(monkeypatch):
    router = _FakeRouter(
        RouteResult(
            route_type=RouteType.RAG,
            confidence=0.95,
            standalone_query="retrieval augmented generation definition",
            freshness="none",
        )
    )
    monkeypatch.setattr(intent_module, "get_router", lambda: router)

    result = intent_node(_state("What is RAG?"))

    assert result["intent"] == "known"
    assert result["intent_confidence"] == 0.95


def test_intent_node_passes_memory_context_to_canonical_router(monkeypatch):
    router = _FakeRouter(
        RouteResult(
            route_type=RouteType.RAG,
            confidence=0.96,
            standalone_query="GraphRAG disadvantages compared with RAG",
            freshness="none",
        )
    )
    monkeypatch.setattr(intent_module, "get_router", lambda: router)

    result = intent_node(
        _state(
            "What about GraphRAG?",
            memory_context="Previous discussion: disadvantages of RAG",
        )
    )

    assert result["query"] == "GraphRAG disadvantages compared with RAG"
    assert router.calls == [
        ("What about GraphRAG?", "Previous discussion: disadvantages of RAG")
    ]
