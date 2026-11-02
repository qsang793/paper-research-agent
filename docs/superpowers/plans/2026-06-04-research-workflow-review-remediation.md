# Research Workflow Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Repo rule (overrides any skill default): NEVER run `git commit`.** Each task ends with a *suggested* commit message — surface it to the user; the user commits.

**Goal:** Fix the promotion blockers and mechanical findings from `docs/research-workflow/REVIEW_2026-06-04.md` so the research workflow rollout ladder (`off → manual → shadow → arxiv → default`) becomes measurable, honest to users, and promotable.

**Architecture:** All fixes stay behind the existing rollout flags — default behavior remains unchanged (`RESEARCH_WORKFLOW_ENABLED=false`). Shadow execution moves to FastAPI/Starlette background-task primitives (deterministic in tests, no GC footgun, no test-runner detection in prod code). The eval gate learns to distinguish infra failure (provider 429/timeout → zero candidates) from quality failure and reports `PASS | FAIL | INCONCLUSIVE`. Chat-facing research calls always generate real answers; the deterministic placeholder stays only on the dev-facing `/api/research/preview`. The frontend hides the "Research Papers" option unless the backend reports it available.

**Tech Stack:** FastAPI/Starlette (BackgroundTasks/BackgroundTask), pytest + fastapi.testclient, Next.js 16 / React 19, Makefile targets, UV.

**Decisions baked into this plan (alternatives considered):**
1. *Eval infra detection:* a labeled row with **zero candidates** in a live run is counted `no_candidate` and excluded from recall/precision means; gate returns `INCONCLUSIVE` (exit 2) when `no_candidate_rate > 0.2`. (Alternative — plumbing per-provider error reporting through `discover_papers` — rejected as a larger contract change; revisit if the heuristic proves too coarse.)
2. *Pacing:* sleep between eval rows (`--sleep 3` in the gate target) instead of inside `arxiv_provider`, so production chat latency is untouched.
3. *Shadow:* `BackgroundTasks` (non-streaming) and `StreamingResponse(background=...)` (streaming) instead of `asyncio.create_task` — fixes M1 (GC footgun) and M2 (`PYTEST_CURRENT_TEST`) at once, because Starlette runs background work inside the request lifecycle (TestClient waits for it).
4. *Config cliff:* chat paths call `run_research_preview(..., generate=True)`; the env flag `RESEARCH_PREVIEW_GENERATE` now only affects `/api/research/preview`. Shadow runs keep `generate` unset (no LLM cost for observability). The remaining deterministic messages keep the codebase's unaccented-Vietnamese style (see `agent/answerability.py:32-38`) but never mention env vars.
5. *UI gating:* new `GET /api/features` endpoint; frontend hides the "Research Papers" option when unavailable (fail-closed on fetch error).

---

## File Structure

| File | Change |
|---|---|
| `eval/research_eval.py` | Add `--sleep`, no-candidate accounting, `gate_verdict()` (PASS/FAIL/INCONCLUSIVE), exit code 2 |
| `tests/research/test_research_eval_metrics.py` | Tests for `gate_verdict` |
| `Makefile` | `eval-research-gate` gains `--sleep 3` |
| `agent/research/ranking/reranker.py` | Log cross-encoder failures (M3) |
| `tests/research/test_reranker.py` | New — failure-logging test |
| `agent/research/rollout.py` | Add `is_research_search_available()` |
| `tests/research/test_rollout.py` | Tests for the new helper |
| `api/routes/chat.py` | BackgroundTasks shadow (M1/M2), streaming shadow (3.1), streaming ladder unification (3.5), `generate=True` (3.3), `/api/features` (3.4) |
| `tests/research/test_research_chat_integration.py` | Updated fakes + new shadow/streaming/features tests |
| `agent/research/workflow.py` | `generate` parameter; placeholder message without env hint |
| `web/src/lib/api.ts` | `getFeatures()` |
| `web/src/app/chat/page.tsx` | Fetch features, thread `researchAvailable` |
| `web/src/components/chat/chat-input.tsx` | Forward `researchAvailable` prop |
| `web/src/components/chat/search-mode-selector.tsx` | Filter sources by availability |
| `.env.example` | Clarifying comment for `RESEARCH_PREVIEW_GENERATE` |
| `docs/research-workflow/CHECKLOG.md` | New decisions + verification entries; fix stale handoff note |

Conventions: absolute imports, `os.getenv` with defaults, node/test style mirrors existing files. Run all Python commands with `uv run`.

---

### Task 1: Eval gate — pacing + INCONCLUSIVE verdict

**Files:**
- Modify: `eval/research_eval.py`
- Modify: `tests/research/test_research_eval_metrics.py`
- Modify: `Makefile` (target `eval-research-gate`)

- [ ] **Step 1: Write the failing tests**

Append to `tests/research/test_research_eval_metrics.py` (import style at the top of that file already includes `from eval.research_eval import passes_thresholds, run_eval` — extend it to also import `gate_verdict`):

