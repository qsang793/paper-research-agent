# Research Workflow Production Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the new `agent/research/` preview workflow into the real chat workflow without breaking the existing LangGraph path, streaming contract, or UI.

**Architecture:** Keep the current custom LangGraph pipeline as the rollback path. Add a production adapter around `agent/research.workflow`, expose it through explicit rollout modes, validate it through live eval gates, then wire it to backend streaming and the frontend as an opt-in source before making it the default for paper-search queries.

**Tech Stack:** FastAPI, LangGraph, Vercel AI SDK v3 UI Message Stream Protocol, Next.js, Python pytest, `uv`, arXiv/Semantic Scholar/OpenAlex providers, project Makefile.

---

## Current State

The preview workflow already exists:

- `agent/research/` contains query planning, discovery providers, indexing, ranking, evidence, synthesis, evals, observability, and `run_research_preview`.
- `/api/research/preview` exists behind `RESEARCH_WORKFLOW_ENABLED=true`.
- `tests/research/` passes.
- Full backend tests previously passed with `145 passed, 30 skipped`.
- Live arXiv smoke for `ROS2 trong robotics là gì` returned ROS 2 papers including `2306.17157` and `2209.14030`.

The production chat workflow still uses:

- Non-streaming: `api/routes/chat.py::chat` -> `run_agent_graph`.
- Streaming: `api/routes/chat.py::chat_stream` -> `run_agent_retrieval` -> `stream_answer`.
- Frontend proxy: `web/src/app/api/chat/route.ts`.
- Frontend mode/source selector: `web/src/components/chat/search-mode-selector.tsx`.

## Rollout Policy

Use environment flags rather than replacing default behavior in one step:

```env
RESEARCH_WORKFLOW_ENABLED=true
RESEARCH_WORKFLOW_ROLLOUT=off
RESEARCH_WORKFLOW_SHADOW=false
RESEARCH_WORKFLOW_STREAMING=false
RESEARCH_WORKFLOW_DEFAULT_FOR_ARXIV=false
RESEARCH_PREVIEW_GENERATE=false
```

Allowed rollout values:

```python
RESEARCH_ROLLOUT_VALUES = {"off", "manual", "shadow", "arxiv", "default"}
```

Meaning:

- `off`: `/api/research/preview` can exist, but `/api/chat` never uses research workflow.
- `manual`: `/api/chat` uses research workflow only when `search_source == "research"`.
- `shadow`: `/api/chat` returns current LangGraph output but also runs research workflow in the background for metrics.
- `arxiv`: `/api/chat` uses research workflow for `search_source in {"research", "arxiv"}`.
- `default`: `/api/chat` uses research workflow for paper/research RAG queries unless the policy is static, chat-only, or out-of-scope.

Manual gates:

- A human must approve switching `RESEARCH_WORKFLOW_ROLLOUT` from `manual` to `arxiv`.
- A human must approve switching from `arxiv` to `default`.
- `RESEARCH_PREVIEW_GENERATE=true` should only be enabled after confirming the local/provider LLM key works.

## File Map

Create:

- `agent/research/rollout.py` - feature flag parsing and route decision helpers.
- `agent/research/chat_adapter.py` - converts `run_research_preview` output to chat-compatible payloads and stream events.
- `tests/research/test_rollout.py` - rollout policy tests.
- `tests/research/test_research_chat_adapter.py` - adapter tests.
- `tests/research/test_research_chat_integration.py` - backend chat/stream integration tests.
- `web/src/components/chat/search-mode-selector.test.tsx` - source selector contract if frontend test infra is available.

Modify:

- `api/models.py` - add `SearchSource.RESEARCH`.
- `api/routes/chat.py` - call adapter in manual/shadow/arxiv/default rollout modes.
- `api/streaming.py` - only if helper reuse is cleaner than local helpers in `chat_adapter.py`.
- `web/src/components/chat/search-mode-selector.tsx` - add "Research Papers" source.
- `web/src/app/chat/page.tsx` - pass `search_source: "research"` when selected.
- `web/src/app/api/chat/route.ts` - preserve request body passthrough and stream headers.
- `.env.example` - add rollout flags.
- `CLAUDE.md` - document the real workflow rollout command path.
- `docs/research-workflow/CHECKLOG.md` - record rollout decisions and verification.

