"""
LlamaIndex-based generate node for LangGraph.

This module provides a generate_node implementation using LlamaIndex
LLM while maintaining compatibility with the existing interface.
"""

import os
from typing import Dict, List, Optional

from agent.citation_validator import validate_citations
from agent.state import AgentState
from agent.frameworks.llamaindex.llm import LlamaIndexLLMWrapper
from agent.generator import build_context, DEFAULT_PROMPT


async def generate_answer_llamaindex(
    question: str,
    topk_snippets: List[dict],
    *,
    backend: Optional[str] = None,
    temperature: float = 0.2,
    memory_context: str = "",
    prompt_template: Optional[str] = None,
) -> str:
    """
    Generate answer using LlamaIndex LLM.
    
    Args:
        question: User question
        topk_snippets: Retrieved snippets
        backend: LLM backend (ollama, gemini, openrouter)
        temperature: Generation temperature
        memory_context: Conversation history
        prompt_template: Custom prompt template
        
    Returns:
        Generated answer text
    """
    # Build context from snippets
    ctx = build_context(topk_snippets)
    
    # Format memory context
    memory_str = ""
    if memory_context:
        memory_str = f"\n--- LỊCH SỬ HỘI THOẠI LIÊN QUAN ---\n{memory_context}\n--- KẾT THÚC LỊCH SỬ ---\n"
    
    # Format prompt
    prompt = (prompt_template or DEFAULT_PROMPT).format(
        context=ctx, question=question, memory=memory_str
    )
    
    # Get backend
    backend_choice = (backend or os.getenv("LLM_BACKEND", "ollama")).strip().lower()
    
    # Initialize LlamaIndex LLM
    llm = LlamaIndexLLMWrapper(
        backend=backend_choice,
        temperature=temperature
    )
    
    # Generate answer (non-streaming for now)
    answer = llm.complete(prompt)
    return answer


def generate_node_llamaindex(state: AgentState) -> AgentState:
    """
    LangGraph node: generate final answer using LlamaIndex LLM.
    
    This is a drop-in replacement for generate_node that uses LlamaIndex
    LLM while maintaining the same interface and behavior.
    
    Supports memory-only generation when no snippets are available but
    memory context exists.
    """
    snippets: List[Dict] = state.get("merged_snippets", []) or []
    memory_context = state.get("memory_context", "")
    
    # Allow generation if we have EITHER snippets OR memory context
    if not snippets and not memory_context:
        state["answer"] = "Chưa đủ nguồn để trả lời câu hỏi này."
        state["citations"] = []
        state["citations_ok"] = 0  # type: ignore[assignment]
        state["citations_total"] = 0  # type: ignore[assignment]
        state["citations_dead"] = []  # type: ignore[assignment]
        return state
    
    # Get LLM backend from state or environment
    llm_backend = state.get("llm_backend") or os.getenv("LLM_BACKEND", "ollama")
    temperature = state.get("temperature", 0.2)
    
    # Generate answer with memory context
    # Note: generate_answer_llamaindex is async, but LangGraph nodes are sync
    # So we need to run it synchronously
    import asyncio
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, we can't use it - need to create new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    generate_answer_llamaindex(
                        state["query"],
                        snippets,
                        backend=llm_backend,
                        temperature=temperature,
                        memory_context=memory_context,
                    )
                )
                answer = future.result()
        else:
            answer = loop.run_until_complete(generate_answer_llamaindex(
                state["query"],
                snippets,
                backend=llm_backend,
                temperature=temperature,
                memory_context=memory_context,
            ))
    except RuntimeError:
        # No event loop, create new one
        answer = asyncio.run(generate_answer_llamaindex(
            state["query"],
            snippets,
            backend=llm_backend,
            temperature=temperature,
            memory_context=memory_context,
        ))
    state["answer"] = answer  # type: ignore[assignment]
    
    # Extract URLs from snippets for citation validation
    snippet_urls = [
        (s.get("metadata") or {}).get("source_url") or ""
        for s in snippets
    ]
    
    # Validate citations
    validation = validate_citations(answer, snippet_urls)
    state["citations"] = validation.get("checked", [])  # type: ignore[assignment]
    state["citations_ok"] = validation.get("ok", 0)  # type: ignore[assignment]
    state["citations_total"] = validation.get("total", 0)  # type: ignore[assignment]
    state["citations_dead"] = validation.get("dead", [])  # type: ignore[assignment]
    
    return state
