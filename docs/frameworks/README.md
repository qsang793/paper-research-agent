# Optional Framework Notes

This folder contains notes for optional framework experiments. These documents
are not production routing guidance.

## Current Production Path

`/api/chat` and `/api/chat/stream` use `agent/research/` for retrieval-backed
paper questions. Static, out-of-scope, and LLM-only policies still bypass
retrieval.

## LlamaIndex

The LlamaIndex notes were archived under
[../archive/llamaindex-migration/](../archive/llamaindex-migration/). They may
describe drop-in replacement ideas for the older LangGraph path, but LlamaIndex
is not wired into production chat.

Before promoting any framework path:

- create a fresh implementation plan,
- run the research eval gate,
- verify the Vercel UI stream protocol,
- update [../research-workflow/CHECKLOG.md](../research-workflow/CHECKLOG.md).
