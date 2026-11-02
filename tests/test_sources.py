from agent.sources import source_from_snippet, sources_from_snippets


def test_source_from_snippet_normalizes_metadata_shape():
    source = source_from_snippet(
        {
            "text": "Retrieval augmented generation combines search and generation.",
            "metadata": {
                "title": "RAG Paper",
                "source_url": "https://arxiv.org/abs/2005.11401",
                "published_at": "2020-05-22",
            },
            "source": "arxiv",
            "rerank_score": 4.2,
        },
        index=0,
    )

    assert source["id"] == "source_0"
    assert source["title"] == "RAG Paper"
    assert source["url"] == "https://arxiv.org/abs/2005.11401"
    assert source["source_type"] == "arxiv"
    assert source["relevance_score"] == 1.0
    assert source["alive_status"] == "unchecked"
    assert source["snippet"].startswith("Retrieval augmented")


def test_sources_from_snippets_skips_empty_url_by_default():
    sources = sources_from_snippets([
        {"text": "No URL", "metadata": {"title": "Missing"}},
        {"text": "Has URL", "metadata": {"title": "Found", "source_url": "https://example.com"}},
    ])

    assert len(sources) == 1
    assert sources[0]["title"] == "Found"
