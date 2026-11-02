from typing import Any, Dict, List, Literal, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """State schema shared across LangGraph nodes for Stage 2."""

    # Input / query
    # original_query is the latest user wording; standalone_query is the
    # context-resolved form used only for search/retrieval. `query` remains a
    # compatibility alias for the active retrieval query in legacy nodes.
    original_query: str
    standalone_query: str
    query: str
    query_embedding: Optional[List[float]]  # Cached query embedding for reuse

    # Intent classification
    intent: Literal["known", "fresh", "mixed"]
    intent_confidence: float
    freshness: Literal["none", "current", "mixed"]

    # Routing decisions
    route_type: Literal["kb_only", "search", "both", "search_only"]
    kb_confidence: float

    # Search (multi-query)
    expanded_queries: List[str]
    search_results: List[Dict]

    # Retrieval
    kb_snippets: List[Dict]
    merged_snippets: List[Dict]

    # Re-ranking
    rerank_enabled: bool
    rerank_model: str

    # Generation output
    answer: str
    citations: List[Dict]
    citations_ok: int
    citations_total: int
    citations_dead: List[str]
    sources: List[Dict]
    answerability: Dict[str, Any]
    no_answer_message: str
    query_policy: Dict[str, Any]

    # Memory context
    memory_context: str

    # Error handling
    error: str

    # Runtime configuration (passed through state)
    chroma_path: str
    embed_model: str
    llm_backend: str
    clean_dir: str
    top_k: int
    search_source: Literal["arxiv", "tavily", "mixed"]
