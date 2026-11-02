import json

from eval.model_synthesis_eval import FIXED_ALLOWED_IDS, FIXED_EXPECTED_TERMS, grade_synthesis_output, main


def test_grade_synthesis_output_passes_claim_cited_answer():
    answer = "The Transformer uses self-attention [E1]. It removes recurrence [E1]."

    grade = grade_synthesis_output(
        answer,
        expected_terms=FIXED_EXPECTED_TERMS,
        allowed_ids=FIXED_ALLOWED_IDS,
    )

    assert grade["passes"] is True
    assert grade["term_recall"] == 1.0


def test_grade_synthesis_output_fails_missing_terms_or_citations():
    answer = "The Transformer is important."

    grade = grade_synthesis_output(
        answer,
        expected_terms=FIXED_EXPECTED_TERMS[:1],
        allowed_ids=FIXED_ALLOWED_IDS,
    )

    assert grade["passes"] is False


def test_cli_with_answer_returns_grade(capsys):
    answer = "The Transformer uses self-attention [E1]. It removes recurrence [E1]."

    exit_code = main(["--answer", answer])

    out = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert out["answer"] == answer
    assert out["grade"]["passes"] is True