---

### Task 1: Add Rollout Policy Module

**Files:**

- Create: `agent/research/rollout.py`
- Test: `tests/research/test_rollout.py`

- [ ] **Step 1: Write failing tests**

Create `tests/research/test_rollout.py`:

```python
from agent.research.rollout import ResearchRollout, should_use_research_workflow, should_shadow_research_workflow


def test_rollout_off_never_uses_research():
    rollout = ResearchRollout(mode="off", enabled=True)

    assert should_use_research_workflow(rollout, search_source="research", policy_decision="rag") is False
    assert should_shadow_research_workflow(rollout) is False


def test_rollout_manual_uses_research_source_only():
    rollout = ResearchRollout(mode="manual", enabled=True)

    assert should_use_research_workflow(rollout, search_source="research", policy_decision="rag") is True
    assert should_use_research_workflow(rollout, search_source="arxiv", policy_decision="rag") is False


def test_rollout_arxiv_uses_research_for_arxiv_and_research_sources():
    rollout = ResearchRollout(mode="arxiv", enabled=True)

    assert should_use_research_workflow(rollout, search_source="research", policy_decision="rag") is True
    assert should_use_research_workflow(rollout, search_source="arxiv", policy_decision="rag") is True
    assert should_use_research_workflow(rollout, search_source="tavily", policy_decision="rag") is False


def test_rollout_default_does_not_override_static_chat_or_out_of_scope():
    rollout = ResearchRollout(mode="default", enabled=True)

    assert should_use_research_workflow(rollout, search_source="mixed", policy_decision="rag") is True
    assert should_use_research_workflow(rollout, search_source="mixed", policy_decision="static") is False
    assert should_use_research_workflow(rollout, search_source="mixed", policy_decision="chat") is False
    assert should_use_research_workflow(rollout, search_source="mixed", policy_decision="out_of_scope") is False


def test_shadow_mode_runs_shadow_but_returns_current_pipeline():
    rollout = ResearchRollout(mode="shadow", enabled=True)

    assert should_use_research_workflow(rollout, search_source="research", policy_decision="rag") is False
    assert should_shadow_research_workflow(rollout) is True
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run pytest tests/research/test_rollout.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'agent.research.rollout'`.

- [ ] **Step 3: Implement rollout policy**

Create `agent/research/rollout.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass


RESEARCH_ROLLOUT_VALUES = {"off", "manual", "shadow", "arxiv", "default"}
NON_RAG_DECISIONS = {"static", "chat", "out_of_scope"}


@dataclass(frozen=True)
class ResearchRollout:
    mode: str = "off"
    enabled: bool = False
    streaming_enabled: bool = False


def get_research_rollout() -> ResearchRollout:
    mode = os.getenv("RESEARCH_WORKFLOW_ROLLOUT", "off").strip().lower()
    if mode not in RESEARCH_ROLLOUT_VALUES:
        mode = "off"
    return ResearchRollout(
        mode=mode,
        enabled=os.getenv("RESEARCH_WORKFLOW_ENABLED", "false").lower() == "true",
        streaming_enabled=os.getenv("RESEARCH_WORKFLOW_STREAMING", "false").lower() == "true",
    )


def should_use_research_workflow(
    rollout: ResearchRollout,
    *,
    search_source: str,
    policy_decision: str,
) -> bool:
    if not rollout.enabled or rollout.mode in {"off", "shadow"}:
        return False
    if policy_decision in NON_RAG_DECISIONS:
        return False
    if rollout.mode == "manual":
        return search_source == "research"
    if rollout.mode == "arxiv":
        return search_source in {"research", "arxiv"}
    if rollout.mode == "default":
        return True
    return False


def should_shadow_research_workflow(rollout: ResearchRollout) -> bool:
    return rollout.enabled and rollout.mode == "shadow"
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
uv run pytest tests/research/test_rollout.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add agent/research/rollout.py tests/research/test_rollout.py
git commit -m "feat(research): add workflow rollout policy"
```

---

### Task 2: Add Research Source To API Contract

**Files:**

- Modify: `api/models.py`
- Modify: `tests/test_chat_contract.py`

- [ ] **Step 1: Write failing contract test**

