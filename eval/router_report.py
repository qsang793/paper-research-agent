from __future__ import annotations

import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from eval.reporting import build_report

ROUTES = ("static", "llm_only", "rag", "out_of_scope")


def _terms(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.casefold()]
    return [str(item).casefold() for item in value]


def _ratio(numerator: int, denominator: int, default: float = 1.0) -> float:
    return numerator / denominator if denominator else default


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile / 100)
    return ordered[index]


def _per_route_metrics(confusion: dict[str, Counter]) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for route in ROUTES:
        true_positive = confusion.get(route, Counter()).get(route, 0)
        expected_total = sum(confusion.get(route, Counter()).values())
        predicted_total = sum(counter.get(route, 0) for counter in confusion.values())
        metrics[route] = {
            "precision": _ratio(true_positive, predicted_total, 0.0),
            "recall": _ratio(true_positive, expected_total, 0.0),
        }
    return metrics


def _memory_key_group_metrics(rows: list[dict], results: list[dict[str, Any]]) -> dict[str, Any]:
    row_by_id = {row["id"]: row for row in rows}
    result_by_id = {result["id"]: result for result in results}
    groups: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        group = row.get("consistency_group")
        if group:
            groups[group].append(row["id"])

    group_results: dict[str, dict[str, Any]] = {}
    consistent_groups = 0
    correct_groups = 0
    for group, row_ids in sorted(groups.items()):
        actual_keys = [result_by_id[row_id].get("actual_memory_key") for row_id in row_ids]
        expected_key = row_by_id[row_ids[0]]["expected_memory_key"]
        non_empty = [key for key in actual_keys if key]
        consistent = len(non_empty) == len(actual_keys) and len(set(non_empty)) == 1
        correct = consistent and non_empty[0] == expected_key
        consistent_groups += int(consistent)
        correct_groups += int(correct)
        group_results[group] = {
            "expected_memory_key": expected_key,
            "actual_memory_keys": actual_keys,
            "consistent": consistent,
            "correct": correct,
        }

    total_groups = len(groups)
    return {
        "memory_key_consistency_rate": _ratio(consistent_groups, total_groups, 0.0),
        "memory_key_group_accuracy": _ratio(correct_groups, total_groups, 0.0),
        "memory_key_groups": group_results,
    }


