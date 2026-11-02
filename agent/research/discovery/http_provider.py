"""HTTP helpers for research discovery providers.

Shared helpers intentionally stay small and conservative: read/write JSON cache
files by request params and perform status-aware retry with exponential
backoff. The module never logs request URLs or credentials.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Mapping

import requests

logger = logging.getLogger(__name__)
_provider_last_request_at: dict[str, float] = {}
_provider_pacing_lock = threading.Lock()


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using %s", name, raw, default)
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using %s", name, raw, default)
        return default
    return max(value, 0)


def _default_cache_dir(name: str, default: str) -> Path | None:
    raw = os.getenv(name, default).strip()
    return Path(raw) if raw else None


def _cache_key(params: Mapping[str, Any]) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_path(cache_dir: Path, params: Mapping[str, Any], suffix: str = ".json") -> Path:
    return cache_dir / f"{_cache_key(params)}{suffix}"


def _read_cached_response(cache_dir: Path | None, params: Mapping[str, Any], ttl_seconds: float) -> str | None:
    if cache_dir is None or ttl_seconds <= 0:
        return None
    path = _cache_path(cache_dir, params)
    if not path.exists():
        return None
    try:
        if time.time() - path.stat().st_mtime > ttl_seconds:
            return None
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _write_cached_response(cache_dir: Path | None, params: Mapping[str, Any], text: str, ttl_seconds: float) -> None:
    if cache_dir is None or ttl_seconds <= 0:
        return
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = _cache_path(cache_dir, params)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(path)
    except OSError:
        logger.warning("Unable to cache provider response in %s", cache_dir)


def _retry_after_seconds(response: requests.Response | None) -> float | None:
    if response is None:
        return None
    retry_after = response.headers.get("Retry-After") if response.headers else None
    if not retry_after:
        return None
    value = retry_after.strip()
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max((parsed - now).total_seconds(), 0.0)


def _compute_backoff_seconds(
    attempt: int,
    base_seconds: float,
    max_seconds: float,
    response: requests.Response | None,
) -> float:
    base_seconds = max(base_seconds, 0.0)
    max_seconds = max(max_seconds, 0.0)
    retry_after = _retry_after_seconds(response)
    if retry_after is not None:
        return min(retry_after, max_seconds)
    return min(base_seconds * (2**attempt), max_seconds)


def _pace_provider_request(pacing_key: str, min_interval_seconds: float) -> None:
    if min_interval_seconds <= 0:
        return
    with _provider_pacing_lock:
        now = time.monotonic()
        last_request_at = _provider_last_request_at.get(pacing_key)
        if last_request_at is not None:
            wait_seconds = min_interval_seconds - (now - last_request_at)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
                now += wait_seconds
        _provider_last_request_at[pacing_key] = now


def fetch_provider_json(
    url: str,
    params: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout: int,
    *,
    provider_name: str,
    max_retries: int = 3,
    base_backoff_seconds: float = 1.0,
    max_backoff_seconds: float = 60.0,
    min_interval_seconds: float = 0.0,
    pacing_key: str | None = None,
) -> str | None:
    attempts = max_retries + 1
    if attempts < 1:
        attempts = 1
    for attempt in range(attempts):
        try:
            _pace_provider_request(pacing_key or provider_name, min_interval_seconds)
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException:
            if attempt + 1 >= attempts:
                logger.warning("%s request failed after %s attempts", provider_name, attempts)
                return None
            delay = _compute_backoff_seconds(attempt, base_backoff_seconds, max_backoff_seconds, None)
            logger.warning("%s request error on attempt %s/%s; retrying in %.1fs", provider_name, attempt + 1, attempts, delay)
            time.sleep(delay)
            continue

        status = response.status_code
        if status in {401, 403}:
            logger.warning("%s unavailable: HTTP %s", provider_name, status)
            return None
        if status == 429 or status >= 500:
            if attempt + 1 >= attempts:
                logger.warning(
                    "%s temporary error HTTP %s after %s attempts",
                    provider_name,
                    status,
                    attempts,
                )
                return None
            delay = _compute_backoff_seconds(attempt, base_backoff_seconds, max_backoff_seconds, response)
            logger.warning(
                "%s temporary error HTTP %s on attempt %s/%s; retrying in %.1fs",
                provider_name,
                status,
                attempt + 1,
                attempts,
                delay,
            )
            time.sleep(delay)
            continue

        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.warning("%s request failed with status %s", provider_name, status)
            return None
        return response.text

    return None