Append to `tests/test_chat_contract.py`:

```python
def test_chat_request_accepts_research_search_source():
    request = ChatRequest(query="ROS2 trong robotics là gì", search_source="research")

    assert request.search_source == SearchSource.RESEARCH
    assert request.search_source.value == "research"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/test_chat_contract.py::test_chat_request_accepts_research_search_source -q
```

Expected: FAIL with enum validation error for `research`.

- [ ] **Step 3: Add enum value**

Modify `api/models.py`:

```python
class SearchSource(str, Enum):
    """Search source options for retrieval-backed chat."""
    MIXED = "mixed"
    ARXIV = "arxiv"
    TAVILY = "tavily"
    RESEARCH = "research"
```

Update the `search_source` field description:

```python
description="Retrieval source when mode is 'search': 'mixed', 'arxiv', 'tavily', or 'research'",
```

- [ ] **Step 4: Run contract tests**

Run:

```bash
uv run pytest tests/test_chat_contract.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 5: Commit**

```bash
git add api/models.py tests/test_chat_contract.py
git commit -m "feat(api): add research search source"
```

---

### Task 3: Add Chat Adapter For Research Workflow

**Files:**

- Create: `agent/research/chat_adapter.py`
- Test: `tests/research/test_research_chat_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/research/test_research_chat_adapter.py`:

```python
import json

from agent.research.chat_adapter import (
    research_preview_to_chat_response,
    research_preview_to_source_events,
    stream_research_text_events,
)


def test_research_preview_to_chat_response_matches_chat_shape():
    preview = {
        "answer": "ROS 2 is middleware.",
        "citations": [
            {
                "title": "ROS 2 paper",
                "authors": ["Ada"],
                "url": "https://example.test/ros2",
                "arxiv_id": "2306.17157",
                "relevance_score": 0.91,
                "snippet": "ROS 2 middleware.",
            }
        ],
        "answerability": {"can_answer": True, "reason": "ANSWERABLE"},
        "evidence": [{"paper_id": "p1", "quote": "ROS 2 middleware."}],
        "metrics": {"paper_count": 1, "evidence_count": 1},
    }

    response = research_preview_to_chat_response(preview, session_id="s1", response_time_ms=12.5)

    assert response.answer == "ROS 2 is middleware."
    assert response.session_id == "s1"
    assert response.citations[0].arxiv_id == "2306.17157"


def test_research_preview_to_source_events_keeps_ui_stream_contract():
    preview = {
        "citations": [
            {"title": "ROS 2 paper", "url": "https://example.test/ros2"},
            {"title": "No URL", "url": ""},
        ]
    }

    events = research_preview_to_source_events(preview)

    assert len(events) == 1
    assert events[0]["type"] == "source-url"
    assert events[0]["sourceId"] == "research_source_0"


def test_stream_research_text_events_emits_vercel_ui_message_protocol():
    events = list(stream_research_text_events("msg1", "text1", "hello"))
    payloads = [json.loads(item.removeprefix("data: ").strip()) for item in events]

    assert payloads[0]["type"] == "start"
    assert payloads[1]["type"] == "text-start"
    assert payloads[2] == {"type": "text-delta", "id": "text1", "delta": "hello"}
    assert payloads[3]["type"] == "text-end"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run pytest tests/research/test_research_chat_adapter.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'agent.research.chat_adapter'`.

- [ ] **Step 3: Implement adapter**

Create `agent/research/chat_adapter.py`:

```python
from __future__ import annotations

import json
from typing import Dict, Iterable, List

from api.models import ChatResponse, Citation


def research_preview_to_chat_response(
    preview: Dict,
    *,
    session_id: str,
    response_time_ms: float,
) -> ChatResponse:
    citations = []
    for item in preview.get("citations", []) or []:
        citations.append(
            Citation(
                title=item.get("title") or "Unknown",
                authors=item.get("authors") or [],
                url=item.get("url") or "",
                arxiv_id=item.get("arxiv_id"),
                relevance_score=float(item.get("relevance_score") or 0.0),
                snippet=item.get("snippet"),
            )
        )
    return ChatResponse(
        answer=preview.get("answer") or "",
        citations=citations,
        session_id=session_id,
        response_time_ms=response_time_ms,
        tokens_used=None,
    )


