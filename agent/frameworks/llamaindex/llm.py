"""
LlamaIndex LLM Integration.

This module provides LlamaIndex-based LLM wrappers that can be used
as alternatives to the current custom LLM implementations.
"""

import logging
import os
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

# Note: LlamaIndex LLM packages are optional and need to be installed separately:
# - llama-index-llms-openai (for OpenAI/OpenRouter)
# - llama-index-llms-ollama (for Ollama)
# - llama-index-llms-gemini (for Gemini)

try:
    # Try importing LlamaIndex LLM classes
    try:
        from llama_index.llms.openai import OpenAI
    except ImportError:
        try:
            from llama_index.core.llms.openai import OpenAI
        except ImportError:
            OpenAI = None
    
    # For now, only support OpenAI-compatible (OpenRouter)
    # Ollama and Gemini support can be added when packages are installed
    LLAMAINDEX_LLM_AVAILABLE = OpenAI is not None
    
    if not LLAMAINDEX_LLM_AVAILABLE:
        logger.warning("LlamaIndex LLM classes not available. Install: pip install llama-index-llms-openai")
except ImportError:
    LLAMAINDEX_LLM_AVAILABLE = False
    OpenAI = None
    logger.warning("LlamaIndex not installed")


class LlamaIndexLLMWrapper:
    """
    Wrapper for LlamaIndex LLM classes to provide unified streaming interface.
    
    Supports:
    - Ollama (local)
    - Gemini (Google)
    - OpenRouter (via OpenAI-compatible API)
    
    Usage:
        >>> llm = LlamaIndexLLMWrapper(backend="ollama", model="llama2")
        >>> async for token in llm.stream("Hello"):
        ...     print(token, end="")
    """
    
    def __init__(
        self,
        backend: str = "ollama",
        model: Optional[str] = None,
        temperature: float = 0.2,
        timeout: Optional[int] = None
    ):
        """
        Initialize LlamaIndex LLM wrapper.
        
        Args:
            backend: LLM backend ("ollama", "gemini", "openrouter")
            model: Model name (default from env or backend-specific)
            temperature: Generation temperature
            timeout: Request timeout in seconds
        """
        if not LLAMAINDEX_LLM_AVAILABLE:
            raise ImportError(
                "LlamaIndex LLM classes not available. "
                "Install with: pip install llama-index[llms]"
            )
        
        self.backend = backend.strip().lower()
        self.temperature = temperature
        self.timeout = timeout or 60
        
        # Initialize LLM based on backend
        # For now, only support OpenRouter (OpenAI-compatible)
        # Ollama and Gemini support can be added when packages are installed
        if self.backend == "openrouter":
            # OpenRouter uses OpenAI-compatible API
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise RuntimeError("OPENROUTER_API_KEY is not set")
            if OpenAI is None:
                raise ImportError("OpenAI LLM not available. Install: pip install llama-index-llms-openai")
            base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            model = model or os.getenv("OPENROUTER_MODEL", "xiaomi/mimo-v2-flash:free")
            self._llm = OpenAI(
                api_key=api_key,
                model=model,
                temperature=temperature,
                timeout=self.timeout,
                base_url=base_url,
                default_headers={
                    "HTTP-Referer": "https://github.com/qsang793/ai-research-agent",
                    "X-Title": "AI Research Agent",
                }
            )
        elif self.backend == "ollama":
            raise NotImplementedError(
                "Ollama support via LlamaIndex not yet implemented. "
                "Install: pip install llama-index-llms-ollama"
            )
        elif self.backend == "gemini":
            raise NotImplementedError(
                "Gemini support via LlamaIndex not yet implemented. "
                "Install: pip install llama-index-llms-gemini"
            )
        else:
            raise ValueError(f"Unsupported backend: {backend}. Use 'openrouter' (others coming soon)")
    
    async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Stream LLM response tokens.
        
        Args:
            prompt: Input prompt
            
        Yields:
            Token strings as they arrive
        """
        try:
            # LlamaIndex LLM streaming
            # Use astream_complete for streaming
            response_stream = self._llm.astream_complete(prompt)
            async for token in response_stream:
                # Extract text from response
                if hasattr(token, 'text'):
                    yield token.text
                elif hasattr(token, 'delta'):
                    yield token.delta
                elif isinstance(token, str):
                    yield token
                else:
                    # Try to get text from response object
                    text = getattr(token, 'text', str(token))
                    if text:
                        yield text
        except Exception as exc:
            logger.error(f"LlamaIndex LLM streaming error: {exc}")
            raise RuntimeError(f"LLM streaming failed: {str(exc)}") from exc
    
    def complete(self, prompt: str) -> str:
        """
        Get complete LLM response (non-streaming).
        
        Args:
            prompt: Input prompt
            
        Returns:
            Complete response text
        """
        try:
            response = self._llm.complete(prompt)
            if hasattr(response, 'text'):
                return response.text
            return str(response)
        except Exception as exc:
            logger.error(f"LlamaIndex LLM completion error: {exc}")
            raise RuntimeError(f"LLM completion failed: {str(exc)}") from exc
