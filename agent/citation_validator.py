import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set

import requests


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def extract_markdown_links(text: str) -> List[str]:
    if not text:
        return []
    return [m.group(2) for m in _MD_LINK_RE.finditer(text)]


def is_alive(url: str, timeout: float = 5.0) -> bool:
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout)
        if 200 <= r.status_code < 400:
            return True
    except requests.RequestException:
        pass
    try:
        r = requests.get(url, allow_redirects=True, timeout=timeout)
        return 200 <= r.status_code < 400
    except requests.RequestException:
        return False


def validate_citations(answer_text: str, snippet_urls: List[str], timeout: float = 5.0, max_workers: int = 10) -> dict:
    """
    Validate citations by checking if URLs are alive.

    Uses parallel requests to check multiple URLs simultaneously for better performance.

    Args:
        answer_text: Text containing markdown links
        snippet_urls: List of URLs from snippets
        timeout: Request timeout in seconds
        max_workers: Maximum number of parallel workers for URL checking

    Returns:
        Dictionary with validation results: {total, ok, dead, checked}
    """
    urls: Set[str] = set()
    for u in extract_markdown_links(answer_text):
        urls.add(u)
    for u in snippet_urls:
        if u:
            urls.add(u)
    total = len(urls)

    if total == 0:
        return {"total": 0, "ok": 0, "dead": [], "checked": []}

    # Parallelize URL checking for better performance
    ok = 0
    dead: List[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all URL checks in parallel
        future_to_url = {
            executor.submit(is_alive, url, timeout): url
            for url in urls
        }

        # Collect results as they complete
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                if future.result():
                    ok += 1
                else:
                    dead.append(url)
            except Exception:
                dead.append(url)

    return {"total": total, "ok": ok, "dead": dead, "checked": list(urls)}


def validate_citation_sources(
    answer_text: str,
    sources: List[Dict],
    timeout: float = 5.0,
    max_workers: int = 10,
) -> dict:
    """Validate URLs while preserving the canonical source dictionaries."""
    urls: Set[str] = set(extract_markdown_links(answer_text))
    for source in sources:
        url = source.get("url")
        if url:
            urls.add(url)

    if not urls:
        return {"total": 0, "ok": 0, "dead": [], "checked": [], "sources": sources}

    alive_by_url: Dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(is_alive, url, timeout): url
            for url in urls
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                alive_by_url[url] = bool(future.result())
            except Exception:
                alive_by_url[url] = False

    annotated = []
    for source in sources:
        source_copy = dict(source)
        url = source_copy.get("url")
        if url:
            source_copy["alive_status"] = "ok" if alive_by_url.get(url, False) else "dead"
        else:
            source_copy["alive_status"] = "missing_url"
        annotated.append(source_copy)

    dead = sorted(url for url, alive in alive_by_url.items() if not alive)
    ok = sum(1 for alive in alive_by_url.values() if alive)
    return {
        "total": len(alive_by_url),
        "ok": ok,
        "dead": dead,
        "checked": sorted(alive_by_url.keys()),
        "sources": annotated,
    }
