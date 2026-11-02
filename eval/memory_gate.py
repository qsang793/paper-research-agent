from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate_gate(report: dict, *, min_contradiction_accuracy: float) -> tuple[bool, list[str]]:
    metrics = report.get("metrics") or {}
    failures: list[str] = []
    hard_gate_failures = int(metrics.get("hard_gate_failures", 0) or 0)
    contradiction_accuracy = float(metrics.get("contradiction_resolution_accuracy", 0.0) or 0.0)

    if hard_gate_failures:
        failures.append(f"hard_gate_failures={hard_gate_failures}")
    if contradiction_accuracy < min_contradiction_accuracy:
        failures.append(
            "contradiction_resolution_accuracy="
            f"{contradiction_accuracy:.3f} < {min_contradiction_accuracy:.3f}"
        )
    return not failures, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate a Stage 4C memory evaluation report.")
    parser.add_argument("report")
    parser.add_argument("--min-contradiction-accuracy", type=float, default=1.0)
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    passed, failures = evaluate_gate(
        report,
        min_contradiction_accuracy=args.min_contradiction_accuracy,
    )
    if passed:
        print("MEMORY GATE: PASS")
        return 0
    print("MEMORY GATE: FAIL")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
