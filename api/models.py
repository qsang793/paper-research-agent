"""
Pydantic models for API request/response schemas.
"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class SearchSource(str, Enum):
    """Search source options for retrieval-backed chat."""
    RESEARCH = "research"


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""
    query: str = Field(..., min_length=1, max_length=2000, description="User query")
    session_id: Optional[str] = Field(default=None, description="Conversation session ID")
    user_id: Optional[str] = Field(default=None, description="Server-provided authenticated user ID")
    top_k: Optional[int] = Field(default=6, ge=1, le=20, description="Number of documents to retrieve")
    mode: Optional[str] = Field(default="auto", description="Processing mode: 'auto', 'search', 'chat'")
    search_source: Optional[SearchSource] = Field(
        default=None,
        description="Retrieval source when mode is 'search'. Only 'research' is supported.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is RAG?",
                "session_id": "user-123",
                "user_id": "auth-user-123",
                "top_k": 6,
                "mode": "search",
                "search_source": "research",
            }
        }


class Citation(BaseModel):
    """Citation/source document metadata."""
    title: str
    authors: List[str] = Field(default_factory=list)
    url: str
    arxiv_id: Optional[str] = None
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    snippet: Optional[str] = None


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""
    answer: str = Field(..., description="Generated answer")
    citations: List[Citation] = Field(default_factory=list, description="Source citations")
    session_id: str = Field(..., description="Conversation session ID")
    response_time_ms: float = Field(..., description="Response time in milliseconds")
    tokens_used: Optional[int] = Field(default=None, description="Approximate tokens used")

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "RAG stands for Retrieval-Augmented Generation...",
                "citations": [
                    {
                        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
                        "authors": ["Patrick Lewis", "Ethan Perez"],
                        "url": "https://arxiv.org/abs/2005.11401",
                        "arxiv_id": "2005.11401",
                        "relevance_score": 0.95,
                        "snippet": "We introduce RAG models..."
                    }
                ],
                "session_id": "user-123",
                "response_time_ms": 3450.5,
                "tokens_used": 512
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime
    chroma_status: str


class InfoResponse(BaseModel):
    """API configuration info response."""
    embed_model: str
    llm_backend: str
    reranking_enabled: bool
    rerank_model: Optional[str] = None
