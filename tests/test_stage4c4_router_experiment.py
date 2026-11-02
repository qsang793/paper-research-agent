from __future__ import annotations

from copy import deepcopy

import pytest

from eval.router_experiment import evaluate_router_experiment


def _report(*, strategy: str, model: str = "model-a") -> dict:
    return {
        "report_schema_version": 1,
        "evaluation": "router",
        "dataset": "eval/router_golden_set.jsonl",
        "dataset_hash": "same-dataset-hash",
        "git_sha": "abc123",
        "strategy": strategy,
        "backend": "openrouter",
        "model": model,
        "query_count": 28,
        "metrics": {
            "route_accuracy": 0.92,
            "freshness_accuracy": 0.93,
            "standalone_rewrite_pass_rate": 0.94,
            "memory_write_precision": 1.0,
            "memory_write_recall": 0.95,
            "memory_key_accuracy": 0.92,
            "memory_key_consistency_rate": 0.95,
            "memory_key_group_accuracy": 0.92,
            "structured_success_rate": 0.98,
            "fallback_rate": 0.02,
            "p95_latency_ms": 100.0,
            "hard_gate_failures": 0,
        },
        "failure_stage_counts": {"passed": 26, "route_miss": 2},
        "results": [],
        "metadata": {},
    }


def test_promotes_candidate_when_quality_is_safe_and_latency_improves():
    baseline = _report(strategy="baseline", model="baseline-model")
    candidate = _report(strategy="candidate", model="candidate-model")
    candidate["metrics"]["p95_latency_ms"] = 80.0

    result = evaluate_router_experiment(baseline, candidate)

    assert result["verdict"] == "PROMOTE_CANDIDATE"
    assert result["constraints"]["absolute_gate_ok"] is True
    assert result["constraints"]["non_regression_ok"] is True
    assert result["constraints"]["latency_envelope_ok"] is True
    assert result["improvements"]["latency"] is True
    assert result["cost"]["available"] is False


def test_keeps_baseline_when_candidate_is_equivalent_without_measured_gain():
    baseline = _report(strategy="baseline")
    candidate = _report(strategy="candidate", model="same-quality-model")

    result = evaluate_router_experiment(baseline, candidate)

    assert result["verdict"] == "KEEP_BASELINE"
    assert result["improvements"]["any_measured_improvement"] is False


def test_rejects_candidate_that_fails_absolute_quality_gate():
    baseline = _report(strategy="baseline")
    candidate = _report(strategy="candidate")
    candidate["metrics"]["route_accuracy"] = 0.85

    result = evaluate_router_experiment(baseline, candidate)

    assert result["verdict"] == "REJECT_CANDIDATE"
    assert result["constraints"]["absolute_gate_ok"] is False


def test_rejects_candidate_outside_latency_envelope_even_with_quality_gain():
    baseline = _report(strategy="baseline")
    candidate = _report(strategy="candidate")
    candidate["metrics"]["route_accuracy"] = 0.96
    candidate["metrics"]["p95_latency_ms"] = 140.0

    result = evaluate_router_experiment(baseline, candidate)

    assert result["verdict"] == "REJECT_CANDIDATE"
    assert result["constraints"]["latency_envelope_ok"] is False


def test_rejects_candidate_with_hard_gate_failure():
    baseline = _report(strategy="baseline")
    candidate = _report(strategy="candidate")
    candidate["metrics"]["hard_gate_failures"] = 1

    result = evaluate_router_experiment(baseline, candidate)

    assert result["verdict"] == "REJECT_CANDIDATE"
    assert result["candidate"]["gate"]["checks"]["hard_gates"] is False


def test_reports_must_use_same_dataset_hash():
    baseline = _report(strategy="baseline")
    candidate = _report(strategy="candidate")
    candidate["dataset_hash"] = "different"

    with pytest.raises(ValueError, match="same dataset hash"):
        evaluate_router_experiment(baseline, candidate)
