from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from agent.research.discovery.service import discover_papers
from agent.research.evals.datasets import load_golden_dataset
from agent.research.evals.metrics import (
    paper_hit_ranks_at_k,
    paper_mrr_at_k,
    paper_precision_at_k,
    paper_recall_at_k,
)

load_dotenv()

EVAL_REPORT_SCHEMA_VERSION = 4
RESUMABLE_RESULT_FIELDS = {
    "candidate_count",
    "id",
    "mrr_at_k",
    "no_candidates",
    "precision_at_k",
    "query",
    "recall_at_k",
    "task_type",
    "top_papers",
}


def missing_live_provider_config() -> list[str]:
    required = ["SEMANTIC_SCHOLAR_API_KEY", "OPENALEX_API_KEY"]
    return [name for name in required if not os.getenv(name)]


def _load_resume_results(path: Path | None) -> dict[str, dict]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("report_schema_version") != EVAL_REPORT_SCHEMA_VERSION:
        return {}
    return {
        item["id"]: item
        for item in payload.get("results", []) or []
        if item.get("id")
        and not item.get("no_candidates")
        and RESUMABLE_RESULT_FIELDS.issubset(item)
    }


def _build_report(dataset_path: Path, rows, results: list[dict], *, dry_run: bool) -> dict:
    row_by_id = {row.id: row for row in rows}
    recall_values = []
    precision_values = []
    mrr_values = []
    no_candidate_count = 0
    failure_stage_counts: dict[str, int] = {}

    for result in results:
        failure_stage = result.get("failure_stage") or "unknown"
        failure_stage_counts[failure_stage] = failure_stage_counts.get(failure_stage, 0) + 1
        row = row_by_id.get(result.get("id"))
        if row is None or not row.expected_papers:
            continue
        if result.get("no_candidates"):
            no_candidate_count += 1
            continue
        recall_values.append(float(result.get("recall_at_k", 0.0)))
        precision_values.append(float(result.get("precision_at_k", 0.0)))
        mrr_values.append(float(result.get("mrr_at_k", 0.0)))

    labeled_count = sum(1 for row in rows if row.expected_papers)
    return {
        "report_schema_version": EVAL_REPORT_SCHEMA_VERSION,
        "dataset": str(dataset_path),
        "dry_run": dry_run,
        "query_count": len(rows),
        "paper_labeled_query_count": labeled_count,
        "paper_unlabeled_query_count": len(rows) - labeled_count,
        "paper_scored_query_count": len(recall_values),
        "no_candidate_query_count": no_candidate_count,
        "mean_recall_at_k": sum(recall_values) / len(recall_values) if recall_values else 0.0,
        "mean_precision_at_k": sum(precision_values) / len(precision_values) if precision_values else 0.0,
        "mean_mrr_at_k": sum(mrr_values) / len(mrr_values) if mrr_values else 0.0,
        "failure_stage_counts": failure_stage_counts,
        "results": results,
    }


def _failure_stage(
    *,
    dry_run: bool,
    has_expected_papers: bool,
    no_candidates: bool,
    recall: float,
    best_hit_rank: int | None,
) -> str:
    if dry_run:
        return "dry_run"
    if not has_expected_papers:
        return "unlabeled"
    if no_candidates:
        return "provider_or_discovery"
    if recall <= 0.0:
        return "candidate_miss"
    if best_hit_rank and best_hit_rank > 1:
        return "ranking_miss"
    return "passed"


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def run_eval(
    dataset_path: Path,
    *,
    dry_run: bool = False,
    top_k: int = 10,
    sleep_seconds: float = 0.0,
    resume_path: Path | None = None,
    checkpoint_path: Path | None = None,
) -> dict:
    rows = load_golden_dataset(dataset_path)
    resumed_results = _load_resume_results(resume_path)
    results = []

    for index, row in enumerate(rows):
        if row.id in resumed_results:
            results.append(resumed_results[row.id])
            if checkpoint_path:
                _write_report(checkpoint_path, _build_report(dataset_path, rows, results, dry_run=dry_run))
            continue
        if sleep_seconds > 0 and index > 0 and not dry_run:
            time.sleep(sleep_seconds)
        candidates = [] if dry_run else discover_papers(row.query, max_results=top_k)
        recall = paper_recall_at_k(candidates, row.expected_papers, k=top_k)
        precision = paper_precision_at_k(candidates, row.expected_papers, k=top_k)
        mrr = paper_mrr_at_k(candidates, row.expected_papers, k=top_k)
        hit_ranks = paper_hit_ranks_at_k(candidates, row.expected_papers, k=top_k)
        best_hit_rank = min(hit_ranks.values()) if hit_ranks else None
        has_expected_papers = bool(row.expected_papers)
        no_candidates = not dry_run and has_expected_papers and not candidates
        failure_stage = _failure_stage(
            dry_run=dry_run,
            has_expected_papers=has_expected_papers,
            no_candidates=no_candidates,
            recall=recall,
            best_hit_rank=best_hit_rank,
        )
        results.append(
            {
                "id": row.id,
                "query": row.query,
                "task_type": row.task_type,
                "candidate_count": len(candidates),
                "no_candidates": no_candidates,
                "recall_at_k": recall,
                "precision_at_k": precision,
                "mrr_at_k": mrr,
                "hit_ranks": hit_ranks,
                "best_hit_rank": best_hit_rank,
                "failure_stage": failure_stage,
                "top_papers": [
                    {
                        "title": candidate.title,
                        "arxiv_id": candidate.arxiv_id,
                        "doi": candidate.doi,
                        "score": candidate.score,
                    }
                    for candidate in candidates[:top_k]
                ],
            }
        )
        if checkpoint_path:
            _write_report(checkpoint_path, _build_report(dataset_path, rows, results, dry_run=dry_run))

    return _build_report(dataset_path, rows, results, dry_run=dry_run)


