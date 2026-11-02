from __future__ import annotations

from pathlib import Path

from agent.query_router import RouteResult, RouteType
from eval.reporting import build_report
from eval.router_eval import load_rows, validate_coverage
from eval.router_gate import gate_router_report
from eval.router_report import score_rows


class FakeRouter:
    def __init__(self, keys: dict[str, str | None]):
        self._keys = keys

    def route(self, query: str, *, conversation_context: str = "") -> RouteResult:
        del conversation_context
        key = self._keys.get(query)
        return RouteResult(
            route_type=RouteType.LLM_ONLY,
            intent="remember_preference",
            confidence=0.99,
            standalone_query=query,
            freshness="none",
            memory_write=f"Memory for {query}",
            memory_key=key,
        )


def _memory_rows() -> list[dict]:
    return [
        {
            "id": "style_vi",
            "language": "vi",
            "query": "style-vi",
            "expected_route_type": "llm_only",
            "expected_freshness": "none",
            "expected_standalone_contains": "style-vi",
            "expect_memory_write": True,
            "expected_memory_key": "answer_style",
            "consistency_group": "answer_style",
        },
        {
            "id": "style_en",
            "language": "en",
            "query": "style-en",
            "expected_route_type": "llm_only",
            "expected_freshness": "none",
            "expected_standalone_contains": "style-en",
            "expect_memory_write": True,
            "expected_memory_key": "answer_style",
            "consistency_group": "answer_style",
        },
    ]


def test_router_v2_dataset_has_cross_language_consistency_groups():
    rows = load_rows(Path("eval/router_golden_set.jsonl"))
    validate_coverage(rows)
    assert len(rows) >= 28
    groups = {row["consistency_group"] for row in rows if row.get("consistency_group")}
    assert {"answer_style", "current_research_project", "citation_preference", "answer_format"}.issubset(groups)


def test_memory_key_accuracy_and_consistency_are_separate_metrics():
    rows = _memory_rows()
    correct = score_rows(rows, FakeRouter({"style-vi": "answer_style", "style-en": "answer_style"}))
    assert correct["memory_key_accuracy"] == 1.0
    assert correct["memory_key_consistency_rate"] == 1.0
    assert correct["memory_key_group_accuracy"] == 1.0

    consistently_wrong = score_rows(rows, FakeRouter({"style-vi": "response_style", "style-en": "response_style"}))
    assert consistently_wrong["memory_key_accuracy"] == 0.0
    assert consistently_wrong["memory_key_consistency_rate"] == 1.0
    assert consistently_wrong["memory_key_group_accuracy"] == 0.0


def test_router_report_includes_per_route_precision_and_recall():
    rows = _memory_rows()
    scored = score_rows(rows, FakeRouter({"style-vi": "answer_style", "style-en": "answer_style"}))
    assert scored["per_route"]["llm_only"]["precision"] == 1.0
    assert scored["per_route"]["llm_only"]["recall"] == 1.0
    assert scored["route_accuracy_by_language"] == {"en": 1.0, "vi": 1.0}


def test_router_gate_is_report_only_until_explicitly_enforced(tmp_path):
    dataset = tmp_path / "router.jsonl"
    dataset.write_text('{"id":"row"}\n', encoding="utf-8")
    report = build_report(
        evaluation="router",
        dataset_path=dataset,
        strategy="baseline",
        backend="test",
        model="test",
        metrics={
            "route_accuracy": 0.95,
            "freshness_accuracy": 0.95,
            "standalone_rewrite_pass_rate": 0.95,
            "memory_write_precision": 1.0,
            "memory_key_accuracy": 0.80,
            "memory_key_consistency_rate": 1.0,
            "fallback_rate": 0.0,
            "hard_gate_failures": 0,
        },
        failure_stage_counts={"passed": 1},
        results=[{"id": "row", "ok": True}],
    )
    verdict = gate_router_report(report)
    assert verdict["verdict"] == "FAIL"
    assert verdict["checks"]["memory_key_accuracy"] is False
    assert verdict["checks"]["memory_key_consistency_rate"] is True
