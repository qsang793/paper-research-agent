# UV Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace pip + two `requirements.txt` files with UV-managed `pyproject.toml` + `uv.lock`, with API/eval optional dependency groups, UV-based Makefile/Dockerfile, and an auto-exported `requirements.txt` fallback.

**Architecture:** A single `pyproject.toml` (PEP 621) declares core deps plus `api`/`eval` optional groups and a `dev` dependency-group. `[tool.uv] package = false` because the repo is a flat-layout application (`agent/ api/ ingest/`), not a buildable package. `uv.lock` pins exact resolved versions; `requirements.txt` is regenerated from it for non-UV consumers.

**Tech Stack:** UV (Astral), Python 3.12 (pinned via `.python-version`; the host runs 3.14 which lacks wheels for the pinned ML libs), FastAPI, LangGraph, ChromaDB, sentence-transformers.

> **PROJECT RULE — NO AUTO-COMMIT:** Per the user's global instruction, NEVER run `git commit`. Every "commit" step below only **stages** files (`git add`) and **prints a suggested commit message** for the user to run themselves.

> **Network note:** Installing UV, downloading CPython 3.12, and resolving packages (incl. torch ~GB via sentence-transformers) require network access. If a step fails with a network/sandbox error, re-run it with the sandbox disabled or ask the user to run it in their shell with `! <command>`.

---

### Task 1: Install and verify UV

**Files:** none (environment setup)

- [ ] **Step 1: Check whether UV is already installed**

Run: `uv --version`
Expected: either a version (skip to Task 2) or `command not found` (continue).

- [ ] **Step 2: Install UV via the official installer**

Run: `curl -LsSf https://astral.sh/uv/install.sh | sh`
Expected: installs to `~/.local/bin/uv`. (Alternative on macOS: `brew install uv`.)

- [ ] **Step 3: Verify UV is on PATH**

Run: `uv --version`
Expected: prints a version like `uv 0.x.y`. If `command not found`, run `export PATH="$HOME/.local/bin:$PATH"` and retry.

---

### Task 2: Create pyproject.toml + .python-version, lock and sync

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `uv.lock` (generated)

- [ ] **Step 1: Create `.python-version`**

Create `.python-version` with exactly:

```
3.12
```

- [ ] **Step 2: Create `pyproject.toml`**

Create `pyproject.toml` with this exact content:

```toml
[project]
name = "ai-research-agent"
version = "0.1.0"
description = "Agentic RAG system for research papers (arXiv-focused)"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "llama-index>=0.11.15,<0.12",
    "langgraph>=0.2.0,<0.3",
    "langchain>=0.3.0,<0.4",
    "langchain-community>=0.3.0,<0.4",
    "chromadb>=0.5.5,<0.6",
    "sentence-transformers>=2.7.0,<3",
    "rank-bm25>=0.2.2",
    "openai>=1.0.0",
    "google-generativeai>=0.5.0",
    "ollama>=0.3.3",
    "tavily-python>=0.3.5",
    "beautifulsoup4>=4.12.3",
    "unstructured>=0.15.7",
    "requests>=2.32.3",
    "python-dotenv>=1.0.1",
]

[project.optional-dependencies]
api = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic[email]>=2.10.0",
    "python-multipart>=0.0.12",
    "sse-starlette>=2.1.3",
    "bcrypt>=4.1.2",
    "PyJWT>=2.8.0",
]
eval = [
    "ragas>=0.1.0",
    "datasets>=2.14.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[tool.uv]
package = false
```

- [ ] **Step 3: Resolve and generate the lock file**

Run: `uv lock`
Expected: `uv.lock` is created; output ends without a resolution error. UV downloads CPython 3.12 if not present. If resolution fails on a capped ML lib, widen that cap one minor/major and re-run.

- [ ] **Step 4: Create the API development environment**

Run: `uv sync --extra api`
Expected: `.venv/` created; core + api + dev installed (large download incl. torch on first run).

- [ ] **Step 5: Smoke-test imports**

Run: `uv run python -c "import fastapi, langgraph, chromadb, sentence_transformers, llama_index; print('imports OK')"`
Expected: prints `imports OK` with no ImportError.

- [ ] **Step 6: Stage and suggest commit (do NOT run git commit)**

Run: `git add pyproject.toml .python-version uv.lock`
Then print this suggested message for the user:

```
build: introduce uv (pyproject.toml + uv.lock), pin python 3.12
```

---

### Task 3: Verify the existing test suite under UV

**Files:** none (verification)

- [ ] **Step 1: Run the unit tests**

Run: `uv run pytest tests/ -q`
Expected: tests collect and run. **Report honestly:** `tests/sanity_mvp.py` and several `tests/test_stage2_*` / integration tests need a live Ollama/network/model and may error or be skipped in a sandbox. Distinguish import/dependency failures (must fix) from external-service failures (expected, note them). A dependency-level regression = a failing `import` or collection error, and must be fixed (usually by adjusting a version cap in `pyproject.toml`, then `uv lock` + `uv sync`).

