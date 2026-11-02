from agent.research.discovery.models import PaperCandidate
from agent.research.discovery.openalex_provider import normalize_openalex_work
from agent.research.discovery.semantic_scholar_provider import normalize_semantic_scholar_paper
from agent.research.discovery.service import discover_papers, merge_duplicate_candidates


def test_paper_candidate_stable_key_priority():
    assert PaperCandidate(title="T", arxiv_id="2306.17157").stable_key() == "arxiv:2306.17157"
    assert PaperCandidate(title="T", doi="10.1000/X").stable_key() == "doi:10.1000/x"
    assert PaperCandidate(title="T", semantic_scholar_id="S2").stable_key() == "s2:S2"
    assert PaperCandidate(title="A   Paper!").stable_key() == "title:a paper"


def test_discovery_deduplicates_by_identifier_and_title_similarity():
    left = PaperCandidate(
        title="ROS 2 in robotics research",
        arxiv_id="2306.17157",
        source_provider="arxiv",
        provider_rank=1,
    )
    right = PaperCandidate(
        title="ROS 2 in Robotics Research",
        semantic_scholar_id="S2",
        source_provider="semantic_scholar",
        provider_rank=2,
    )

    merged = merge_duplicate_candidates([left, right])

    assert len(merged) == 1
    assert merged[0].arxiv_id == "2306.17157"
    assert merged[0].semantic_scholar_id == "S2"
    assert set(merged[0].source_providers) == {"arxiv", "semantic_scholar"}


def test_discover_papers_scores_and_orders_provider_results():
    def fake_provider(plan, max_results=20):
        return [
            PaperCandidate(
                title="Unrelated database paper",
                abstract="A database benchmark.",
                source_provider="fake",
                provider_rank=1,
            ),
            PaperCandidate(
                title="ROS 2 middleware for robotics",
                abstract="Robot Operating System 2 supports distributed robotics.",
                categories=["cs.RO"],
                source_provider="fake",
                provider_rank=2,
                year=2024,
            ),
        ]

    results = discover_papers(
        "ROS2 trong robotics là gì",
        providers={"fake": fake_provider},
        provider_names=["fake"],
    )

    assert results[0].title == "ROS 2 middleware for robotics"
    assert results[0].score_breakdown["entity_match"] > 0
    assert results[0].score_breakdown["category_match"] > 0


def test_discover_papers_ranks_high_citation_paper_above_recent_incidental_match():
    def fake_provider(plan, max_results=20):
        return [
            PaperCandidate(
                title="A recent paper that mentions BERT in passing",
                abstract="We briefly compare against BERT as a baseline.",
                source_provider="fake",
                provider_rank=1,
                year=2024,
                citation_count=3,
                arxiv_id="2401.00001",
            ),
            PaperCandidate(
                title="BERT: Pre-training of Deep Bidirectional Transformers",
                abstract="We introduce BERT, a language representation model.",
                source_provider="fake",
                provider_rank=2,
                year=2018,
                citation_count=80000,
                arxiv_id="1810.04805",
            ),
        ]

    results = discover_papers("BERT", providers={"fake": fake_provider}, provider_names=["fake"])

    # Both match the query equally; citation authority must break the tie toward
    # the seminal paper instead of the newer incidental match.
    assert results[0].arxiv_id == "1810.04805"
    assert (
        results[0].score_breakdown["citation_signal"]
        > results[1].score_breakdown["citation_signal"]
    )


def test_discover_papers_ranks_exact_arxiv_id_match_first():
    def fake_provider(plan, max_results=20):
        return [
            PaperCandidate(
                title="Transformer retrospective with many citations",
                abstract="This survey discusses arXiv 1706.03762 and later transformer variants.",
                source_provider="semantic_scholar",
                provider_rank=1,
                year=2024,
                citation_count=100000,
                arxiv_id="2401.00001",
            ),
            PaperCandidate(
                title="Attention Is All You Need",
                abstract="We propose the Transformer, a model architecture based solely on attention mechanisms.",
                source_provider="arxiv",
                provider_rank=2,
                year=2017,
                arxiv_id="1706.03762",
            ),
        ]

    results = discover_papers(
        "paper 1706.03762 summary",
        providers={"fake": fake_provider},
        provider_names=["fake"],
    )

    assert results[0].arxiv_id == "1706.03762"
    assert results[0].score_breakdown["identifier_match"] == 1.0


def test_discover_papers_boosts_canonical_transformer_target():
    def fake_provider(plan, max_results=20):
        return [
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

    results = discover_papers("Transformer paper có gì", providers={"fake": fake_provider}, provider_names=["fake"])

    assert results[0].arxiv_id == "1706.03762"
    assert results[0].score_breakdown["canonical_match"] == 1.0


def test_semantic_scholar_and_openalex_normalizers_degrade_without_raw_leakage():
    s2 = normalize_semantic_scholar_paper(
        {
            "paperId": "S2",
            "title": "A paper",
            "abstract": "Abstract",
            "year": 2024,
            "authors": [{"name": "Grace"}],
            "externalIds": {"ArXiv": "2401.00001", "DOI": "10.1/abc"},
            "openAccessPdf": {"url": "https://example.test/paper.pdf"},
            "url": "https://semanticscholar.org/paper/S2",
            "citationCount": 7,
        },
        provider_rank=1,
    )
    openalex = normalize_openalex_work(
        {
            "id": "https://openalex.org/W123",
            "display_name": "OpenAlex paper",
            "publication_year": 2023,
            "doi": "https://doi.org/10.2/xyz",
            "cited_by_count": 9,
            "authorships": [{"author": {"display_name": "Alan"}}],
            "primary_location": {
                "landing_page_url": "https://example.test/landing",
                "pdf_url": "https://example.test/paper.pdf",
            },
            "abstract_inverted_index": {"A": [0], "test": [1]},
        },
        provider_rank=2,
    )

    assert s2.arxiv_id == "2401.00001"
    assert s2.raw is None
    assert openalex.openalex_id == "W123"
    assert openalex.abstract == "A test"
