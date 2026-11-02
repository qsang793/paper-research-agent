# Stage 4C — Evaluation-Driven Intelligence

Status: design proposal

Canonical baseline: `main` after Stage 4B gap closure.

## 1. Decision summary

Stage 4C will **not** begin by replacing the current router or memory subsystem.

The current system already has durable architectural boundaries:

```text
Production chat
API
  -> StructuredQueryRouter
  -> QueryPolicy
  -> ResearchChatWorkflow
      -> discovery
      -> ranking
      -> evidence
      -> synthesis
      -> persistent memory

Legacy compatibility
LangGraph
  -> intent compatibility node
  -> legacy adaptive-RAG retrieval/generation
```

The Stage 4C strategy is:

```text
measure -> diagnose -> experiment -> compare -> roll out
```

Router v2 and Memory v2 are therefore **experiments behind evaluation contracts**, not predefined rewrites.

The durable Stage 4B boundaries remain unchanged unless an evaluation demonstrates that a boundary itself is the problem.

## 2. Why this stage exists

Stage 4B removed the largest architectural ambiguity: natural-language interpretation has one canonical source of truth, retrieval text is separated from conversation context, and durable memory has a production persistence layer.

The remaining risk is different: future improvements can easily become prompt tuning, threshold tuning, or memory heuristics with no objective evidence that they improve the system.

Stage 4C solves that by making behavior measurable before making it more sophisticated.

The system should be able to answer these questions with repeatable reports:

- Did a router change improve route accuracy?
- Did it make freshness classification worse?
- Did it rewrite follow-up queries more faithfully?
- Did a cheaper router reduce cost without unacceptable quality loss?
- Did a memory-write policy remember more useful facts without storing incidental or sensitive facts?
- Did memory retrieval return the right user facts without leaking another session/user?
- Did summary compaction preserve the facts needed later?
- Did a research retrieval/ranking change improve recall/MRR or merely move failures between stages?
- What latency/cost trade-off did each change introduce?

## 3. Existing foundation on `main`

Stage 4C must reuse, not duplicate, the current evaluation work.

### Router

Current assets:

- `agent/query_router.py`
  - structured LLM output
  - route type
  - freshness
  - confidence
  - standalone query
  - optional direct response
  - explicit memory-write candidate
- `agent/query_policy.py`
  - deterministic execution policy
  - no natural-language phrase datasets
- `eval/router_golden_set.jsonl`
  - initial static/chat/research/out-of-scope coverage
  - freshness coverage
  - follow-up rewrite case
  - explicit memory case
- `eval/router_eval.py`
  - dataset validation
  - optional live router scoring

Current weakness: the router set is intentionally small and the report is too coarse for model/prompt selection.

### Memory

Current assets:

- persistent Postgres/pgvector-backed memory store
- session transcript persistence
- session summaries
- user/profile memories
- relevant-memory lookup
- context assembler
- memory controls
- session ownership checks
- `eval/memory_golden_set.jsonl`
- `eval/conversational_memory_golden_set.jsonl`
- memory unit/integration tests

Current weakness: `eval/memory_eval.py` currently loads rows but does not produce a behavioral quality score suitable for comparing memory strategies.

### Research

Current assets are already more mature:

- `eval/research_eval.py`
- recall@k
- precision@k
- MRR@k
- hit-rank analysis
- provider/discovery vs candidate vs ranking failure attribution
- resumable/checkpointed reports
- PASS / FAIL / INCONCLUSIVE gate semantics

Stage 4C should copy this evaluation discipline into routing and memory rather than inventing a separate style.

## 4. Core principles

### 4.1 Baseline before optimization

Every behavioral optimization must have a baseline report generated with the current production implementation.

A new strategy must be compared against the same dataset and evaluation schema.

### 4.2 Dataset examples belong in eval, not runtime logic

A failed example should normally become a golden/eval case.

It must not automatically become:

- a phrase list,
- a keyword exception,
- a year rule,
- a query-specific branch,
- or a hardcoded memory special case.

### 4.3 Safety/integrity metrics are hard constraints

Some metrics are not tradable for average quality:

- cross-user/session memory leakage must remain zero,
- sensitive-memory writes must remain zero for explicitly prohibited classes,
- router structured-output parse failures must fall back safely,
- retrieval context must never be formed by concatenating raw conversation history into search text.

