import pytest

from agent.research.discovery.models import PaperCandidate
from agent.research.query_plan import plan_research_query
from agent.research.ranking.reranker import rank_candidates


def _candidates(reverse: bool = False):
    candidates = [
        PaperCandidate(title="ROS 2 middleware", abstract="robotics middleware"),
        PaperCandidate(title="Unrelated", abstract="cooking"),
    ]
    return list(reversed(candidates)) if reverse else candidates


def test_rank_candidates_logs_cross_encoder_failure(caplog):
    plan = plan_research_query("ROS2 middleware")
    baseline = rank_candidates(plan, _candidates(), top_k=2)

    def broken_cross_encoder(pairs):
        raise RuntimeError("model exploded")

    with caplog.at_level("WARNING", logger="agent.research.ranking.reranker"):
        ranked = rank_candidates(
            plan,
            _candidates(reverse=True),
            top_k=2,
            cross_encoder=broken_cross_encoder,
        )

    ranked_titles = [candidate.title for candidate in ranked]
    baseline_titles = [candidate.title for candidate in baseline]
    ranked_scores = [candidate.score for candidate in ranked]
    baseline_scores = [candidate.score for candidate in baseline]

    assert len(ranked) == 2
    assert ranked_titles == baseline_titles
    assert ranked_scores == pytest.approx(baseline_scores)
    assert "Cross-encoder rerank failed" in caplog.text
