from agent.answerability import (
    AnswerabilityReason,
    answerability_node,
    build_no_answer_message,
    evaluate_answerability,
)


def test_answerability_blocks_empty_evidence_for_kb_route():
    result = evaluate_answerability({
        "query": "What is RAG?",
        "route_type": "kb_only",
        "merged_snippets": [],
        "search_results": [],
    })

    assert result["can_answer"] is False
    assert result["reason"] == AnswerabilityReason.NO_KB_MATCH.value


def test_answerability_blocks_all_very_negative_rerank_scores():
    result = evaluate_answerability({
        "query": "What is RAG?",
        "route_type": "both",
        "merged_snippets": [
            {"text": "irrelevant", "metadata": {"source_url": "https://example.com"}, "rerank_score": -10.5}
        ],
    })

    assert result["can_answer"] is False
    assert result["reason"] == AnswerabilityReason.WEAK_EVIDENCE.value


def test_answerability_allows_snippets_without_rerank_scores():
    result = evaluate_answerability({
        "query": "What is RAG?",
        "route_type": "kb_only",
        "merged_snippets": [
            {"text": "RAG combines retrieval and generation.", "metadata": {"source_url": "https://example.com"}}
        ],
    })

    assert result["can_answer"] is True
    assert result["evidence_count"] == 1


def test_answerability_node_adds_no_answer_message_when_blocked():
    state = answerability_node({
        "query": "What is RAG?",
        "route_type": "kb_only",
        "merged_snippets": [],
    })

    assert state["answerability"]["can_answer"] is False
    assert state["no_answer_message"] == build_no_answer_message(AnswerabilityReason.NO_KB_MATCH.value)
