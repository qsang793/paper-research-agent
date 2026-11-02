# Phase 2: Paper Indexing

## Goal

Store paper metadata and full-text-derived content in a paper-aware index that
preserves section context and provenance.

## Scope

### Create

- `agent/research/indexing/paper_store.py`
- `agent/research/indexing/section_parser.py`
- `agent/research/indexing/contextual_chunks.py`
- `tests/research/test_paper_store.py`
- `tests/research/test_section_parser.py`
- `tests/research/test_contextual_chunks.py`

### Modify

- Existing `ingest/` modules only if shared PDF parsing/fetching utilities are
  reused.

Do not replace current `ingest/index.py` in this phase.

## Design

Paper indexing should store at least:

- Paper metadata.
- Abstract.
- Sections.
- Chunk text.
- Section title and paper title on every chunk.
- Citation/reference metadata where available.
- Source provider and retrieval timestamp.

## Recommended Store Strategy

Short term:

- Keep metadata in SQLite or JSONL cache for minimal operational complexity.
- Keep vectors in the current vector store only for experimental indexes.

Production target:

- Postgres for metadata and provider IDs.
- Object/file cache for PDFs and parsed text.
- Qdrant, Weaviate, OpenSearch, or pgvector for retrieval indexes depending on
  deployment constraints.

## Contextual Chunking

Follow the Contextual Retrieval principle: chunks should not lose their parent
paper/section context.

Chunk template:

```text
Paper: {title}
Authors: {authors}
Year: {year}
Section: {section_title}
Context: {section_summary_or_abstract}

{chunk_text}
```

## Implementation Tasks

### Task 1: Paper metadata store

- [ ] Define `StoredPaper` and `PaperStore`.
- [ ] Add upsert by stable paper ID.
- [ ] Add tests for duplicate provider IDs mapping to one paper.

### Task 2: Section parser

- [ ] Parse title, abstract, and section-like headings from text.
- [ ] Preserve fallback behavior for abstract-only candidates.
- [ ] Add tests with representative paper text.

### Task 3: Contextual chunks

- [ ] Implement chunk creation with paper and section context.
- [ ] Add tests that every chunk includes paper ID, title, section, source URL.
- [ ] Add chunk size and overlap configuration.

### Task 4: Index writer

- [ ] Write paper metadata to `PaperStore`.
- [ ] Write contextual chunks to the retrieval index.
- [ ] Add tests with fake vector store.

## Validation

```bash
uv run pytest tests/research/test_paper_store.py tests/research/test_section_parser.py tests/research/test_contextual_chunks.py -q
```

## Exit Criteria

- [ ] A discovered paper can be stored without provider-specific dictionaries.
- [ ] Abstract-only papers are searchable.
- [ ] Full-text papers produce section-aware chunks.
- [ ] Chunk provenance is sufficient for citation and debugging.