def research_preview_to_source_events(preview: Dict) -> List[Dict]:
    events = []
    for index, citation in enumerate(preview.get("citations", []) or []):
        url = citation.get("url")
        if not url:
            continue
        events.append(
            {
                "type": "source-url",
                "sourceId": f"research_source_{index}",
                "url": url,
                "title": citation.get("title") or "Unknown",
            }
        )
    return events


def stream_research_text_events(message_id: str, text_id: str, answer: str) -> Iterable[str]:
    yield f'data: {json.dumps({"type": "start", "messageId": message_id})}\\n\\n'
    yield f'data: {json.dumps({"type": "text-start", "id": text_id})}\\n\\n'
    yield f'data: {json.dumps({"type": "text-delta", "id": text_id, "delta": answer})}\\n\\n'
    yield f'data: {json.dumps({"type": "text-end", "id": text_id})}\\n\\n'
```

- [ ] **Step 4: Run adapter tests**

Run:

```bash
uv run pytest tests/research/test_research_chat_adapter.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add agent/research/chat_adapter.py tests/research/test_research_chat_adapter.py
git commit -m "feat(research): add chat response adapter"
```

---

### Task 4: Wire Non-Streaming Chat In Manual Rollout

**Files:**

- Modify: `api/routes/chat.py`
- Test: `tests/research/test_research_chat_integration.py`

- [ ] **Step 1: Write failing non-streaming integration test**

Create `tests/research/test_research_chat_integration.py`:

```python
import os

from api.models import ChatRequest
from api.routes.chat import chat, sessions


def test_chat_uses_research_workflow_in_manual_rollout(monkeypatch):
    calls = {"research": 0, "legacy": 0}

    class FakeRouter:
        def route(self, query):
            from agent.query_router import RouteResult, RouteType
            return RouteResult(route_type=RouteType.RAG, intent="domain_specific")

        def get_llm_prompt(self, query, intent):
            return query

    def fake_research(query, top_k=5, providers=None):
        calls["research"] += 1
        return {
            "answer": "research answer",
            "citations": [{"title": "Paper", "url": "https://example.test", "relevance_score": 0.9}],
            "evidence": [],
            "answerability": {"can_answer": True, "reason": "ANSWERABLE"},
            "metrics": {},
        }

    def fake_legacy(*args, **kwargs):
        calls["legacy"] += 1
        return {"answer": "legacy answer", "citations": []}

    monkeypatch.setenv("RESEARCH_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_WORKFLOW_ROLLOUT", "manual")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: FakeRouter())
    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_research)
    monkeypatch.setattr("api.routes.chat.run_agent_graph", fake_legacy)
    sessions.clear()

    response = awaitable(chat(ChatRequest(query="ROS2 là gì", mode="search", search_source="research")))

    assert response.answer == "research answer"
    assert response.citations[0].title == "Paper"
    assert calls == {"research": 1, "legacy": 0}


def awaitable(coro):
    import asyncio
    return asyncio.run(coro)
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/research/test_research_chat_integration.py::test_chat_uses_research_workflow_in_manual_rollout -q
```

Expected: FAIL because `/api/chat` still calls legacy `run_agent_graph`.

- [ ] **Step 3: Implement non-streaming branch**

Modify `api/routes/chat.py` imports:

```python
from agent.research.chat_adapter import research_preview_to_chat_response
from agent.research.rollout import get_research_rollout, should_use_research_workflow
```

Inside `chat()`, after policy static/out-of-scope/chat-only handling and before `run_agent_graph`, add:

```python
        rollout = get_research_rollout()
        search_source = request.search_source.value if request.search_source else "mixed"
        if should_use_research_workflow(
            rollout,
            search_source=search_source,
            policy_decision=policy.decision.value,
        ):
            preview = await asyncio.to_thread(
                run_research_preview,
                request.query,
                top_k=request.top_k or 5,
                providers=None,
            )
            response_time_ms = (time.time() - start_time) * 1000
            return research_preview_to_chat_response(
                preview,
                session_id=session_id,
                response_time_ms=response_time_ms,
            )
