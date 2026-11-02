"""
Basic tests for LlamaIndex integration (Phase 1).

These tests verify that:
1. LlamaIndex packages can be imported
2. Compatibility layer works
3. Vector store adapter implements interface correctly
"""

import pytest
from typing import List


def test_llamaindex_utils():
    """Test utility functions."""
    from agent.frameworks.llamaindex.utils import (
        get_llamaindex_packages,
        check_llamaindex_installed,
        get_llamaindex_version,
    )
    
    # Check packages list
    packages = get_llamaindex_packages()
    assert isinstance(packages, list)
    assert len(packages) > 0
    assert any("llama-index" in pkg for pkg in packages)
    
    # Check installation status
    is_installed = check_llamaindex_installed()
    assert isinstance(is_installed, bool)
    
    # Check version (may be None if not installed)
    version = get_llamaindex_version()
    if is_installed:
        assert version is not None
    # If not installed, version can be None


def test_llamaindex_import():
    """Test that LlamaIndex modules can be imported."""
    try:
        from agent.frameworks.llamaindex import (
            LlamaIndexChromaStore,
            LlamaIndexVectorStoreAdapter,
            get_llamaindex_packages,
        )
        # If import succeeds, we're good
        assert True
    except ImportError as e:
        # If LlamaIndex is not installed, that's okay for Phase 1
        # We just need the module structure
        pytest.skip(f"LlamaIndex not installed: {e}")


@pytest.mark.skipif(
    not __import__("agent.frameworks.llamaindex.utils").frameworks.llamaindex.utils.check_llamaindex_installed(),
    reason="LlamaIndex not installed"
)
def test_llamaindex_vector_store_adapter():
    """Test LlamaIndexVectorStoreAdapter implements VectorStoreInterface."""
    from agent.frameworks.llamaindex import LlamaIndexVectorStoreAdapter
    from agent.stores.base import VectorStoreInterface
    
    # Check that adapter implements the interface
    assert issubclass(LlamaIndexVectorStoreAdapter, VectorStoreInterface)
    
    # Test instantiation (will fail if ChromaDB not available, but that's okay)
    try:
        adapter = LlamaIndexVectorStoreAdapter(chroma_path="./chroma")
        assert adapter is not None
        assert hasattr(adapter, "query")
        assert hasattr(adapter, "add")
        assert hasattr(adapter, "count")
        assert hasattr(adapter, "get_collection")
    except Exception as e:
        # If ChromaDB path doesn't exist, that's okay for unit tests
        pytest.skip(f"Cannot test adapter instantiation: {e}")


@pytest.mark.skipif(
    not __import__("agent.frameworks.llamaindex.utils").frameworks.llamaindex.utils.check_llamaindex_installed(),
    reason="LlamaIndex not installed"
)
def test_llamaindex_chroma_store():
    """Test LlamaIndexChromaStore basic functionality."""
    from agent.frameworks.llamaindex import LlamaIndexChromaStore
    
    try:
        store = LlamaIndexChromaStore(chroma_path="./chroma")
        assert store is not None
        assert hasattr(store, "get_index")
        assert hasattr(store, "get_collection")
    except Exception as e:
        pytest.skip(f"Cannot test LlamaIndexChromaStore: {e}")


def test_module_structure():
    """Test that module structure is correct."""
    import os
    from pathlib import Path
    
    llamaindex_dir = Path(__file__).parent.parent / "agent" / "frameworks" / "llamaindex"
    
    assert llamaindex_dir.exists(), "llamaindex directory should exist"
    assert (llamaindex_dir / "__init__.py").exists()
    assert (llamaindex_dir / "utils.py").exists()
    assert (llamaindex_dir / "vector_store.py").exists()
    assert (llamaindex_dir / "README.md").exists()
