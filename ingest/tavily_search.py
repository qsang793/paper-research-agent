"""
Tavily Web Search integration for Stage 3.

Provides semantic web search capabilities beyond ArXiv papers.
"""
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

from tavily import TavilyClient

logger = logging.getLogger(__name__)


@dataclass
class TavilyResult:
    """Structured result from Tavily search."""

    title: str
    url: str
    content: str
    score: float
    published_date: Optional[str] = None


def search_tavily(query: str, max_results: int = 5, max_retries: int = 3) -> List[TavilyResult]:
    """
    Search the web using Tavily API with retry logic.

    Args:
        query: Search query
        max_results: Maximum number of results to return
        max_retries: Maximum retry attempts on failure

    Returns:
        List of TavilyResult objects (empty list on failure)

    Requires:
        TAVILY_API_KEY environment variable
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.warning("TAVILY_API_KEY not set. Skipping web search.")
        return []

    last_exception = None
    for attempt in range(max_retries):
        try:
            logger.debug(f"Tavily search attempt {attempt + 1}/{max_retries}: {query}")
            client = TavilyClient(api_key=api_key)
            # search_depth="advanced" provides better quality for research
            # but uses more credits. Use "basic" for faster/cheaper searches.
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=max_results,
                include_answer=False,  # We generate our own answers
                include_raw_content=False,  # Clean content is sufficient
                include_images=False,
            )

            results = []
            for item in response.get("results", []):
                results.append(
                    TavilyResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        score=item.get("score", 0.0),
                        published_date=item.get("published_date"),
                    )
                )

            logger.info(f"Tavily search successful: {len(results)} results for '{query}'")
            return results
            
        except Exception as exc:
            last_exception = exc
            logger.warning(f"Tavily search error (attempt {attempt + 1}/{max_retries}): {exc}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
    
    # All retries exhausted - return empty list as fallback
    logger.error(f"Tavily search failed after {max_retries} attempts. Last error: {last_exception}")
    return []