- [ ] **Step 2: Record the result**

No commit. Summarize which tests passed, which failed for environment reasons, in the handoff to the user.

---

### Task 4: Regenerate requirements.txt and delete api/requirements-api.txt

**Files:**
- Modify (regenerate): `requirements.txt`
- Delete: `api/requirements-api.txt`

- [ ] **Step 1: Export the runtime requirements from the lock**

Run: `uv export --no-hashes --no-dev --extra api -o requirements.txt`
Expected: `requirements.txt` rewritten with pinned core + api deps (no dev).

- [ ] **Step 2: Confirm the export contains API runtime deps**

Run: `grep -E "^(fastapi|uvicorn|llama-index|chromadb)" requirements.txt`
Expected: matches for all four — proves the old "core-only" gap is closed in the fallback too.

- [ ] **Step 3: Delete the now-redundant API requirements file**

Run: `git rm api/requirements-api.txt`
Expected: file removed and staged.

- [ ] **Step 4: Stage and suggest commit (do NOT run git commit)**

Run: `git add requirements.txt`
Then print this suggested message for the user:

```
build: export requirements.txt from uv.lock, drop api/requirements-api.txt
```

---

### Task 5: Update the Makefile to UV

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add `export-reqs` to `.PHONY`**

Replace the `.PHONY` line:

```makefile
.PHONY: help install install-api install-web run-api run-web dev clean migrate-e5 docker-build docker-run docker-test setup-env start-local stop-local tunnel stop-tunnel
```

with:

```makefile
.PHONY: help install install-api install-web run-api run-web dev clean migrate-e5 test-e5 docker-build docker-run docker-test setup-env start-local stop-local tunnel stop-tunnel export-reqs
```

- [ ] **Step 2: Replace the installation targets**

Replace this block:

```makefile
install: install-api install-web

install-api:
	@echo "Installing Backend dependencies..."
	pip install -r api/requirements-api.txt
	pip install -r requirements.txt

install-web:
	@echo "Installing Frontend dependencies..."
	cd web && npm install
```

with:

```makefile
install: install-api install-web

install-api:
	@echo "Installing Backend dependencies (UV)..."
	uv sync --extra api

install-web:
	@echo "Installing Frontend dependencies..."
	cd web && npm install
```

- [ ] **Step 3: Replace the `run-api` target**

Replace this block:

```makefile
run-api:
	@echo "Starting Backend..."
	@if [ -f ".venv/bin/python" ]; then \
		echo "Using virtual environment..."; \
		.venv/bin/python -m uvicorn api.main:app --reload --port 8000; \
	else \
		echo "Virtual environment not detected (or .venv/bin/python missing). Trying global python3..."; \
		python3 -m uvicorn api.main:app --reload --port 8000; \
	fi
```

with:

```makefile
run-api:
	@echo "Starting Backend (UV)..."
	uv run uvicorn api.main:app --reload --port 8000
```

- [ ] **Step 4: Replace the `migrate-e5` and `test-e5` targets**

Replace this block:

```makefile
migrate-e5:
	@echo "🔄 Migrating ChromaDB to e5-base-v2 embeddings..."
	@if [ -f ".venv/bin/python" ]; then \
		.venv/bin/python scripts/migrate_to_e5.py --input ./cache/clean --chroma ./chroma --backup; \
	else \
		python3 scripts/migrate_to_e5.py --input ./cache/clean --chroma ./chroma --backup; \
	fi

test-e5:
	@echo "🧪 Testing e5-base-v2 performance..."
	@if [ -f ".venv/bin/python" ]; then \
		.venv/bin/python scripts/test_e5_performance.py --chroma ./chroma --backup-dir $$(ls -td ./chroma_backup_* 2>/dev/null | head -1); \
	else \
		python3 scripts/test_e5_performance.py --chroma ./chroma --backup-dir $$(ls -td ./chroma_backup_* 2>/dev/null | head -1); \
	fi
```

with:

```makefile
migrate-e5:
	@echo "🔄 Migrating ChromaDB to e5-base-v2 embeddings..."
	uv run python scripts/migrate_to_e5.py --input ./cache/clean --chroma ./chroma --backup

test-e5:
	@echo "🧪 Testing e5-base-v2 performance..."
	uv run python scripts/test_e5_performance.py --chroma ./chroma --backup-dir $$(ls -td ./chroma_backup_* 2>/dev/null | head -1)
```

(Note: `scripts/migrate_to_e5.py` and `scripts/test_e5_performance.py` do not currently exist — a pre-existing gap, intentionally left unchanged beyond the `uv run` swap.)

- [ ] **Step 5: Add the `export-reqs` target**

Immediately after the `clean:` target block, add:

```makefile
# --- Export requirements.txt fallback from uv.lock ---
export-reqs:
	@echo "📤 Exporting requirements.txt from uv.lock..."
	uv export --no-hashes --no-dev --extra api -o requirements.txt
```

