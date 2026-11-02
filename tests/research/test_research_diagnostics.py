from agent.research.discovery.models import PaperCandidate
from agent.research.evidence.models import EvidenceSpan
from eval.research_diagnostics import diagnose_row, summarize_diagnostics


def test_diagnose_row_marks_discovery_miss(monkeypatch):
    def fake_discover(plan, provider_names=None, max_results=10):
        return [PaperCandidate(title="Unrelated", arxiv_id="9999.99999")]

    monkeypatch.setattr("eval.research_diagnostics.discover_papers", fake_discover)

    row = {
        "id": "transformer-original-vi",
        "query": "Transformer paper có gì",
        "expected_papers": ["1706.03762"],
        "expected_terms": ["self-attention"],
        "task_type": "paper_lookup",
    }

    result = diagnose_row(row, top_k=5, providers=["fake"])

    assert result["id"] == "transformer-original-vi"
    assert result["stage"] == "discovery_or_ranking_miss"
    assert result["paper_hit_ranks"] == {}


def test_summarize_diagnostics_counts_stages():
    report = summarize_diagnostics(
        [
            {"stage": "passed"},
            {"stage": "discovery_or_ranking_miss"},
            {"stage": "discovery_or_ranking_miss"},
        ]
    )

    assert report["stage_counts"] == {
        "passed": 1,
        "discovery_or_ranking_miss": 2,
    }


def test_diagnose_row_retrieves_evidence_once_after_all_chunks(monkeypatch):
    def fake_discover(plan, provider_names=None, max_results=10):
        return [
            PaperCandidate(title="Unrelated", abstract="This abstract has no expected term.", arxiv_id="9999.99999"),
            PaperCandidate(
                title="Attention Is All You Need",
                abstract="The Transformer uses self-attention.",
                arxiv_id="1706.03762",
            ),
        ]

    retrieve_calls = []

    def fake_retrieve(query, chunks, paper_ids, top_k=10):
        retrieve_calls.append({"chunks": chunks, "paper_ids": paper_ids})
        return [
            EvidenceSpan(
                paper_id=paper_ids[-1],
                title="Attention Is All You Need",
                url="https://arxiv.org/abs/1706.03762",
                quote="The Transformer uses self-attention.",
                score=0.9,
            )
        ]

    monkeypatch.setattr("eval.research_diagnostics.discover_papers", fake_discover)
    monkeypatch.setattr("eval.research_diagnostics.retrieve_evidence", fake_retrieve)

    row = {
        "id": "transformer-original-vi",
        "query": "Transformer paper có gì",
        "expected_papers": ["1706.03762"],
        "expected_terms": ["self-attention"],
        "task_type": "paper_lookup",
    }

    result = diagnose_row(row, top_k=5, providers=["fake"])

    assert result["stage"] == "passed"
    assert result["evidence_count"] == 1
    assert result["evidence_term_recall"] == 1.0
    assert len(retrieve_calls) == 1
    assert len(retrieve_calls[0]["chunks"]) == 2
