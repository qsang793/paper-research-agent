from agent.research.discovery.models import PaperCandidate
from agent.research.indexing.section_parser import parse_paper_text


def test_parse_paper_text_extracts_abstract_and_sections():
    text = """
Title: ROS 2 in robotics

Abstract
ROS 2 is middleware for robotics research.

1 Introduction
Robots need distributed communication.

2 Methods
We evaluate ROS 2 nodes.
"""

    parsed = parse_paper_text(text)

    assert parsed.title == "ROS 2 in robotics"
    assert parsed.abstract == "ROS 2 is middleware for robotics research."
    assert [section.title for section in parsed.sections] == ["Introduction", "Methods"]


def test_parse_paper_text_falls_back_to_abstract_only_candidate():
    candidate = PaperCandidate(
        title="Fallback paper",
        abstract="Only abstract is available.",
        source_url="https://example.test",
    )

    parsed = parse_paper_text("", candidate=candidate)

    assert parsed.title == "Fallback paper"
    assert parsed.sections[0].title == "Abstract"
    assert parsed.sections[0].text == "Only abstract is available."
