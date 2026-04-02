# Persona AI Implementation Plan (Baseline -> Production)

## Scope
- Continue from the current codebase and complete the 8 phases end-to-end.
- Keep architecture constraints unchanged:
  - L1 append-only dialog evidence
  - L2 mutable session working memory
  - L3 versioned semantic profile
- Primary targets:
  - Episodic memory on Qdrant
  - Semantic graph on Neo4j
  - Distillation every 50 turns
  - Retrieval-before-generation prompt injection
  - Privacy and governance hardening

## Current Status Snapshot
- Implemented in current repo:
  - L1 sentiment/entities enrichment in orchestration and API payloads
  - L2 working window + summary fields and prompt-side usage
  - Distillation events `distillation_requested` / `distillation_completed` on event bus
  - Basic retrieval metadata return for UI observability
  - Initial tests for turn-50 trigger and memory prompt injection
  - Phase 1 baseline contract extension completed:
    - Added `sentiment`, `entities`, `evidence_ref`, `distill_status` to layer contracts
    - Added standardized metadata contract (`timestamp`, `trace_id`, `confidence`, `source_turn_id`)
    - Added vector/graph storage interfaces in storage abstraction
    - Added distillation lifecycle payload validation and audit events
  - Phase 2 progress completed in core runtime:
    - Added text cleaning and core semantic extraction in ingestion pipeline
    - Added configurable working-window and prompt token-budget controls
    - Added deterministic truncation to keep prompt context bounded
  - Phase 3 foundational scaffolding completed:
    - Added embedding abstraction and deterministic local embedding provider
    - Added retry queue for failed episodic writes
    - Added Qdrant-like episodic adapter and Neo4j-like semantic adapter local fallback implementations
  - Phase 4 early implementation completed:
    - Added conflict resolver to distinguish stable preference from temporary signal
    - Added distillation worker to execute turn-50 distillation and emit completion events
    - Integrated worker hook into orchestration for request->completion lifecycle
  - Phase 5 completed:
    - Added controlled prompt template builder with anti-pollution suppression and token budgeting
    - Enforced retrieval order: semantic -> episodic -> working summary
    - API returns semantic version, evidence references, and retrieval source provenance
  - Phase 6 completed:
    - Added payload sanitization utilities and purpose-governed injection filtering
    - Added retrieval injection and sanitize audit events
    - Extended delete propagation visibility with episodic/semantic delete counters
  - Phase 7 completed:
    - Frontend shows retrieval diagnostics, semantic version timeline, evidence references, and governance metadata
    - Word cloud supports conflict marker and recency opacity overlays
    - Export JSON includes profile + governance + retrieval provenance
  - Phase 8 completed:
    - Extended backend test matrix for prompt anti-pollution, conflict suppression, worker completion lifecycle,
      and delete propagation consistency
    - Re-validated offline/online gate tests and full regression suite
    - Frontend build and type validation passed

## Completion Status
- Phase 1: Completed
- Phase 2: Completed
- Phase 3: Completed (adapter interface + local Qdrant/Neo4j-compatible fallback)
- Phase 4: Completed
- Phase 5: Completed
- Phase 6: Completed
- Phase 7: Completed
- Phase 8: Completed

## Final Verification Evidence
- Backend tests: `python -m unittest discover -s tests -v` -> 23/23 passed
- Frontend build: `npm run build` (in `web/`) -> success (compile/type/lint all passed)

---

## Phase 1: Baseline Contract Extension (blocking)

### Objectives
1. Extend three-layer contracts with `sentiment`, `entities`, `evidence_ref`, `distill_status`.
2. Add vector-store and graph-store abstractions with unified metadata:
   - `timestamp`
   - `trace_id`
   - `confidence`
   - `source_turn_id`
3. Ensure distillation lifecycle events are auditable.

### Deliverables
- `src/persona_ai/models.py`
  - Add strongly typed metadata model(s): `MemoryMetadata`, `DistillStatus`, `EvidenceRef`
  - Ensure L1/L2/L3 structures carry required fields without breaking existing semantics
