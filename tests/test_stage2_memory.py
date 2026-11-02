import numpy as np

from agent.memory import ConversationMemory
from agent.memory import inject_memory_context


class TestConversationMemory:
    """Test conversation memory functionality."""

    def test_memory_lru_eviction(self):
        """Test LRU eviction when memory is full."""
        memory = ConversationMemory(max_size=3, embed_model="sentence-transformers/all-MiniLM-L6-v2")
        for i in range(5):
            memory.add(f"query{i}", f"answer{i}", [f"url{i}"])

        assert memory.size() == 3
        # Oldest entries should be evicted
        assert "query0" not in memory.memory
        assert "query1" not in memory.memory
        # Newest entries should remain
        assert "query2" in memory.memory
        assert "query3" in memory.memory
        assert "query4" in memory.memory

    def test_memory_semantic_search(self):
        """Test semantic search in conversation history."""
        memory = ConversationMemory(
            max_size=10,
            embed_model="sentence-transformers/all-MiniLM-L6-v2",
            similarity_threshold=0.5,  # Lower threshold for testing
        )

        class DummyEmbedModel:
            def encode(self, texts, convert_to_numpy=True):
                vecs = []
                for text in texts:
                    lower = text.lower()
                    if "rag" in lower or "retrieval augmented generation" in lower:
                        vecs.append(np.array([1.0, 0.0, 0.0]))
                    else:
                        vecs.append(np.array([0.0, 1.0, 0.0]))
                return np.stack(vecs)

        memory._embed_model = DummyEmbedModel()

        memory.add("RAG techniques", "RAG is retrieval augmented generation...", ["url1"])
        memory.add("Python programming", "Python is a programming language...", [])

        similar = memory.search_similar(
            "retrieval augmented generation", top_k=1, similarity_threshold=0.2
        )
        assert len(similar) >= 1
        assert "rag" in similar[0].query.lower()

    def test_memory_add_and_retrieve(self):
        """Test adding and retrieving entries."""
        memory = ConversationMemory(max_size=10, embed_model="sentence-transformers/all-MiniLM-L6-v2")
        memory.add("Test query", "Test answer", ["url1", "url2"])

        assert memory.size() == 1
        entry = memory.memory["Test query"]
        assert entry.query == "Test query"
        assert entry.answer == "Test answer"
        assert entry.citations == ["url1", "url2"]

    def test_memory_get_recent(self):
        """Test getting recent entries."""
        memory = ConversationMemory(max_size=10, embed_model="sentence-transformers/all-MiniLM-L6-v2")
        for i in range(5):
            memory.add(f"query{i}", f"answer{i}", [])

        recent = memory.get_recent(n=3)
        assert len(recent) == 3
        # Most recent first
        assert recent[0].query == "query4"
        assert recent[1].query == "query3"
        assert recent[2].query == "query2"

    def test_memory_clear(self):
        """Test clearing memory."""
        memory = ConversationMemory(max_size=10, embed_model="sentence-transformers/all-MiniLM-L6-v2")
        memory.add("query1", "answer1", [])
        memory.add("query2", "answer2", [])

        assert memory.size() == 2
        memory.clear()
        assert memory.size() == 0

    def test_memory_serialization(self):
        """Test memory serialization to/from dict."""
        memory = ConversationMemory(max_size=10, embed_model="sentence-transformers/all-MiniLM-L6-v2")
        memory.add("query1", "answer1", ["url1"])

        data = memory.to_dict()
        assert "max_size" in data
        assert "entries" in data
        assert len(data["entries"]) == 1

        # Reconstruct from dict
        memory2 = ConversationMemory.from_dict(data, embed_model="sentence-transformers/all-MiniLM-L6-v2")
        assert memory2.size() == 1
        assert "query1" in memory2.memory


class TestMemoryContextInjection:
    """Test memory context injection."""

    def test_inject_memory_context_no_memory(self):
        """Test context injection with no memory."""
        query = "Test query"
        enhanced, context = inject_memory_context(query, None)
        assert enhanced == query
        assert context == ""

    def test_inject_memory_context_no_similar(self):
        """Test context injection with no similar entries."""
        memory = ConversationMemory(
            max_size=10,
            embed_model="sentence-transformers/all-MiniLM-L6-v2",
            similarity_threshold=0.95,  # Very high threshold
        )
        memory.add("Unrelated query", "Unrelated answer", [])

        query = "Completely different topic"
        enhanced, context = inject_memory_context(query, memory)
        
        # New behavior: Recent context is ALWAYS injected (last 1 item)
        # to support implicit references or "what did I just say" queries.
        assert "Unrelated query" in context
        assert "Previous context" in enhanced

    def test_inject_memory_context_with_similar(self):
        """Test context injection with similar entries."""
        memory = ConversationMemory(
            max_size=10,
            embed_model="sentence-transformers/all-MiniLM-L6-v2",
            similarity_threshold=0.5,  # Lower threshold for testing
        )
        memory.add("RAG là gì?", "RAG là retrieval augmented generation...", ["url1"])

        query = "RAG có ưu điểm gì?"
        enhanced, context = inject_memory_context(query, memory)

        assert query in enhanced
        assert "Previous context" in enhanced or "Previous Q" in enhanced
        assert "RAG là" in enhanced
        assert len(context) > 0

    def test_inject_memory_context_recent(self):
        """Test that recent context is injected even if semantic search fails."""
        memory = ConversationMemory(
            max_size=10,
            embed_model="sentence-transformers/all-MiniLM-L6-v2",
            similarity_threshold=0.99,  # High threshold to force semantic search failure
        )
        # Add a recent entry
        memory.add("What is RAG?", "Retrieval Augmented Generation...", [])
        
        # Query that is semantically different but requires recent context
        query = "Repeat that please"
        enhanced, context = inject_memory_context(query, memory)
        
        assert "What is RAG?" in context
        assert "Previous context" in enhanced
