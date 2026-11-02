from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval.reporting import load_report


def gate_router_report(
    report: dict[str, Any],
    *,
    min_route_accuracy: float = 0.90,
    min_freshness_accuracy: float = 0.90,
    min_rewrite_rate: float = 0.90,
    min_memory_write_precision: float = 0.95,
    min_memory_key_accuracy: float = 0.90,
    min_memory_key_consistency: float = 0.90,
    max_fallback_rate: float = 0.10,
) -> dict[str, Any]:
    if report.get("evaluation") != "router":
        raise ValueError("router gate requires a router evaluation report")

    metrics = report.get("metrics") or {}
    checks = {
        "hard_gates": int(metrics.get("hard_gate_failures", 0)) == 0,
        "route_accuracy": float(metrics.get("route_accuracy", 0.0)) >= min_route_accuracy,
        "freshness_accuracy": float(metrics.get("freshness_accuracy", 0.0)) >= min_freshness_accuracy,
        "standalone_rewrite_pass_rate": float(metrics.get("standalone_rewrite_pass_rate", 0.0)) >= min_rewrite_rate,
        "memory_write_precision": float(metrics.get("memory_write_precision", 0.0)) >= min_memory_write_precision,
        "memory_key_accuracy": float(metrics.get("memory_key_accuracy", 0.0)) >= min_memory_key_accuracy,
        "memory_key_consistency_rate": float(metrics.get("memory_key_consistency_rate", 0.0)) >= min_memory_key_consistency,
        "fallback_rate": float(metrics.get("fallback_rate", 1.0)) <= max_fallback_rate,
    }
    return {
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "strategy": report.get("strategy"),
        "backend": report.get("backend"),
        "model": report.get("model"),
        "query_count": report.get("query_count", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Router v2 quality thresholds.")
    parser.add_argument("report")
    parser.add_argument("--min-route-accuracy", type=float, default=0.90)
    parser.add_argument("--min-freshness-accuracy", type=float, default=0.90)
    parser.add_argument("--min-rewrite-rate", type=float, default=0.90)
    parser.add_argument("--min-memory-write-precision", type=float, default=0.95)
    parser.add_argument("--min-memory-key-accuracy", type=float, default=0.90)
    parser.add_argument("--min-memory-key-consistency", type=float, default=0.90)
    parser.add_argument("--max-fallback-rate", type=float, default=0.10)
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit non-zero on FAIL. Without this flag the command is report-only.",
    )
    args = parser.parse_args()

    report = load_report(Path(args.report))
    result = gate_router_report(
        report,
        min_route_accuracy=args.min_route_accuracy,
        min_freshness_accuracy=args.min_freshness_accuracy,
        min_rewrite_rate=args.min_rewrite_rate,
        min_memory_write_precision=args.min_memory_write_precision,
        min_memory_key_accuracy=args.min_memory_key_accuracy,
        min_memory_key_consistency=args.min_memory_key_consistency,
        max_fallback_rate=args.max_fallback_rate,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"ROUTER GATE: {result['verdict']}")
    if args.enforce and result["verdict"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