```python
def test_gate_verdict_passes_when_no_thresholds():
    report = {
        "paper_labeled_query_count": 0,
        "no_candidate_query_count": 0,
        "mean_recall_at_k": 0.0,
        "mean_precision_at_k": 0.0,
    }
    assert gate_verdict(report, min_recall=None, min_precision=None) == "PASS"


def test_gate_verdict_pass_fail_and_inconclusive():
    base = {
        "paper_labeled_query_count": 26,
        "no_candidate_query_count": 1,
        "mean_recall_at_k": 0.7,
        "mean_precision_at_k": 0.4,
    }
    assert gate_verdict(base, min_recall=0.55, min_precision=0.35) == "PASS"
    assert (
        gate_verdict({**base, "mean_recall_at_k": 0.3}, min_recall=0.55, min_precision=0.35)
        == "FAIL"
    )
    inconclusive = {**base, "no_candidate_query_count": 10}
    assert (
        gate_verdict(inconclusive, min_recall=0.55, min_precision=0.35)
        == "INCONCLUSIVE"
    )


def test_run_eval_dry_run_keeps_labeled_rows_scored(tmp_path):
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(
        '{"id":"a","query":"q1","task_type":"concept","expected_papers":["1111.11111"]}\n'
        '{"id":"b","query":"q2","task_type":"concept"}\n',
        encoding="utf-8",
    )
    report = run_eval(dataset, dry_run=True, top_k=5)
    assert report["paper_labeled_query_count"] == 1
    assert report["paper_scored_query_count"] == 1
    assert report["no_candidate_query_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/research/test_research_eval_metrics.py -q`
Expected: FAIL with `ImportError: cannot import name 'gate_verdict'`

- [ ] **Step 3: Implement in `eval/research_eval.py`**

Add `import time` to the imports. Replace `run_eval` with:

```python
def run_eval(
    dataset_path: Path,
    *,
    dry_run: bool = False,
    top_k: int = 10,
    sleep_seconds: float = 0.0,
) -> dict:
    rows = load_golden_dataset(dataset_path)
    results = []
    recall_values = []
    precision_values = []
    no_candidate_count = 0

    for index, row in enumerate(rows):
        if sleep_seconds > 0 and index > 0 and not dry_run:
            time.sleep(sleep_seconds)
        candidates = [] if dry_run else discover_papers(row.query, max_results=top_k)
        recall = paper_recall_at_k(candidates, row.expected_papers, k=top_k)
        precision = paper_precision_at_k(candidates, row.expected_papers, k=top_k)
        has_expected_papers = bool(row.expected_papers)
        # A labeled row with zero candidates in a live run almost always means
        # provider 429/timeout (providers fail soft and return []). Count it as
        # inconclusive infra data instead of recall=0 quality data.
        no_candidates = not dry_run and has_expected_papers and not candidates
        if no_candidates:
            no_candidate_count += 1
        elif has_expected_papers:
            recall_values.append(recall)
            precision_values.append(precision)
        results.append(
            {
                "id": row.id,
                "query": row.query,
                "task_type": row.task_type,
                "candidate_count": len(candidates),
                "no_candidates": no_candidates,
                "recall_at_k": recall,
                "precision_at_k": precision,
                "top_papers": [
                    {
                        "title": candidate.title,
                        "arxiv_id": candidate.arxiv_id,
                        "doi": candidate.doi,
                        "score": candidate.score,
                    }
                    for candidate in candidates[:top_k]
                ],
            }
        )

    labeled_count = sum(1 for row in rows if row.expected_papers)
    return {
        "dataset": str(dataset_path),
        "dry_run": dry_run,
        "query_count": len(rows),
        "paper_labeled_query_count": labeled_count,
        "paper_unlabeled_query_count": len(rows) - labeled_count,
        "paper_scored_query_count": len(recall_values),
        "no_candidate_query_count": no_candidate_count,
        "mean_recall_at_k": sum(recall_values) / len(recall_values) if recall_values else 0.0,
        "mean_precision_at_k": sum(precision_values) / len(precision_values) if precision_values else 0.0,
        "results": results,
    }
```

Keep `passes_thresholds` unchanged. Add below it:

```python
def gate_verdict(
    report: dict,
    *,
    min_recall: float | None = None,
    min_precision: float | None = None,
    max_no_candidate_rate: float = 0.2,
) -> str:
    """PASS/FAIL on thresholds, INCONCLUSIVE when too many labeled rows had no data."""
    if min_recall is None and min_precision is None:
        return "PASS"
    labeled = report.get("paper_labeled_query_count") or 0
    no_candidates = report.get("no_candidate_query_count") or 0
    if labeled and no_candidates / labeled > max_no_candidate_rate:
        return "INCONCLUSIVE"
    if passes_thresholds(report, min_recall=min_recall, min_precision=min_precision):
        return "PASS"
    return "FAIL"
```

In `main()`, add the new arguments and replace the exit logic:

```python
    parser.add_argument("--sleep", type=float, default=0.0,
                        help="Seconds to sleep between live queries (provider pacing)")
    parser.add_argument("--max-no-candidate-rate", type=float, default=0.2,
                        help="Labeled-row no-candidate rate above which the gate is INCONCLUSIVE")
```