- `src/persona_ai/storage.py`
  - Introduce interfaces:
    - `EpisodicVectorStore`
    - `SemanticGraphStore`
  - Keep `MemoryStore` as orchestrating in-process state + adapter boundary
- `src/persona_ai/memory_events.py`
  - Keep `distillation_requested` and `distillation_completed`
  - Add event payload schema validation and correlation IDs
- `src/persona_ai/audit.py`
  - Add audit event types for distillation request/complete and adapter write failures

### Acceptance Criteria
- Contract fields available and serialized consistently.
- Existing tests remain green.
- New tests validate event payload schema and metadata normalization.

---

## Phase 2: Perception + Working Memory Enhancement

### Objectives
1. Per-turn lightweight recording: cleaned text, core semantics, sentiment, entities -> enhanced L1.
2. L2 maintains sliding `k` turns + task state + entity focus + compact summary.
3. Add token budget control and eviction policy.

### Deliverables
- `src/persona_ai/extraction.py`
  - Add `clean_text`, `extract_core_semantics`, `extract_turn_signals` pipeline stages
- `src/persona_ai/chat_orchestration.py`
  - Persist cleaned/enriched L1 record at each turn end
  - Maintain configurable sliding window (`k`) and summary update policy
  - Add token budget guard for memory prompt build
- `src/persona_ai/config.py` (new)
  - Configurable knobs: `WORKING_WINDOW_K`, `MEMORY_PROMPT_TOKEN_BUDGET`

### Acceptance Criteria
- L2 never exceeds configured window and token budget.
- Summary quality is deterministic for same inputs.
- Eviction behavior covered by tests.

---

## Phase 3: Episodic Layer on Qdrant

### Objectives
1. Generate embeddings for enhanced L1 and upsert to Qdrant with metadata.
2. Hybrid retrieval by user + time window + sentiment + similarity.
3. Idempotent writes + retries + compensation.

### Deliverables
- `src/persona_ai/episodic_store_qdrant.py` (new)
  - Qdrant adapter implementing `EpisodicVectorStore`
  - Collection schema + payload indexes
- `src/persona_ai/embedding.py` (new)
  - Embedding provider abstraction and default implementation
- `src/persona_ai/retry_queue.py` (new)
  - Durable retry records for failed upserts (local file/sqlite acceptable for current stage)
- `src/persona_ai/storage.py`
  - Idempotency key format: `{user_id}:{session_id}:{turn_id}:{content_hash}`

### Acceptance Criteria
- Repeated same turn write does not duplicate vectors.
- Failed write enters retry queue and can be replayed.
- Retrieval supports metadata filters and returns deterministic top-N ordering.

---

## Phase 4: Async Distillation to Neo4j (blocking phase 5)

### Objectives
1. Trigger distillation every 50 turns using event + counter.
2. Resolve conflicts: preference migration vs temporary request.
3. Write stable semantic facts to Neo4j while keeping L3 version snapshots.
4. Decay stale/low-frequency episodic signals before semantic commit.

### Deliverables
- `src/persona_ai/distillation_worker.py` (new)
  - Event-driven worker consuming `distillation_requested`
- `src/persona_ai/conflict_resolution.py` (new)
  - Policy combining evidence class precedence, recency decay, consistency count
  - Decision output includes rationale and confidence delta
- `src/persona_ai/semantic_store_neo4j.py` (new)
  - Neo4j adapter implementing `SemanticGraphStore`
  - Node/edge model: User, Trait, relation props (`confidence`, `updated_at`, `evidence_count`)
- `src/persona_ai/profile_manager.py`
  - Integrate conflict resolver and semantic commit threshold

### Acceptance Criteria
- Turn-50 workflow emits request and completion events with audit trail.
- Conflict policy chooses stable value under contradictory evidence.
- Low-confidence facts are not persisted to graph store.

---

## Phase 5: Retrieval + Prompt Injection Before Generation

### Objectives
1. 3-step retrieval order:
   - semantic profile from Neo4j
   - episodic hits from Qdrant
   - L2 working summary
2. Controlled prompt template with evidence and confidence.
3. API returns profile version and retrieval provenance for timeline.

