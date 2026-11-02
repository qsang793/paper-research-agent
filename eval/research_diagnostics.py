from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.research.discovery.service import discover_papers
from agent.research.evals.metrics import evidence_term_recall, paper_hit_ranks_at_k, paper_recall_at_k
from agent.research.indexing.contextual_chunks import create_contextual_chunks
from agent.research.indexing.paper_store import PaperStore
from agent.research.indexing.section_parser import parse_paper_text
from agent.research.query_plan import plan_research_query
from agent.research.ranking.reranker import rank_candidates
from agent.research.evidence.retriever import retrieve_evidence


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def diagnose_row(row: dict[str, Any], top_k: int = 10, providers: list[str] | None = None) -> dict[str, Any]:
    plan = plan_research_query(row["query"])
    candidates = discover_papers(plan, provider_names=providers, max_results=max(top_k * 3, 10))
    ranked = rank_candidates(plan, candidates, top_k=top_k)
    expected = row.get("expected_papers", []) or []

    hit_ranks = paper_hit_ranks_at_k(ranked, expected, k=top_k)
    paper_recall = paper_recall_at_k(ranked, expected, k=top_k) if expected else 0.0

    stage = "passed"
    if expected and paper_recall == 0.0:
        stage = "discovery_or_ranking_miss"

    evidence_count = 0
    evidence_term_coverage = 0.0
    expected_terms = row.get("expected_terms") or []
    if stage == "passed" and expected:
        store = PaperStore()
        chunks = []
        for candidate in ranked:
            paper = store.upsert_candidate(candidate)
            parsed = parse_paper_text(candidate.abstract or "", candidate=candidate)
            chunks.extend(create_contextual_chunks(paper, parsed))
        evidence = retrieve_evidence(
            row["query"],
            chunks,
            paper_ids=[paper.paper_id for paper in store.all()],
            top_k=top_k,
        )
        evidence_count = len(evidence)
        evidence_term_coverage = evidence_term_recall(evidence, expected_terms)
        if expected_terms and evidence_count > 0 and evidence_term_coverage == 0.0:
            stage = "weak_evidence"
        if evidence_count == 0:
            stage = "evidence_miss"

    return {
        "id": row["id"],
        "query": row["query"],
        "stage": stage,
        "paper_hit_ranks": hit_ranks,
        "paper_recall_at_k": paper_recall,
        "evidence_term_recall": evidence_term_coverage,
        "candidate_count": len(candidates),
        "ranked_count": len(ranked),
        "evidence_count": evidence_count,
        "top_papers": [
            {"title": item.title, "arxiv_id": item.arxiv_id, "score": item.score}
            for item in ranked[:top_k]
        ],
    }


def summarize_diagnostics(results: list[dict[str, Any]]) -> dict[str, Any]:
    items = list(results)
    return {
        "query_count": len(items),
        "stage_counts": dict(Counter(item["stage"] for item in items)),
        "results": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="eval/answer_quality_golden_set.jsonl")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--providers", default="")
    args = parser.parse_args()

    providers = [item.strip() for item in args.providers.split(",") if item.strip()] or None
    rows = _load_jsonl(Path(args.dataset))
    report = summarize_diagnostics(
        diagnose_row(row, top_k=args.top_k, providers=providers) for row in rows
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
