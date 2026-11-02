# Stage 4B gap review against canonical `main`

This document reviews the original Stage 4B goals against the reconciled `main`
baseline after `dev` was promoted. The implementation strategy is **gap-only**:
keep the newer production memory/research architecture and change only missing or
incorrect boundaries.

## Requirement matrix

| Stage 4B requirement | Canonical `main` before this gap patch | Action |
|---|---|---|
| Persistent conversation transcript | Implemented with `MemoryStore` / `PostgresMemoryStore` | Keep |
| Stable conversation session identity | Implemented in frontend `session-id.ts` | Keep |
| User/session ownership checks | Implemented in memory store and transcript workflow | Keep |
| Session summaries / context budgeting | Implemented with summaries + `ContextAssembler` | Keep |
| Long-term memory storage | Implemented storage model, but normal writes were session-scoped and extraction used English cue phrases | Fix gap |
| Cross-conversation profile recall | User scope existed, but recall depended on lexical overlap with the current query | Fix gap |
| Research discovery/ranking/evidence workflow | Implemented under `agent/research` | Keep |
| One canonical natural-language router | Missing: embedding example router + query-policy phrase lists + legacy freshness classifier all classified language independently | Fix gap |
| Structured route contract | Missing | Fix gap |
| Runtime-date freshness | Missing in legacy classifier; fixed years existed in source | Fix gap |
| Standalone query for multi-turn retrieval | Missing in production chat path | Fix gap |
| Conversation memory separated from retrieval text | Missing: assembled memory blob was sent directly to research discovery/evidence retrieval | Fix gap |
| Memory context available to generation | Implemented partially; now made explicit and marked non-evidence | Harden |
| Explicit durable memory write | Missing: transcript writer inferred memory from a few English phrases | Fix gap |
| User-scoped memory across conversations | Store supported it, but normal transcript writes did not use it | Fix gap |
| Semantic/episodic memory consolidation | Not required for Stage 4B foundation | Defer to later evaluation-driven work |
| Learned/adaptive routing | Not required for Stage 4B foundation | Defer to Stage 4C |

## Router boundary

Natural-language classification now has one owner: `agent/query_router.py`.

The router returns a validated structured decision:

- `route_type`: `static | llm_only | rag | out_of_scope`
- `intent`: semantic label for observability
- `confidence`
- `standalone_query`
- `freshness`: `none | current | mixed`
- optional `response` for static turns
- optional `memory_write` for explicit durable memory requests

`agent/query_policy.py` is now language-agnostic execution policy. It may honor
explicit UI controls such as `mode=chat` or `mode=search`, but it does not maintain
natural-language phrase lists.

The legacy LangGraph intent node is a compatibility adapter over the same router;
it no longer contains separate keyword/year classification rules.

## Query/context boundary

The central invariant is:

```text
latest user message + conversation context
                |
                v
        structured router
                |
      standalone_query
                |
                v
 discovery / ranking / evidence retrieval
```

Conversation context is **not** concatenated into `standalone_query`.

For synthesis:

```text
original user question
+ conversation context (continuity/preferences; NOT evidence)
+ retrieved evidence (factual support)
                |
                v
             answer
```

This prevents transcript/summary/user-memory text from changing embeddings,
provider queries, paper discovery, or evidence retrieval while preserving the
context needed to interpret follow-up questions.

## Durable memory boundary

The router may emit `memory_write` only for an explicit request to remember a
durable fact or preference. Transcript persistence no longer scans the raw query
for a fixed list of English cue phrases.

When an authenticated `user_id` exists, the memory item is written with
`scope="user"` and `session_id=None`, making it available to another conversation
owned by the same user. When no authenticated user exists, the compatibility
fallback is session-scoped.

Stage 4B treats these bounded user-scoped items as **profile memory**. A small set
of recent profile memories is loaded by `user_id` even if the current question has
no lexical overlap with the preference, then merged/deduplicated with query-relevant
memory. This closes the common failure where a preference such as “answer concisely”
was stored successfully but disappeared on a later unrelated research question.
`USER_PROFILE_MEMORY_LIMIT` bounds this context contribution.

This profile read is still intentionally simple. Semantic/episodic ranking,
contradiction resolution, temporal validity, importance, and forgetting remain
later evaluation-driven work rather than being smuggled into Stage 4B.

Sensitive credential-like candidates are still rejected by `MemoryWriter`; this is
a data-safety rule, not natural-language routing policy.

## Verification requirements

The Stage 4B gap patch is not complete until CI verifies:

- structured router parse/fallback and runtime-date prompt contract;
- no legacy intent dataset / fixed-year classifier;
- language-agnostic query policy;
- clean standalone research query with memory kept separate;
- claim synthesis treats conversation context as non-evidence;
- explicit user-scoped memory recall across sessions;
- query-independent bounded profile-memory recall;
- the same user isolation/profile behavior against real pgvector/Postgres;
- existing research tests, API imports, frontend contracts/build, and Docker smoke.

## Explicitly deferred

The following remain later-stage work rather than reasons to rebuild Stage 4B:

- routing/memory golden-set evaluation and calibration;
- semantic or episodic memory consolidation and contradiction handling;
- memory importance/decay/forgetting policy;
- learned/adaptive router selection;
- backend-native AuthN/AuthZ enforcement for direct API clients;
- richer user-facing memory management and conversation history UI.
