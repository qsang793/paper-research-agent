import argparse
import hashlib
import json
import math
import os
import sys
import time
from typing import Any, Dict, List

import requests


def sha1_hex(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def fetch(url: str, timeout: int, max_retries: int, backoff_base: int, max_mb: int) -> bytes | None:
    for attempt in range(max_retries + 1):
        try:
            r = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "ai-research-agent/0.1"},
                allow_redirects=True,
            )
            if r.status_code != 200:
                raise requests.RequestException(f"status {r.status_code}")
            ct = r.headers.get("Content-Type", "")
            if not any(t in ct for t in ["text/html", "application/xhtml+xml"]):
                raise requests.RequestException(f"unsupported content-type {ct}")
            size_mb = len(r.content) / 1024 / 1024
            if size_mb > max_mb:
                raise requests.RequestException(f"too large {size_mb:.2f} MB")
            return r.content
        except requests.RequestException:
            if attempt == max_retries:
                return None
            time.sleep(backoff_base * (2 ** attempt))
    return None


def main():
    parser = argparse.ArgumentParser(description="Crawl arXiv abstract pages from search results JSON")
    parser.add_argument("--from", dest="input_json", required=True, help="Path to search_results.json")
    parser.add_argument("--out", dest="out_dir", required=True, help="Directory to write raw HTML files")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--backoff", type=int, default=2)
    parser.add_argument("--max-mb", type=int, default=2)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    try:
        with open(args.input_json, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        print(f"Failed to read {args.input_json}: {exc}", file=sys.stderr)
        sys.exit(1)

    results: List[Dict[str, Any]] = payload.get("results", [])
    crawled_ok = 0
    crawled_fail = 0
    manifest: List[Dict[str, Any]] = []

    for item in results:
        url = item.get("abs_url") or item.get("url")
        # Fallback: build abs url from pdf_url if needed
        if not url and item.get("pdf_url"):
            pdf = item["pdf_url"].replace("http://", "https://")
            if "/pdf/" in pdf:
                url = pdf.replace("/pdf/", "/abs/")
        if not url:
            crawled_fail += 1
            continue
        key = sha1_hex(url)
        out_path = os.path.join(args.out_dir, f"{key}.html")
        if os.path.exists(out_path):
            manifest.append({"url": url, "path": out_path})
            continue
        content = fetch(url, args.timeout, args.retries, args.backoff, args.max_mb)
        if content is None:
            crawled_fail += 1
            continue
        with open(out_path, "wb") as f:
            f.write(content)
        crawled_ok += 1
        manifest.append({"url": url, "path": out_path})

    manifest_path = os.path.join(args.out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"entries": manifest}, f, ensure_ascii=False, indent=2)

    print(f"Crawled ok={crawled_ok} fail={crawled_fail}. Manifest: {manifest_path}")


if __name__ == "__main__":
    main()