def passes_thresholds(
    report: dict,
    *,
    min_recall: float | None = None,
    min_precision: float | None = None,
    min_mrr: float | None = None,
) -> bool:
    if min_recall is not None and report["mean_recall_at_k"] < min_recall:
        return False
    if min_precision is not None and report["mean_precision_at_k"] < min_precision:
        return False
    if min_mrr is not None and report.get("mean_mrr_at_k", 0.0) < min_mrr:
        return False
    return True


def gate_verdict(
    report: dict,
    *,
    min_recall: float | None = None,
    min_precision: float | None = None,
    min_mrr: float | None = None,
    max_no_candidate_rate: float = 0.2,
) -> str:
    """Return PASS/FAIL on thresholds, or INCONCLUSIVE for likely infra failure."""
    if report.get("dry_run"):
        return "PASS"
    if min_recall is None and min_precision is None and min_mrr is None:
        return "PASS"
    labeled = report.get("paper_labeled_query_count") or 0
    no_candidates = report.get("no_candidate_query_count") or 0
    if labeled and no_candidates / labeled > max_no_candidate_rate:
        return "INCONCLUSIVE"
    if passes_thresholds(report, min_recall=min_recall, min_precision=min_precision, min_mrr=min_mrr):
        return "PASS"
    return "FAIL"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic research workflow evals.")
    parser.add_argument("--dataset", default="eval/research_golden_set.jsonl")
    parser.add_argument("--out", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--min-recall", type=float, default=None)
    parser.add_argument("--min-precision", type=float, default=None)
    parser.add_argument(
        "--min-mrr",
        type=float,
        default=None,
        help="Minimum mean reciprocal rank of expected papers (rank-quality gate)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to sleep between live queries (provider pacing)",
    )
    parser.add_argument(
        "--max-no-candidate-rate",
        type=float,
        default=0.2,
        help="Labeled-row no-candidate rate above which the gate is INCONCLUSIVE",
    )
    parser.add_argument("--resume", default="", help="Existing eval report to resume from")
    parser.add_argument(
        "--require-provider-config",
        action="store_true",
        help="Exit INCONCLUSIVE before live gate if Semantic Scholar/OpenAlex config is absent",
    )
    args = parser.parse_args()

    if args.require_provider_config and not args.dry_run:
        missing = missing_live_provider_config()
        if missing:
            print(
                "GATE VERDICT: INCONCLUSIVE "
                f"(missing live provider config: {', '.join(missing)})",
                file=sys.stderr,
            )
            return 2

    report = run_eval(
        Path(args.dataset),
        dry_run=args.dry_run,
        top_k=args.top_k,
        sleep_seconds=args.sleep,
        resume_path=Path(args.resume) if args.resume else None,
        checkpoint_path=Path(args.out) if args.out else None,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        _write_report(Path(args.out), report)
    else:
        print(payload)

    verdict = gate_verdict(
        report,
        min_recall=args.min_recall,
        min_precision=args.min_precision,
        min_mrr=args.min_mrr,
        max_no_candidate_rate=args.max_no_candidate_rate,
    )
    print(f"GATE VERDICT: {verdict}", file=sys.stderr)
    if verdict == "FAIL":
        return 1
    if verdict == "INCONCLUSIVE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
