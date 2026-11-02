from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from agent.memory.models import MemoryItemRecord
from agent.memory.store import InMemoryMemoryStore
from agent.memory.writer import MemoryWriter
from eval.reporting import build_report, write_report

ALLOWED_OPERATIONS = {"write", "dedup", "retrieval"}
HARD_GATES = {"sensitive_write", "cross_session_leak", "cross_user_leak"}


def load_memory_eval_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no} expected object")
        row_id = row.get("id")
        operation = row.get("operation")
        if not isinstance(row_id, str) or not row_id.strip():
            raise ValueError(f"{path}:{line_no} missing/empty id")
        if row_id in seen_ids:
            raise ValueError(f"{path}:{line_no} duplicate id {row_id!r}")
        if operation not in ALLOWED_OPERATIONS:
            raise ValueError(f"{path}:{line_no} invalid operation {operation!r}")
        if row.get("hard_gate") not in HARD_GATES | {None}:
            raise ValueError(f"{path}:{line_no} invalid hard_gate")
        seen_ids.add(row_id)
        rows.append(row)
    return rows


def validate_coverage(rows: list[dict[str, Any]]) -> None:
    operations = {row["operation"] for row in rows}
    missing = ALLOWED_OPERATIONS - operations
    if missing:
        raise ValueError(f"memory behavior dataset missing operations: {sorted(missing)}")
    gates = {row.get("hard_gate") for row in rows if row.get("hard_gate")}
    missing_gates = HARD_GATES - gates
    if missing_gates:
        raise ValueError(f"memory behavior dataset missing hard-gate coverage: {sorted(missing_gates)}")
    contradiction_rows = [row for row in rows if row.get("failure_stage") == "contradiction_failure"]
    if not contradiction_rows:
        raise ValueError("memory behavior dataset must include a contradiction scenario")
    if not all(
        any(memory.get("memory_key") for memory in row.get("seed_memories", []) or [])
        for row in contradiction_rows
    ):
        raise ValueError("contradiction scenarios must identify an overwriteable memory key")


def _seed_store(store: InMemoryMemoryStore, row: dict[str, Any]) -> None:
    for session in row.get("seed_sessions", []) or []:
        store.ensure_session(session["session_id"], user_id=session.get("user_id"))

    probe_session = row.get("probe_session_id")
    if probe_session:
        store.ensure_session(probe_session, user_id=row.get("probe_user_id"))

    memories = sorted(
        row.get("seed_memories", []) or [],
        key=lambda raw: int(raw.get("updated_at", 1)),
    )
    for raw in memories:
        session_id = raw.get("session_id")
        user_id = raw.get("user_id")
        if session_id:
            store.ensure_session(session_id, user_id=user_id)
        item = MemoryItemRecord(
            id=raw["id"],
            scope=raw["scope"],
            text=raw["text"],
            session_id=session_id,
            user_id=user_id,
            confidence=float(raw.get("confidence", 1.0)),
            privacy_class=raw.get("privacy_class", "normal"),
            memory_key=raw.get("memory_key"),
            created_at=int(raw.get("created_at", raw.get("updated_at", 1))),
            updated_at=int(raw.get("updated_at", 1)),
        )
        if item.memory_key:
            store.replace_active_memory_item(item)
        else:
            store.upsert_memory_item(item)


def _run_write(row: dict[str, Any]) -> dict[str, Any]:
    store = InMemoryMemoryStore()
    writer = MemoryWriter(store)
    result = writer.write_candidate(
        text=row["text"],
        session_id=row.get("session_id"),
        user_id=row.get("user_id"),
        source_message_id=None,
        scope=row.get("scope", "session"),
        memory_key=row.get("memory_key"),
    )
    actual_written = result is not None
    expected_written = bool(row.get("expect_written", True))
    passed = actual_written == expected_written
    failure_stage = "passed"
    if not passed:
        failure_stage = row.get("hard_gate") or ("write_miss" if expected_written else "unwanted_write")
    return {
        "id": row["id"],
        "operation": "write",
        "ok": passed,
        "failure_stage": failure_stage,
        "hard_gate": row.get("hard_gate"),
        "expected_written": expected_written,
        "actual_written": actual_written,
        "stored_text": result.text if result else None,
        "memory_key": result.memory_key if result else None,
    }


def _run_dedup(row: dict[str, Any]) -> dict[str, Any]:
    store = InMemoryMemoryStore()
    writer = MemoryWriter(store)
    returned_ids: list[str] = []
    for text in row.get("texts", []) or []:
        result = writer.write_candidate(
            text=text,
            session_id=row.get("session_id"),
            user_id=row.get("user_id"),
            source_message_id=None,
            scope=row.get("scope", "session"),
            memory_key=row.get("memory_key"),
        )
        if result:
            returned_ids.append(result.id)
    unique_count = len(set(returned_ids))
    expected = int(row.get("expected_unique_count", 1))
    passed = unique_count == expected
    return {
        "id": row["id"],
        "operation": "dedup",
        "ok": passed,
        "failure_stage": "passed" if passed else "dedup_failure",
        "hard_gate": row.get("hard_gate"),
        "expected_unique_count": expected,
        "actual_unique_count": unique_count,
    }