```python
    report = run_eval(
        Path(args.dataset), dry_run=args.dry_run, top_k=args.top_k, sleep_seconds=args.sleep
    )
```

```python
    verdict = gate_verdict(
        report,
        min_recall=args.min_recall,
        min_precision=args.min_precision,
        max_no_candidate_rate=args.max_no_candidate_rate,
    )
    print(f"GATE VERDICT: {verdict}", file=sys.stderr)
    if verdict == "FAIL":
        return 1
    if verdict == "INCONCLUSIVE":
        return 2
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/research/test_research_eval_metrics.py -q`
Expected: PASS (all, including pre-existing tests)

- [ ] **Step 5: Update Makefile gate target**

```makefile
eval-research-gate:
	@echo "📊 Running live research workflow promotion gate..."
	uv run python eval/research_eval.py --dataset eval/research_golden_set.jsonl --top-k 10 --min-recall 0.55 --min-precision 0.35 --sleep 3
```

- [ ] **Step 6: Verify dry-run target still works**

Run: `make eval-research`
Expected: JSON report printed, exit 0, `"paper_labeled_query_count": 26`

- [ ] **Step 7: Suggest commit (user runs it)**

```
fix(eval): separate infra failure from quality failure in promotion gate
```

---

### Task 2: Reranker — log cross-encoder failures (M3)

**Files:**
- Modify: `agent/research/ranking/reranker.py:35-43`
- Create: `tests/research/test_reranker.py`

- [ ] **Step 1: Write the failing test**

Create `tests/research/test_reranker.py`:

```python
from agent.research.discovery.models import PaperCandidate
from agent.research.query_plan import plan_research_query
from agent.research.ranking.reranker import rank_candidates


def _candidates():
    return [
        PaperCandidate(title="ROS 2 middleware", abstract="robotics middleware"),
        PaperCandidate(title="Unrelated", abstract="cooking"),
    ]


def test_rank_candidates_logs_cross_encoder_failure(caplog):
    plan = plan_research_query("ROS2 middleware")

    def broken_cross_encoder(pairs):
        raise RuntimeError("model exploded")

    with caplog.at_level("WARNING", logger="agent.research.ranking.reranker"):
        ranked = rank_candidates(plan, _candidates(), cross_encoder=broken_cross_encoder)

    assert len(ranked) == 2  # ranking still succeeds on base scores
    assert "Cross-encoder rerank failed" in caplog.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/research/test_reranker.py -q`
Expected: FAIL — `assert "Cross-encoder rerank failed" in caplog.text` (nothing logged)

- [ ] **Step 3: Implement**

In `agent/research/ranking/reranker.py`, add after the existing imports:

```python
import logging

logger = logging.getLogger(__name__)
```

Replace the bare `except Exception: pass` (lines 42-43) with:

```python
        except Exception:
            logger.warning("Cross-encoder rerank failed; using base scores", exc_info=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/research/test_reranker.py -q`
Expected: PASS

- [ ] **Step 5: Suggest commit (user runs it)**

```
fix(research): log cross-encoder rerank failures instead of silently passing
```

---

### Task 3: Rollout availability helper + `GET /api/features`

**Files:**
- Modify: `agent/research/rollout.py`
- Modify: `tests/research/test_rollout.py`
- Modify: `api/routes/chat.py` (new endpoint on the existing `router = APIRouter(prefix="/api", tags=["chat"])`)
- Modify: `tests/research/test_research_chat_integration.py`

- [ ] **Step 1: Write the failing unit tests**

Append to `tests/research/test_rollout.py` (it already imports from `agent.research.rollout`; extend the import to include `is_research_search_available` and `ResearchRollout` if not present):

```python
def test_research_search_available_requires_enabled_streaming_and_active_mode():
    assert is_research_search_available(
        ResearchRollout(mode="manual", enabled=True, streaming_enabled=True)
    )
    assert is_research_search_available(
        ResearchRollout(mode="arxiv", enabled=True, streaming_enabled=True)
    )
    assert is_research_search_available(
        ResearchRollout(mode="default", enabled=True, streaming_enabled=True)
    )


def test_research_search_unavailable_when_off_shadow_disabled_or_not_streaming():
    assert not is_research_search_available(
        ResearchRollout(mode="off", enabled=True, streaming_enabled=True)
    )
    assert not is_research_search_available(
        ResearchRollout(mode="shadow", enabled=True, streaming_enabled=True)
    )
    assert not is_research_search_available(
        ResearchRollout(mode="manual", enabled=False, streaming_enabled=True)
    )
    assert not is_research_search_available(
        ResearchRollout(mode="manual", enabled=True, streaming_enabled=False)
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/research/test_rollout.py -q`
Expected: FAIL with `ImportError: cannot import name 'is_research_search_available'`

- [ ] **Step 3: Implement the helper**

Append to `agent/research/rollout.py`:

