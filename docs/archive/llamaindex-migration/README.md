# LlamaIndex Migration Archive

These files are migration notes for optional LlamaIndex work. They predate the
production `agent/research/` workflow and may recommend migration paths that are
no longer current.

Current state:

- Production chat uses `agent/research/`.
- LlamaIndex code under `agent/frameworks/llamaindex/` remains optional.
- Do not wire LlamaIndex into production without a new approved plan and eval
  gate.

Related current docs:

- [../../frameworks/README.md](../../frameworks/README.md)
- [../../research-workflow/ARCHITECTURE.md](../../research-workflow/ARCHITECTURE.md)

## Sections

- Root `llamaindex_*` notes from the old docs folder.
- [frameworks-llamaindex/](./frameworks-llamaindex/) - historical framework
  result notes that previously lived under `docs/frameworks/llamaindex/`.
