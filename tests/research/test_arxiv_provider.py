from agent.research.discovery.arxiv_provider import (
    build_arxiv_queries,
    parse_arxiv_atom,
    search_arxiv_papers,
)
from agent.research.query_plan import plan_research_query


ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2306.17157v1</id>
    <updated>2023-06-29T17:59:00Z</updated>
    <published>2023-06-29T17:59:00Z</published>
    <title>ROS 2 in robotics research</title>
    <summary>Robot Operating System 2 middleware is used for distributed robotic systems.</summary>
    <author><name>Ada Lovelace</name></author>
    <arxiv:primary_category term="cs.RO" />
    <category term="cs.RO" />
    <link href="http://arxiv.org/abs/2306.17157v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2306.17157v1" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""


class FakeResponse:
    status_code = 200
    text = ARXIV_XML

    def raise_for_status(self):
        return None


def test_build_arxiv_queries_uses_boolean_variants_not_exact_phrase_only():
    plan = plan_research_query("ROS2 trong robotics là gì")

    queries = build_arxiv_queries(plan)

    assert "all:ROS2 AND all:robotics" in queries
    assert any('all:"ROS 2"' in query for query in queries)
    assert any("cat:cs.RO" in query for query in queries)
    assert not all(query.startswith('all:"') for query in queries)


def test_build_arxiv_queries_includes_canonical_id_queries_first():
    plan = plan_research_query("Transformer paper có gì")

    queries = build_arxiv_queries(plan)

    assert queries[0] == "id:1706.03762"
    assert any("Transformer" in query for query in queries[1:])


def test_parse_arxiv_atom_returns_paper_candidate_with_metadata():
    candidates = parse_arxiv_atom(ARXIV_XML)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "ROS 2 in robotics research"
    assert candidate.arxiv_id == "2306.17157"
    assert candidate.pdf_url == "https://arxiv.org/pdf/2306.17157v1"
    assert candidate.source_url == "https://arxiv.org/abs/2306.17157v1"
    assert candidate.categories == ["cs.RO"]


def test_search_arxiv_papers_uses_planned_query_and_normalizes(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["search_query"])
        return FakeResponse()

    monkeypatch.setattr("agent.research.discovery.arxiv_provider.requests.get", fake_get)
    plan = plan_research_query("ROS2 trong robotics là gì")

    candidates = search_arxiv_papers(plan, max_results=5, cache_ttl_seconds=0, min_interval_seconds=0)

    assert candidates[0].title == "ROS 2 in robotics research"
    assert any("ROS2" in query and "robotics" in query for query in calls)


def test_search_arxiv_papers_caches_successful_api_responses(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["search_query"])
        return FakeResponse()

    monkeypatch.setattr("agent.research.discovery.arxiv_provider.requests.get", fake_get)
    plan = plan_research_query("paper 2306.17157 summary")

    first = search_arxiv_papers(
        plan,
        max_results=5,
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        min_interval_seconds=0,
    )
    second = search_arxiv_papers(
        plan,
        max_results=5,
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        min_interval_seconds=0,
    )

    assert first[0].arxiv_id == "2306.17157"
    assert second[0].arxiv_id == "2306.17157"
    assert len(calls) == 1


def test_search_arxiv_papers_falls_back_to_network_when_cache_is_corrupt(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["search_query"])
        return FakeResponse()

    monkeypatch.setattr("agent.research.discovery.arxiv_provider.requests.get", fake_get)
    monkeypatch.setattr(
        "agent.research.discovery.arxiv_provider._read_cached_response",
        lambda cache_dir, params, ttl_seconds: "<not atom xml",
    )
    plan = plan_research_query("paper 2306.17157 summary")

    candidates = search_arxiv_papers(
        plan,
        max_results=5,
        cache_dir=tmp_path,
        cache_ttl_seconds=3600,
        min_interval_seconds=0,
    )

    assert candidates[0].arxiv_id == "2306.17157"
    assert len(calls) == 1


def test_search_arxiv_papers_paces_uncached_subqueries(monkeypatch):
    calls = []
    sleeps = []
    timestamps = iter([10.0, 11.0])

    class EmptyResponse:
        text = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>
"""

        def raise_for_status(self):
            return None

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params["search_query"])
        return EmptyResponse()

    monkeypatch.setattr("agent.research.discovery.arxiv_provider.requests.get", fake_get)
    monkeypatch.setattr("agent.research.discovery.arxiv_provider.time.monotonic", lambda: next(timestamps))
    monkeypatch.setattr("agent.research.discovery.arxiv_provider.time.sleep", sleeps.append)
    monkeypatch.setattr("agent.research.discovery.arxiv_provider._last_arxiv_request_at", None)

    plan = plan_research_query("ROS2 trong robotics là gì")

    search_arxiv_papers(plan, max_results=5, min_interval_seconds=3, cache_ttl_seconds=0)

    assert len(calls) >= 2
    assert sleeps == [2.0]


def test_search_arxiv_papers_pacing_uses_lock(monkeypatch):
    events = []
    timestamps = iter([10.0])

    class FakeLock:
        def __enter__(self):
            events.append("enter")

        def __exit__(self, exc_type, exc, tb):
            events.append("exit")

    monkeypatch.setattr("agent.research.discovery.arxiv_provider._arxiv_pacing_lock", FakeLock())
    monkeypatch.setattr("agent.research.discovery.arxiv_provider.time.monotonic", lambda: next(timestamps))
    monkeypatch.setattr("agent.research.discovery.arxiv_provider._last_arxiv_request_at", None)

    from agent.research.discovery.arxiv_provider import _pace_arxiv_request

    _pace_arxiv_request(3)

    assert events == ["enter", "exit"]
