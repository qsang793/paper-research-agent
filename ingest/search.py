import argparse
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from typing import List, Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"


@dataclass
class SearchResult:
    title: str
    abs_url: str
    pdf_url: Optional[str]
    published_at: Optional[str]
    authors: List[str]
    primary_category: Optional[str]
    abstract: Optional[str]  # Abstract text from <summary> tag in XML


def _parse_arxiv_atom(xml_text: str) -> List[SearchResult]:
    # Minimal, dependency-free parse via string ops; good enough for MVP
    # For production, use feedparser.
    results: List[SearchResult] = []
    items = xml_text.split("<entry>")
    for item in items[1:]:
        try:
            title = _extract(item, "<title>", "</title>") or ""
            published = _extract(item, "<published>", "</published>")
            abs_url = _extract(item, '<link rel="alternate" type="text/html" href="', '"')
            if not abs_url:
                # Fallback: <id>https://arxiv.org/abs/...</id>
                id_url = _extract(item, "<id>", "</id>")
                if id_url and "/abs/" in id_url:
                    abs_url = id_url.strip()
            pdf_url = _extract(item, '<link title="pdf" href="', '"')
            primary_cat = _extract(item, '<arxiv:primary_category term="', '"')
            authors = _extract_all(item, "<name>", "</name>")
            # Extract abstract from <summary> tag
            abstract_raw = _extract(item, "<summary>", "</summary>") or ""
            # Clean abstract: remove newlines, extra whitespace, HTML entities
            abstract = " ".join(abstract_raw.split()) if abstract_raw else ""
            # Normalize scheme to https
            if abs_url and abs_url.startswith("http://"):
                abs_url = "https://" + abs_url[len("http://"):]
            if pdf_url and pdf_url.startswith("http://"):
                pdf_url = "https://" + pdf_url[len("http://"):]
            results.append(
                SearchResult(
                    title=title.strip(),
                    abs_url=abs_url or "",
                    pdf_url=pdf_url,
                    published_at=published,
                    authors=authors,
                    primary_category=primary_cat,
                    abstract=abstract,
                )
            )
        except Exception:
            continue
    return results


def _extract(src: str, start: str, end: str) -> Optional[str]:
    s = src.find(start)
    if s == -1:
        return None
    s += len(start)
    e = src.find(end, s)
    if e == -1:
        return None
    return src[s:e]


def _extract_all(src: str, start: str, end: str) -> List[str]:
    out: List[str] = []
    i = 0
    while True:
        s = src.find(start, i)
        if s == -1:
            break
        s += len(start)
        e = src.find(end, s)
        if e == -1:
            break
        out.append(src[s:e].strip())
        i = e + len(end)
    return out


def search_arxiv(query: str, max_results: int) -> List[SearchResult]:
    """
    Search ArXiv API with improved query formatting.
    
    ArXiv query syntax:
    - Spaces are treated as OR by default
    - Use "double quotes" for phrase search
    - Use AND for multi-term AND search
    """
    # Clean and format query for better ArXiv search
    # Remove punctuation that might break ArXiv API (e.g. ?, !, etc)
    # Keep hyphens as they are common in technical terms
    cleaned_query = re.sub(r'[^\w\s-]', '', query).strip()
    
    # If query looks like a phrase (3+ words), use phrase search OR AND logic
    words = cleaned_query.split()
    if len(words) >= 2:
        # Try phrase search first (for exact matches)
        # Format: all:"retrieval augmented generation"
        search_query = f'all:"{cleaned_query}"'
    else:
        # Single word - direct search
        search_query = f'all:{cleaned_query}'
    
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",  # Changed from submittedDate to relevance
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API}?{urlencode(params)}"
    headers = {"User-Agent": "ai-research-agent/0.1"}
    resp = requests.get(url, timeout=15, headers=headers)
    resp.raise_for_status()
    return _parse_arxiv_atom(resp.text)


def main():
    parser = argparse.ArgumentParser(description="Search arXiv and save results to JSON")
    parser.add_argument("--q", required=True, help="Query string for arXiv API")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--max", dest="max_results", type=int, default=5, help="Max results")
    args = parser.parse_args()

    try:
        results = search_arxiv(args.q, args.max_results)
    except Exception as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "query": args.q,
        "retrieved_at": int(time.time()),
        "provider": "arxiv",
        "results": [asdict(r) for r in results],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(results)} results to {args.out}")


if __name__ == "__main__":
    main()