```python
def is_research_search_available(rollout: ResearchRollout) -> bool:
    """Whether the streaming chat UI can reach the research workflow."""
    return (
        rollout.enabled
        and rollout.streaming_enabled
        and rollout.mode in {"manual", "arxiv", "default"}
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/research/test_rollout.py -q`
Expected: PASS

- [ ] **Step 5: Write the failing endpoint test**

Append to `tests/research/test_research_chat_integration.py`:

```python
def test_features_reports_research_search_availability(monkeypatch):
    for var in [
        "RESEARCH_WORKFLOW_ENABLED",
        "RESEARCH_WORKFLOW_ROLLOUT",
        "RESEARCH_WORKFLOW_STREAMING",
    ]:
        monkeypatch.delenv(var, raising=False)
    client = TestClient(app)
    assert client.get("/api/features").json() == {"research_search_available": False}

    monkeypatch.setenv("RESEARCH_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_WORKFLOW_ROLLOUT", "manual")
    monkeypatch.setenv("RESEARCH_WORKFLOW_STREAMING", "true")
    assert client.get("/api/features").json() == {"research_search_available": True}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/research/test_research_chat_integration.py::test_features_reports_research_search_availability -q`
Expected: FAIL with 404

- [ ] **Step 7: Implement the endpoint**

In `api/routes/chat.py`, extend the rollout import block to include `is_research_search_available`, then add (next to `research_preview`):

```python
@router.get("/features")
async def features():
    """Feature availability flags for the frontend (config-driven, no auth)."""
    rollout = get_research_rollout()
    return {"research_search_available": is_research_search_available(rollout)}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/research/test_research_chat_integration.py::test_features_reports_research_search_availability -q`
Expected: PASS

- [ ] **Step 9: Suggest commit (user runs it)**

```
feat(api): expose research search availability via /api/features
```

---

### Task 4: Non-streaming shadow via BackgroundTasks (fixes M1 + M2)

**Files:**
- Modify: `api/routes/chat.py` (imports, `chat()` signature, shadow branch at ~lines 268-277)

- [ ] **Step 1: Change the import**

In `api/routes/chat.py` replace:

```python
from fastapi import APIRouter, HTTPException
```

with:

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException
```

- [ ] **Step 2: Update `chat()` signature**

```python
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
```

- [ ] **Step 3: Replace the shadow branch**

Replace:

```python
        if should_shadow_research_workflow(rollout):
            shadow = _run_research_shadow(
                request.query,
                top_k=request.top_k,
                memory=memory,
            )
            if os.getenv("PYTEST_CURRENT_TEST"):
                await shadow
            else:
                asyncio.create_task(shadow)
```

with:

```python
        if should_shadow_research_workflow(rollout):
            # Starlette runs this after the response is sent — no GC'able task,
            # deterministic in TestClient.
            background_tasks.add_task(
                _run_research_shadow,
                request.query,
                top_k=request.top_k,
                memory=memory,
            )
```

`_run_research_shadow` itself is unchanged (it already wraps `asyncio.to_thread` and swallows/logs failures).

- [ ] **Step 4: Run the existing shadow tests**

Run: `uv run pytest tests/research/test_research_chat_integration.py -q -k shadow`
Expected: PASS (`test_shadow_rollout_returns_legacy_answer_and_records_metrics`, `test_shadow_research_failure_returns_legacy_answer_and_logs_warning`) — Starlette executes background tasks inside the TestClient request, so the caplog assertions still hold without the `PYTEST_CURRENT_TEST` hack.

- [ ] **Step 5: Run the whole integration file + grep for the removed hack**

Run: `uv run pytest tests/research/test_research_chat_integration.py -q && grep -c "PYTEST_CURRENT_TEST" api/routes/chat.py`
Expected: tests PASS; grep prints `0` (grep exits 1 on zero matches — that is the expected "clean" outcome)

- [ ] **Step 6: Suggest commit (user runs it)**

```
fix(api): run research shadow via BackgroundTasks instead of orphaned asyncio task
```

---

### Task 5: Shadow mode for `/api/chat/stream` (finding 3.1)

**Files:**
- Modify: `api/routes/chat.py` (`chat_stream`, lines ~360-560)
- Modify: `tests/research/test_research_chat_integration.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/research/test_research_chat_integration.py`. Note: streaming tests in this file call `chat_stream()` directly, so the test executes `response.background` explicitly after draining the stream:

```python
def test_chat_stream_shadow_rollout_keeps_legacy_stream_and_records_metrics(monkeypatch, caplog):
    calls = {"research": 0, "legacy": 0}

    monkeypatch.setenv("RESEARCH_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_WORKFLOW_ROLLOUT", "shadow")
    monkeypatch.setenv("RESEARCH_WORKFLOW_STREAMING", "false")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: _RagRouter())

    def fake_research_preview(query, top_k=5, providers=None):
        calls["research"] += 1
        return {
            "answer": "shadow answer",
            "citations": [],
            "evidence": [],
            "answerability": {"can_answer": True, "reason": "ANSWERABLE"},
            "metrics": {"ranked_papers": 3},
        }

    def fake_legacy_retrieval(**kwargs):
        calls["legacy"] += 1
        return {
            "merged_snippets": [{"text": "legacy snippet", "metadata": {}}],
            "memory_context": "",
            "answerability": {"can_answer": True},
            "sources": [],
        }

    async def fake_stream_answer(**kwargs):
        yield "legacy streamed answer"

    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_research_preview)
    monkeypatch.setattr("api.routes.chat.run_agent_retrieval", fake_legacy_retrieval)
    monkeypatch.setattr("api.routes.chat.stream_answer", fake_stream_answer)

    response = _await(chat_stream(ChatRequest(query="shadow stream query", mode="search")))
    events = _collect_stream_events(response)

    assert _event_text(events) == "legacy streamed answer"
    assert calls == {"research": 0, "legacy": 1}  # shadow has not run yet

    with caplog.at_level("INFO", logger="api.routes.chat"):
        assert response.background is not None
        _await(response.background())

    assert calls == {"research": 1, "legacy": 1}
    assert "Research workflow shadow run completed" in caplog.text


