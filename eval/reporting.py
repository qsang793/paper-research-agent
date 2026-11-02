from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

REPORT_SCHEMA_VERSION = 1
REQUIRED_REPORT_FIELDS = {
    "report_schema_version",
    "evaluation",
    "dataset",
    "dataset_hash",
    "git_sha",
    "strategy",
    "backend",
    "model",
    "query_count",
    "metrics",
    "failure_stage_counts",
    "results",
}


def dataset_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_git_sha() -> str:
    env_sha = (os.getenv("GITHUB_SHA") or "").strip()
    if env_sha:
        return env_sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        sha = result.stdout.strip()
        return sha or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def build_report(
    *,
    evaluation: str,
    dataset_path: Path,
    strategy: str,
    backend: str | None,
    model: str | None,
    metrics: dict[str, Any],
    failure_stage_counts: dict[str, int],
    results: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "evaluation": evaluation,
        "dataset": str(dataset_path),
        "dataset_hash": dataset_sha256(dataset_path),
        "git_sha": resolve_git_sha(),
        "strategy": strategy,
        "backend": backend or "deterministic",
        "model": model or "none",
        "query_count": len(results),
        "metrics": metrics,
        "failure_stage_counts": failure_stage_counts,
        "results": results,
    }
    if metadata:
        report["metadata"] = metadata
    validate_report(report)
    return report


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    missing = REQUIRED_REPORT_FIELDS - set(report)
    if missing:
        raise ValueError(f"evaluation report missing fields: {sorted(missing)}")
    if report["report_schema_version"] != REPORT_SCHEMA_VERSION:
        raise ValueError("unsupported evaluation report schema version")
    if not isinstance(report["evaluation"], str) or not report["evaluation"].strip():
        raise ValueError("evaluation must be a non-empty string")
    if not isinstance(report["dataset_hash"], str) or len(report["dataset_hash"]) != 64:
        raise ValueError("dataset_hash must be a sha256 hex digest")
    if not isinstance(report["query_count"], int) or report["query_count"] < 0:
        raise ValueError("query_count must be a non-negative integer")
    if not isinstance(report["metrics"], dict):
        raise ValueError("metrics must be an object")
    if not isinstance(report["failure_stage_counts"], dict):
        raise ValueError("failure_stage_counts must be an object")
    if not isinstance(report["results"], list):
        raise ValueError("results must be an array")
    if report["query_count"] != len(report["results"]):
        raise ValueError("query_count must equal len(results)")
    return report


def write_report(path: Path, report: dict[str, Any]) -> None:
    validate_report(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return validate_report(payload)


def metric_value(report: dict[str, Any], path: str) -> float:
    current: Any = report
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(f"metric path not found: {path}")
        current = current[part]
    if not isinstance(current, (int, float)) or isinstance(current, bool):
        raise TypeError(f"metric path is not numeric: {path}")
    return float(current)
