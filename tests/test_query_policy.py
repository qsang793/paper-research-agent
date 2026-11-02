from agent.query_policy import (
    AnswerPolicy,
    QueryDecision,
    SourcePolicy,
    decide_query_policy,
)
from agent.query_router import RouteResult, RouteType


def test_static_route_stays_static():
    policy = decide_query_policy(
        "hello",
        mode="auto",
        route_result=RouteResult(
            route_type=RouteType.STATIC,
            response="Hello",
            intent="greeting",
            confidence=0.9,
            standalone_query="hello",
        ),
    )

    assert policy.decision == QueryDecision.STATIC
    assert policy.answer_policy == AnswerPolicy.STATIC
    assert policy.source_policy == SourcePolicy.NONE
    assert policy.response == "Hello"


def test_manual_chat_bypasses_retrieval_but_keeps_memory_write():
    policy = decide_query_policy(
        "Remember my preference",
        mode="chat",
        route_result=RouteResult(
            route_type=RouteType.RAG,
            intent="remember_preference",
            standalone_query="Remember my preference",
            memory_write="User prefers concise answers.",
        ),
    )

    assert policy.decision == QueryDecision.CHAT
    assert policy.answer_policy == AnswerPolicy.LLM
    assert policy.source_policy == SourcePolicy.NONE
    assert policy.memory_write == "User prefers concise answers."


def test_out_of_scope_comes_from_structured_router_not_phrase_lists():
    policy = decide_query_policy(
        "unrelated request",
        mode="auto",
        route_result=RouteResult(
            route_type=RouteType.OUT_OF_SCOPE,
            intent="outside_research_scope",
            confidence=0.95,
            standalone_query="unrelated request",
        ),
    )

    assert policy.decision == QueryDecision.OUT_OF_SCOPE
    assert policy.answer_policy == AnswerPolicy.NO_ANSWER
    assert policy.source_policy == SourcePolicy.NONE


def test_manual_search_forces_research_even_if_router_says_out_of_scope():
    policy = decide_query_policy(
        "manual research request",
        mode="search",
        route_result=RouteResult(
            route_type=RouteType.OUT_OF_SCOPE,
            intent="outside_research_scope",
            standalone_query="manual research request",
        ),
    )

    assert policy.decision == QueryDecision.HYBRID
    assert policy.answer_policy == AnswerPolicy.RAG
    assert policy.source_policy == SourcePolicy.HYBRID


def test_research_policy_preserves_standalone_query_and_freshness():
    policy = decide_query_policy(
        "What about this year's work?",
        mode="auto",
        route_result=RouteResult(
            route_type=RouteType.RAG,
            intent="research_follow_up",
            confidence=0.91,
            standalone_query="2026 GraphRAG research developments",
            freshness="current",
        ),
    )

    assert policy.decision == QueryDecision.HYBRID
    assert policy.answer_policy == AnswerPolicy.RAG
    assert policy.standalone_query == "2026 GraphRAG research developments"
    assert policy.freshness == "current"


def test_llm_only_route_uses_chat_policy():
    policy = decide_query_policy(
        "repeat your previous answer",
        mode="auto",
        route_result=RouteResult(
            route_type=RouteType.LLM_ONLY,
            intent="conversation_follow_up",
            confidence=0.92,
            standalone_query="repeat your previous answer",
        ),
    )

    assert policy.decision == QueryDecision.CHAT
    assert policy.answer_policy == AnswerPolicy.LLM
    assert policy.source_policy == SourcePolicy.NONE
