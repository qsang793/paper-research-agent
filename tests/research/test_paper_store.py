from agent.research.discovery.models import PaperCandidate
from agent.research.indexing.paper_store import PaperStore, StoredPaper


def test_paper_store_upserts_duplicate_provider_ids_to_one_paper():
    store = PaperStore()
    arxiv_candidate = PaperCandidate(
        title="ROS 2 in robotics",
        arxiv_id="2306.17157",
        doi="10.1/ros2",
        source_url="https://arxiv.org/abs/2306.17157",
    )
    s2_candidate = PaperCandidate(
        title="ROS 2 in robotics",
        semantic_scholar_id="S2",
        doi="10.1/ros2",
        source_url="https://semanticscholar.org/paper/S2",
    )

    first = store.upsert_candidate(arxiv_candidate)
    second = store.upsert_candidate(s2_candidate)

    assert first.paper_id == second.paper_id
    assert store.get_by_provider_id("semantic_scholar", "S2") == second
    assert len(store.all()) == 1


def test_stored_paper_contains_required_provenance_fields():
    paper = StoredPaper(
        paper_id="doi:10.1/abc",
        title="A paper",
        abstract="Abstract",
        source_url="https://example.test",
        source_provider="openalex",
    )

    assert paper.paper_id == "doi:10.1/abc"
    assert paper.retrieved_at is not None
