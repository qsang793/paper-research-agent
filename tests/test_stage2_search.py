import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pytest

from agent.nodes.search import dedup_queries, expand_query


class TestQueryExpansion:
    """Test query expansion functionality."""

    def test_expand_query_llm_parsing_and_injection(self):
        """LLM output is parsed and original query is injected if missing."""
        question = "RAG techniques"

        def fake_llm(_: str) -> str:
            return "- retrieval augmented generation basics\n- hybrid retrieval methods"

        queries = expand_query(question, max_variations=5, llm=fake_llm, embedder=None, dedup_threshold=0.95)

        assert question in queries  # original injected
        assert "retrieval augmented generation basics" in queries
        assert "hybrid retrieval methods" in queries
        assert len(queries) <= 5

    def test_expand_query_deduplication_with_cosine(self):
        """Queries with high cosine similarity are deduped."""
        question = "RAG techniques"

        def fake_llm(_: str) -> str:
            return "RAG techniques\nRAG technique\nRAG methods"

        def fake_embedder(qs):
            # Map strings to simple 2D vectors to control cosine
            mapping = {
                "RAG techniques": np.array([1.0, 0.0]),
                "RAG technique": np.array([0.99, 0.01]),
                "RAG methods": np.array([0.0, 1.0]),
            }
            return [mapping.get(q, np.array([0.5, 0.5])) for q in qs]

        queries = expand_query(
            question,
            max_variations=5,
            llm=fake_llm,
            embedder=fake_embedder,
            dedup_threshold=0.95,
        )

        # "RAG techniques" and "RAG technique" are similar -> keep one
        assert any("RAG techniques" in q for q in queries)
        assert all(q != "RAG technique" for q in queries)
        # "RAG methods" different vector -> should remain
        assert "RAG methods" in queries

    def test_dedup_queries_threshold(self):
        """dedup_queries respects similarity threshold."""
        queries = ["a", "a variant", "b"]

        def embedder(qs):
            # Make first two highly similar, third orthogonal
            vecs = {
                "a": np.array([1.0, 0.0]),
                "a variant": np.array([0.98, 0.02]),
                "b": np.array([0.0, 1.0]),
            }
            return [vecs[q] for q in qs]

        deduped = dedup_queries(queries, threshold=0.9, embedder=embedder)
        assert "a" in deduped
        assert "a variant" not in deduped
        assert "b" in deduped

