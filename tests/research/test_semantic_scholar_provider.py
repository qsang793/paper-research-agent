import json
import requests

from agent.research.discovery.semantic_scholar_provider import search_semantic_scholar_papers
from agent.research.query_plan import plan_research_query


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None, headers: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload if payload is not None else {}

    @property
    def text(self) -> str:
        return json.dumps(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _semantic_payload():
    return {"data": [{"paperId": "S1", "title": "Semantic paper"}]}


def test_search_semantic_scholar_papers_uses_api_key_header(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(headers.get("x-api-key"))
        return FakeResponse(payload=_semantic_payload())

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "s2-key")
    monkeypatch.setattr("agent.research.discovery.semantic_scholar_provider.requests.get", fake_get)

    results = search_semantic_scholar_papers(
        plan_research_query("semantic scholar papers"),
        max_results=3,
        cache_ttl_seconds=0,
        min_interval_seconds=0,
    )

    assert len(results) == 1
    assert results[0].semantic_scholar_id == "S1"
    assert calls[0] == "s2-key"


def test_search_semantic_scholar_papers_caches_successful_json_responses(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["query"])
        return FakeResponse(payload=_semantic_payload())

    monkeypatch.setattr("agent.research.discovery.semantic_scholar_provider.requests.get", fake_get)
    plan = plan_research_query("deep learning with transformers")

    first = search_semantic_scholar_papers(
        plan,
        max_results=5,
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        min_interval_seconds=0,
    )
    second = search_semantic_scholar_papers(
        plan,
        max_results=5,
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        min_interval_seconds=0,
    )

    assert first[0].semantic_scholar_id == "S1"
    assert second[0].semantic_scholar_id == "S1"
    assert len(calls) == 1


def test_search_semantic_scholar_papers_retries_and_respects_retry_after(monkeypatch, tmp_path):
    calls = []
    sleeps = []
    responses = iter(
        [
            FakeResponse(status_code=429, headers={"Retry-After": "4"}),
            FakeResponse(payload=_semantic_payload()),
        ]
    )

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["query"])
        return next(responses)

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "s2-key")
    monkeypatch.setattr("agent.research.discovery.semantic_scholar_provider.requests.get", fake_get)
    monkeypatch.setattr("agent.research.discovery.http_provider.time.sleep", sleeps.append)

    result = search_semantic_scholar_papers(
        plan_research_query("semantic retry after"),
        max_results=5,
        cache_ttl_seconds=0,
        max_retries=3,
        backoff_base_seconds=1,
        backoff_max_seconds=30,
        cache_dir=tmp_path,
        min_interval_seconds=0,
    )

    assert len(result) == 1
    assert result[0].title == "Semantic paper"
    assert sleeps == [4.0]
    assert len(calls) == 2


def test_search_semantic_scholar_papers_falls_back_when_retry_after_is_invalid(monkeypatch):
    sleeps = []
    responses = iter(
        [
            FakeResponse(status_code=429, headers={"Retry-After": "not-a-date"}),
            FakeResponse(payload=_semantic_payload()),
        ]
    )

    def fake_get(url, params=None, headers=None, timeout=None):
        return next(responses)

    monkeypatch.setattr("agent.research.discovery.semantic_scholar_provider.requests.get", fake_get)
    monkeypatch.setattr("agent.research.discovery.http_provider.time.sleep", sleeps.append)

    result = search_semantic_scholar_papers(
        plan_research_query("semantic malformed retry after"),
        max_results=5,
        cache_ttl_seconds=0,
        max_retries=1,
        backoff_base_seconds=2,
        backoff_max_seconds=30,
        min_interval_seconds=0,
    )

    assert len(result) == 1
    assert sleeps == [2]


def test_search_semantic_scholar_papers_paces_uncached_requests(monkeypatch):
    calls = []
    sleeps = []
    monotonic_values = iter([10.0, 11.0])

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["query"])
        return FakeResponse(payload=_semantic_payload())

    monkeypatch.setattr("agent.research.discovery.semantic_scholar_provider.requests.get", fake_get)
    monkeypatch.setattr("agent.research.discovery.http_provider.time.monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr("agent.research.discovery.http_provider.time.sleep", sleeps.append)
    monkeypatch.setattr("agent.research.discovery.http_provider._provider_last_request_at", {})

    search_semantic_scholar_papers(
        plan_research_query("semantic pacing one"),
        max_results=5,
        cache_ttl_seconds=0,
        min_interval_seconds=3,
    )
    search_semantic_scholar_papers(
        plan_research_query("semantic pacing two"),
        max_results=5,
        cache_ttl_seconds=0,
        min_interval_seconds=3,
    )

    assert len(calls) == 2
    assert sleeps == [2.0]


def test_search_semantic_scholar_papers_returns_empty_and_logs_after_retry_exhaustion(monkeypatch, caplog):
    calls = []
    sleeps = []
    responses = iter([FakeResponse(status_code=500), FakeResponse(status_code=500), FakeResponse(status_code=500)])

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["query"])
        return next(responses)

    monkeypatch.setattr("agent.research.discovery.semantic_scholar_provider.requests.get", fake_get)
    monkeypatch.setattr("agent.research.discovery.http_provider.time.sleep", sleeps.append)

    with caplog.at_level("WARNING", logger="agent.research.discovery.semantic_scholar_provider"):
        results = search_semantic_scholar_papers(
            plan_research_query("retry exhausted"),
            max_retries=2,
            cache_ttl_seconds=0,
            backoff_base_seconds=1,
            backoff_max_seconds=5,
            min_interval_seconds=0,
        )

    assert results == []
    assert len(calls) == 3
    assert sleeps == [1, 2]
    assert "Semantic Scholar temporary error HTTP 500 after 3 attempts" in caplog.text
