from agent.research.indexing.contextual_chunks import create_contextual_chunks
from agent.research.indexing.paper_store import StoredPaper
from agent.research.indexing.section_parser import ParsedPaper, Section


def test_contextual_chunks_include_paper_section_and_source_context():
    paper = StoredPaper(
        paper_id="arxiv:2306.17157",
        title="ROS 2 in robotics",
        authors=["Ada"],
        year=2023,
        abstract="ROS 2 is middleware.",
        source_url="https://arxiv.org/abs/2306.17157",
    )
    parsed = ParsedPaper(
        title="ROS 2 in robotics",
        abstract="ROS 2 is middleware.",
        sections=[Section(title="Introduction", text="Robots use ROS 2 for communication.")],
    )

    chunks = create_contextual_chunks(paper, parsed, chunk_size=40, overlap=5)

    assert chunks
    assert chunks[0].paper_id == "arxiv:2306.17157"
    assert chunks[0].section_title == "Introduction"
    assert chunks[0].source_url == "https://arxiv.org/abs/2306.17157"
    assert "Paper: ROS 2 in robotics" in chunks[0].text
    assert "Section: Introduction" in chunks[0].text
