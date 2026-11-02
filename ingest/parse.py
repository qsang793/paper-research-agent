import argparse
import glob
import json
import os
import sys
import time
from typing import Any, Dict

from bs4 import BeautifulSoup

from .utils_normalize import compute_content_hash, normalize_url


def parse_arxiv_abs_html(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    # Title
    title_el = soup.select_one("h1.title") or soup.find("title")
    title = title_el.get_text(strip=True).replace("Title:", "").strip() if title_el else ""
    # Authors
    auth_el = soup.select_one("div.authors")
    authors = []
    if auth_el:
        authors = [a.get_text(strip=True) for a in auth_el.find_all("a")] or [auth_el.get_text(strip=True)]
    # Abstract
    abs_el = soup.select_one("blockquote.abstract")
    abstract = ""
    if abs_el:
        abstract = abs_el.get_text(" ", strip=True).replace("Abstract:", "").strip()
    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
    }


def main():
    parser = argparse.ArgumentParser(description="Parse raw arXiv HTML into clean JSON chunks")
    parser.add_argument("--input", required=True, help="Directory containing raw HTML files")
    parser.add_argument("--out", required=True, help="Directory to write cleaned JSON files")
    parser.add_argument("--source-base", default="https://arxiv.org", help="Base URL for manifest mapping (optional)")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # Try to read manifest for url mapping
    manifest_path = os.path.join(args.input, "manifest.json")
    url_by_key = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f).get("entries", [])
            for e in manifest:
                url = e.get("url")
                path = e.get("path", "")
                key = os.path.splitext(os.path.basename(path))[0]
                if url and key:
                    url_by_key[key] = url
        except Exception:
            pass

    count = 0
    for fp in glob.glob(os.path.join(args.input, "*.html")):
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                html = f.read()
            meta = parse_arxiv_abs_html(html)
            key = os.path.splitext(os.path.basename(fp))[0]
            source_url = url_by_key.get(key, "")
            nurl = normalize_url(source_url) if source_url else ""
            cleaned_text = meta.get("abstract") or ""
            content_hash = compute_content_hash(nurl, meta.get("title", ""), cleaned_text)
            out = {
                "id": content_hash,
                "text": cleaned_text,
                "metadata": {
                    "source_url": source_url,
                    "title": meta.get("title"),
                    "authors": meta.get("authors", []),
                    "published_at": None,  # not available in HTML reliably at this step
                    "retrieved_at": int(time.time()),
                    "language": "en",
                    "doc_type": "paper",
                    "section": "abstract",
                },
            }
            out_path = os.path.join(args.out, f"{content_hash}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            count += 1
        except Exception as exc:
            print(f"Parse failed for {fp}: {exc}")
            continue

    print(f"Parsed {count} documents to {args.out}")


if __name__ == "__main__":
    main()


