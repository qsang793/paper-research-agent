from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List


@dataclass
class TraceSpan:
    name: str
    duration_ms: int
    metadata: Dict = field(default_factory=dict)


@dataclass
class ResearchTrace:
    spans: List[TraceSpan] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)

    @contextmanager
    def span(self, name: str, **metadata) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.spans.append(TraceSpan(name=name, duration_ms=duration_ms, metadata=metadata))

    def to_metrics(self) -> Dict:
        by_name: dict[str, list[int]] = {}
        for span in self.spans:
            by_name.setdefault(span.name, []).append(span.duration_ms)
        return {
            "trace_context": dict(self.context),
            "spans": [
                {"name": span.name, "duration_ms": span.duration_ms, "metadata": span.metadata}
                for span in self.spans
            ],
            "latency_summary": {
                name: {
                    "count": len(values),
                    "p50_ms": _percentile(values, 50),
                    "p95_ms": _percentile(values, 95),
                    "max_ms": max(values),
                }
                for name, values in by_name.items()
            },
            "phoenix_enabled": os.getenv("RESEARCH_ENABLE_PHOENIX", "false").lower() == "true",
        }


def _percentile(values: list[int], percentile: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * (percentile / 100))
    return ordered[index]
