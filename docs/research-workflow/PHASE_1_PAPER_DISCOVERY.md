# Phase 1: Paper Discovery

## Goal

Build a provider-backed paper discovery layer that turns messy user questions
into normalized `PaperCandidate` results with explainable scores.

## Why First

The historical arXiv-source failure for `ROS2 trong robotics là gì` was caused
by poor query planning and arXiv query formatting. Fixing generation or
answerability will not solve missing candidate discovery.

## Scope

### Create

- `agent/research/__init__.py`
- `agent/research/query_plan.py`
- `agent/research/discovery/__init__.py`
- `agent/research/discovery/models.py`
- `agent/research/discovery/arxiv_provider.py`
- `agent/research/discovery/semantic_scholar_provider.py`
- `agent/research/discovery/openalex_provider.py`
- `agent/research/discovery/service.py`
- `tests/research/test_query_plan.py`
- `tests/research/test_arxiv_provider.py`
- `tests/research/test_discovery_service.py`

### Modify

- `ingest/search.py` only if a shared arXiv XML parser should be reused.
- `docs/research-workflow/CHECKLOG.md` after decisions are finalized.

Do not modify `api/routes/chat.py` in this phase.

## Design

### QueryPlan

Use a deterministic baseline first, then optionally add LLM planning behind a
flag later.

Required behavior:

- Remove Vietnamese question filler such as `là gì`, `trong`, `về`, `cho tôi`.
- Preserve technical entities and acronyms.
- Expand aliases using configurable data, not inline `if query contains X`.
- Suggest arXiv categories from entity/domain terms where obvious.

Example:

```python
plan = plan_research_query("ROS2 trong robotics là gì")
assert plan.entities == ["ROS2", "robotics"]
assert plan.aliases["ROS2"] == ["ROS 2", "Robot Operating System 2"]
assert "cs.RO" in plan.categories
```

### ArXiv Provider

Generate multiple query strategies:

```text
all:ROS2 AND all:robotics
(all:ROS2 OR all:"ROS 2" OR all:"Robot Operating System 2") AND (all:robotics OR cat:cs.RO)
ti:ROS2 OR abs:ROS2 OR ti:"ROS 2" OR abs:"ROS 2"
```

Do not rely on one exact phrase query.

### Provider Service

Provider service responsibilities:

- Run selected providers.
- Enforce per-provider timeout.
- Normalize to `PaperCandidate`.
- Deduplicate by arXiv ID, DOI, Semantic Scholar ID, OpenAlex ID, then title
  similarity.
- Return candidates with `score_breakdown`.

## Implementation Tasks

### Task 1: QueryPlan schema and deterministic planner

**Files:**

- Create: `agent/research/query_plan.py`
- Test: `tests/research/test_query_plan.py`

Steps:

- [ ] Write tests for multilingual filler stripping and ROS2 alias expansion.
- [ ] Implement `QueryPlan` dataclass.
- [ ] Implement `plan_research_query(query: str) -> QueryPlan`.
- [ ] Move alias data into a module-level dictionary such as
      `TECHNICAL_ALIASES`, not inline branching.
- [ ] Run `uv run pytest tests/research/test_query_plan.py -q`.

Acceptance:

- `ROS2 trong robotics là gì` produces `ROS2`, `robotics`, aliases, and `cs.RO`.
- Query planner does not call an LLM by default.

### Task 2: PaperCandidate schema

**Files:**

- Create: `agent/research/discovery/models.py`
- Test: `tests/research/test_discovery_service.py`

Steps:

- [ ] Define `PaperCandidate`.
- [ ] Add `stable_key()` helper using arXiv ID, DOI, S2 ID, OpenAlex ID, or
      normalized title.
- [ ] Add tests for stable key priority.
- [ ] Run `uv run pytest tests/research/test_discovery_service.py -q`.

Acceptance:

- Provider-specific raw dictionaries do not leak past provider modules.

### Task 3: ArXiv provider v2

**Files:**

- Create: `agent/research/discovery/arxiv_provider.py`
- Test: `tests/research/test_arxiv_provider.py`

Steps:

- [ ] Write tests for query string generation from `QueryPlan`.
- [ ] Reuse or replace `_parse_arxiv_atom` with XML parsing that preserves
      title, abstract, authors, categories, arXiv ID, abs URL, and PDF URL.
- [ ] Implement `search_arxiv_papers(plan, max_results=20)`.
- [ ] Add a test that mocked arXiv XML returns `PaperCandidate`.
- [ ] Run `uv run pytest tests/research/test_arxiv_provider.py -q`.

Acceptance:

- The generated arXiv queries include boolean AND/OR variants.
- A query equivalent to `ROS2 robotics` is possible from the Vietnamese input.

### Task 4: Semantic Scholar and OpenAlex providers

**Files:**

- Create: `agent/research/discovery/semantic_scholar_provider.py`
- Create: `agent/research/discovery/openalex_provider.py`
- Test: `tests/research/test_discovery_service.py`

Steps:

- [ ] Implement request builders without requiring API keys for import.
- [ ] Normalize provider responses to `PaperCandidate`.
- [ ] Add timeout and status-code handling.
- [ ] Add tests using mocked responses.

Acceptance:

- Providers degrade gracefully when keys are absent or rate limited.

### Task 5: Discovery service and ranking baseline

**Files:**

- Create: `agent/research/discovery/service.py`
- Test: `tests/research/test_discovery_service.py`

Steps:

- [ ] Implement provider fan-out.
- [ ] Implement deduplication.
- [ ] Implement first-pass score breakdown:
      `entity_match`, `alias_match`, `category_match`, `recency`, `provider_rank`.
- [ ] Add tests for deduping and score ordering.

Acceptance:

- `discover_papers("ROS2 trong robotics là gì", providers=["arxiv"])` can return
  ROS 2 robotics candidates when provider responses contain them.

## Validation

Run:

```bash
uv run pytest tests/research/test_query_plan.py tests/research/test_arxiv_provider.py tests/research/test_discovery_service.py -q
uv run python -m py_compile agent/research/query_plan.py agent/research/discovery/*.py
```

Expected:

- All tests pass.
- No network is required for unit tests.

## Exit Criteria

- [ ] Provider-backed discovery returns normalized `PaperCandidate` objects.
- [ ] ArXiv query generation is no longer exact-phrase-only.
- [ ] Query planning handles multilingual filler and aliases.
- [ ] Existing chat API remains unchanged.
