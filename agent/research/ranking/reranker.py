from __future__ import annotations

import logging
from typing import Callable, List, Sequence

from agent.research.discovery.models import PaperCandidate
from agent.research.query_plan import QueryPlan
from agent.research.ranking.features import score_candidate


logger = logging.getLogger(__name__)

CrossEncoderFn = Callable[[List[list[str]]], Sequence[float]]
DenseScorerFn = Callable[[str, str], float]


def rank_candidates(
    plan: QueryPlan,
    candidates: List[PaperCandidate],
    *,
    top_k: int = 10,
    rerank_top_n: int = 20,
    dense_scorer: DenseScorerFn | None = None,
    cross_encoder: CrossEncoderFn | None = None,
) -> List[PaperCandidate]:
    for candidate in candidates:
        if dense_scorer:
            candidate.score_breakdown["dense_score"] = float(
                dense_scorer(plan.normalized_query, f"{candidate.title}\n{candidate.abstract}")
            )
        score, breakdown = score_candidate(plan, candidate)
        candidate.score = score
        candidate.score_breakdown.update(breakdown)

    rerank_pool = candidates[:rerank_top_n]
    if cross_encoder and rerank_pool:
        pairs = [[plan.normalized_query, f"{candidate.title}\n{candidate.abstract}"] for candidate in rerank_pool]
        try:
            scores = [float(score) for score in cross_encoder(pairs)]
            for candidate, rerank_score in zip(rerank_pool, scores):
                candidate.score_breakdown["rerank_score"] = rerank_score
                base_score, breakdown = score_candidate(plan, candidate)
                candidate.score_breakdown.update(breakdown)
                candidate.score = base_score + 0.35 * rerank_score
        except Exception:
            logger.warning("Cross-encoder rerank failed; using base scores", exc_info=True)

    def _final_sort_key(candidate: PaperCandidate) -> tuple[float, float]:
        exact = candidate.score_breakdown.get("identifier_match", 0.0)
        canonical = candidate.score_breakdown.get("canonical_match", 0.0)
        return (max(exact, canonical), candidate.score)

    return sorted(candidates, key=_final_sort_key, reverse=True)[:top_k]