```

- [ ] **Step 4: Run integration test**

Run:

```bash
uv run pytest tests/research/test_research_chat_integration.py::test_chat_uses_research_workflow_in_manual_rollout -q
```

Expected: PASS.

- [ ] **Step 5: Run related backend tests**

Run:

```bash
uv run pytest tests/research/test_research_chat_integration.py tests/test_chat_contract.py tests/test_query_policy.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add api/routes/chat.py tests/research/test_research_chat_integration.py
git commit -m "feat(api): route manual research source through research workflow"
```

---

### Task 5: Wire Streaming Chat In Manual Rollout

**Files:**

- Modify: `api/routes/chat.py`
- Test: `tests/research/test_research_chat_integration.py`
- Test: `tests/test_chat_streaming.py`

- [ ] **Step 1: Write failing streaming test**

Append to `tests/research/test_research_chat_integration.py`:

```python
import json

from api.models import ChatRequest
from api.routes.chat import chat_stream


def test_chat_stream_uses_research_workflow_in_manual_rollout(monkeypatch):
    calls = {"research": 0, "legacy": 0}

    class FakeRouter:
        def route(self, query):
            from agent.query_router import RouteResult, RouteType
            return RouteResult(route_type=RouteType.RAG, intent="domain_specific")

        def get_llm_prompt(self, query, intent):
            return query

    def fake_research(query, top_k=5, providers=None):
        calls["research"] += 1
        return {
            "answer": "research streamed answer",
            "citations": [{"title": "Paper", "url": "https://example.test", "relevance_score": 0.9}],
            "evidence": [{"paper_id": "p1", "quote": "quote"}],
            "answerability": {"can_answer": True, "reason": "ANSWERABLE"},
            "metrics": {},
        }

    def fake_legacy(*args, **kwargs):
        calls["legacy"] += 1
        return {"merged_snippets": []}

    monkeypatch.setenv("RESEARCH_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_WORKFLOW_ROLLOUT", "manual")
    monkeypatch.setenv("RESEARCH_WORKFLOW_STREAMING", "true")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: FakeRouter())
    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_research)
    monkeypatch.setattr("api.routes.chat.run_agent_retrieval", fake_legacy)

    response = awaitable(chat_stream(ChatRequest(query="ROS2 là gì", mode="search", search_source="research")))
    chunks = []
    async def collect():
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    awaitable(collect())

    body = "".join(chunks)
    assert "research streamed answer" in body
    assert '"type": "source-url"' in body
    assert calls == {"research": 1, "legacy": 0}
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/research/test_research_chat_integration.py::test_chat_stream_uses_research_workflow_in_manual_rollout -q
```

Expected: FAIL because streaming still uses `run_agent_retrieval`.

- [ ] **Step 3: Implement streaming branch**

Modify `api/routes/chat.py` imports:

```python
from agent.research.chat_adapter import (
    research_preview_to_chat_response,
    research_preview_to_source_events,
    stream_research_text_events,
)
```

Inside `chat_stream.generate()`, after static/out-of-scope/chat-only handling and before legacy retrieval:

```python
            rollout = get_research_rollout()
            search_source = request.search_source.value if request.search_source else "mixed"
            if rollout.streaming_enabled and should_use_research_workflow(
                rollout,
                search_source=search_source,
                policy_decision=policy.decision.value,
            ):
                preview = await asyncio.to_thread(
                    run_research_preview,
                    request.query,
                    top_k=request.top_k or 5,
                    providers=None,
                )
                for event in stream_research_text_events(message_id, text_id, preview.get("answer") or ""):
                    yield event
                for source_event in research_preview_to_source_events(preview):
                    yield f"data: {json.dumps(source_event)}\\n\\n"
                yield f'data: {json.dumps({"type": "finish", "finishReason": "stop"})}\\n\\n'
                return