### 4.4 Optimize on a Pareto frontier

Router and memory changes must be evaluated on more than accuracy.

Candidate selection should consider:

- quality,
- latency,
- model/API cost,
- stability/failure rate,
- and privacy/integrity constraints.

A 1% quality gain that doubles latency/cost is not automatically better.

### 4.5 Live-model eval is not an unconditional PR gate

Provider-backed evals can be noisy or unavailable.

CI should always run deterministic schema/contract evaluation.

Live evaluation should initially be report-only and become a merge gate only after:

1. the dataset is sufficiently representative,
2. the provider/model is stable,
3. repeated baseline runs show acceptable variance.

## 5. Stage 4C architecture

Stage 4C adds an evaluation/telemetry plane around the existing runtime rather than inserting a new orchestration layer.

```text
                       +-------------------------+
                       |   Evaluation datasets   |
                       +------------+------------+
                                    |
                                    v
+---------+     +-------------------+-------------------+
| Request | --> | Current production runtime           |
+---------+     | Router -> Policy -> Research/Memory   |
                +-------------------+-------------------+
                                    |
                          trace + decisions + outputs
                                    |
                                    v
                       +------------+------------+
                       | Evaluation report schema |
                       +------------+------------+
                                    |
                    +---------------+----------------+
                    |                                |
                    v                                v
             baseline report                  candidate report
                    |                                |
                    +---------------+----------------+
                                    |
                                    v
                             experiment verdict
```

No production request should need an evaluator in order to complete.

Evaluation is a consumer of the same public contracts used by production.

## 6. Unified evaluation report contract

Router and memory reports should follow the same conventions as research eval.

Every report should contain at least:

```json
{
  "report_schema_version": 1,
  "evaluation": "router | memory | research",
  "dataset": "...",
  "dataset_hash": "...",
  "git_sha": "...",
  "strategy": "baseline",
  "backend": "...",
  "model": "...",
  "query_count": 0,
  "metrics": {},
  "failure_stage_counts": {},
  "results": []
}
```

Provider keys/secrets must never be serialized into reports.

Reports should be reproducible enough to compare two commits or strategies.

## 7. Phase 4C.0 — Evaluation foundation

This is the first implementation phase and is required before Router v2 or Memory v2 work.

### Deliverables

1. Shared report conventions for router/memory evals.
2. Baseline command(s) that emit JSON reports.
3. Dataset validation tests.
4. Failure-stage attribution.
5. A comparison command that accepts baseline and candidate reports.
6. CI deterministic gates.
7. Optional live-eval workflow/manual command.

### Initial failure taxonomy

Router:

- `parse_failure`
- `route_miss`
- `freshness_miss`
- `standalone_rewrite_miss`
- `memory_write_false_positive`
- `memory_write_false_negative`
- `passed`

Memory:

- `write_miss`
- `unwanted_write`
- `sensitive_write`
- `dedup_failure`
- `retrieval_miss`
- `cross_session_leak`
- `cross_user_leak`
- `summary_loss`
- `contradiction_failure`
- `passed`

Research keeps its existing failure taxonomy.

## 8. Phase 4C.1 — Router evaluation v2

### Dataset dimensions

The router golden set should be expanded systematically rather than by random examples.

Required dimensions:

#### Interaction route

- static/direct
- conversational/LLM-only
- research/RAG
- clearly out-of-scope

#### Freshness

- none
- current
- mixed

#### Conversation structure

- single-turn
- pronoun follow-up
- entity follow-up
- comparison follow-up
- correction by the user
- topic switch

#### Language

At minimum:

- Vietnamese
- English

Mixed-language technical queries should be included once the first two are stable.

#### Memory intent

- explicit durable preference
- explicit durable project fact
- incidental personal fact that must not be written
- sensitive credential/secret that must not be written
- temporary/session-only information

#### Ambiguity

- request that can be answered conversationally without retrieval
- request where evidence/citations materially improve the answer
- latest/current request
- established knowledge + latest developments

### Router metrics

At minimum:

- route accuracy
- per-route precision/recall
- route confusion matrix
- freshness accuracy
- standalone rewrite pass rate
- memory-write precision
- memory-write recall
- structured parse success rate
- fallback rate
- p50/p95 router latency
- model/API cost per routed request when available

