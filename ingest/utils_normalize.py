import hashlib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.hostname.lower() if parsed.hostname else ""
    path = parsed.path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    # drop fragment
    normalized = urlunparse((parsed.scheme.lower() or "http", host, path, parsed.params, query, ""))
    return normalized


def compute_content_hash(normalized_url: str, title: str, cleaned_text: str) -> str:
    hasher = hashlib.sha256()
    hasher.update((normalized_url or "").encode("utf-8"))
    hasher.update((title or "").strip().encode("utf-8"))
    hasher.update((cleaned_text or "")[:4096].encode("utf-8"))
    return hasher.hexdigest()