```

- [ ] **Step 4: Run streaming tests**

Run:

```bash
uv run pytest tests/research/test_research_chat_integration.py::test_chat_stream_uses_research_workflow_in_manual_rollout tests/test_chat_streaming.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/routes/chat.py tests/research/test_research_chat_integration.py
git commit -m "feat(api): stream manual research workflow answers"
```

---

### Task 6: Add Shadow Mode Metrics Without Changing User Output

**Files:**

- Modify: `api/routes/chat.py`
- Modify: `agent/research/observability.py`
- Test: `tests/research/test_research_chat_integration.py`

- [ ] **Step 1: Write failing shadow test**

Append to `tests/research/test_research_chat_integration.py`:

```python
def test_shadow_rollout_returns_legacy_answer_and_runs_research(monkeypatch):
    calls = {"research": 0, "legacy": 0}

    class FakeRouter:
        def route(self, query):
            from agent.query_router import RouteResult, RouteType
            return RouteResult(route_type=RouteType.RAG, intent="domain_specific")

        def get_llm_prompt(self, query, intent):
            return query

    def fake_research(query, top_k=5, providers=None):
        calls["research"] += 1
        return {"answer": "research answer", "citations": [], "evidence": [], "answerability": {}, "metrics": {}}

    def fake_legacy(*args, **kwargs):
        calls["legacy"] += 1
        return {"answer": "legacy answer", "citations": []}

    monkeypatch.setenv("RESEARCH_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_WORKFLOW_ROLLOUT", "shadow")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: FakeRouter())
    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_research)
    monkeypatch.setattr("api.routes.chat.run_agent_graph", fake_legacy)

    response = awaitable(chat(ChatRequest(query="ROS2 là gì", mode="search", search_source="arxiv")))

    assert response.answer == "legacy answer"
    assert calls == {"research": 1, "legacy": 1}
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/research/test_research_chat_integration.py::test_shadow_rollout_returns_legacy_answer_and_runs_research -q
```

Expected: FAIL because no shadow branch runs.

- [ ] **Step 3: Add shadow helper**

In `api/routes/chat.py`, import:

```python
from agent.research.rollout import get_research_rollout, should_shadow_research_workflow, should_use_research_workflow
```

Add helper near `_collect_simple_llm`:

```python
async def _run_research_shadow(query: str, top_k: int | None) -> None:
    try:
        await asyncio.to_thread(run_research_preview, query, top_k=top_k or 5, providers=None)
    except Exception as exc:
        logger.warning("Research workflow shadow run failed: %s", exc)
```

Inside `chat()`, before legacy `run_agent_graph`:

```python
        rollout = get_research_rollout()
        if should_shadow_research_workflow(rollout):
            asyncio.create_task(_run_research_shadow(request.query, request.top_k))
```

For deterministic tests, use direct await when `os.getenv("PYTEST_CURRENT_TEST")` is present:

```python
        if should_shadow_research_workflow(rollout):
            if os.getenv("PYTEST_CURRENT_TEST"):
                await _run_research_shadow(request.query, request.top_k)
            else:
                asyncio.create_task(_run_research_shadow(request.query, request.top_k))
```

- [ ] **Step 4: Run shadow test**

Run:

```bash
uv run pytest tests/research/test_research_chat_integration.py::test_shadow_rollout_returns_legacy_answer_and_runs_research -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/routes/chat.py tests/research/test_research_chat_integration.py
git commit -m "feat(research): add shadow rollout mode"
```

---

### Task 7: Add Frontend Research Source Option

**Files:**

- Modify: `web/src/components/chat/search-mode-selector.tsx`
- Modify: `web/src/app/chat/page.tsx`
- Modify: `web/src/lib/api.ts`

- [ ] **Step 1: Update frontend types**

Modify `web/src/components/chat/search-mode-selector.tsx`:

```ts
export type SearchSource = "mixed" | "arxiv" | "tavily" | "research"
```

Modify `web/src/lib/api.ts`:

```ts
search_source?: "mixed" | "arxiv" | "tavily" | "research";
```

- [ ] **Step 2: Add selector option**

In `searchSources`, insert before `ArXiv Only`:

```ts
{
    value: "research" as SearchSource,
    label: "Research Papers",
    description: "Production paper workflow",
},
```

- [ ] **Step 3: Keep request body unchanged**

Confirm `web/src/app/chat/page.tsx` still sends:

```ts
{ body: { mode: searchMode, search_source: searchMode === "search" ? searchSource : undefined } }
```

No code change is needed in `web/src/app/api/chat/route.ts` because it already forwards `...body`.

- [ ] **Step 4: Run frontend lint/build**

Run:

```bash
cd web && npm run lint
cd web && npm run build
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/chat/search-mode-selector.tsx web/src/lib/api.ts
git commit -m "feat(web): add research papers search source"
```

---

### Task 8: Extend Live Eval Gates For Promotion

**Files:**

- Modify: `eval/research_eval.py`
- Modify: `Makefile`
- Test: `tests/research/test_research_eval_metrics.py`

- [ ] **Step 1: Add failing threshold test**

Append to `tests/research/test_research_eval_metrics.py`:

```python
from eval.research_eval import passes_thresholds


