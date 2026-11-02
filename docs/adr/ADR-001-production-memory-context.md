# ADR-001: Production Memory Context
Date: 2026-06-29
Status: Proposed

## Context

The chat API currently keeps conversation memory in process-local Python dictionaries.
That loses context on restart, does not work across multiple workers, and makes
streaming web sessions depend on backend-generated ids that the frontend does not
persist.

## Decision

Use a custom memory layer with a narrow `MemoryStore` interface. PostgreSQL plus
pgvector is the production storage target. In-memory storage remains available for
tests and for feature-flagged rollback. The canonical research workflow remains
`agent/research/`; LangGraph and LlamaIndex are not introduced as production
orchestration dependencies in this decision.

The memory rollout is feature-flagged in this order:

1. Stable session id propagation.
2. Persistent transcript storage.
3. Context assembly and session summary.
4. Long-term scoped memory.
5. Research-specific memory.

## Consequences

**Positive:** durable sessions, multi-worker compatibility, explicit rollback,
clear test surfaces, and no framework lock-in for citation/privacy policy.

**Negative:** more local code than adopting a managed memory framework.

**Risks:** schema drift, prompt bloat, and privacy leakage. These are mitigated
through feature flags, memory provenance, deletion endpoints, evals, and avoiding
plaintext secret logging.
