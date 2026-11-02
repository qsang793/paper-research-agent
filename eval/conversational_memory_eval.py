from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_row(row: dict, *, line_no: int, path: Path) -> dict:
    if not isinstance(row, dict):
        raise ValueError(f"{path}:{line_no} invalid row, expected object")

    turns = row.get("turns")
    if not isinstance(turns, list) or not turns:
        raise ValueError(f"{path}:{line_no} missing or empty 'turns'")

    for turn_index, turn in enumerate(turns, start=1):
        if not isinstance(turn, dict):
            raise ValueError(
                f"{path}:{line_no} turn {turn_index} invalid, expected object with role/content"
            )
        if not isinstance(turn.get("role"), str) or turn["role"] not in {"user", "assistant"}:
            raise ValueError(
                f"{path}:{line_no} turn {turn_index} missing/invalid role: {turn.get('role')!r}"
            )
        if not isinstance(turn.get("content"), str) or not turn["content"].strip():
            raise ValueError(
                f"{path}:{line_no} turn {turn_index} missing/empty content for role {turn.get('role')!r}"
            )

    expected = row.get("expected_contains")
    if not isinstance(expected, str) or not expected.strip():
        raise ValueError(f"{path}:{line_no} missing/empty expected_contains")

    return row


def load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        row = json.loads(stripped)
        rows.append(validate_row(row, line_no=idx, path=path))
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load conversational memory golden rows.")
    parser.add_argument(
        "--dataset",
        default="eval/conversational_memory_golden_set.jsonl",
        help="Path to conversational memory golden set (JSONL).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    path = Path(args.dataset)
    rows = load_rows(path)
    print(f"loaded {len(rows)} conversational memory eval rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