def test_passes_thresholds_requires_min_recall_and_precision():
    report = {"mean_recall_at_k": 0.7, "mean_precision_at_k": 0.4}

    assert passes_thresholds(report, min_recall=0.6, min_precision=0.3) is True
    assert passes_thresholds(report, min_recall=0.8, min_precision=0.3) is False
    assert passes_thresholds(report, min_recall=0.6, min_precision=0.5) is False
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/research/test_research_eval_metrics.py::test_passes_thresholds_requires_min_recall_and_precision -q
```

Expected: FAIL because `passes_thresholds` does not exist.

- [ ] **Step 3: Implement thresholds**

In `eval/research_eval.py`, add:

```python
def passes_thresholds(
    report: dict,
    *,
    min_recall: float | None = None,
    min_precision: float | None = None,
) -> bool:
    if min_recall is not None and report["mean_recall_at_k"] < min_recall:
        return False
    if min_precision is not None and report["mean_precision_at_k"] < min_precision:
        return False
    return True
```

Add CLI arg:

```python
parser.add_argument("--min-precision", type=float, default=None)
```

Replace the final threshold condition with:

```python
    if not passes_thresholds(report, min_recall=args.min_recall, min_precision=args.min_precision):
        return 1
```

- [ ] **Step 4: Add Makefile targets**

Modify `Makefile`:

```make
eval-research-live:
	@echo "📊 Running live research workflow eval..."
	uv run python eval/research_eval.py --dataset eval/research_golden_set.jsonl --top-k 10

eval-research-gate:
	@echo "🚦 Running gated research workflow eval..."
	uv run python eval/research_eval.py --dataset eval/research_golden_set.jsonl --top-k 10 --min-recall 0.55 --min-precision 0.35
```

- [ ] **Step 5: Run eval tests and dry-run**

Run:

```bash
uv run pytest tests/research/test_research_eval_metrics.py -q
uv run python eval/research_eval.py --dataset eval/research_golden_set.jsonl --dry-run --min-recall 0.0 --min-precision 0.0
```

Expected: tests pass and dry-run exits `0`.

- [ ] **Step 6: Manual live eval gate**

Run with network access and provider config:

```bash
make eval-research-live
```

If the live eval exits `0`, record a row like this in
`docs/research-workflow/CHECKLOG.md` with the exact metric values printed by
the command:

```markdown
| 2026-05-31 | `make eval-research-live` | Passed | mean_recall_at_k=0.61, mean_precision_at_k=0.38. |
```

If the live eval exits non-zero, record a row like this and stop promotion:

```markdown
| 2026-05-31 | `make eval-research-live` | Failed | mean_recall_at_k=0.42, mean_precision_at_k=0.21; keep rollout at `manual`. |
```

- [ ] **Step 7: Commit**

```bash
git add eval/research_eval.py Makefile tests/research/test_research_eval_metrics.py docs/research-workflow/CHECKLOG.md
git commit -m "feat(eval): add research workflow promotion gates"
```

---

### Task 9: Promote ArXiv Mode After Manual Approval

**Files:**

- Modify: `.env.example`
- Modify: `docs/research-workflow/CHECKLOG.md`
- Test: no code test; this is a config/documentation gate.

- [ ] **Step 1: Verify promotion prerequisites**

Run:

```bash
uv run pytest tests/ -q
make eval-research-gate
```

Expected:

- Python tests pass.
- Eval gate exits `0`.
- `CHECKLOG.md` contains live eval values.

- [ ] **Step 2: Ask for manual approval**

Ask the user:

```text
Live eval gate passed. Do you approve changing rollout recommendation from manual to arxiv?
```

Proceed only after explicit approval.

- [ ] **Step 3: Update recommended config**

Modify `.env.example`:

```env
RESEARCH_WORKFLOW_ROLLOUT=manual
RESEARCH_WORKFLOW_STREAMING=false
```

Do not set `.env` directly. The user owns secret/local runtime config.

- [ ] **Step 4: Record decision**

Append to `docs/research-workflow/CHECKLOG.md` Decisions:

```markdown
| 2026-05-31 | Keep `.env.example` rollout at `manual` until user explicitly promotes runtime config. | The repo template should remain safe even if live eval passes locally. | Accepted |
```

- [ ] **Step 5: Commit**

```bash
git add .env.example docs/research-workflow/CHECKLOG.md
git commit -m "docs(research): document safe rollout config"
```

---

### Task 10: Production Smoke Test With UI

**Files:**

- Modify only docs unless a bug is found.
- Update: `docs/research-workflow/CHECKLOG.md`

- [ ] **Step 1: Start backend and frontend**

Run:

```bash
make run-api
make run-web
```

Expected:

- Backend listens on `http://localhost:8000`.
- Frontend listens on `http://localhost:3000`.

