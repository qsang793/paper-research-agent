"""
Utility functions for LlamaIndex integration.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def get_llamaindex_packages() -> List[str]:
    """
    Get list of required LlamaIndex packages for installation.
    
    Note: Package availability depends on LlamaIndex version.
    For 0.11.15, some packages may not exist or have different names.
    
    Returns:
        List of package names with versions
    """
    return [
        "llama-index>=0.11.0",
        # Core packages (try to install, may fail for older versions)
        "llama-index-vector-stores-chroma>=0.1.0",  # Available as 0.5.5
        # Optional packages (may not exist for 0.11.15)
        # "llama-index-embeddings-sentence-transformers>=0.1.0",  # May not exist
        # "llama-index-llms-ollama>=0.1.0",  # May not exist
        # "llama-index-llms-openai>=0.1.0",  # May not exist
    ]


def get_llamaindex_optional_packages() -> List[str]:
    """
    Get list of optional LlamaIndex packages (may not be available for all versions).
    
    Returns:
        List of optional package names
    """
    return [
        "llama-index-embeddings-sentence-transformers>=0.1.0",
        "llama-index-llms-ollama>=0.1.0",
        "llama-index-llms-openai>=0.1.0",
    ]


def check_llamaindex_installed() -> bool:
    """
    Check if LlamaIndex is installed and importable.
    
    Returns:
        True if LlamaIndex can be imported, False otherwise
    """
    try:
        import llama_index
        return True
    except ImportError:
        return False


def get_llamaindex_version() -> Optional[str]:
    """
    Get installed LlamaIndex version.
    
    Returns:
        Version string or None if not installed
    """
    try:
        import llama_index
        return getattr(llama_index, "__version__", "unknown")
    except ImportError:
        return None
