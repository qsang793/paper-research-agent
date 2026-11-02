from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.compare_reports import compare_reports
from eval.reporting import load_report, metric_value
from eval.router_gate import gate_router_report

QUALITY_METRICS = [
    "metrics.route_accuracy",
    "metrics.freshness_accuracy",
    "metrics.standalone_rewrite_pass_rate",
    "metrics.memory_write_precision",
    "metrics.memory_write_recall",
    "metrics.memory_key_accuracy",
    "metrics.memory_key_consistency_rate",
    "metrics.memory_key_group_accuracy",
    "metrics.structured_success_rate",
]
LOWER_IS_BETTER = ["metrics.fallback_rate"]


def _ratio(candidate: float, baseline: float) -> float | None:
    if baseline <= 0:
        return None
    return candidate / baseline


def evaluate_router_experiment(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    quality_tolerance: float = 0.02,
    max_p95_latency_ratio: float = 1.25,
    min_quality_gain: float = 0.02,
    min_latency_improvement_ratio: float = 0.10,
) -> dict[str, Any]:
    """Return a promotion verdict for one router candidate.

    Promotion is intentionally stricter than a simple baseline comparison:
    the candidate must pass absolute Router v2 gates, preserve baseline quality
    within tolerance, remain inside the latency envelope, and demonstrate at
    least one measured improvement. Cost is not inferred when provider usage
    metadata is unavailable.
    """
    if baseline.get("evaluation") != "router" or candidate.get("evaluation") != "router":
        raise ValueError("router experiment requires two router evaluation reports")
    if baseline.get("dataset_hash") != candidate.get("dataset_hash"):
        raise ValueError("baseline and candidate must use the same dataset hash")

    baseline_gate = gate_router_report(baseline)
    candidate_gate = gate_router_report(candidate)
    comparison = compare_reports(
        baseline,
        candidate,
        higher_is_better=QUALITY_METRICS,
        lower_is_better=LOWER_IS_BETTER,
        tolerance=quality_tolerance,
    )

    baseline_p95 = metric_value(baseline, "metrics.p95_latency_ms")
    candidate_p95 = metric_value(candidate, "metrics.p95_latency_ms")
    latency_ratio = _ratio(candidate_p95, baseline_p95)
    latency_envelope_ok = latency_ratio is None or latency_ratio <= max_p95_latency_ratio

    quality_improvements = []
    for metric in QUALITY_METRICS:
        base_value = metric_value(baseline, metric)
        candidate_value = metric_value(candidate, metric)
        delta = candidate_value - base_value
        if delta >= min_quality_gain:
            quality_improvements.append(
                {"metric": metric, "baseline": base_value, "candidate": candidate_value, "delta": delta}
            )

    lower_metric_improvements = []
    for metric in LOWER_IS_BETTER:
        base_value = metric_value(baseline, metric)
        candidate_value = metric_value(candidate, metric)
        delta = base_value - candidate_value
        if delta >= min_quality_gain:
            lower_metric_improvements.append(
                {"metric": metric, "baseline": base_value, "candidate": candidate_value, "improvement": delta}
            )

    latency_improved = (
        latency_ratio is not None
        and latency_ratio <= 1.0 - min_latency_improvement_ratio
    )
    measured_improvement = bool(quality_improvements or lower_metric_improvements or latency_improved)

    absolute_gate_ok = candidate_gate["verdict"] == "PASS"
    non_regression_ok = comparison["verdict"] == "PASS"
    promotion_eligible = absolute_gate_ok and non_regression_ok and latency_envelope_ok

    if not promotion_eligible:
        verdict = "REJECT_CANDIDATE"
    elif measured_improvement:
        verdict = "PROMOTE_CANDIDATE"
    else:
        verdict = "KEEP_BASELINE"

    return {
        "experiment_schema_version": 1,
        "evaluation": "router",
        "dataset_hash": baseline["dataset_hash"],
        "baseline": {
            "strategy": baseline.get("strategy"),
            "backend": baseline.get("backend"),
            "model": baseline.get("model"),
            "gate": baseline_gate,
        },
        "candidate": {
            "strategy": candidate.get("strategy"),
            "backend": candidate.get("backend"),
            "model": candidate.get("model"),
            "gate": candidate_gate,
        },
        "constraints": {
            "absolute_gate_ok": absolute_gate_ok,
            "non_regression_ok": non_regression_ok,
            "latency_envelope_ok": latency_envelope_ok,
            "quality_tolerance": quality_tolerance,
            "max_p95_latency_ratio": max_p95_latency_ratio,
        },
        "latency": {
            "baseline_p95_ms": baseline_p95,
            "candidate_p95_ms": candidate_p95,
            "candidate_to_baseline_ratio": latency_ratio,
            "improved": latency_improved,
        },
        "improvements": {
            "quality": quality_improvements,
            "lower_is_better": lower_metric_improvements,
            "latency": latency_improved,
            "any_measured_improvement": measured_improvement,
        },
        "comparison": comparison,
        "cost": {
            "available": False,
            "note": "Provider cost/usage is not currently emitted by the router report; do not infer cost from model name.",
        },
        "verdict": verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare a live router candidate against a baseline report.")
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--quality-tolerance", type=float, default=0.02)
    parser.add_argument("--max-p95-latency-ratio", type=float, default=1.25)
    parser.add_argument("--min-quality-gain", type=float, default=0.02)
    parser.add_argument("--min-latency-improvement-ratio", type=float, default=0.10)
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit non-zero only when the candidate is rejected. KEEP_BASELINE remains a successful experiment outcome.",
    )
    args = parser.parse_args()

    result = evaluate_router_experiment(
        load_report(Path(args.baseline)),
        load_report(Path(args.candidate)),
        quality_tolerance=args.quality_tolerance,
        max_p95_latency_ratio=args.max_p95_latency_ratio,
        min_quality_gain=args.min_quality_gain,
        min_latency_improvement_ratio=args.min_latency_improvement_ratio,
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    print(f"ROUTER EXPERIMENT: {result['verdict']}")
    if args.enforce and result["verdict"] == "REJECT_CANDIDATE":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
