from agent.research.observability import ResearchTrace, TraceSpan


def test_research_trace_summarizes_latency_by_span_name(monkeypatch):
    monkeypatch.setenv("RESEARCH_ENABLE_PHOENIX", "false")
    trace = ResearchTrace(
        spans=[
            TraceSpan(name="discovery", duration_ms=10, metadata={"provider": "arxiv"}),
            TraceSpan(name="discovery", duration_ms=30, metadata={"provider": "openalex"}),
            TraceSpan(name="synthesis", duration_ms=5, metadata={}),
        ]
    )

    metrics = trace.to_metrics()

    assert metrics["latency_summary"] == {
        "discovery": {"count": 2, "p50_ms": 10, "p95_ms": 30, "max_ms": 30},
        "synthesis": {"count": 1, "p50_ms": 5, "p95_ms": 5, "max_ms": 5},
    }
