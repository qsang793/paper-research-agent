from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class GoldenQuery:
    id: str
    query: str
    expected_papers: List[str] = field(default_factory=list)
    expected_terms: List[str] = field(default_factory=list)
    task_type: str = ""
    notes: str = ""


def _validate_row(row: dict, line_number: int) -> GoldenQuery:
    missing = [key for key in ["id", "query", "task_type"] if not row.get(key)]
    if missing:
        raise ValueError(f"Invalid golden row {line_number}: missing {', '.join(missing)}")
    expected_papers = row.get("expected_papers") or []
    expected_terms = row.get("expected_terms") or []
    if not isinstance(expected_papers, list) or not isinstance(expected_terms, list):
        raise ValueError(f"Invalid golden row {line_number}: expected lists for expected_papers/expected_terms")
    return GoldenQuery(
        id=str(row["id"]),
        query=str(row["query"]),
        expected_papers=[str(item) for item in expected_papers],
        expected_terms=[str(item) for item in expected_terms],
        task_type=str(row["task_type"]),
        notes=str(row.get("notes") or ""),
    )


def load_golden_dataset(path: str | Path) -> List[GoldenQuery]:
    rows: List[GoldenQuery] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows.append(_validate_row(json.loads(line), line_number))
    return rows
