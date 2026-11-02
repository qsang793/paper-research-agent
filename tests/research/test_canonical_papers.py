from agent.research.canonical_papers import resolve_canonical_papers


def test_resolves_transformer_paper_from_vietnamese_lookup():
    matches = resolve_canonical_papers("Transformer paper có gì")

    assert matches[0].arxiv_id == "1706.03762"
    assert matches[0].title == "Attention Is All You Need"


def test_resolves_lora_and_qlora_for_comparison():
    matches = resolve_canonical_papers("compare LoRA and QLoRA papers")

    assert [match.arxiv_id for match in matches] == ["2106.09685", "2305.14314"]


def test_does_not_resolve_generic_transformer_survey():
    matches = resolve_canonical_papers("recent transformer surveys for time series")

    assert matches == []
