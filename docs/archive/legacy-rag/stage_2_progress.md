# AI Research Agent — Stage 2 Progress (Agentic Orchestration)

This file tracks progress against `stage_2_agent.md`.

## Goals (Stage 2)

- LangGraph orchestration with deterministic control
- Multi-query search (3–5 queries) and merged results
- Conversation memory (history + optional semantic recall)
- Self-routing (KB-only vs Search vs Both) based on confidence
- Basic tests for mixed-intent scenarios

## Current Status

- Orchestration
  - State schema defined (`agent/state.py`) ☑️
  - Graph defined với đầy đủ nodes/edges (`agent/graph.py`) ☑️
  - Conditional routing (intent → route → search/retrieve/generate) ☑️
- Multi-query Search
  - Query expansion via LLM ☐ (đang dùng heuristic, sẽ nâng cấp ở Stage 3)
  - Parallel arXiv search + dedup URLs ☑️
  - Merge results với priority scoring/RRF ☑️
- Memory
  - Conversation memory class (`agent/memory/conversation.py`) ☑️
  - Semantic recall + lexical fallback ☑️
  - UI/CLI integration (Streamlit + `run_agent_graph`) ☑️
- Self-routing
  - KB confidence metric (bounded similarity) ☑️
  - Route decision (kb_only/search/both) ☑️
- Integration
  - Pipeline wrapper (`agent/pipeline.py`) ☑️
  - Streamlit UI integration + metrics ☑️
- Tests
  - Unit tests (intent, expansion, memory) ☑️
  - Integration + scenario tests (routing, memory recall) ☑️

## Milestones

1) Week 1 – Graph + Intent + Routing
- Create state schema and base graph
- Implement intent classifier (rule + LLM fallback)
- Implement route node and conditional edges

2) Week 2 – Multi-query + Memory
- Query expansion and parallel search
- Conversation memory with LRU and optional persistence
- Context injection wiring

3) Week 3 – Integration + Tests
- Integrate with UI (routing info & metrics)
- Add tests for mixed-intent scenarios
- Stabilize and document

## Known Notes

- Keep Stage 1 pipeline intact; wrap functions into nodes
- Pin versions for `langgraph`, `langchain`, `langchain-community`
- Track metrics per node (duration, routing decisions)

## Commands Cheat Sheet (setup)

```bash
# Install Stage 2 deps
pip install langgraph>=0.2.0 langchain>=0.3.0 langchain-community>=0.3.0
```

## Next Steps

- Nâng cấp query expansion dùng LLM (Gemini/Ollama) khi Stage 3 bắt đầu
- Bổ sung metrics chi tiết per-node (latency, token usage)
- Thêm e2e test cho kết hợp memory + fresh intent với nguồn mới
