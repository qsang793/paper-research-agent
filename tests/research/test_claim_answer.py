from agent.research.evidence.models import EvidenceSpan
from agent.research.synthesis.claim_answer import (
    assess_evidence_answerability,
    build_claim_grounded_prompt,
    generate_claim_grounded_answer,
    validate_claim_citations,
)


def test_build_claim_grounded_prompt_requires_cited_evidence():
    evidence = [
        EvidenceSpan(
            claim="ROS 2 is robotics middleware.",
            paper_id="p1",
            title="ROS 2 paper",
            url="https://example.test/p1",
            quote="ROS 2 is middleware for robotics.",
            score=0.9,
        )
    ]

    prompt = build_claim_grounded_prompt(
        "ROS2 trong robotics là gì",
        evidence,
        memory_context="User prefers concise answers.",
    )

    assert "ROS2 trong robotics là gì" in prompt
    assert "[E1]" in prompt
    assert "User prefers concise answers." in prompt
    assert "Conversation context (not evidence)" in prompt
    assert "Every major factual claim must cite evidence IDs" in prompt
    assert "Do not cite an evidence ID that is not listed" in prompt
    assert "Do not group all citations at the end" in prompt


def test_assess_evidence_answerability_distinguishes_no_paper_no_evidence_and_weak():
    assert assess_evidence_answerability([], paper_count=0)["reason"] == "NO_PAPER_FOUND"
    assert assess_evidence_answerability([], paper_count=2)["reason"] == "NO_EVIDENCE_FOUND"
    assert assess_evidence_answerability(
        [EvidenceSpan(paper_id="p1", title="T", url="u", quote="weak", score=0.1)],
        paper_count=1,
        min_score=0.5,
    )["reason"] == "WEAK_EVIDENCE"


def test_generate_claim_grounded_answer_sends_evidence_and_memory_separately(monkeypatch):
    calls = {}
    evidence = [
        EvidenceSpan(
            claim="ROS 2 is middleware for robotics.",
            paper_id="p1",
            title="ROS 2 paper",
            url="https://example.test/p1",
            quote="ROS 2 is middleware for robotics.",
            section_title="Abstract",
            score=0.9,
        )
    ]

    def fake_generate_answer(
        question,
        snippets,
        prompt_template=None,
        backend=None,
        memory_context="",
    ):
        calls["question"] = question
        calls["snippets"] = snippets
        calls["prompt_template"] = prompt_template
        calls["backend"] = backend
        calls["memory_context"] = memory_context
        return "ROS 2 is middleware for robotics [E1]."

    monkeypatch.setattr("agent.research.synthesis.claim_answer.generate_answer", fake_generate_answer)

    answer = generate_claim_grounded_answer(
        "ROS2 trong robotics là gì",
        evidence,
        backend="test",
        memory_context="User prefers concise answers.",
    )

    assert answer == "ROS 2 is middleware for robotics [E1]."
    assert calls["question"] == "ROS2 trong robotics là gì"
    assert calls["backend"] == "test"
    assert calls["memory_context"] == "User prefers concise answers."
    assert "Every major factual claim must cite evidence IDs" in calls["prompt_template"]
    assert "[E1]" in calls["snippets"][0]["text"]
    assert "Section: Abstract" in calls["snippets"][0]["text"]
    assert "Quote: ROS 2 is middleware for robotics." in calls["snippets"][0]["text"]


def test_validate_claim_citations_rejects_uncited_claims():
    answer = "The Transformer uses attention mechanisms effectively. It removed recurrence. [E1]"
    result = validate_claim_citations(answer, allowed_ids={"E1"})

    assert result["valid"] is False
    assert result["uncited_claim_count"] >= 1


def test_validate_claim_citations_accepts_cited_claims():
    answer = "The Transformer uses attention [E1]. It removed recurrence [E1]."
    result = validate_claim_citations(answer, allowed_ids={"E1"})

    assert result["valid"] is True
    assert result["invalid_ids"] == []
    assert result["uncited_claim_count"] == 0


def test_validate_claim_citations_flags_invalid_ids():
    answer = "The Transformer uses attention [E9]."
    result = validate_claim_citations(answer, allowed_ids={"E1"})

    assert result["valid"] is False
    assert result["invalid_ids"] == ["E9"]
