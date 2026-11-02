from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.reporting import load_report, metric_value


def compare_reports(
    baseline: dict,
    candidate: dict,
    *,
    higher_is_better: list[str] | None = None,
    lower_is_better: list[str] | None = None,
    tolerance: float = 0.0,
) -> dict:
    if baseline["evaluation"] != candidate["evaluation"]:
        raise ValueError("baseline and candidate evaluation types differ")
    if baseline["dataset_hash"] != candidate["dataset_hash"]:
        raise ValueError("baseline and candidate datasets differ")

    higher = higher_is_better or []
    lower = lower_is_better or []
    comparisons = []
    failed = False

    baseline_hard = float(baseline.get("metrics", {}).get("hard_gate_failures", 0))
    candidate_hard = float(candidate.get("metrics", {}).get("hard_gate_failures", 0))
    hard_gate_ok = candidate_hard == 0
    failed = failed or not hard_gate_ok

    for path in higher:
        base_value = metric_value(baseline, path)
        candidate_value = metric_value(candidate, path)
        delta = candidate_value - base_value
        ok = delta >= -tolerance
        failed = failed or not ok
        comparisons.append(
            {
                "metric": path,
                "direction": "higher_is_better",
                "baseline": base_value,
                "candidate": candidate_value,
                "delta": delta,
                "ok": ok,
            }
        )

    for path in lower:
        base_value = metric_value(baseline, path)
        candidate_value = metric_value(candidate, path)
        delta = candidate_value - base_value
        ok = delta <= tolerance
        failed = failed or not ok
        comparisons.append(
            {
                "metric": path,
                "direction": "lower_is_better",
                "baseline": base_value,
                "candidate": candidate_value,
                "delta": delta,
                "ok": ok,
            }
        )

    return {
        "comparison_schema_version": 1,
        "evaluation": baseline["evaluation"],
        "dataset_hash": baseline["dataset_hash"],
        "baseline_strategy": baseline["strategy"],
        "candidate_strategy": candidate["strategy"],
        "hard_gate": {
            "baseline_failures": baseline_hard,
            "candidate_failures": candidate_hard,
            "ok": hard_gate_ok,
        },
        "comparisons": comparisons,
        "verdict": "FAIL" if failed else "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare baseline and candidate evaluation reports.")
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--higher-is-better", action="append", default=[])
    parser.add_argument("--lower-is-better", action="append", default=[])
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    report = compare_reports(
        load_report(Path(args.baseline)),
        load_report(Path(args.candidate)),
        higher_is_better=args.higher_is_better,
        lower_is_better=args.lower_is_better,
        tolerance=args.tolerance,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
