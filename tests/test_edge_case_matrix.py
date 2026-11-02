import pytest

from agent.answerability import AnswerabilityReason, evaluate_answerability
from agent.query_policy import AnswerPolicy, QueryDecision, decide_query_policy
from agent.query_router import RouteResult, RouteType


@pytest.mark.parametrize(
    ("query", "route_result", "mode", "expected_decision", "expected_answer_policy"),
    [
        (
            "hello",
            RouteResult(route_type=RouteType.STATIC, response="Hello", intent="greeting"),
            "auto",
            QueryDecision.STATIC,
            AnswerPolicy.STATIC,
        ),
        (
            "ok",
            RouteResult(route_type=RouteType.LLM_ONLY, intent="conversation"),
            "auto",
            QueryDecision.CHAT,
            AnswerPolicy.LLM,
        ),
        (
            "unrelated request",
            RouteResult(route_type=RouteType.OUT_OF_SCOPE, intent="outside_research_scope"),
            "auto",
            QueryDecision.OUT_OF_SCOPE,
            AnswerPolicy.NO_ANSWER,
        ),
        (
            "manual retrieval request",
            RouteResult(route_type=RouteType.OUT_OF_SCOPE, intent="outside_research_scope"),
            "search",
            QueryDecision.HYBRID,
            AnswerPolicy.RAG,
        ),
        (
            "Explain RAG",
            RouteResult(route_type=RouteType.RAG, intent="research"),
            "chat",
            QueryDecision.CHAT,
            AnswerPolicy.LLM,
        ),
    ],
)
def test_query_policy_edge_case_matrix(query, route_result, mode, expected_decision, expected_answer_policy):
    policy = decide_query_policy(query, mode=mode, route_result=route_result)

    assert policy.decision == expected_decision
    assert policy.answer_policy == expected_answer_policy


@pytest.mark.parametrize(
    ("state", "can_answer", "reason"),
    [
        (
            {"route_type": "kb_only", "merged_snippets": []},
            False,
            AnswerabilityReason.NO_KB_MATCH.value,
        ),
        (
            {"route_type": "search_only", "merged_snippets": [], "search_results": []},
            False,
            AnswerabilityReason.NO_SEARCH_RESULTS.value,
        ),
        (
            {
                "route_type": "both",
                "merged_snippets": [
                    {"text": "bad", "metadata": {"source_url": "https://example.com"}, "rerank_score": -11.0}
                ],
            },
            False,
            AnswerabilityReason.WEAK_EVIDENCE.value,
        ),
        (
            {
                "route_type": "kb_only",
                "merged_snippets": [
                    {"text": "RAG combines retrieval and generation.", "metadata": {"source_url": "https://example.com"}}
                ],
            },
            True,
            AnswerabilityReason.ANSWERABLE.value,
        ),
    ],
)
def test_answerability_edge_case_matrix(state, can_answer, reason):
    result = evaluate_answerability(state)

    assert result["can_answer"] is can_answer
    assert result["reason"] == reason
