from agent.research.discovery.models import PaperCandidate
from agent.research.query_plan import plan_research_query
from agent.research.ranking.features import score_candidate
from agent.research.ranking.reranker import rank_candidates


def test_score_candidate_rewards_entities_aliases_category_and_recency():
    plan = plan_research_query("ROS2 trong robotics là gì")
    candidate = PaperCandidate(
        title="ROS 2 middleware for robotics",
        abstract="Robot Operating System 2 supports distributed robots.",
        categories=["cs.RO"],
        year=2024,
        citation_count=12,
        provider_rank=1,
    )

    score, breakdown = score_candidate(plan, candidate)

    assert score > 0.5
    assert breakdown["entity_match"] > 0
    assert breakdown["alias_match"] > 0
    assert breakdown["category_match"] > 0
    assert breakdown["recency"] > 0


def test_rank_candidates_preserves_fallback_and_applies_fake_rerank_top_only():
    plan = plan_research_query("ROS2 robotics")
    candidates = [
        PaperCandidate(title="Weak", abstract="nothing", provider_rank=1),
        PaperCandidate(title="ROS 2 robotics", abstract="middleware", provider_rank=2),
    ]

    ranked = rank_candidates(
        plan,
        candidates,
        top_k=2,
        rerank_top_n=2,
        cross_encoder=lambda pairs: [0.1, 0.9],
    )

    assert ranked[0].title == "ROS 2 robotics"
    assert ranked[0].score_breakdown["rerank_score"] == 0.9


def test_rank_candidates_keeps_exact_arxiv_id_match_first():
    plan = plan_research_query("paper 1706.03762 summary")
    candidates = [
        PaperCandidate(
            title="Transformer retrospective with many citations",
            abstract="This survey discusses arXiv 1706.03762 and later transformer variants.",
            arxiv_id="2401.00001",
            provider_rank=1,
            citation_count=100000,
            year=2024,
        ),
        PaperCandidate(
            title="Attention Is All You Need",
            abstract="We propose the Transformer, a model architecture based solely on attention mechanisms.",
            arxiv_id="1706.03762",
            provider_rank=2,
            year=2017,
        ),
    ]

    ranked = rank_candidates(plan, candidates, top_k=2)

    assert ranked[0].arxiv_id == "1706.03762"
    assert ranked[0].score_breakdown["identifier_match"] == 1.0


def test_rank_candidates_keeps_canonical_transformer_first():
    plan = plan_research_query("Transformer paper có gì")
    candidates = [
        PaperCandidate(
            title="Robotics Transformer for Real-World Control at Scale",
            abstract="A transformer model for robotics.",
            arxiv_id="2212.06817",
            citation_count=1000,
            year=2022,
            provider_rank=1,
        ),
        PaperCandidate(
            title="Attention Is All You Need",
            abstract="We propose the Transformer architecture.",
            arxiv_id="1706.03762",
            citation_count=100000,
            year=2017,
            provider_rank=2,
        ),
    ]

    ranked = rank_candidates(plan, candidates, top_k=2)

    assert ranked[0].arxiv_id == "1706.03762"
    assert ranked[0].score_breakdown["canonical_match"] == 1.0


def test_rank_candidates_keeps_both_lora_and_qlora_for_comparison():
    plan = plan_research_query("compare LoRA and QLoRA papers")
    candidates = [
        PaperCandidate(
            title="A photovoltaic defect classifier using QLoRA",
            abstract="QLoRA is used for classification.",
            arxiv_id="2401.00001",
            provider_rank=1,
            year=2024,
        ),
        PaperCandidate(
            title="LoRA: Low-Rank Adaptation of Large Language Models",
            abstract="LoRA reduces trainable parameters.",
            arxiv_id="2106.09685",
            provider_rank=2,
            year=2021,
            citation_count=10000,
        ),
        PaperCandidate(
            title="QLoRA: Efficient Finetuning of Quantized LLMs",
            abstract="QLoRA uses 4-bit quantization and low-rank adapters.",
            arxiv_id="2305.14314",
            provider_rank=3,
            year=2023,
            citation_count=8000,
        ),
    ]

    ranked = rank_candidates(plan, candidates, top_k=2)

    assert {item.arxiv_id for item in ranked} == {"2106.09685", "2305.14314"}
    assert all(item.score_breakdown["comparison_target_match"] == 1.0 for item in ranked)
