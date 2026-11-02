import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Pytest configuration
import pytest


@pytest.fixture(scope="session")
def embed_model():
    """Shared embedding model for tests."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


@pytest.fixture(scope="session")
def chroma_path():
    """ChromaDB path for tests."""
    return "./chroma"


def pytest_collection_modifyitems(config, items):
    """Keep optional LlamaIndex migration tests out of the default suite."""
    if os.getenv("RUN_LLAMA_INDEX_OPTIONAL_TESTS") == "1":
        return

    optional_llamaindex_files = {
        "test_llamaindex_vector_store_phase2.py",
        "test_llamaindex_retriever_phase3.py",
        "test_llamaindex_llm_phase4.py",
        "test_llamaindex_reranker_phase5.py",
        "test_llamaindex_full_integration_phase6.py",
    }
    skip_optional = pytest.mark.skip(
        reason="optional LlamaIndex migration test; set RUN_LLAMA_INDEX_OPTIONAL_TESTS=1 to run"
    )

    for item in items:
        if item.path.name in optional_llamaindex_files:
            item.add_marker(skip_optional)
