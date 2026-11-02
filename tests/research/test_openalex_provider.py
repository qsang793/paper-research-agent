import json
import requests

from agent.research.discovery.openalex_provider import search_openalex_papers
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


def _openalex_payload():
    return {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "display_name": "OpenAlex paper",
                "publication_year": 2023,
                "primary_location": {"landing_page_url": "https://example.test/paper"},
            }
        ]
    }


def test_search_openalex_papers_uses_api_key_param_and_ignores_mailto(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params)
        return FakeResponse(payload=_openalex_payload())

    monkeypatch.setenv("OPENALEX_API_KEY", "openalex-key")
    monkeypatch.setenv("OPENALEX_MAILTO", "legacy@example.com")
    monkeypatch.setattr("agent.research.discovery.openalex_provider.requests.get", fake_get)

    results = search_openalex_papers(
        plan_research_query("OpenAlex index scholarly works"),
        max_results=5,
        cache_ttl_seconds=0,
        min_interval_seconds=0,
    )

    assert results[0].openalex_id == "W123"
    assert calls[0]["api_key"] == "openalex-key"
    assert "mailto" not in calls[0]


def test_search_openalex_papers_caches_successful_json_responses(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["search"])
        return FakeResponse(payload=_openalex_payload())

    monkeypatch.setattr("agent.research.discovery.openalex_provider.requests.get", fake_get)
    plan = plan_research_query("openalex paper discovery")

    first = search_openalex_papers(
        plan,
        max_results=5,
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        min_interval_seconds=0,
    )
    second = search_openalex_papers(
        plan,
        max_results=5,
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        min_interval_seconds=0,
    )

    assert first[0].openalex_id == "W123"
    assert second[0].openalex_id == "W123"
    assert len(calls) == 1


def test_search_openalex_papers_retries_and_uses_exponential_backoff(monkeypatch):
    calls = []
    sleeps = []
    responses = iter([FakeResponse(status_code=500), FakeResponse(status_code=500), FakeResponse(payload=_openalex_payload())])

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["search"])
        return next(responses)

    monkeypatch.setattr("agent.research.discovery.openalex_provider.requests.get", fake_get)
    monkeypatch.setattr("agent.research.discovery.http_provider.time.sleep", sleeps.append)

    result = search_openalex_papers(
        plan_research_query("retry test openalex"),
        max_results=5,
        cache_ttl_seconds=0,
        max_retries=3,
        backoff_base_seconds=1,
        backoff_max_seconds=10,
        min_interval_seconds=0,
    )

    assert len(result) == 1
    assert result[0].title == "OpenAlex paper"
    assert sleeps == [1.0, 2.0]
    assert len(calls) == 3


def test_search_openalex_papers_paces_uncached_requests(monkeypatch):
    calls = []
    sleeps = []
    monotonic_values = iter([20.0, 21.5])

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["search"])
        return FakeResponse(payload=_openalex_payload())

    monkeypatch.setattr("agent.research.discovery.openalex_provider.requests.get", fake_get)
    monkeypatch.setattr("agent.research.discovery.http_provider.time.monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr("agent.research.discovery.http_provider.time.sleep", sleeps.append)
    monkeypatch.setattr("agent.research.discovery.http_provider._provider_last_request_at", {})

    search_openalex_papers(
        plan_research_query("openalex pacing one"),
        max_results=5,
        cache_ttl_seconds=0,
        min_interval_seconds=4,
    )
    search_openalex_papers(
        plan_research_query("openalex pacing two"),
        max_results=5,
        cache_ttl_seconds=0,
        min_interval_seconds=4,
    )

    assert len(calls) == 2
    assert sleeps == [2.5]


def test_search_openalex_papers_returns_empty_and_logs_after_retry_exhaustion(monkeypatch, caplog):
    calls = []
    sleeps = []
    responses = iter([FakeResponse(status_code=429), FakeResponse(status_code=429), FakeResponse(status_code=429)])

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["search"])
        return next(responses)

    monkeypatch.setattr("agent.research.discovery.openalex_provider.requests.get", fake_get)
    monkeypatch.setattr("agent.research.discovery.http_provider.time.sleep", sleeps.append)

    with caplog.at_level("WARNING", logger="agent.research.discovery.openalex_provider"):
        results = search_openalex_papers(
            plan_research_query("retry exhausted openalex"),
            max_retries=2,
            cache_ttl_seconds=0,
            backoff_base_seconds=1,
            backoff_max_seconds=4,
            min_interval_seconds=0,
        )

    assert results == []
    assert len(calls) == 3
    assert sleeps == [1, 2]
    assert "OpenAlex temporary error HTTP 429 after 3 attempts" in caplog.text
