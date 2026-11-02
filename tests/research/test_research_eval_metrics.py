from pathlib import Path

from agent.research.evidence.models import EvidenceSpan
from agent.research.discovery.models import PaperCandidate
from agent.research.evals.datasets import load_golden_dataset
from agent.research.evals.metrics import (
    evidence_term_recall,
    paper_hit_ranks_at_k,
    paper_mrr_at_k,
    paper_precision_at_k,
    paper_recall_at_k,
)
from eval.research_eval import (
    EVAL_REPORT_SCHEMA_VERSION,
    gate_verdict,
    missing_live_provider_config,
    passes_thresholds,
    run_eval,
)


def test_retrieval_metrics_are_deterministic():
    candidates = [
        PaperCandidate(title="A", arxiv_id="1111.11111"),
        PaperCandidate(title="B", arxiv_id="2222.22222"),
        PaperCandidate(title="C", arxiv_id="3333.33333"),
    ]

    assert paper_recall_at_k(candidates, ["1111.11111", "3333.33333"], k=2) == 0.5
    assert paper_precision_at_k(candidates, ["1111.11111", "3333.33333"], k=2) == 0.5


def test_paper_mrr_at_k_rewards_rank_of_first_hit():
    candidates = [
        PaperCandidate(title="A", arxiv_id="1111.11111"),
        PaperCandidate(title="B", arxiv_id="2222.22222"),
        PaperCandidate(title="C", arxiv_id="3333.33333"),
    ]

    # single expected paper at rank 1 -> reciprocal rank 1.0
    assert paper_mrr_at_k(candidates, ["1111.11111"], k=10) == 1.0
    # single expected paper at rank 3 -> 1/3
    assert paper_mrr_at_k(candidates, ["3333.33333"], k=10) == 1.0 / 3.0
    # expected paper beyond k is a miss -> 0.0
    assert paper_mrr_at_k(candidates, ["3333.33333"], k=2) == 0.0
    # not retrieved at all -> 0.0
    assert paper_mrr_at_k(candidates, ["9999.99999"], k=10) == 0.0
    # multiple expected papers -> mean of reciprocal ranks (rank 1 and rank 2)
    assert paper_mrr_at_k(candidates, ["1111.11111", "2222.22222"], k=10) == 0.75
    # no expected papers -> 0.0
    assert paper_mrr_at_k(candidates, [], k=10) == 0.0


def test_paper_hit_ranks_at_k_reports_expected_paper_positions():
    candidates = [
        PaperCandidate(title="A", arxiv_id="1111.11111"),
        PaperCandidate(title="B", doi="10.1234/example"),
        PaperCandidate(title="C", arxiv_id="3333.33333"),
    ]

    ranks = paper_hit_ranks_at_k(candidates, ["10.1234/example", "3333.33333", "9999.99999"], k=2)

    assert ranks == {"10.1234/example": 2}


def test_evidence_term_recall_counts_expected_terms_across_quotes():
    evidence = [
        EvidenceSpan(paper_id="p1", title="T", url="u", quote="The Transformer uses self-attention.", score=0.9),
        EvidenceSpan(paper_id="p1", title="T", url="u", quote="It has encoder and decoder stacks.", score=0.8),
    ]

    assert evidence_term_recall(evidence, ["self-attention", "encoder", "decoder"]) == 1.0
    assert evidence_term_recall(evidence, ["self-attention", "missing"]) == 0.5


def test_load_golden_dataset_validates_jsonl_schema(tmp_path: Path):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        '{"id":"ros2","query":"ROS2 trong robotics là gì","expected_papers":["2306.17157"],"expected_terms":["ROS 2"],"task_type":"concept"}\n',
        encoding="utf-8",
    )

    rows = load_golden_dataset(dataset)

    assert rows[0].id == "ros2"
    assert rows[0].expected_papers == ["2306.17157"]


def test_passes_thresholds_requires_min_recall_and_precision():
    report = {
        "mean_recall_at_k": 0.7,
        "mean_precision_at_k": 0.4,
    }

    assert passes_thresholds(report, min_recall=0.6, min_precision=0.3) is True
    assert passes_thresholds(report, min_recall=0.8, min_precision=0.3) is False
    assert passes_thresholds(report, min_recall=0.6, min_precision=0.5) is False


def test_passes_thresholds_supports_min_mrr():
    report = {
        "mean_recall_at_k": 0.7,
        "mean_precision_at_k": 0.4,
        "mean_mrr_at_k": 0.5,
    }

    assert passes_thresholds(report, min_recall=0.6, min_mrr=0.4) is True
    assert passes_thresholds(report, min_recall=0.6, min_mrr=0.6) is False