- [ ] **Step 2: Set local runtime config manually**

The user should set these in local `.env`; do not print or inspect the file:

```env
RESEARCH_WORKFLOW_ENABLED=true
RESEARCH_WORKFLOW_ROLLOUT=manual
RESEARCH_WORKFLOW_STREAMING=true
RESEARCH_PREVIEW_GENERATE=false
```

- [ ] **Step 3: Manual UI smoke**

In the UI:

```text
Mode: Search DB -> Research Papers
Question: ROS2 trong robotics là gì
```

Expected:

- The answer streams without protocol errors.
- Source citations appear.
- Sources include ROS 2/arXiv papers.
- No static/chat-only/out-of-scope path is affected.

- [ ] **Step 4: Backend curl smoke**

Run:

```bash
curl -N http://localhost:8000/api/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"query":"ROS2 trong robotics là gì","mode":"search","search_source":"research","top_k":3}'
```

Expected stream contains:

```text
"type": "start"
"type": "text-start"
"type": "text-delta"
"type": "source-url"
"type": "finish"
```

- [ ] **Step 5: Record result**

If the smoke test passes, append this shape to
`docs/research-workflow/CHECKLOG.md` with the actual source titles observed:

```markdown
| 2026-05-31 | Manual UI smoke: Research Papers source with `ROS2 trong robotics là gì` | Passed | Sources included `FogROS2-SGC` and `Monitoring ROS2`; stream rendered source cards. |
```

If the smoke test fails, append this shape and keep rollout below `arxiv`:

```markdown
| 2026-05-31 | Manual UI smoke: Research Papers source with `ROS2 trong robotics là gì` | Failed | Stream rendered text but no source cards; keep rollout at `manual`. |
```

- [ ] **Step 6: Commit docs if updated**

```bash
git add docs/research-workflow/CHECKLOG.md
git commit -m "docs(research): record production rollout smoke"
```

---

## Rollback Plan

Immediate rollback is config-only:

```env
RESEARCH_WORKFLOW_ROLLOUT=off
RESEARCH_WORKFLOW_STREAMING=false
```

This keeps `/api/research/preview` available when `RESEARCH_WORKFLOW_ENABLED=true`, but `/api/chat` returns to the current LangGraph path.

If a code rollback is required, revert the commits from Tasks 1-7 in reverse order. Do not revert the original `agent/research/` preview package unless the preview route itself is broken.

## Acceptance Criteria

- `uv run pytest tests/ -q` passes.
- `cd web && npm run lint` passes.
- `cd web && npm run build` passes.
- `make eval-research-gate` passes before `arxiv` rollout.
- Manual UI smoke passes before any `default` rollout.
- Existing static/chat-only/out-of-scope paths continue to short-circuit without research provider calls.
- Streaming response keeps `x-vercel-ai-ui-message-stream: v1`.

## Manual Decisions Needed

- Whether to provide `SEMANTIC_SCHOLAR_API_KEY` and `OPENALEX_MAILTO` for live eval reliability.
- Whether to enable `RESEARCH_PREVIEW_GENERATE=true` after verifying LLM provider credentials.
- Whether to promote rollout from `manual` to `arxiv`.
- Whether to promote rollout from `arxiv` to `default`.
