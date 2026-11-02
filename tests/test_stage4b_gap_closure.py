import json

import agent.nodes.intent as intent_module
import agent.query_router as query_router
from agent.nodes.generate import generate_node


def test_legacy_intent_node_keeps_original_and_standalone_query(monkeypatch):
    monkeypatch.setattr(
        query_router,
        "_call_router",
        lambda prompt, backend, model=None: json.dumps(
            {
                "route_type": "rag",
                "intent": "research_follow_up",
                "confidence": 0.95,
                "standalone_query": "GraphRAG disadvantages compared with RAG",
                "freshness": "none",
                "response": None,
                "memory_write": None,
            }
        ),
    )
    query_router._router_instance = None
    state = {
        "query": "Còn GraphRAG thì sao?",
        "memory_context": "Previous turn discussed disadvantages of RAG.",
    }
    result = intent_module.intent_node(state)
    assert result["original_query"] == "Còn GraphRAG thì sao?"
    assert result["standalone_query"] == "GraphRAG disadvantages compared with RAG"
    assert result["query"] == result["standalone_query"]
    query_router._router_instance = None


def test_generate_uses_original_query_not_retrieval_rewrite(monkeypatch):
    captured = {}

    def fake_generate(question, snippets, **kwargs):
        captured["question"] = question
        return "answer"

    monkeypatch.setattr("agent.nodes.generate.generate_answer", fake_generate)
    monkeypatch.setattr(
        "agent.nodes.generate.validate_citation_sources",
        lambda answer, sources: {"sources": sources, "ok": 0, "total": 0, "dead": []},
    )
    state = {
        "original_query": "Còn GraphRAG thì sao?",
        "standalone_query": "GraphRAG disadvantages compared with RAG",
        "query": "GraphRAG disadvantages compared with RAG",
        "merged_snippets": [{"text": "evidence", "metadata": {"title": "Paper"}}],
        "memory_context": "Previous turn discussed disadvantages of RAG.",
        "llm_backend": "openrouter",
        "answerability": {"can_answer": True},
        "sources": [],
    }
    generate_node(state)
    assert captured["question"] == "Còn GraphRAG thì sao?"
    assert state["answer"] == "answer"


def test_no_runtime_phrase_dataset_reintroduced():
    assert not hasattr(query_router, "INTENT_EXAMPLES")
    assert "FRESH_KEYWORDS" not in vars(query_router)
    assert "KNOWN_KEYWORDS" not in vars(query_router)
