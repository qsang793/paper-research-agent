# Memory Rollout Runbook

How to take the persistent session/memory system from "flags off" to production, one reversible stage at a time. All flags default to **false** — deploying the code alone changes nothing.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `PERSISTENT_TRANSCRIPT_ENABLED` | `false` | Master switch: persist transcripts + sources to the memory store |
| `MEMORY_DATABASE_URL` | (empty) | Postgres DSN. Empty ⇒ `InMemoryMemoryStore` (dev only, lost on restart). Append `?connect_timeout=5` (libpq honors it) so a dead DB fails fast instead of hanging request threads. |
| `RESEARCH_MEMORY_ENABLED` | `false` | Assemble persistent context (recent messages, summary, memory items) into research answers |
| `SESSION_SUMMARY_ENABLED` | `false` | Maintain a rolling per-session summary |
| `LONG_TERM_MEMORY_ENABLED` | `false` | Extract and store long-term memory items |
| `CONVERSATIONAL_MEMORY_ENABLED` | `false` | Include persistent recent messages in meta-chat and LLM-only chat context |
| `MEMORY_RECENT_MESSAGE_LIMIT` | `8` | Recent messages pulled into context |
| `MEMORY_MAX_CONTEXT_CHARS` | `12000` | Context assembly budget |
| `SESSIONS_MAX` / `SESSIONS_TTL_SECONDS` | `500` / `3600` | Bounds for the legacy in-process session cache (per worker) |

## Pre-flight (once per environment)

1. Provision Postgres (locally: `make compose-db`, uses `pgvector/pg16`).
2. Run the integration suite against it:
   `MEMORY_TEST_DATABASE_URL=postgresql://research:research@localhost:5432/research_memory make test-memory-postgres`
   All tests must pass. For a remote environment, point the URL at a throwaway database in the same engine version.
3. Confirm the app user's DSN is in the deployment secret store — never in the repo.

## Stages

Roll forward one stage at a time; each stage is independently revertible by flipping its flag off.

| Stage | Flags | What changes |
|---|---|---|
| 0 (today) | all false | Prototype behavior, in-process only |
| 1 | `PERSISTENT_TRANSCRIPT_ENABLED=true` + `MEMORY_DATABASE_URL=…` | Transcripts + sources durable; answers unchanged |
| 2 | + `RESEARCH_MEMORY_ENABLED=true` | Persistent context feeds research answers |
| 3 | + `SESSION_SUMMARY_ENABLED=true`, then `LONG_TERM_MEMORY_ENABLED=true` | Summaries, then long-term memory |
| 4 | + `CONVERSATIONAL_MEMORY_ENABLED=true` | Meta-chat and LLM-only chat use persistent recent messages |

## Verification after each deploy

1. `curl -s $API/api/memory/features` — expect the stage's flags `true`, `memory_store_backend: "postgres"`, `memory_store_error: null`.
   - `"unavailable"` + an error string ⇒ store init failed; the API still serves answers but persists nothing. Fix the DSN/DB before proceeding.
   - `"inmemory"` in production ⇒ `MEMORY_DATABASE_URL` is missing from the environment.
2. Send a chat message via the UI, then confirm rows exist:
   `psql $MEMORY_DATABASE_URL -c "select id, role, left(content, 40) from chat_messages order by created_at desc limit 5;"`
3. Delete flow: `curl -X DELETE $API/api/memory/session/<session_id>` — expect `deleted_persistent_session: true`; repeat expects 404.

### Stage 4: Conversational Memory Manual QA
- Ask `bạn có thể chơi trò đếm số với tôi không ?`
- Then ask `bạn có thể nhắc lại câu hỏi vừa rồi của tôi không ?` — assistant should include exactly `bạn có thể chơi trò đếm số với tôi không ?` from prior turn.
- Ask `hi`; after the assistant replies, ask `Bạn có thể nhắc lại câu trả lời của bạn 1 lần nữa không` — assistant should repeat its previous answer rather than produce a fresh greeting.
- Refresh page/browser without signing out and repeat the question — it should continue the same session and still remember context.
- Start "New chat" or sign out and start again — the session should rotate and not retain conversational context from prior session.
- Simulate a client request with a fake `user_id` in `/api/chat` body (for example from devtools/curl); confirm server-side proxy user from NextAuth is used and client-supplied `user_id` is ignored.

## Monitoring

- Alert on the log line `Failed to initialize persistent memory store` (logged at ERROR) — it means silent no-persistence degradation.
- Poll `/api/memory/features` from uptime monitoring; treat `memory_store_backend != "postgres"` as unhealthy in stages ≥ 1.
  - Caveat: the store is cached in-process after its first successful connection, so this probe only catches init-time failures. A DB that dies mid-life keeps reporting `"postgres"` here even though every request is now failing — the probe alone is not sufficient for stage ≥ 1 alerting.
- Also alert on these per-request WARNING log lines from `api/chat_orchestrator.py`, which catch the mid-life outage the features probe misses:
  - `Failed to assemble persistent memory context`
  - `Failed to persist chat transcript`

## Rollback

Flip the stage's flag back to `false` and redeploy. Data already in Postgres is retained and compatible with re-enabling later. Deleting user data on request: `DELETE /api/memory/session/{session_id}` — the session record is soft-deleted; its messages, sources, summaries, and memory items are permanently removed.

## Known limits

- Multi-worker deployments: the legacy in-process session cache is per worker; the Postgres store is shared and consistent.
- Summary/long-term extraction runs synchronously in the request path — watch p95 latency when enabling stage 3.
- The localStorage chat session id is per-browser-profile, not per-account. It now rotates on sign-out, but on a shared browser a user who closes the tab without signing out still hands the next login the same session id. Scope stage-2 rollout (persistent context feeding into answers) accordingly.
- With all flags off, the in-process session cache now evicts conversations idle longer than `SESSIONS_TTL_SECONDS` (default 1h); previously they survived for the process lifetime.
