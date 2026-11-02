"""
Optional framework integrations.

This module provides optional wrappers for frameworks like LlamaIndex and Haystack.
These are NOT required for the core RAG pipeline but can be used for specific features.

Current implementation uses LangGraph + custom nodes, which is already optimized and production-ready.
Frameworks can be used for:
- Document loading/ingestion
- Specific retrieval strategies
- Monitoring/observability
- Future enhancements

Usage:
    # Optional: Use LlamaIndex for document loading
    from agent.frameworks.llamaindex_wrapper import load_documents_with_llamaindex
    
    # Keep using current retrieval (recommended)
    from agent.nodes.retrieve import retrieve_node
"""

__all__ = [
    # Will be populated as frameworks are added
]
