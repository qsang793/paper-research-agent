# syntax=docker/dockerfile:1
# Multi-stage build using uv with a CPU-only PyTorch runtime.
# Pin the uv builder digest so CLI flags cannot change underneath CI.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Build toolchain for any wheels that compile from source.
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency manifests first for better layer caching.
COPY pyproject.toml uv.lock ./

# Export the locked production environment, then replace the PyPI CUDA-enabled
# torch branch with the official CPU wheel. `uv export --prune` only prunes
# workspace roots, not transitive dependencies, so GPU-only entries are filtered
# explicitly from the flat no-hash export. Installing the remaining flat lock
# with --no-deps prevents sentence-transformers from re-resolving PyPI torch.
RUN uv export \
        --frozen \
        --no-dev \
        --extra api \
        --no-hashes \
        --no-emit-project \
        --output-file /tmp/requirements-locked.txt \
    && python - <<'PY'
from pathlib import Path

source = Path('/tmp/requirements-locked.txt')
target = Path('/tmp/requirements-runtime.txt')
blocked_prefixes = ('torch==', 'triton==', 'nvidia-')
kept = [
    line
    for line in source.read_text().splitlines()
    if not line.lstrip().lower().startswith(blocked_prefixes)
]
target.write_text('\n'.join(kept) + '\n')
PY
RUN uv venv /app/.venv \
    && uv pip install \
        --python /app/.venv/bin/python \
        --index https://download.pytorch.org/whl/cpu \
        'torch==2.2.2+cpu' \
    && uv pip install \
        --python /app/.venv/bin/python \
        --no-deps \
        -r /tmp/requirements-runtime.txt

# --- Final runtime stage ---
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/chroma /app/cache \
    && chown -R appuser:appuser /app /home/appuser

# Bring in the resolved virtualenv from the builder. It is read-only at runtime.
COPY --from=builder /app/.venv /app/.venv

# Copy application code with runtime ownership.
COPY --chown=appuser:appuser . .

ENV PATH="/app/.venv/bin:$PATH" \
    HOME=/home/appuser \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false \
    PORT=8000

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port \"${PORT}\""]
