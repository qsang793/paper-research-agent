from agent.research.evidence.extractor import extract_evidence_spans
from agent.research.indexing.contextual_chunks import ContextualChunk


def test_extract_evidence_spans_preserves_metadata():
    chunks = [
        ContextualChunk(
            chunk_id="c1",
            paper_id="p1",
            title="ROS 2 paper",
            section_title="Abstract",
            text="ROS 2 is middleware. It supports distributed robotics.",
            source_url="https://example.test/p1",
            score=0.8,
        )
    ]

    spans = extract_evidence_spans(chunks, query="ROS2 middleware")

    assert spans[0].paper_id == "p1"
    assert spans[0].title == "ROS 2 paper"
    assert spans[0].section_title == "Abstract"
    assert "middleware" in spans[0].quote
    assert spans[0].url == "https://example.test/p1"


def test_extract_evidence_spans_matches_compact_entities_without_fallback_noise():
    chunks = [
        ContextualChunk(
            chunk_id="c1",
            paper_id="p1",
            title="ROS 2 paper",
            section_title="Abstract",
            text="ROS 2 is robotics middleware. Databases store rows.",
            source_url="https://example.test/p1",
            score=0.1,
        ),
        ContextualChunk(
            chunk_id="c2",
            paper_id="p2",
            title="Database paper",
            section_title="Abstract",
            text="Databases store rows. Transactions preserve consistency.",
            source_url="https://example.test/p2",
            score=0.9,
        ),
    ]

    spans = extract_evidence_spans(chunks, query="ROS2 trong robotics la gi")

    assert [span.paper_id for span in spans] == ["p1"]
    assert spans[0].quote == "ROS 2 is robotics middleware."
    assert spans[0].score > 0.5