def _run_retrieval(row: dict[str, Any]) -> dict[str, Any]:
    store = InMemoryMemoryStore()
    _seed_store(store, row)
    selected = store.search_memory_items(
        row["query"],
        session_id=row.get("probe_session_id"),
        user_id=row.get("probe_user_id"),
        limit=int(row.get("limit", 10)),
    )
    selected_text = "\n".join(item.text for item in selected).casefold()
    expected = [str(term).casefold() for term in row.get("expected_contains", []) or []]
    forbidden = [str(term).casefold() for term in row.get("forbidden_contains", []) or []]
    missing_expected = [term for term in expected if term not in selected_text]
    forbidden_hits = [term for term in forbidden if term in selected_text]
    passed = not missing_expected and not forbidden_hits
    failure_stage = "passed"
    if not passed:
        if forbidden_hits and row.get("hard_gate"):
            failure_stage = row["hard_gate"]
        else:
            failure_stage = row.get("failure_stage") or "retrieval_miss"
    superseded = [
        {
            "id": item.id,
            "memory_key": item.memory_key,
            "superseded_by_id": item.superseded_by_id,
        }
        for item in store.memory_items.values()
        if item.status == "superseded"
    ]
    return {
        "id": row["id"],
        "operation": "retrieval",
        "ok": passed,
        "failure_stage": failure_stage,
        "hard_gate": row.get("hard_gate"),
        "selected_memory_ids": [item.id for item in selected],
        "selected_memory_texts": [item.text for item in selected],
        "missing_expected": missing_expected,
        "forbidden_hits": forbidden_hits,
        "superseded_history": superseded,
    }


def run_behavior_eval(rows: list[dict[str, Any]], dataset_path: Path, *, strategy: str = "baseline") -> dict[str, Any]:
    validate_coverage(rows)
    results: list[dict[str, Any]] = []
    for row in rows:
        operation = row["operation"]
        if operation == "write":
            result = _run_write(row)
        elif operation == "dedup":
            result = _run_dedup(row)
        else:
            result = _run_retrieval(row)
        results.append(result)

    failure_counts = Counter(result["failure_stage"] for result in results)
    hard_gate_failures = sum(
        1
        for result in results
        if result["failure_stage"] in HARD_GATES
    )

    write_rows = [result for result in results if result["operation"] == "write"]
    tp = sum(1 for result in write_rows if result["expected_written"] and result["actual_written"])
    fp = sum(1 for result in write_rows if not result["expected_written"] and result["actual_written"])
    fn = sum(1 for result in write_rows if result["expected_written"] and not result["actual_written"])

    def ratio(numerator: int, denominator: int, default: float = 1.0) -> float:
        return numerator / denominator if denominator else default

    retrieval_rows = [result for result in results if result["operation"] == "retrieval"]
    contradiction_rows = [
        result for result in results
        if result["failure_stage"] == "contradiction_failure"
        or result["id"].startswith("newer_contradiction")
    ]
    contradiction_passes = sum(1 for result in contradiction_rows if result["ok"])

    metrics = {
        "pass_rate": ratio(sum(1 for result in results if result["ok"]), len(results), 0.0),
        "write_precision": ratio(tp, tp + fp),
        "write_recall": ratio(tp, tp + fn),
        "dedup_pass_rate": ratio(
            sum(1 for result in results if result["operation"] == "dedup" and result["ok"]),
            sum(1 for result in results if result["operation"] == "dedup"),
        ),
        "retrieval_pass_rate": ratio(
            sum(1 for result in retrieval_rows if result["ok"]),
            len(retrieval_rows),
        ),
        "cross_session_leakage_rate": ratio(failure_counts.get("cross_session_leak", 0), 1, 0.0),
        "cross_user_leakage_rate": ratio(failure_counts.get("cross_user_leak", 0), 1, 0.0),
        "sensitive_write_rate": ratio(failure_counts.get("sensitive_write", 0), 1, 0.0),
        "contradiction_resolution_accuracy": ratio(contradiction_passes, len(contradiction_rows), 0.0),
        "hard_gate_failures": hard_gate_failures,
    }
    return build_report(
        evaluation="memory",
        dataset_path=dataset_path,
        strategy=strategy,
        backend="inmemory-production-contract",
        model="none",
        metrics=metrics,
        failure_stage_counts=dict(failure_counts),
        results=results,
        metadata={"hard_gates": sorted(HARD_GATES)},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or run deterministic memory behavior evaluation.")
    parser.add_argument("--dataset", default="eval/memory_behavior_golden_set.jsonl")
    parser.add_argument("--run-behavior", action="store_true")
    parser.add_argument("--strategy", default="baseline")
    parser.add_argument("--out", default="")
    parser.add_argument("--hard-gates", action="store_true", help="Fail only when a privacy/integrity hard gate is violated.")
    args = parser.parse_args()

    path = Path(args.dataset)
    rows = load_memory_eval_rows(path)
    validate_coverage(rows)
    if not args.run_behavior:
        print(f"validated {len(rows)} memory behavior rows with required coverage")
        return 0

    report = run_behavior_eval(rows, path, strategy=args.strategy)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        write_report(Path(args.out), report)
    else:
        print(payload)
    if args.hard_gates and report["metrics"]["hard_gate_failures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
