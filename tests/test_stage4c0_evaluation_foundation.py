from __future__ import annotations

from pathlib import Path

from eval.compare_reports import compare_reports
from eval.memory_eval import load_memory_eval_rows, run_behavior_eval
from eval.reporting import build_report, load_report, write_report
from eval.router_eval import load_rows as load_router_rows, validate_coverage as validate_router_coverage


def _report(dataset: Path, *, strategy: str, score: float, hard_gate_failures: int = 0):
    return build_report(
        evaluation="router",
        dataset_path=dataset,
        strategy=strategy,
        backend="test",
        model="test",
        metrics={"route_accuracy": score, "hard_gate_failures": hard_gate_failures},
        failure_stage_counts={"passed": 1},
        results=[{"id": "row", "ok": True}],
    )


def test_unified_report_round_trip(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"id":"row"}\n', encoding="utf-8")
    report = _report(dataset, strategy="baseline", score=0.8)
    output = tmp_path / "report.json"
    write_report(output, report)
    loaded = load_report(output)
    assert loaded["report_schema_version"] == 1
    assert loaded["dataset_hash"] == report["dataset_hash"]
    assert loaded["metrics"]["route_accuracy"] == 0.8


def test_router_dataset_has_stage4c_required_coverage():
    path = Path("eval/router_golden_set.jsonl")
    rows = load_router_rows(path)
    validate_router_coverage(rows)
    assert len(rows) >= 16
    assert {row["language"] for row in rows} == {"vi", "en"}


def test_memory_behavior_eval_enforces_hard_safety_without_requiring_perfect_quality():
    path = Path("eval/memory_behavior_golden_set.jsonl")
    rows = load_memory_eval_rows(path)
    report = run_behavior_eval(rows, path)
    assert report["evaluation"] == "memory"
    assert report["metrics"]["hard_gate_failures"] == 0
    assert "contradiction_resolution_accuracy" in report["metrics"]
    assert report["query_count"] == len(rows)


def test_report_comparator_checks_quality_and_hard_gates(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"id":"row"}\n', encoding="utf-8")
    baseline = _report(dataset, strategy="baseline", score=0.80)
    better = _report(dataset, strategy="candidate", score=0.82)
    result = compare_reports(
        baseline,
        better,
        higher_is_better=["metrics.route_accuracy"],
    )
    assert result["verdict"] == "PASS"

    unsafe = _report(dataset, strategy="candidate-unsafe", score=0.90, hard_gate_failures=1)
    unsafe_result = compare_reports(
        baseline,
        unsafe,
        higher_is_better=["metrics.route_accuracy"],
    )
    assert unsafe_result["verdict"] == "FAIL"