def test_chat_stream_static_query_does_not_shadow(monkeypatch):
    calls = {"research": 0}

    monkeypatch.setenv("RESEARCH_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_WORKFLOW_ROLLOUT", "shadow")

    class _StaticRouter:
        def route(self, query):
            return RouteResult(
                route_type=RouteType.STATIC, intent="greeting",
                confidence=1.0, response="Hello!",
            )

    monkeypatch.setattr("api.routes.chat.get_router", lambda: _StaticRouter())

    def fake_research_preview(*args, **kwargs):
        calls["research"] += 1
        raise AssertionError("static queries must not be shadowed")

    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_research_preview)

    response = _await(chat_stream(ChatRequest(query="hello", mode="auto")))
    _collect_stream_events(response)
    if response.background is not None:
        _await(response.background())

    assert calls == {"research": 0}
```

(If `RouteResult` in `agent/query_router.py` uses a different field than `response` for the static reply, mirror whatever `_RagRouter`-adjacent fakes in `tests/test_chat_streaming.py` use.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/research/test_research_chat_integration.py -q -k "chat_stream_shadow or static_query_does_not_shadow"`
Expected: first test FAILS (`calls == {"research": 1, ...}` assertion — shadow never runs / background is None)

- [ ] **Step 3: Implement**

In `api/routes/chat.py`:

1. Add to the imports: `from starlette.background import BackgroundTask`
2. In `chat_stream`, immediately before `async def generate():`, add:

```python
    # Set inside generate() once the request is known to reach the RAG path;
    # executed by Starlette after the stream completes.
    shadow_state = {"pending": False}

    async def _run_shadow_after_stream() -> None:
        if shadow_state["pending"]:
            await _run_research_shadow(
                request.query,
                top_k=request.top_k,
                memory=memory,
            )
```

3. Inside `generate()`, right after the research-streaming branch (`return` at ~line 452) and before the `# Full RAG pipeline for domain-specific queries` comment, add:

```python
            if should_shadow_research_workflow(rollout):
                shadow_state["pending"] = True
```

4. Attach the background task to the response:

```python
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "x-vercel-ai-ui-message-stream": "v1",
        },
        background=BackgroundTask(_run_shadow_after_stream),
    )
```

(Keep the existing `headers` dict exactly as it currently is in the file — the snippet above shows the shape; only `background=` is new.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/research/test_research_chat_integration.py -q`
Expected: PASS (new tests + all existing streaming tests — static/chitchat paths never set the flag)

- [ ] **Step 5: Suggest commit (user runs it)**

```
feat(api): run research shadow mode on the streaming chat path
```

---

### Task 6: Unify the streaming rollout ladder (finding 3.5)

**Files:**
- Modify: `api/routes/chat.py:424-432`
- Modify: `tests/research/test_research_chat_integration.py:433-466`

- [ ] **Step 1: Rewrite the arxiv-mode streaming test to expect research**

Replace `test_chat_stream_arxiv_rollout_uses_legacy_even_when_streaming_enabled` (lines 433-466) with:

```python
def test_chat_stream_arxiv_rollout_uses_research_when_streaming_enabled(monkeypatch):
    calls = {"research": 0, "legacy": 0}

    monkeypatch.setenv("RESEARCH_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_WORKFLOW_ROLLOUT", "arxiv")
    monkeypatch.setenv("RESEARCH_WORKFLOW_STREAMING", "true")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: _RagRouter())

    def fake_research_preview(query, top_k=5, providers=None):
        calls["research"] += 1
        return {
            "answer": "arxiv research streamed answer",
            "citations": [{"title": "Arxiv paper", "url": "https://example.test/arxiv", "relevance_score": 0.9}],
            "evidence": [],
            "answerability": {"can_answer": True, "reason": "ANSWERABLE"},
            "metrics": {},
        }

    def fake_legacy_retrieval(**kwargs):
        calls["legacy"] += 1
        return {"merged_snippets": []}

    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_research_preview)
    monkeypatch.setattr("api.routes.chat.run_agent_retrieval", fake_legacy_retrieval)

    response = _await(chat_stream(ChatRequest(query="arxiv ROS2 papers", mode="search", search_source="arxiv")))
    events = _collect_stream_events(response)

    assert _event_text(events) == "arxiv research streamed answer"
    assert calls == {"research": 1, "legacy": 0}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/research/test_research_chat_integration.py -q -k arxiv_rollout`
Expected: FAIL (`calls == {"research": 0, "legacy": 1}` — streaming branch is still manual-only)

- [ ] **Step 3: Implement**

In `api/routes/chat.py` `chat_stream` (~line 424), replace:

```python
            if (
                rollout.mode == "manual"
                and rollout.streaming_enabled
                and should_use_research_workflow(
                    rollout,
                    search_source=search_source,
                    policy_decision=policy.decision.value,
                )
            ):
