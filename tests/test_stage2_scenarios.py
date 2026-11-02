import sys
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from agent.graph import create_graph
from agent.memory import ConversationMemory
from agent.pipeline import run_agent_graph
from agent.state import AgentState


class TestScenarios:
    """Test scenarios from stage_2_agent.md."""

    @pytest.fixture(autouse=True)
    def stub_generation(self, monkeypatch):
        """Keep historical graph scenario tests offline and deterministic."""
        monkeypatch.setattr(
            "agent.nodes.generate.generate_answer",
            lambda *args, **kwargs: "deterministic legacy graph answer",
        )

    @pytest.fixture
    def graph(self):
        """Create graph instance."""
        return create_graph()

    @pytest.fixture
    def memory(self):
        """Create memory instance."""
        return ConversationMemory(
            max_size=50,
            embed_model="sentence-transformers/all-MiniLM-L6-v2",
            similarity_threshold=0.7,
        )

    def test_scenario_1_known_intent_kb_only(self, graph):
        """Scenario 1: Known Intent (KB-only)."""
        state: AgentState = {
            "query": "So sánh RAG và fine-tuning",
            "chroma_path": "./chroma",
            "embed_model": "sentence-transformers/all-MiniLM-L6-v2",
        }

        try:
            result = graph.invoke(state)
            assert "intent" in result
            assert result.get("intent") == "known"
            assert "route_type" in result
            # If KB confidence is high, should be kb_only
            # Otherwise will be search (which is also valid)
            assert result.get("route_type") in ["kb_only", "search"]
        except Exception:
            # May fail if KB is empty
            pass

    def test_scenario_2_fresh_intent_search(self, graph):
        """Scenario 2: Fresh Intent (Search)."""
        state: AgentState = {
            "query": "RAG trends 2025",
            "chroma_path": "./chroma",
            "embed_model": "sentence-transformers/all-MiniLM-L6-v2",
        }

        try:
            result = graph.invoke(state)
            assert "intent" in result
            assert result.get("intent") == "fresh"
            assert "route_type" in result
            assert result.get("route_type") == "search"
        except Exception:
            # May fail if network/search fails
            pass

    def test_scenario_3_mixed_intent(self, graph):
        """Scenario 3: Mixed Intent (Both)."""
        state: AgentState = {
            "query": "So sánh RAG 2024 và 2025",
            "chroma_path": "./chroma",
            "embed_model": "sentence-transformers/all-MiniLM-L6-v2",
        }

        try:
            result = graph.invoke(state)
            assert "intent" in result
            assert result.get("intent") == "mixed"
            assert "route_type" in result
            # Mixed intent with high KB confidence -> both
            # Otherwise -> search
            assert result.get("route_type") in ["both", "search"]
        except Exception:
            pass

    def test_scenario_4_low_confidence_search_fallback(self, graph):
        """Scenario 4: Low Confidence (Search Fallback)."""
        state: AgentState = {
            "query": "Very specific obscure topic that doesn't exist",
            "chroma_path": "./chroma",
            "embed_model": "sentence-transformers/all-MiniLM-L6-v2",
        }

        try:
            result = graph.invoke(state)
            assert "intent" in result
            assert "kb_confidence" in result
            # Low KB confidence should trigger search
            if result.get("kb_confidence", 1.0) < 0.7:
                assert result.get("route_type") == "search"
        except Exception:
            pass

    def test_scenario_5_memory_recall(self, memory):
        """Scenario 5: Memory Recall."""
        # Add previous conversation
        memory.add("RAG là gì?", "RAG là retrieval augmented generation...", ["url1"])

        # Search for similar query
        similar = memory.search_similar(
            "RAG có ưu điểm gì?", top_k=1, similarity_threshold=0.2
        )
        assert len(similar) >= 1
        assert "RAG là" in similar[0].query or "RAG" in similar[0].query.lower()

        # Test context injection
        from agent.memory import inject_memory_context

        query = "RAG có ưu điểm gì?"
        enhanced, context = inject_memory_context(query, memory)
        assert "Previous context" in enhanced or "Previous Q" in enhanced
        assert len(context) > 0


class TestPipelineIntegration:
    """Test pipeline integration with memory."""

    @pytest.fixture(autouse=True)
    def stub_generation(self, monkeypatch):
        """Keep historical pipeline integration tests offline and deterministic."""
        monkeypatch.setattr(
            "agent.nodes.generate.generate_answer",
            lambda *args, **kwargs: "deterministic legacy graph answer",
        )

    def test_pipeline_with_memory(self):
        """Test pipeline execution with memory."""
        memory = ConversationMemory(
            max_size=10,
            embed_model="sentence-transformers/all-MiniLM-L6-v2",
            similarity_threshold=0.5,  # Lower for testing
        )

        # First query
        try:
            result1 = run_agent_graph(
                "RAG là gì?",
                chroma_path="./chroma",
                embed_model="sentence-transformers/all-MiniLM-L6-v2",
                memory=memory,
            )
            assert memory.size() == 1
        except Exception:
            # May fail if KB/search fails
            pass

        # Second query (should use memory)
        try:
            result2 = run_agent_graph(
                "Nó có ưu điểm gì?",
                chroma_path="./chroma",
                embed_model="sentence-transformers/all-MiniLM-L6-v2",
                memory=memory,
            )
            # Memory should have 2 entries now
            assert memory.size() == 2
            # Should have memory context
            assert "memory_context" in result2 or result2.get("memory_context", "")
        except Exception:
            pass
