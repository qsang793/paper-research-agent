from agent.research.query_plan import plan_research_query
from agent.research.discovery.arxiv_provider import build_arxiv_queries


def test_plan_research_query_strips_vietnamese_filler_and_expands_ros2():
    plan = plan_research_query("ROS2 trong robotics là gì")

    assert plan.entities == ["ROS2", "robotics"]
    assert plan.aliases["ROS2"] == ["ROS 2", "Robot Operating System 2"]
    assert "cs.RO" in plan.categories
    assert plan.normalized_query == "ROS2 robotics"


def test_plan_research_query_keeps_lookup_ids_and_no_llm_by_default():
    plan = plan_research_query("paper 1706.03762 summary")

    assert plan.arxiv_ids == ["1706.03762"]
    assert plan.uses_llm is False
    assert "1706.03762" in plan.entities


def test_plan_research_query_normalizes_versioned_arxiv_ids_for_lookup():
    plan = plan_research_query("paper 1706.03762v7 summary")

    assert plan.arxiv_ids == ["1706.03762"]
    assert "1706.03762" in plan.entities
    assert build_arxiv_queries(plan) == ["id:1706.03762"]


def test_plan_research_query_drops_request_descriptor_words_from_entities():
    # "original" describes the request, not the topic; AND-ing it excludes the
    # seminal paper (its text never contains the word "original").
    assert plan_research_query("original BERT paper").entities == ["BERT"]
    assert plan_research_query("Vision Transformer original paper").entities == [
        "Vision",
        "Transformer",
    ]
    assert plan_research_query("Mamba architecture paper explained").entities == [
        "Mamba",
        "architecture",
    ]


def test_plan_research_query_drops_conjunctions_and_comparison_words():
    # "compare" and "and" must not become required AND terms.
    assert plan_research_query("compare LoRA and QLoRA papers").entities == [
        "LORA",
        "QLORA",
    ]
    assert plan_research_query("Tree of Thoughts paper").entities == [
        "Tree",
        "Thoughts",
    ]


def test_plan_research_query_resolves_canonical_transformer_lookup():
    plan = plan_research_query("Transformer paper có gì")

    assert plan.canonical_arxiv_ids == ["1706.03762"]
    assert plan.canonical_titles == ["Attention Is All You Need"]


def test_plan_research_query_resolves_lora_qlora_comparison_targets():
    plan = plan_research_query("compare LoRA and QLoRA papers")

    assert plan.canonical_arxiv_ids == ["2106.09685", "2305.14314"]