```

with:

```python
            if rollout.streaming_enabled and should_use_research_workflow(
                rollout,
                search_source=search_source,
                policy_decision=policy.decision.value,
            ):
```

- [ ] **Step 4: Run the full integration file**

Run: `uv run pytest tests/research/test_research_chat_integration.py -q`
Expected: PASS — `test_chat_stream_manual_research_uses_legacy_when_streaming_disabled` still passes (the `streaming_enabled` flag remains the streaming kill-switch).

- [ ] **Step 5: Suggest commit (user runs it)**

```
feat(api): honor arxiv/default rollout modes on the streaming chat path
```

---

### Task 7: Always generate real answers in chat research paths (finding 3.3)

**Files:**
- Modify: `agent/research/workflow.py`
- Modify: `api/routes/chat.py` (`_run_research_chat_response`, `_run_research_stream_preview`)
- Modify: `tests/research/test_research_chat_integration.py` (all `fake_research_preview` signatures)
- Modify: `.env.example`

- [ ] **Step 1: Write the failing tests**

Append to `tests/research/test_research_chat_integration.py`:

```python
def test_manual_research_chat_forces_generation(monkeypatch):
    monkeypatch.setenv("RESEARCH_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_WORKFLOW_ROLLOUT", "manual")
    monkeypatch.setenv("RESEARCH_PREVIEW_GENERATE", "false")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: _RagRouter())

    seen = {}

    def fake_research_preview(query, top_k=5, providers=None, generate=None):
        seen["generate"] = generate
        return {"answer": "generated answer", "citations": []}

    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_research_preview)
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        json={"query": "ROS2 trong robotics là gì", "mode": "search", "search_source": "research"},
    )

    assert response.status_code == 200
    assert seen["generate"] is True


def test_research_stream_skips_memory_when_not_answerable(monkeypatch):
    monkeypatch.setenv("RESEARCH_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_WORKFLOW_ROLLOUT", "manual")
    monkeypatch.setenv("RESEARCH_WORKFLOW_STREAMING", "true")
    monkeypatch.setattr("api.routes.chat.get_router", lambda: _RagRouter())

    memory = _EmptyFakeMemory()
    sessions["no-answer-session"] = memory

    def fake_research_preview(query, top_k=5, providers=None, generate=None):
        return {
            "answer": "Khong tim thay paper phu hop cho cau hoi nay.",
            "citations": [],
            "evidence": [],
            "answerability": {"can_answer": False, "reason": "NO_PAPER_FOUND"},
            "metrics": {},
        }

    monkeypatch.setattr("api.routes.chat.run_research_preview", fake_research_preview)

    response = _await(
        chat_stream(
            ChatRequest(
                query="obscure topic",
                session_id="no-answer-session",
                mode="search",
                search_source="research",
            )
        )
    )
    _collect_stream_events(response)

    assert memory.add_calls == []