- [ ] **Step 6: Verify the Makefile parses and targets resolve**

Run: `make -n run-api`
Expected: prints `uv run uvicorn api.main:app --reload --port 8000` (dry run, no execution).

- [ ] **Step 7: Stage and suggest commit (do NOT run git commit)**

Run: `git add Makefile`
Then print this suggested message for the user:

```
build: drive Makefile targets through uv
```

---

### Task 6: Update the Dockerfile to a UV multi-stage build

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Replace the entire Dockerfile**

Replace the whole file with:

```dockerfile
# syntax=docker/dockerfile:1
# Multi-stage build using UV for dependency management
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Build toolchain for any wheels that compile from source
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Install core + api deps (no dev/eval) into /app/.venv
RUN uv sync --frozen --no-dev --extra api

# --- Final runtime stage ---
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Bring in the resolved virtualenv from the builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false \
    PORT=8000

RUN mkdir -p /app/chroma

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
```

- [ ] **Step 2: Confirm build-context files are available to Docker**

Run: `grep -nE "pyproject|uv\.lock|\.venv" .dockerignore || echo "no matches"`
Expected: `.dockerignore` does NOT exclude `pyproject.toml` or `uv.lock` (it may exclude `.venv/`, which is correct — the venv is built inside the image, not copied from the host).

- [ ] **Step 3 (OPTIONAL, heavy ~GB — only with explicit go-ahead): Build the image**

Run: `make docker-build`
Expected: build succeeds; `uv sync` installs fastapi/uvicorn (the previously-missing API deps). Skip in CI/sandbox if network or disk is constrained — note that it was skipped.

- [ ] **Step 4: Stage and suggest commit (do NOT run git commit)**

Run: `git add Dockerfile`
Then print this suggested message for the user:

```
build: UV multi-stage Dockerfile, install api deps (fix missing fastapi/uvicorn)
```

---

### Task 7: Update CLAUDE.md and ignore files

**Files:**
- Modify: `CLAUDE.md`
- Modify: `.gitignore` (only if needed)

- [ ] **Step 1: Update the `make install` comment in CLAUDE.md**

In `CLAUDE.md`, replace:

```
make install           # Backend (pip) + frontend (npm) deps
```

with:

```
make install           # Backend (UV api extra) + frontend (npm) deps
```

- [ ] **Step 2: Add a dependency-management note in CLAUDE.md**

In `CLAUDE.md`, immediately below the line:

```
make setup-env         # Create .env and web/.env.local from templates
```

add a blank line then:

```
# Dependencies: managed by UV (pyproject.toml + uv.lock). `uv sync` builds .venv.
# requirements.txt is auto-exported from the lock (`make export-reqs`) for non-UV use.
```

- [ ] **Step 3: Prefix the Python test/eval commands with `uv run` in CLAUDE.md**

In the `### Testing` block of `CLAUDE.md`, replace:

```bash
pytest tests/                          # All Python tests
pytest tests/test_query_router.py      # A single file
pytest tests/test_query_router.py::test_name   # A single test
python tests/sanity_mvp.py             # End-to-end sanity check with pass/fail thresholds
python eval/evaluate.py                # Ragas evaluation (eval/ has METRICS/RESULTS docs)
```

with:

```bash
uv run pytest tests/                          # All Python tests
uv run pytest tests/test_query_router.py      # A single file
uv run pytest tests/test_query_router.py::test_name   # A single test
uv run python tests/sanity_mvp.py             # End-to-end sanity check with pass/fail thresholds
uv run --extra eval python eval/evaluate.py   # Ragas evaluation (installs eval extra)
```

- [ ] **Step 4: Ensure `.gitignore` ignores `.venv` and tracks lock/manifest**

Run: `grep -nE "^\.venv|uv\.lock|pyproject" .gitignore`
Expected: `.venv` is present (it is, line ~27). `uv.lock` and `pyproject.toml` must NOT be ignored. If `uv.lock` appears in an ignore pattern, add `!uv.lock`. (Current `.gitignore` does not ignore them — likely no change needed.)

- [ ] **Step 5: Stage and suggest commit (do NOT run git commit)**

Run: `git add CLAUDE.md .gitignore`
Then print this suggested message for the user:

```
docs: document UV workflow in CLAUDE.md
```

---

## Final verification checklist

- [ ] `uv --version` works.
- [ ] `pyproject.toml`, `uv.lock`, `.python-version` exist and are staged.
- [ ] `uv sync --extra api` succeeds; smoke imports pass.
- [ ] `uv run pytest tests/ -q` run; results reported (dependency failures fixed, runtime-service failures noted).
- [ ] `requirements.txt` regenerated and contains fastapi/uvicorn; `api/requirements-api.txt` deleted.
- [ ] `make -n run-api` shows the `uv run` command.
- [ ] Dockerfile uses UV and installs the `api` extra (optionally built).
- [ ] `CLAUDE.md` Commands section reflects UV.
- [ ] All changes staged; suggested commit messages handed to the user (NO auto-commit).