def score_rows(rows: list[dict], router) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    confusion: dict[str, Counter] = defaultdict(Counter)
    memory_tp = memory_fp = memory_fn = 0
    fallback_count = 0
    hard_gate_failures = 0
    latencies_ms: list[float] = []
    language_route_correct: Counter = Counter()
    language_counts: Counter = Counter()
    memory_key_expected = 0
    memory_key_correct = 0
    memory_key_present = 0

    for row in rows:
        started = time.perf_counter()
        routed = router.route(row["query"], conversation_context=row.get("conversation_context", ""))
        latency_ms = (time.perf_counter() - started) * 1000
        latencies_ms.append(latency_ms)

        actual_route = routed.route_type.value
        expected_route = row["expected_route_type"]
        confusion[expected_route][actual_route] += 1
        language = row.get("language", "unknown")
        language_counts[language] += 1
        language_route_correct[language] += int(actual_route == expected_route)

        standalone = routed.standalone_query.casefold()
        standalone_ok = all(term in standalone for term in _terms(row.get("expected_standalone_contains")))
        standalone_ok = standalone_ok and not any(
            term in standalone for term in _terms(row.get("expected_standalone_forbidden"))
        )
        expected_memory = bool(row.get("expect_memory_write", False))
        actual_memory = bool(routed.memory_write)
        memory_tp += int(expected_memory and actual_memory)
        memory_fp += int(not expected_memory and actual_memory)
        memory_fn += int(expected_memory and not actual_memory)

        expected_memory_key = row.get("expected_memory_key")
        actual_memory_key = routed.memory_key
        memory_key_ok = True
        if expected_memory_key is not None:
            memory_key_expected += 1
            memory_key_present += int(bool(actual_memory_key))
            memory_key_ok = actual_memory_key == expected_memory_key
            memory_key_correct += int(memory_key_ok)
        orphan_memory_key = bool(actual_memory_key) and not actual_memory

        fallback = routed.intent in {"router_fallback", "router_disabled"}
        fallback_count += int(fallback)
        safety_violation = actual_memory and row.get("memory_safety", "none") in {"incidental", "sensitive"}
        hard_gate_failures += int(safety_violation)

        checks = {
            "route_type": actual_route == expected_route,
            "freshness": routed.freshness == row["expected_freshness"],
            "memory_write": actual_memory == expected_memory,
            "memory_key": memory_key_ok,
            "memory_key_contract": not orphan_memory_key,
            "standalone": standalone_ok,
            "memory_safety": not safety_violation,
        }
        if not checks["route_type"]:
            failure_stage = "route_miss"
        elif not checks["freshness"]:
            failure_stage = "freshness_miss"
        elif not checks["standalone"]:
            failure_stage = "standalone_rewrite_miss"
        elif expected_memory and not actual_memory:
            failure_stage = "memory_write_false_negative"
        elif not expected_memory and actual_memory:
            failure_stage = "memory_write_false_positive"
        elif not checks["memory_key"]:
            failure_stage = "memory_key_miss"
        elif not checks["memory_key_contract"]:
            failure_stage = "memory_key_contract_failure"
        else:
            failure_stage = "passed"

        results.append(
            {
                "id": row["id"],
                "ok": all(checks.values()),
                "failure_stage": failure_stage,
                "expected_route_type": expected_route,
                "actual_route_type": actual_route,
                "expected_freshness": row["expected_freshness"],
                "actual_freshness": routed.freshness,
                "expected_memory_key": expected_memory_key,
                "actual_memory_key": actual_memory_key,
                "consistency_group": row.get("consistency_group"),
                "confidence": routed.confidence,
                "fallback": fallback,
                "latency_ms": round(latency_ms, 3),
                "checks": checks,
            }
        )

    total = len(results)
    route_correct = sum(result["checks"]["route_type"] for result in results)
    freshness_correct = sum(result["checks"]["freshness"] for result in results)
    rewrite_correct = sum(result["checks"]["standalone"] for result in results)
    passed = sum(result["ok"] for result in results)
    key_group_metrics = _memory_key_group_metrics(rows, results)
    return {
        "total": total,
        "passed": passed,
        "accuracy": _ratio(passed, total, 0.0),
        "route_accuracy": _ratio(route_correct, total, 0.0),
        "freshness_accuracy": _ratio(freshness_correct, total, 0.0),
        "standalone_rewrite_pass_rate": _ratio(rewrite_correct, total, 0.0),
        "memory_write_precision": _ratio(memory_tp, memory_tp + memory_fp),
        "memory_write_recall": _ratio(memory_tp, memory_tp + memory_fn),
        "memory_key_accuracy": _ratio(memory_key_correct, memory_key_expected, 0.0),
        "memory_key_present_rate": _ratio(memory_key_present, memory_key_expected, 0.0),
        "memory_key_consistency_rate": key_group_metrics["memory_key_consistency_rate"],
        "memory_key_group_accuracy": key_group_metrics["memory_key_group_accuracy"],
        "fallback_rate": _ratio(fallback_count, total, 0.0),
        "structured_success_rate": _ratio(total - fallback_count, total, 0.0),
        "p50_latency_ms": round(_percentile(latencies_ms, 50), 3),
        "p95_latency_ms": round(_percentile(latencies_ms, 95), 3),
        "hard_gate_failures": hard_gate_failures,
        "per_route": _per_route_metrics(confusion),
        "route_accuracy_by_language": {
            language: _ratio(language_route_correct[language], count, 0.0)
            for language, count in sorted(language_counts.items())
        },
        "confusion_matrix": {expected: dict(actual) for expected, actual in sorted(confusion.items())},
        "memory_key_groups": key_group_metrics["memory_key_groups"],
        "results": results,
    }


def build_router_report(rows: list[dict], dataset_path: Path, *, strategy: str, router) -> dict[str, Any]:
    scored = score_rows(rows, router)
    failures = Counter(result["failure_stage"] for result in scored["results"])
    metrics = {key: value for key, value in scored.items() if key not in {"total", "passed", "results"}}
    metrics["pass_rate"] = scored["accuracy"]
    backend = os.getenv("ROUTER_BACKEND", os.getenv("LLM_BACKEND", "openrouter"))
    model = os.getenv("ROUTER_MODEL") or os.getenv("OPENROUTER_MODEL") or os.getenv("GENAI_MODEL") or os.getenv("LLM_MODEL")
    return build_report(
        evaluation="router",
        dataset_path=dataset_path,
        strategy=strategy,
        backend=backend,
        model=model,
        metrics=metrics,
        failure_stage_counts=dict(failures),
        results=scored["results"],
        metadata={
            "languages": sorted({row.get("language", "unknown") for row in rows}),
            "consistency_groups": sorted({row["consistency_group"] for row in rows if row.get("consistency_group")}),
        },
    )
