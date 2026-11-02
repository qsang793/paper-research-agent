from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from eval.reporting import write_report
from eval.router_report import build_router_report, score_rows as _score_rows

ALLOWED_ROUTES = {"static", "llm_only", "rag", "out_of_scope"}
ALLOWED_FRESHNESS = {"none", "current", "mixed"}
MEMORY_SAFETY_CLASSES = {"none", "incidental", "sensitive"}


def validate_row(row: dict, *, line_no: int, path: Path) -> dict:
    if not isinstance(row, dict):
        raise ValueError(f"{path}:{line_no} invalid row, expected object")
    for key in ["id", "query", "expected_route_type", "expected_freshness"]:
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path}:{line_no} missing/empty {key}")
    if row["expected_route_type"] not in ALLOWED_ROUTES:
        raise ValueError(f"{path}:{line_no} invalid expected_route_type")
    if row["expected_freshness"] not in ALLOWED_FRESHNESS:
        raise ValueError(f"{path}:{line_no} invalid expected_freshness")
    if not isinstance(row.get("conversation_context", ""), str):
        raise ValueError(f"{path}:{line_no} conversation_context must be a string")
    if not isinstance(row.get("expect_memory_write", False), bool):
        raise ValueError(f"{path}:{line_no} expect_memory_write must be boolean")
    if row.get("memory_safety", "none") not in MEMORY_SAFETY_CLASSES:
        raise ValueError(f"{path}:{line_no} invalid memory_safety")
    if row.get("language") not in {"vi", "en"}:
        raise ValueError(f"{path}:{line_no} language must be vi or en")

    expected_memory_key = row.get("expected_memory_key")
    if expected_memory_key is not None:
        if not isinstance(expected_memory_key, str) or not expected_memory_key.strip():
            raise ValueError(f"{path}:{line_no} expected_memory_key must be a non-empty string")
        if not row.get("expect_memory_write"):
            raise ValueError(f"{path}:{line_no} expected_memory_key requires expect_memory_write=true")

    consistency_group = row.get("consistency_group")
    if consistency_group is not None:
        if not isinstance(consistency_group, str) or not consistency_group.strip():
            raise ValueError(f"{path}:{line_no} consistency_group must be a non-empty string")
        if not expected_memory_key:
            raise ValueError(f"{path}:{line_no} consistency_group requires expected_memory_key")
    return row


def load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    seen_ids: set[str] = set()
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = validate_row(json.loads(line), line_no=idx, path=path)
        if row["id"] in seen_ids:
            raise ValueError(f"{path}:{idx} duplicate id {row['id']!r}")
        seen_ids.add(row["id"])
        rows.append(row)
    return rows


def validate_coverage(rows: list[dict]) -> None:
    route_counts = Counter(row["expected_route_type"] for row in rows)
    freshness_counts = Counter(row["expected_freshness"] for row in rows)
    missing_routes = ALLOWED_ROUTES - set(route_counts)
    missing_freshness = ALLOWED_FRESHNESS - set(freshness_counts)
    if missing_routes:
        raise ValueError(f"router golden set missing route coverage: {sorted(missing_routes)}")
    if missing_freshness:
        raise ValueError(f"router golden set missing freshness coverage: {sorted(missing_freshness)}")
    if not any(row.get("conversation_context") for row in rows):
        raise ValueError("router golden set must include a multi-turn rewrite case")
    if not any(row.get("expect_memory_write") for row in rows):
        raise ValueError("router golden set must include an explicit durable-memory case")
    if not any(row.get("memory_safety") == "incidental" for row in rows):
        raise ValueError("router golden set must include an incidental-memory safety case")
    if not any(row.get("memory_safety") == "sensitive" for row in rows):
        raise ValueError("router golden set must include a sensitive-memory safety case")
    languages = {row.get("language") for row in rows}
    if not {"vi", "en"}.issubset(languages):
        raise ValueError("router golden set must cover Vietnamese and English")

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        group = row.get("consistency_group")
        if group:
            groups[group].append(row)
    if not groups:
        raise ValueError("router golden set must include memory-key consistency groups")
    for group, grouped_rows in groups.items():
        if len(grouped_rows) < 2:
            raise ValueError(f"router consistency group {group!r} must contain at least two rows")
        expected_keys = {row["expected_memory_key"] for row in grouped_rows}
        if len(expected_keys) != 1:
            raise ValueError(f"router consistency group {group!r} must share one expected_memory_key")
        group_languages = {row["language"] for row in grouped_rows}
        if not {"vi", "en"}.issubset(group_languages):
            raise ValueError(f"router consistency group {group!r} must cover Vietnamese and English")


def score_rows(rows: list[dict], router=None) -> dict:
    if router is None:
        from agent.query_router import StructuredQueryRouter

        router = StructuredQueryRouter()
    return _score_rows(rows, router)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or score the router golden set.")
    parser.add_argument("--dataset", default="eval/router_golden_set.jsonl")
    parser.add_argument("--run-router", action="store_true")
    parser.add_argument("--strategy", default="baseline")
    parser.add_argument("--out", default="")
    parser.add_argument("--min-accuracy", type=float, default=0.75)
    parser.add_argument("--hard-gates", action="store_true")
    args = parser.parse_args()

    path = Path(args.dataset)
    rows = load_rows(path)
    validate_coverage(rows)
    if not args.run_router:
        print(f"validated {len(rows)} router golden rows with complete coverage")
        return 0

    from agent.query_router import StructuredQueryRouter

    report = build_router_report(rows, path, strategy=args.strategy, router=StructuredQueryRouter())
    if args.out:
        write_report(Path(args.out), report)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.hard_gates and report["metrics"]["hard_gate_failures"]:
        return 1
    return 0 if report["metrics"]["pass_rate"] >= args.min_accuracy else 1


if __name__ == "__main__":
    raise SystemExit(main())
