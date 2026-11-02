from agent.research.evidence.retriever import retrieve_evidence
from agent.research.indexing.contextual_chunks import ContextualChunk


def test_retrieve_evidence_filters_selected_papers_and_scores_chunks():
    chunks = [
        ContextualChunk(
            chunk_id="a",
            paper_id="p1",
            title="ROS 2 paper",
            section_title="Intro",
            text="Paper: ROS 2 paper\nSection: Intro\nROS 2 is robotics middleware.",
            source_url="https://example.test/p1",
        ),
        ContextualChunk(
            chunk_id="b",
            paper_id="p2",
            title="Database paper",
            section_title="Intro",
            text="Databases store rows.",
            source_url="https://example.test/p2",
        ),
    ]

    evidence = retrieve_evidence("ROS2 robotics middleware", chunks, paper_ids=["p1"], top_k=1)

    assert len(evidence) == 1
    assert evidence[0].paper_id == "p1"
    assert evidence[0].score > 0