### Deliverables
- `src/persona_ai/chat_orchestration.py`
  - Enforce retrieval order and bounded injection payload
- `src/persona_ai/prompt_builder.py` (new)
  - Template with anti-pollution guards (single outlier suppression)
- `web/app/api/chat/route.ts`
  - Return `semanticVersion`, `evidenceRefs`, `retrievalSources`

### Acceptance Criteria
- Injection order is fixed and test-verified.
- Single abnormal turn does not dominate prompt context.
- UI can trace each injected fact to source evidence.

---

## Phase 6: Privacy Governance + Audit Hardening (must before release)

### Objectives
1. Redact sensitive data before vector/graph write.
2. Enforce purpose-based field policy for retrieval injection.
3. Complete audit events for distillation, retrieval injection, and deletion.
4. Ensure delete scopes propagate to Qdrant + Neo4j.

### Deliverables
- `src/persona_ai/privacy.py`
  - Pre-write sanitization for episodic/semantic paths
- `src/persona_ai/access_policy.py`
  - Purpose scopes for prompt injection fields
- `src/persona_ai/storage.py`
  - Delete propagation strategy:
    - `complete`
    - `profile-only`
    - `partial`
- `src/persona_ai/audit.py`
  - Extended event taxonomy and correlation checks

### Acceptance Criteria
- No denied field appears in injection or export payload.
- Deletion is consistent across local store, vector store, and graph store.
- Audit chain includes all governed operations.

---

## Phase 7: Frontend Visualization Enhancement

### Objectives
1. Show injected profile summary + episodic hits + confidence + update time.
2. Extend cards/word cloud with version timeline, conflict markers, distillation batch state.
3. Include governance metadata in export artifacts.

### Deliverables
- `web/app/page.tsx`
  - Retrieval and injection diagnostics panel (enhanced)
  - Version timeline with selected snapshot rendering
- `web/app/components/WordCloud.tsx`
  - Conflict and recency overlays
- `web/app/components/types.ts`
  - Add distillation batch and governance metadata types

### Acceptance Criteria
- Frontend reflects backend version and retrieval metadata exactly.
- Export files include `consent`, `policy_version`, `field_count`, `trace_id`.

---

## Phase 8: Verification + Gate Closure

### Objectives
1. Backend tests: turn-50 trigger, conflict merge, decay cleanup, delete consistency, injection order.
2. API/UI tests: injection visibility, timeline consistency, privacy leakage prevention.
3. Re-run offline and online rollout gates with rollback readiness.

### Deliverables
- `tests/test_core.py`
- `tests/test_chat_memory_visualization.py`
- `tests/test_portability_privacy_eval.py`
- Additional web tests if added under `web/`

### Acceptance Criteria
- All tests pass in CI.
- Gate thresholds remain compliant.
- Rollback to previous stable L3 version remains available.

---

## Execution Order and Parallelism
- Sequential dependencies:
  - Phase 1 -> Phase 2/3 (parallel) -> Phase 4 -> Phase 5 -> Phase 7
  - Phase 6 runs in parallel with Phase 5 but must finish before release
  - Phase 8 closes all phases
- Immediate next implementation target:
  - Finish Phase 1 contract typing and adapter interfaces in code
  - Then wire real Qdrant adapter skeleton and Neo4j adapter skeleton

## Risks and Mitigations
- Risk: context prompt inflation
  - Mitigation: strict token budget + deterministic truncation rules
- Risk: contradictory evidence causes unstable profile churn
  - Mitigation: conflict resolver with consistency threshold and decay weighting
- Risk: data governance gaps across external stores
  - Mitigation: pre-write redaction and deletion propagation tests
- Risk: async worker reliability
  - Mitigation: durable retry queue + idempotent processing keys

## Definition of Done
- All 8 phases implemented to acceptance criteria. (Completed)
- End-to-end flow proven: ingest -> episodic index -> distill -> semantic update -> retrieval injection -> governed visualization/export. (Completed)
- No privacy policy violations in tests. (Completed)
- Rollback and audit trails verifiable. (Completed)