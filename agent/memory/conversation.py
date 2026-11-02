from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer


@dataclass
class ConversationEntry:
    """Single conversation entry in memory."""

    query: str
    answer: str
    citations: List[str]
    timestamp: int
    query_embedding: Optional[List[float]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "answer": self.answer,
            "citations": self.citations,
            "timestamp": self.timestamp,
            "query_embedding": self.query_embedding,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ConversationEntry:
        """Create from dictionary."""
        return cls(
            query=data["query"],
            answer=data["answer"],
            citations=data.get("citations", []),
            timestamp=data.get("timestamp", int(time.time())),
            query_embedding=data.get("query_embedding"),
        )


class ConversationMemory:
    """Conversation memory with LRU eviction and semantic search."""

    def __init__(
        self,
        max_size: int = 50,
        embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        similarity_threshold: float = 0.7,
    ):
        """
        Initialize conversation memory.

        Args:
            max_size: Maximum number of entries (LRU eviction)
            embed_model: Embedding model for semantic search
            similarity_threshold: Minimum similarity for context injection
        """
        self.memory: OrderedDict[str, ConversationEntry] = OrderedDict[str, ConversationEntry]()
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold
        self._embed_model: Optional[SentenceTransformer] = None
        self._embed_model_name = embed_model

    @property
    def embed_model(self) -> SentenceTransformer:
        """Lazy load embedding model."""
        if self._embed_model is None:
            self._embed_model = SentenceTransformer(self._embed_model_name)
        return self._embed_model

    def add(self, query: str, answer: str, citations: List[str]) -> None:
        """
        Add conversation entry with LRU eviction.

        Args:
            query: User query
            answer: Generated answer
            citations: List of citation URLs
        """
        # Generate query embedding
        query_emb = self.embed_model.encode([query], convert_to_numpy=True)[0].tolist()

        entry = ConversationEntry(
            query=query,
            answer=answer,
            citations=citations,
            timestamp=int(time.time()),
            query_embedding=query_emb,
        )

        # LRU eviction: remove oldest if at capacity
        if len(self.memory) >= self.max_size:
            self.memory.popitem(last=False)  # Remove oldest (FIFO)

        key = query
        self.memory[key] = entry
        self.memory.move_to_end(key)

    def search_similar(
        self,
        query: str,
        top_k: int = 3,
        similarity_threshold: Optional[float] = None,
    ) -> List[ConversationEntry]:
        """
        Semantic search in conversation history.

        Args:
            query: Query to search for
            top_k: Number of similar entries to return

        Returns:
            List of similar conversation entries, sorted by similarity
        """
        if not self.memory:
            return []

        query_emb = self.embed_model.encode([query], convert_to_numpy=True)[0]
        query_norm = float(np.linalg.norm(query_emb))
        if query_norm == 0.0:
            return []

        threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else self.similarity_threshold
        )
        query_tokens = {token for token in query.lower().split() if token}

        similarities: List[tuple[float, ConversationEntry]] = []
        for entry in self.memory.values():
            if entry.query_embedding:
                entry_emb = np.array(entry.query_embedding)
                entry_norm = float(np.linalg.norm(entry_emb))
                if entry_norm == 0.0:
                    continue
                sim = float(np.dot(query_emb, entry_emb) / (query_norm * entry_norm))
                if np.isnan(sim):
                    continue

                lexical_overlap = 0.0
                entry_tokens = {token for token in entry.query.lower().split() if token}
                if query_tokens and entry_tokens:
                    lexical_overlap = len(query_tokens & entry_tokens) / float(len(query_tokens))

                lexical_boost = 0.0
                if lexical_overlap > 0.0:
                    lexical_boost = min(0.99, 0.5 + 0.5 * lexical_overlap)

                effective_sim = max(sim, lexical_boost)
                if effective_sim >= threshold:
                    similarities.append((effective_sim, entry))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in similarities[:top_k]]

    def get_recent(self, n: int = 5) -> List[ConversationEntry]:
        """
        Get most recent conversation entries.

        Args:
            n: Number of recent entries to return

        Returns:
            List of recent entries (most recent first)
        """
        entries = list(self.memory.values())
        return entries[-n:][::-1]  # Reverse to get most recent first

    def clear(self) -> None:
        """Clear all conversation history."""
        self.memory.clear()

    def size(self) -> int:
        """Get current memory size."""
        return len(self.memory)

    def to_dict(self) -> dict:
        """Convert memory to dictionary for serialization."""
        return {
            "max_size": self.max_size,
            "similarity_threshold": self.similarity_threshold,
            "entries": [entry.to_dict() for entry in self.memory.values()],
        }

    @classmethod
    def from_dict(cls, data: dict, embed_model: str = "sentence-transformers/all-MiniLM-L6-v2") -> ConversationMemory:
        """Create memory from dictionary."""
        memory = cls(
            max_size=data.get("max_size", 50),
            embed_model=embed_model,
            similarity_threshold=data.get("similarity_threshold", 0.7),
        )
        for entry_data in data.get("entries", []):
            entry = ConversationEntry.from_dict(entry_data)
            memory.memory[entry.query] = entry
        return memory

