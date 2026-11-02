"""
Regression tests for the embedding helpers used by the agent graph.

Root cause being fixed: `agent/nodes/route.py` and `agent/nodes/retrieve.py`
import `embed_query` and `embed_with_prefix` from `agent.utils`, but those
functions were never defined — breaking import of `agent.nodes`, `agent.graph`
and `api.main` (the whole RAG path / FastAPI app).

These tests pin the documented contract:
- `embed_query(model_name, query)` -> list[float], applies the E5 "query: "
  prefix for E5 models (mirrors E5EmbeddingFunction in agent/query_router.py).
- `embed_with_prefix(model_name, texts, prefix)` -> list[list[float]], applies
  the given prefix per text for E5 models.
- Non-E5 models (e.g. MiniLM) are encoded raw (matches ingest/index.py).

The embedding model is monkeypatched so the tests are fast and deterministic
(no model download).
"""
import numpy as np

import agent.utils.embeddings as emb_mod
from agent.utils import embed_query, embed_with_prefix


class _FakeModel:
    """Records the exact strings passed to encode()."""

    def __init__(self):
        self.seen = []

    def encode(self, texts, normalize_embeddings=False, **kwargs):
        self.seen.extend(list(texts))
        # Deterministic 4-dim vectors, one per input text.
        return np.array([[float(len(t))] * 4 for t in texts], dtype=np.float32)


def test_embed_query_applies_e5_query_prefix(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(emb_mod, "get_embed_model", lambda name: fake)

    vec = embed_query("intfloat/e5-base-v2", "what is rag")

    assert fake.seen == ["query: what is rag"]
    assert isinstance(vec, list)
    assert len(vec) == 4
    assert all(isinstance(x, float) for x in vec)


def test_embed_with_prefix_applies_passage_prefix(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(emb_mod, "get_embed_model", lambda name: fake)

    out = embed_with_prefix("intfloat/e5-base-v2", ["doc a", "doc b"], prefix="passage:")

    assert fake.seen == ["passage: doc a", "passage: doc b"]
    assert isinstance(out, list)
    assert len(out) == 2
    assert all(isinstance(row, list) and len(row) == 4 for row in out)


def test_non_e5_model_is_encoded_without_prefix(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(emb_mod, "get_embed_model", lambda name: fake)

    embed_query("sentence-transformers/all-MiniLM-L6-v2", "hello")

    assert fake.seen == ["hello"]


def test_agent_graph_and_api_import():
    """Regression: these modules were unimportable before the fix."""
    import agent.graph
    import api.main

    assert hasattr(agent.graph, "create_graph")
    assert hasattr(api.main, "app")