def test_deterministic_preview_answer_never_mentions_env_vars():
    from agent.research.workflow import _deterministic_preview_answer

    for evidence_count, paper_count in [(0, 0), (0, 2), (3, 2)]:
        assert "RESEARCH_PREVIEW_GENERATE" not in _deterministic_preview_answer(
            evidence_count, paper_count
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/research/test_research_chat_integration.py -q -k "forces_generation or skips_memory or never_mentions"`
Expected: FAIL — `seen["generate"] is None`, `memory.add_calls` non-empty, env var present in message

- [ ] **Step 3: Implement `generate` parameter in `agent/research/workflow.py`**

Change the placeholder message (line 30) to drop the env hint:

```python
    return f"Da tim thay {evidence_count} evidence span tu {paper_count} paper ung vien."
```

Change the signature and the synthesis branch:

```python
def run_research_preview(
    query: str,
    *,
    top_k: int = 5,
    providers: List[str] | None = None,
    generate: bool | None = None,
) -> Dict:
```

```python
    generate_enabled = (
        generate
        if generate is not None
        else os.getenv("RESEARCH_PREVIEW_GENERATE", "false").lower() == "true"
    )
    answerability = assess_evidence_answerability(evidence, paper_count=len(ranked))
    with trace.span("synthesis", can_answer=answerability["can_answer"]):
        if answerability["can_answer"] and generate_enabled:
            answer = generate_claim_grounded_answer(query, evidence)
        else:
            answer = _deterministic_preview_answer(len(evidence), len(ranked))
```

- [ ] **Step 4: Wire chat paths in `api/routes/chat.py`**

In `_run_research_chat_response`, pass `generate=True` and skip memory on no-answer:

```python
    preview = run_research_preview(
        enhanced_query,
        top_k=top_k or 5,
        providers=None,
        generate=True,
    )
```

```python
    can_answer = (preview.get("answerability") or {}).get("can_answer", True)
    if memory and response.answer and can_answer:
        citation_urls = [citation.url for citation in response.citations if citation.url]
        memory.add(query, response.answer, citation_urls)
```

In `_run_research_stream_preview`, same two changes:

```python
    preview = run_research_preview(
        enhanced_query,
        top_k=top_k or 5,
        providers=None,
        generate=True,
    )
    answer = preview.get("answer") or ""
    can_answer = (preview.get("answerability") or {}).get("can_answer", True)
    if memory and answer and can_answer:
```

Do **not** change `_run_research_shadow_sync` (shadow stays generation-free — observability must not burn LLM tokens) and do **not** change the `/api/research/preview` endpoint (env-driven behavior is its contract).

- [ ] **Step 5: Update every existing `fake_research_preview` in `tests/research/test_research_chat_integration.py`**

The chat helpers now pass `generate=True` as a keyword. Every fake defined as
`def fake_research_preview(query, top_k=5, providers=None):` must become:

```python
    def fake_research_preview(query, top_k=5, providers=None, generate=None):
```

(Fakes defined as `(*args, **kwargs)` already tolerate it.) Locations as of this writing: ~lines 71, 235, 346, 469-onwards — search the file for `def fake_research_preview(query` and update each.

- [ ] **Step 6: Run the integration + preview-api files**

Run: `uv run pytest tests/research/test_research_chat_integration.py tests/research/test_research_preview_api.py -q`
Expected: PASS

- [ ] **Step 7: Clarify `.env.example`**

Replace the `RESEARCH_PREVIEW_GENERATE=false` line with:

```bash
# Only affects /api/research/preview. Chat rollout paths always generate real answers.
RESEARCH_PREVIEW_GENERATE=false
```

- [ ] **Step 8: Suggest commit (user runs it)**

```
fix(research): always generate real answers on chat rollout paths
```

---

### Task 8: Frontend — hide "Research Papers" unless the backend offers it (finding 3.4)

**Files:**
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/app/chat/page.tsx`
- Modify: `web/src/components/chat/chat-input.tsx`
- Modify: `web/src/components/chat/search-mode-selector.tsx`

- [ ] **Step 1: Add the features client**

In `web/src/lib/api.ts`, add after the `ChatRequest` interface:

```typescript
export interface FeaturesResponse {
    research_search_available: boolean;
}
```

Add inside `ApiClient`:

```typescript
    static async getFeatures(): Promise<FeaturesResponse> {
        try {
            const response = await fetch(`${API_BASE_URL}/api/features`);
            if (!response.ok) {
                return { research_search_available: false };
            }
            return await response.json();
        } catch {
            // Fail closed: hide the option rather than silently degrading to "mixed".
            return { research_search_available: false };
        }
    }
```

- [ ] **Step 2: Fetch in the chat page**

In `web/src/app/chat/page.tsx`:
- Ensure `useEffect` is imported from `react` and add `import { ApiClient } from "@/lib/api";` (match the existing import alias style in the file).
- Below `const [searchSource, setSearchSource] = useState<SearchSource>("mixed");` add:

```tsx
    const [researchAvailable, setResearchAvailable] = useState(false);

    useEffect(() => {
        let cancelled = false;
        ApiClient.getFeatures().then((features) => {
            if (!cancelled) setResearchAvailable(features.research_search_available);
        });
        return () => {
            cancelled = true;
        };
    }, []);
```

- In the `composer` function, pass the prop to `ChatInput`:

```tsx
            searchSource={searchSource}
            researchAvailable={researchAvailable}
```

- [ ] **Step 3: Forward through `ChatInput`**

In `web/src/components/chat/chat-input.tsx`: add `researchAvailable?: boolean` to `ChatInputProps`, destructure it in the component signature, and pass `researchAvailable={researchAvailable}` to `<SearchModeSelector ...>`.

- [ ] **Step 4: Filter in the selector**

In `web/src/components/chat/search-mode-selector.tsx`:
- Add `researchAvailable?: boolean` to `SearchModeSelectorProps` and destructure with default `false`.
- After the `searchSources` array definition, add:

```tsx
    const availableSearchSources = searchSources.filter(
        (source) => source.value !== "research" || researchAvailable
    )
```

- Replace both usages of `searchSources` below the definition (`searchSources.find(...)` at ~line 84 and `searchSources.map(...)` at ~line 244) with `availableSearchSources`.

- [ ] **Step 5: Verify the build**

Run: `cd web && npm run build`
Expected: `✓ Compiled successfully`, exit 0. (Lint has known pre-existing failures — do not chase them; only ensure no **new** errors mention the four touched files beyond what main already has.)

- [ ] **Step 6: Suggest commit (user runs it)**

```
feat(web): gate Research Papers option on backend feature availability
```

---

### Task 9: Documentation — CHECKLOG + stale-note fix (M7)

**Files:**
- Modify: `docs/research-workflow/CHECKLOG.md`

- [ ] **Step 1: Add decision rows**

Append to the `## Decisions` table:

```markdown
| 2026-06-04 | Eval gate reports `PASS/FAIL/INCONCLUSIVE` (exit 0/1/2); labeled rows with zero live candidates count as inconclusive infra data, and the gate paces queries (`--sleep 3`). | The 2026-05-31 gate run failed on arXiv/S2 429s, not on quality; an unpassable gate cannot inform promotion. | Implemented |
| 2026-06-04 | Shadow runs via Starlette background tasks on both `/api/chat` and `/api/chat/stream`. | The web UI is streaming-only, so non-streaming-only shadow observed no real traffic; `asyncio.create_task` without a reference risked GC. | Implemented |
| 2026-06-04 | Chat rollout paths always call `run_research_preview(generate=True)`; `RESEARCH_PREVIEW_GENERATE` only affects `/api/research/preview`. | With generation off, end users received a placeholder instructing them to set an env var. | Implemented |
| 2026-06-04 | Streaming honors all active rollout modes (`manual`/`arxiv`/`default`) behind `RESEARCH_WORKFLOW_STREAMING`. | Manual-only streaming would split-brain the two chat endpoints after promotion. | Implemented |
| 2026-06-04 | Frontend hides `Research Papers` unless `GET /api/features` reports it available. | Selecting the option while rollout was off silently degraded to `mixed`. | Implemented |
```

- [ ] **Step 2: Fix the stale handoff note**

Replace the line:

```markdown
- Do not wire new providers directly into `/api/chat/stream` until phase tests
  and eval gates pass.
```

with:

```markdown
- `/api/chat/stream` reaches the research workflow only behind
  `RESEARCH_WORKFLOW_STREAMING=true` plus an active rollout mode; keep runtime
  config at `manual` until the eval gate returns PASS (not INCONCLUSIVE).
```

- [ ] **Step 3: Append verification log entries**

Append to the `## Verification Log` table (fill in the real results from Task 10):

```markdown
| 2026-06-04 | Adversarial branch review | Completed | Report at `docs/research-workflow/REVIEW_2026-06-04.md`; verdict GO (merge flag-gated) / NO-GO (promotion) with findings 3.1-3.5. |
| 2026-06-04 | `uv run pytest tests/ -q` | Passed | 171 passed, 30 skipped before remediation; record the new totals after Task 10. |
```

- [ ] **Step 4: Suggest commit (user runs it)**

```
docs(research): record remediation decisions and gate semantics
```

---

### Task 10: Final verification sweep

- [ ] **Step 1: Full Python suite**

Run: `uv run pytest tests/ -q`
Expected: 0 failures; total ≥ 171 passed + the new tests from Tasks 1-7 (~180+), 30 skipped. Record the exact totals in CHECKLOG (Task 9 Step 3 row).

- [ ] **Step 2: Deterministic eval target**

Run: `make eval-research`
Expected: exit 0, report shows `"no_candidate_query_count": 0`, 26 labeled rows.

- [ ] **Step 3: Frontend build**

Run: `cd web && npm run build`
Expected: `✓ Compiled successfully`, exit 0.

- [ ] **Step 4: Optional live gate re-run (requires network + keys)**

Run: `SEMANTIC_SCHOLAR_API_KEY=<key> OPENALEX_MAILTO=<email> make eval-research-gate`
Expected: with pacing the run takes ≥ 2.5 minutes (50 rows × 3s); verdict line `GATE VERDICT: ...` on stderr. INCONCLUSIVE (exit 2) means re-run later — it is no longer a quality FAIL. Promotion still requires PASS.

- [ ] **Step 5: Report results to the user with suggested final state**

Summarize test totals, eval verdict, build status. Rollout config stays `manual` until the live gate returns PASS.

---

## Self-Review Notes

- **Spec coverage:** 3.1 → Task 5; 3.2 → Task 1; 3.3 → Task 7; 3.4 → Tasks 3+8; 3.5 → Task 6; M1+M2 → Task 4; M3 → Task 2; M7 → Task 9. M4 (TypeError retry hack), M5 (memory.add type drift on the legacy path), M6 (adapter finish-event reordering) are deliberately **out of scope** — pre-existing/low-risk; revisit if they bite.
- **Type consistency:** `gate_verdict` consumes keys produced by `run_eval` (`paper_labeled_query_count`, `no_candidate_query_count`); `is_research_search_available(rollout: ResearchRollout)` matches the frozen dataclass; `fake_research_preview(..., generate=None)` matches the new call sites; `FeaturesResponse.research_search_available` matches the endpoint payload.
- **Known judgment call:** excluding zero-candidate labeled rows from the means could hide a workflow that genuinely finds nothing; the `max_no_candidate_rate` INCONCLUSIVE guard is the backstop, and the per-row `no_candidates` flag stays in the report for auditing.