def test_gate_verdict_passes_when_no_thresholds():
    report = {
        "paper_labeled_query_count": 0,
        "no_candidate_query_count": 0,
        "mean_recall_at_k": 0.0,
        "mean_precision_at_k": 0.0,
        "mean_mrr_at_k": 0.0,
    }

    assert gate_verdict(report, min_recall=None, min_precision=None, min_mrr=None) == "PASS"


def test_gate_verdict_uses_recall_and_mrr():
    base = {
        "paper_labeled_query_count": 26,
        "no_candidate_query_count": 0,
        "mean_recall_at_k": 0.7,
        "mean_precision_at_k": 0.05,
        "mean_mrr_at_k": 0.5,
    }

    assert gate_verdict(base, min_recall=0.55, min_mrr=0.35) == "PASS"
    # recall below target -> FAIL even with strong MRR
    assert gate_verdict({**base, "mean_recall_at_k": 0.3}, min_recall=0.55, min_mrr=0.35) == "FAIL"
    # seminal papers retrieved but buried (low MRR) -> FAIL even with strong recall
    assert gate_verdict({**base, "mean_mrr_at_k": 0.1}, min_recall=0.55, min_mrr=0.35) == "FAIL"


def test_gate_verdict_pass_fail_and_inconclusive():
    base = {
        "paper_labeled_query_count": 26,
        "no_candidate_query_count": 1,
        "mean_recall_at_k": 0.7,
        "mean_precision_at_k": 0.4,
    }

    assert gate_verdict(base, min_recall=0.55, min_precision=0.35) == "PASS"
    assert (
        gate_verdict({**base, "mean_recall_at_k": 0.3}, min_recall=0.55, min_precision=0.35)
        == "FAIL"
    )
    inconclusive = {**base, "no_candidate_query_count": 10}
    assert gate_verdict(inconclusive, min_recall=0.55, min_precision=0.35) == "INCONCLUSIVE"


