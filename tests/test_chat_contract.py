import pytest
from pydantic import ValidationError

from api.models import ChatRequest, SearchSource


@pytest.mark.parametrize("search_source", ["mixed", "arxiv", "tavily", "wikipedia"])
def test_chat_request_rejects_unsupported_search_source(search_source):
    with pytest.raises(ValidationError):
        ChatRequest(query="What is RAG?", search_source=search_source)


def test_chat_request_accepts_research_search_source():
    request = ChatRequest(query="ROS2 trong robotics là gì", search_source="research")

    assert request.search_source == SearchSource.RESEARCH
    assert request.search_source.value == "research"
