"""
Streaming utilities for LLM-only chat responses.
Provides async generators for streaming LLM responses.
"""
import os
from typing import AsyncGenerator, Dict, List, Optional

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


async def stream_openrouter(
    prompt: str,
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
    timeout: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream tokens from OpenRouter API.
    
    Args:
        prompt: The prompt to send
        model: Model name (default from env)
        api_key: API key (default from env)
        temperature: Temperature for generation
        timeout: Request timeout in seconds
        
    Yields:
        Token strings as they arrive
    """
    if AsyncOpenAI is None:
        raise RuntimeError("OpenAI SDK is not installed. Please run `pip install openai`.")

    api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    model = model or os.getenv("OPENROUTER_MODEL", "xiaomi/mimo-v2-flash:free")
    timeout_sec = timeout or int(os.getenv("OPENROUTER_TIMEOUT_SEC", "60"))

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    extra_headers = {
        "HTTP-Referer": "https://github.com/qsang793/ai-research-agent",
        "X-Title": "AI Research Agent",
    }

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            timeout=timeout_sec,
            extra_headers=extra_headers,
            extra_body={"reasoning": {"enabled": False}},
            stream=True,  # Enable streaming
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        raise RuntimeError(f"OpenRouter streaming error: {str(e)}") from e


def build_context(snippets: List[dict]) -> str:
    """Build context string from snippets."""
    lines = []
    for s in snippets:
        title = (s.get("metadata") or {}).get("title") or "(no title)"
        url = (s.get("metadata") or {}).get("source_url") or ""
        text = s.get("text") or s.get("document") or s.get("doc") or s.get("content") or ""
        lines.append(f"[{title}]({url})\n{text}\n")
    return "\n".join(lines)


DEFAULT_PROMPT = (
    "Bạn là trợ lý nghiên cứu. Sử dụng thông tin trong CONTEXT và LỊCH SỬ HỘI THOẠI (nếu có) để trả lời.\n"
    "- Bắt buộc trích dẫn theo [Title](URL) nếu có nguồn từ CONTEXT.\n"
    "- Nếu không có thông tin trong cả CONTEXT và LỊCH SỬ, hãy nói: \"Chưa đủ nguồn\".\n"
    "{memory}\n"
    "CONTEXT:\n{context}\n\nCÂU HỎI: {question}\n"
)


async def stream_answer(
    question: str,
    topk_snippets: List[dict],
    prompt_template: Optional[str] = None,
    *,
    backend: Optional[str] = None,
    temperature: float = 0.2,
    memory_context: str = "",
) -> AsyncGenerator[str, None]:
    """
    Stream answer generation from LLM.
    
    Args:
        question: User question
        topk_snippets: Retrieved snippets
        prompt_template: Custom prompt template
        backend: LLM backend (only openrouter supported for now)
        temperature: Generation temperature
        memory_context: Conversation history
        
    Yields:
        Token strings
    """
    ctx = build_context(topk_snippets)
    
    # Format memory context
    memory_str = ""
    if memory_context:
        memory_str = f"\n--- LỊCH SỬ HỘI THOẠI LIÊN QUAN ---\n{memory_context}\n--- KẾT THÚC LỊCH SỬ ---\n"
    
    prompt = (prompt_template or DEFAULT_PROMPT).format(
        context=ctx, question=question, memory=memory_str
    )
    
    backend_choice = (backend or os.getenv("LLM_BACKEND", "ollama")).strip().lower()

    if backend_choice == "openrouter":
        async for token in stream_openrouter(prompt, temperature=temperature):
            yield token
    else:
        # Fallback: streaming not supported for other backends yet
        raise RuntimeError(
            f"Streaming not supported for backend '{backend_choice}'. "
            "Use 'openrouter' for streaming."
        )


async def stream_simple_llm(
    prompt: str,
    *,
    backend: Optional[str] = None,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """
    Stream LLM response without RAG context.
    
    Used for simple queries (chitchat, help) that don't need retrieval.
    Uses higher temperature for more natural responses.
    
    Args:
        prompt: Formatted prompt to send to LLM
        backend: LLM backend (only openrouter supported)
        temperature: Generation temperature (default 0.7 for chitchat)
        
    Yields:
        Token strings
    """
    backend_choice = (backend or os.getenv("LLM_BACKEND", "ollama")).strip().lower()
    
    if backend_choice == "openrouter":
        async for token in stream_openrouter(prompt, temperature=temperature):
            yield token
    else:
        raise RuntimeError(
            f"Streaming not supported for backend '{backend_choice}'. "
            "Use 'openrouter' for streaming."
        )