### Standalone-query scoring

Exact-string matching is too brittle.

Stage 4C should support layered scoring:

1. deterministic required-term / forbidden-term checks,
2. semantic similarity when appropriate,
3. optional judge-model scoring for ambiguous rewrites.

Judge-based scoring must never be the only safety gate.

### Router target gates

Initial targets are provisional until a larger baseline exists.

Hard constraints:

- structured parse/fallback behavior remains safe,
- memory-write false positives for sensitive/incidental cases = 0 in the safety set,
- no runtime phrase dataset is introduced.

Quality targets after the dataset reaches useful coverage:

- route accuracy >= 0.90,
- freshness accuracy >= 0.90,
- standalone rewrite pass rate >= 0.90,
- explicit-memory precision >= 0.95.

A candidate router must also remain within an accepted latency/cost envelope relative to baseline.

## 9. Phase 4C.2 — Memory evaluation v2

Memory v2 should not mean "add embeddings" by default.

First measure the current system across the complete memory lifecycle:

```text
write decision
   -> normalization/privacy
   -> persistence/dedup
   -> retrieval
   -> context assembly
   -> answer behavior
```

### Dataset scenarios

#### Write policy

- explicit "remember this"
- ordinary mention that should not become durable memory
- user preference
- project/context fact
- secret/token/password request
- duplicate fact

#### Retrieval

- relevant user memory from another session
- irrelevant memory must not dominate context
- recent conversation vs durable memory conflict
- no lexical overlap but semantically relevant preference

#### Isolation

- different session, same user where user-scoped memory is expected
- different session where session-scoped memory must not leak
- different user with identical query

#### Updates and contradiction

Examples:

```text
Remember: I prefer concise answers.
...
Actually, from now on I prefer detailed answers.
```

The evaluator must measure whether the active context reflects the newer state without presenting contradictory profile facts as equally valid.

#### Summary retention

Long conversations should test whether summary compaction preserves:

- current goal,
- decisions,
- named entities,
- unresolved questions,
- explicit user preferences,

while excluding irrelevant old details.

### Memory metrics

- write precision
- write recall
- sensitive-write rate
- exact/semantic dedup rate
- memory retrieval recall@k
- memory retrieval precision@k
- cross-session leakage rate
- cross-user leakage rate
- contradiction-resolution accuracy
- summary fact-retention rate
- context-budget usage
- memory retrieval latency

### Memory hard gates

- cross-user leakage = 0
- forbidden-sensitive-memory write rate = 0
- session ownership tests remain fail-closed

Other targets should be set after baseline measurement rather than guessed before data exists.

## 10. Phase 4C.3 — Telemetry and experiment identity

Current research observability already records spans and latency summaries.

Stage 4C should extend the idea to the full request boundary without requiring a vendor-specific tracing platform.

Minimum per-request experiment metadata:

- request/trace id
- router strategy id
- router model/backend
- route decision
- freshness decision
- router confidence
- whether fallback occurred
- router latency
- memory strategy id
- memory lookup count
- selected memory ids/types (not secret raw values in generic telemetry)
- retrieval/research strategy id
- stage latency summary
- answerability result
- citation count/validation result

Telemetry must be safe to disable and must not be required for request correctness.

## 11. Phase 4C.4 — Router v2 experiments

Only after baseline reports exist should Stage 4C test alternative router strategies.

Candidates may include:

### Candidate A — Current structured router

This remains the control.

### Candidate B — Cheaper/smaller model

Same prompt/contract, lower cost.

Goal: maintain quality while reducing latency/cost.

### Candidate C — Confidence-based escalation

```text
cheap router
   -> high confidence -> accept
   -> low confidence  -> stronger router
```

Evaluation must include the cost of both calls and escalation frequency.

### Candidate D — Prompt/schema refinement

Improve the existing structured contract without changing architecture.

### Candidate E — Learned/adaptive routing

This is last, not first.

A learned classifier/ranker should only be considered after enough labeled examples exist to train/evaluate it without recreating the small-example embedding router that Stage 4B removed.

### Selection rule

A candidate becomes the default only when it beats the baseline on the defined quality/cost/latency trade-off and passes all hard safety constraints.