def test_run_eval_summarizes_paper_metrics_over_labeled_rows_only(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        "\n".join(
            [
                '{"id":"labeled","query":"known paper","expected_papers":["1111.11111"],"expected_terms":[],"task_type":"paper_lookup"}',
                '{"id":"unlabeled","query":"unlabeled discovery","expected_papers":[],"expected_terms":["RAG"],"task_type":"concept"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_discover_papers(query: str, max_results: int):
        if query == "known paper":
            return [PaperCandidate(title="Known", arxiv_id="1111.11111")]
        return [PaperCandidate(title="Unlabeled", arxiv_id="2222.22222")]

    monkeypatch.setattr("eval.research_eval.discover_papers", fake_discover_papers)

    report = run_eval(dataset, top_k=10)

    assert report["query_count"] == 2
    assert report["paper_labeled_query_count"] == 1
    assert report["paper_unlabeled_query_count"] == 1
    assert report["mean_recall_at_k"] == 1.0
    assert report["mean_precision_at_k"] == 1.0
    assert report["paper_scored_query_count"] == 1
    assert report["no_candidate_query_count"] == 0
    assert report["mean_mrr_at_k"] == 1.0
    assert report["results"][0]["no_candidates"] is False
    assert report["results"][0]["failure_stage"] == "passed"
    assert report["results"][0]["hit_ranks"] == {"1111.11111": 1}
    assert report["results"][0]["mrr_at_k"] == 1.0
    assert report["results"][1]["recall_at_k"] == 0.0
    assert report["results"][1]["precision_at_k"] == 0.0
    assert report["results"][1]["mrr_at_k"] == 0.0
    assert report["results"][1]["no_candidates"] is False
    assert report["results"][1]["failure_stage"] == "unlabeled"
    assert report["failure_stage_counts"] == {"passed": 1, "unlabeled": 1}


def test_run_eval_dry_run_keeps_labeled_rows_scored(tmp_path: Path):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        '{"id":"a","query":"q1","task_type":"concept","expected_papers":["1111.11111"]}\n'
        '{"id":"b","query":"q2","task_type":"concept"}\n',
        encoding="utf-8",
    )

    report = run_eval(dataset, dry_run=True, top_k=5)

    assert report["paper_labeled_query_count"] == 1
    assert report["paper_scored_query_count"] == 1
    assert report["no_candidate_query_count"] == 0
    assert report["results"][0]["no_candidates"] is False
    assert report["results"][0]["failure_stage"] == "dry_run"
    assert report["failure_stage_counts"] == {"dry_run": 2}


def test_run_eval_live_zero_candidates_are_infra_data(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        '{"id":"a","query":"q1","task_type":"concept","expected_papers":["1111.11111"]}\n'
        '{"id":"b","query":"q2","task_type":"concept","expected_papers":["2222.22222"]}\n',
        encoding="utf-8",
    )

    def fake_discover_papers(query: str, max_results: int):
        if query == "q1":
            return []
        return [PaperCandidate(title="Matched", arxiv_id="2222.22222")]

    monkeypatch.setattr("eval.research_eval.discover_papers", fake_discover_papers)

    report = run_eval(dataset, top_k=5)

    assert report["paper_labeled_query_count"] == 2
    assert report["paper_scored_query_count"] == 1
    assert report["no_candidate_query_count"] == 1
    assert report["mean_recall_at_k"] == 1.0
    assert report["mean_precision_at_k"] == 1.0
    assert report["results"][0]["no_candidates"] is True
    assert report["results"][0]["failure_stage"] == "provider_or_discovery"
    assert report["results"][1]["no_candidates"] is False


def test_run_eval_marks_candidate_miss_and_ranking_miss(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        '{"id":"miss","query":"q1","task_type":"paper_lookup","expected_papers":["1111.11111"]}\n'
        '{"id":"buried","query":"q2","task_type":"paper_lookup","expected_papers":["2222.22222"]}\n',
        encoding="utf-8",
    )

    def fake_discover_papers(query: str, max_results: int):
        if query == "q1":
            return [PaperCandidate(title="Wrong", arxiv_id="9999.99999")]
        return [
            PaperCandidate(title="Wrong first", arxiv_id="9999.99999"),
            PaperCandidate(title="Expected second", arxiv_id="2222.22222"),
        ]

    monkeypatch.setattr("eval.research_eval.discover_papers", fake_discover_papers)

    report = run_eval(dataset, top_k=10)

    assert report["results"][0]["failure_stage"] == "candidate_miss"
    assert report["results"][1]["failure_stage"] == "ranking_miss"
    assert report["results"][1]["best_hit_rank"] == 2
    assert report["failure_stage_counts"] == {"candidate_miss": 1, "ranking_miss": 1}


def test_run_eval_sleep_only_paces_live_rows(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        '{"id":"a","query":"q1","task_type":"concept","expected_papers":["1111.11111"]}\n'
        '{"id":"b","query":"q2","task_type":"concept","expected_papers":["2222.22222"]}\n',
        encoding="utf-8",
    )
    sleeps = []

    def fake_discover_papers(query: str, max_results: int):
        arxiv_id = "1111.11111" if query == "q1" else "2222.22222"
        return [PaperCandidate(title=query, arxiv_id=arxiv_id)]

    monkeypatch.setattr("eval.research_eval.discover_papers", fake_discover_papers)
    monkeypatch.setattr("eval.research_eval.time.sleep", sleeps.append)

    run_eval(dataset, top_k=5, sleep_seconds=3.0)

    assert sleeps == [3.0]

    run_eval(dataset, dry_run=True, top_k=5, sleep_seconds=3.0)

    assert sleeps == [3.0]


def test_run_eval_resumes_rows_from_previous_report_and_checkpoints(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "golden.jsonl"
    resume = tmp_path / "resume.json"
    checkpoint = tmp_path / "checkpoint.json"
    dataset.write_text(
        '{"id":"a","query":"q1","task_type":"concept","expected_papers":["1111.11111"]}\n'
        '{"id":"b","query":"q2","task_type":"concept","expected_papers":["2222.22222"]}\n',
        encoding="utf-8",
    )
    resume.write_text(
        """
{
  "report_schema_version": __SCHEMA_VERSION__,
  "results": [
    {
      "id": "a",
      "query": "q1",
      "task_type": "concept",
      "candidate_count": 1,
      "no_candidates": false,
      "recall_at_k": 1.0,
      "precision_at_k": 1.0,
      "mrr_at_k": 1.0,
      "top_papers": [{"title": "Cached", "arxiv_id": "1111.11111", "doi": null, "score": 1.0}]
    }
  ]
}
""".strip().replace("__SCHEMA_VERSION__", str(EVAL_REPORT_SCHEMA_VERSION))
        + "\n",
        encoding="utf-8",
    )
    calls = []

    def fake_discover_papers(query: str, max_results: int):
        calls.append(query)
        return [PaperCandidate(title="Fresh", arxiv_id="2222.22222")]

    monkeypatch.setattr("eval.research_eval.discover_papers", fake_discover_papers)

    report = run_eval(dataset, top_k=5, resume_path=resume, checkpoint_path=checkpoint)

    assert calls == ["q2"]
    assert report["paper_scored_query_count"] == 2
    assert report["mean_recall_at_k"] == 1.0
    assert report["mean_precision_at_k"] == 1.0
    saved = checkpoint.read_text(encoding="utf-8")
    assert '"id": "a"' in saved
    assert '"id": "b"' in saved


def test_run_eval_ignores_legacy_resume_rows_without_mrr(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "golden.jsonl"
    resume = tmp_path / "legacy-resume.json"
    dataset.write_text(
        '{"id":"a","query":"q1","task_type":"concept","expected_papers":["1111.11111"]}\n'
        '{"id":"b","query":"q2","task_type":"concept","expected_papers":["2222.22222"]}\n',
        encoding="utf-8",
    )
    resume.write_text(
        """
{
  "results": [
    {
      "id": "a",
      "query": "q1",
      "task_type": "concept",
      "candidate_count": 1,
      "no_candidates": false,
      "recall_at_k": 1.0,
      "precision_at_k": 1.0,
      "top_papers": [{"title": "Legacy", "arxiv_id": "1111.11111", "doi": null, "score": 1.0}]
    }
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    calls = []

    def fake_discover_papers(query: str, max_results: int):
        calls.append(query)
        arxiv_id = "1111.11111" if query == "q1" else "2222.22222"
        return [PaperCandidate(title="Fresh", arxiv_id=arxiv_id)]

    monkeypatch.setattr("eval.research_eval.discover_papers", fake_discover_papers)

    report = run_eval(dataset, top_k=5, resume_path=resume)

    assert calls == ["q1", "q2"]
    assert report["mean_recall_at_k"] == 1.0
    assert report["mean_mrr_at_k"] == 1.0


def test_run_eval_retries_resumed_no_candidate_rows(tmp_path: Path, monkeypatch):
    dataset = tmp_path / "golden.jsonl"
    resume = tmp_path / "resume.json"
    dataset.write_text(
        '{"id":"a","query":"q1","task_type":"concept","expected_papers":["1111.11111"]}\n'
        '{"id":"b","query":"q2","task_type":"concept","expected_papers":["2222.22222"]}\n',
        encoding="utf-8",
    )
    resume.write_text(
        """
{
  "report_schema_version": __SCHEMA_VERSION__,
  "results": [
    {
      "id": "a",
      "query": "q1",
      "task_type": "concept",
      "candidate_count": 0,
      "no_candidates": true,
      "recall_at_k": 0.0,
      "precision_at_k": 0.0,
      "mrr_at_k": 0.0,
      "top_papers": []
    },
    {
      "id": "b",
      "query": "q2",
      "task_type": "concept",
      "candidate_count": 1,
      "no_candidates": false,
      "recall_at_k": 1.0,
      "precision_at_k": 1.0,
      "mrr_at_k": 1.0,
      "top_papers": [{"title": "Cached", "arxiv_id": "2222.22222", "doi": null, "score": 1.0}]
    }
  ]
}
""".strip().replace("__SCHEMA_VERSION__", str(EVAL_REPORT_SCHEMA_VERSION))
        + "\n",
        encoding="utf-8",
    )
    calls = []

    def fake_discover_papers(query: str, max_results: int):
        calls.append(query)
        return [PaperCandidate(title="Fresh", arxiv_id="1111.11111")]

    monkeypatch.setattr("eval.research_eval.discover_papers", fake_discover_papers)

    report = run_eval(dataset, top_k=5, resume_path=resume)

    assert calls == ["q1"]
    assert report["paper_scored_query_count"] == 2
    assert report["no_candidate_query_count"] == 0
    assert report["mean_recall_at_k"] == 1.0


def test_gate_verdict_dry_run_ignores_quality_thresholds():
    report = {
        "dry_run": True,
        "paper_labeled_query_count": 26,
        "no_candidate_query_count": 0,
        "mean_recall_at_k": 0.0,
        "mean_precision_at_k": 0.0,
    }

    assert gate_verdict(report, min_recall=0.55, min_precision=0.35) == "PASS"


def test_missing_live_provider_config_lists_absent_required_env(monkeypatch):
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    monkeypatch.delenv("OPENALEX_MAILTO", raising=False)
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)

    assert missing_live_provider_config() == ["SEMANTIC_SCHOLAR_API_KEY", "OPENALEX_API_KEY"]

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "key")
    monkeypatch.setenv("OPENALEX_API_KEY", "openalex-key")

    assert missing_live_provider_config() == []


def test_answer_quality_dataset_loads_observed_ui_failures():
    rows = load_golden_dataset(Path("eval/answer_quality_golden_set.jsonl"))

    assert [row.id for row in rows] == [
        "transformer-original-vi",
        "lora-qlora-comparison",
        "ros2-robotics-concept",
        "no-evidence-personal",
    ]
    assert rows[0].expected_papers == ["1706.03762"]
    assert rows[1].expected_papers == ["2106.09685", "2305.14314"]
