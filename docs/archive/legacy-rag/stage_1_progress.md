# AI Research Agent — Stage 1 MVP Progress

This file tracks progress against `stage_1_mvp.md`.

## Goals (MVP)

- ✅ End-to-end: search → crawl → parse → chunk → embed → upsert → retrieve → generate
- ✅ Answer with citations (URL + title), >= 2 valid citations when available
- ✅ Basic UI (Streamlit) with step logs and timings
- ✅ Sanity tests (5 questions) with clear pass thresholds

## Current Status

- Ingestion
  - Search: arXiv API implemented (`ingest/search.py`) ✅
  - Crawl: abstract HTML with retry/backoff & size/type filters (`ingest/crawl.py`) ✅
  - Parse: extract title/authors/abstract + normalized metadata + `content_hash` (`ingest/parse.py`) ✅
  - Index: SentenceTransformers + Chroma upsert with metadata sanitization (`ingest/index.py`) ✅
- Retrieval/Answering
  - Query top‑k from Chroma (`agent/query.py`) ✅
  - Generate via Ollama with guardrail prompt (`agent/answer.py`, `agent/generator.py`) ✅
  - Citation format included in prompt ✅
- Config/Infra
  - `requirements.txt` pinned ✅
  - `config/env.example` ✅
  - Caching folders created (raw/clean) ✅
- Completed
  - Streamlit UI (`app/ui.py`) ✅
  - Hybrid BM25 + RRF wired into retrieval path (UI) ✅
  - Citation validator (HTTP 200) integration (`agent/citation_validator.py`) ✅
  - Sanity tests suite (`tests/sanity_mvp.py`) ✅
  - UI metrics improvements (model name, Re-run button) ✅
  - README with Quickstart ✅

## Known Notes

- Chroma telemetry warnings are benign; can disable via `CHROMA_TELEMETRY_DISABLED=1`.
- Ollama calls now have configurable timeout/retry via env.

## MVP Status: ✅ COMPLETE

All MVP goals have been achieved. The system is ready for testing and further development.

## Next Steps (Post-MVP)

1) Run sanity tests: `python tests/sanity_mvp.py` to validate thresholds
2) LangGraph orchestration (see `overview.md` for architecture)
3) Multi-query search expansion
4) Self-evaluation integration (TruLens/Ragas)
5) FastAPI gateway for production
6) Qdrant migration (scalability)

## Commands Cheat Sheet

```bash
# Search (arXiv)
python -m ingest.search --q "RAG 2025 trends" --out ./cache/search_results.json --max 5

# Crawl -> Parse -> Index
python -m ingest.crawl --from ./cache/search_results.json --out ./cache/raw
python -m ingest.parse --input ./cache/raw --out ./cache/clean
python -m ingest.index --input ./cache/clean --chroma ./chroma

# Query / Answer
python -m agent.query --chroma ./chroma --q "retrieval augmented generation survey 2024"
python -m agent.answer --chroma ./chroma --q "Tóm tắt RAG 2024–2025 theo arXiv" --k 6
```

## Environment Tips

```env
OLLAMA_BASE=http://127.0.0.1:11434
OLLAMA_TIMEOUT_SEC=180
OLLAMA_MAX_RETRIES=2
OLLAMA_BACKOFF_BASE=2
CHROMA_TELEMETRY_DISABLED=1
```