## 12. Phase 4C.5 — Memory v2 experiments

Candidate improvements should be isolated and evaluated separately.

Possible experiments:

### Semantic memory retrieval

Rank memory by semantic relevance instead of relying mainly on current store search behavior.

### Hybrid memory ranking

Combine:

- semantic relevance,
- recency,
- confidence,
- scope,
- explicitness/importance.

### Structured profile keys

For stable preferences that naturally form key/value facts, e.g. answer style or preferred language, a structured profile representation may resolve contradictions more cleanly than appending natural-language items.

### Contradiction resolution

Detect when a newer durable memory supersedes an older one.

Do not silently delete historical facts unless the storage semantics explicitly distinguish active vs superseded memory.

### Memory consolidation

Merge near-duplicate durable facts only after semantic-dedup evaluation exists.

### Episodic memory

Defer until profile/retrieval evaluation shows a concrete need. Episodic memory adds complexity in retention, ranking, privacy, and forgetting and should not be introduced merely because it is a common agent pattern.

## 13. CI and rollout model

### PR CI — deterministic

Always run:

- dataset schema validation
- unit/contract tests
- deterministic evaluator tests
- isolation/privacy safety cases
- report-schema tests

### Live evaluation — initially non-blocking

Run manually or in an explicitly configured workflow when provider keys are available.

Record:

- model/backend
- git SHA
- dataset hash
- metrics
- latency/cost

### Promotion to blocking gate

A live metric becomes a merge gate only when variance is understood and the dataset has enough representative cases.

### Runtime rollout

Behavioral strategy changes should support:

1. baseline/current strategy,
2. candidate strategy,
3. explicit configuration/feature flag,
4. rollback without a data migration when possible.

For high-risk routing/memory changes, shadow evaluation is preferred before changing user-visible behavior.

## 14. Recommended implementation order

Stage 4C implementation should proceed in this exact order:

### 4C.0A — Evaluation report foundation

- router report schema
- memory report schema
- comparison utility
- failure attribution

### 4C.0B — Dataset expansion

- expand router set by dimensions
- expand memory lifecycle/isolation set
- freeze initial baseline version

### 4C.0C — Baseline measurement

- run current router
- run current memory strategy
- store baseline reports as CI artifacts or documented benchmark outputs

### 4C.1 — Router experiments

- compare model/prompt/escalation candidates
- choose only after measured improvement

### 4C.2 — Memory experiments

- improve write/retrieval/contradiction behavior one dimension at a time

### 4C.3 — Adaptive strategy rollout

- introduce strategy selection/feature flags
- shadow mode
- controlled default promotion

Do **not** start with learned routing, episodic memory, or a large memory refactor.

## 15. Stage 4C definition of done

Stage 4C is complete when all of the following are true:

1. Router, memory, and research have versioned evaluation reports.
2. Router and memory datasets cover the major production behaviors and safety cases.
3. Current production behavior has reproducible baseline reports.
4. At least one router optimization has been evaluated against the baseline; it is either adopted with evidence or explicitly rejected.
5. At least one memory optimization has been evaluated against the baseline; it is either adopted with evidence or explicitly rejected.
6. Cross-user/session isolation and sensitive-memory safety remain hard gates.
7. Router/memory strategy identity and latency are observable.
8. Production strategies can be rolled back without rewriting the core architecture.
9. No runtime phrase/example dataset has been reintroduced as a substitute for evaluation.
10. The canonical production boundary remains understandable and documented.

## 16. Explicitly deferred

The following are not automatically part of Stage 4C:

- backend authentication/authorization redesign
- full tenant-security program
- user-facing transcript history/hydration UI
- Qdrant migration
- multi-agent orchestration
- autonomous self-modifying prompts
- fine-tuning a router model
- episodic-memory graphs
- broad observability vendor migration

They may become separate stages if evaluation or product requirements justify them.

## 17. First implementation PR after this design

The first code PR for Stage 4C should be narrowly scoped to **Evaluation Foundation**, not Router v2.

Expected contents:

- router report schema + richer metrics/confusion matrix
- real memory behavioral evaluator
- expanded deterministic datasets
- baseline/candidate report comparison utility
- evaluator contract tests
- CI deterministic validation

No production routing or memory policy should change in that first PR.
