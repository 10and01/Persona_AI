"""
Database schema definition for the Persona AI three-layer memory system.

Provides DDL generation for PostgreSQL.  Each table maps to a dataclass or
runtime structure already used by the in-memory implementation so that the
schema can serve as the persistence back-end for MemoryStore, episodic /
semantic adapters, the event bus, and the audit log.

Tables
------
Layer 1 – append-only dialog evidence
    l1_dialog_records, l1_evidence_refs, l1_entities

Layer 2 – mutable session working memory
    l2_session_contexts, l2_working_turns, l2_entity_focus

Layer 3 – versioned semantic profile
    l3_profile_versions, l3_profile_fields, l3_field_evidence,
    l3_field_evidence_refs, l3_field_contradictions

Supporting infrastructure
    memory_metadata, memory_mutation_events, audit_events,
    retry_queue, graph_edge_facts, episodic_vectors

Every column that appears in a WHERE, JOIN, or ORDER BY clause in the
existing Python code-paths has a corresponding index.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# DDL as a single idempotent migration string
# ---------------------------------------------------------------------------

SCHEMA_SQL = """\
-- ==========================================================================
-- Persona AI – Three-Layer Memory System  (PostgreSQL DDL)
-- ==========================================================================
-- Generated from the data-model definitions in src/persona_ai/models.py,
-- storage.py, memory_events.py, audit.py, retry_queue.py,
-- episodic_store_qdrant.py, and semantic_store_neo4j.py.
--
-- Convention: every table uses UUID / TEXT primary keys that match the
-- identifiers already produced by the Python runtime.  JSON(B) columns
-- store semi-structured payloads; strongly-typed columns are added for
-- every field that participates in a WHERE, JOIN, or ORDER BY clause so
-- that indexes can be built on them.
-- ==========================================================================

-- --------------------------------------------------------------------------
-- 1.  L1 – Append-Only Dialog Evidence
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS l1_dialog_records (
    record_id           TEXT        PRIMARY KEY,            -- "{session_id}:{turn_id}"
    user_id             TEXT        NOT NULL,
    session_id          TEXT        NOT NULL,
    turn_id             INTEGER     NOT NULL,
    user_input          TEXT        NOT NULL DEFAULT '',
    assistant_output    TEXT        NOT NULL DEFAULT '',
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata            JSONB       NOT NULL DEFAULT '{}',
    sentiment           TEXT        NOT NULL DEFAULT 'neutral',
    entities            JSONB       NOT NULL DEFAULT '[]',  -- JSON array of strings
    distill_status      TEXT        NOT NULL DEFAULT 'pending'
        CHECK (distill_status IN ('pending', 'completed', 'skipped', 'failed'))
);

-- WHERE user_id = ?
CREATE INDEX IF NOT EXISTS idx_l1_user_id
    ON l1_dialog_records (user_id);

-- WHERE user_id = ? AND session_id = ? AND turn_id = ?
CREATE INDEX IF NOT EXISTS idx_l1_user_session_turn
    ON l1_dialog_records (user_id, session_id, turn_id);

-- WHERE user_id = ? ORDER BY occurred_at DESC  (recent_l1, retention cutoff)
CREATE INDEX IF NOT EXISTS idx_l1_user_occurred
    ON l1_dialog_records (user_id, occurred_at DESC);

-- WHERE sentiment = ?  (episodic search filter)
CREATE INDEX IF NOT EXISTS idx_l1_sentiment
    ON l1_dialog_records (sentiment);

-- WHERE session_id = ? AND turn_id = ?  (build_chat_payload lookup)
CREATE INDEX IF NOT EXISTS idx_l1_session_turn
    ON l1_dialog_records (session_id, turn_id);

-- WHERE distill_status = ?
CREATE INDEX IF NOT EXISTS idx_l1_distill_status
    ON l1_dialog_records (distill_status);


-- Evidence references attached to each L1 record
CREATE TABLE IF NOT EXISTS l1_evidence_refs (
    id                  BIGSERIAL   PRIMARY KEY,
    record_id           TEXT        NOT NULL
        REFERENCES l1_dialog_records (record_id) ON DELETE CASCADE,
    source_layer        TEXT        NOT NULL,
    source_id           TEXT        NOT NULL,
    source_turn_id      INTEGER     NOT NULL
);

-- JOIN l1_dialog_records.record_id = l1_evidence_refs.record_id
CREATE INDEX IF NOT EXISTS idx_l1_evrefs_record
    ON l1_evidence_refs (record_id);

-- WHERE source_turn_id = ?
CREATE INDEX IF NOT EXISTS idx_l1_evrefs_turn
    ON l1_evidence_refs (source_turn_id);


-- Entities stored in normalised form for efficient filtering
CREATE TABLE IF NOT EXISTS l1_entities (
    id                  BIGSERIAL   PRIMARY KEY,
    record_id           TEXT        NOT NULL
        REFERENCES l1_dialog_records (record_id) ON DELETE CASCADE,
    entity              TEXT        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_l1_entities_record
    ON l1_entities (record_id);

-- WHERE entity = ?  (entity-based search)
CREATE INDEX IF NOT EXISTS idx_l1_entities_entity
    ON l1_entities (entity);


-- --------------------------------------------------------------------------
-- 2.  L2 – Mutable Session Working Memory
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS l2_session_contexts (
    session_id          TEXT        PRIMARY KEY,
    user_id             TEXT        NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    context             JSONB       NOT NULL DEFAULT '{}',
    summary             TEXT        NOT NULL DEFAULT '',
    task_state          JSONB       NOT NULL DEFAULT '{}',
    distill_status      TEXT        NOT NULL DEFAULT 'pending'
        CHECK (distill_status IN ('pending', 'completed', 'skipped', 'failed'))
);

-- WHERE user_id = ?  (delete_user_scope)
CREATE INDEX IF NOT EXISTS idx_l2_user_id
    ON l2_session_contexts (user_id);

-- WHERE updated_at >= ?  (retention cutoff)
CREATE INDEX IF NOT EXISTS idx_l2_updated_at
    ON l2_session_contexts (updated_at);


-- Individual turns stored within the working window
CREATE TABLE IF NOT EXISTS l2_working_turns (
    id                  BIGSERIAL   PRIMARY KEY,
    session_id          TEXT        NOT NULL
        REFERENCES l2_session_contexts (session_id) ON DELETE CASCADE,
    turn_id             INTEGER     NOT NULL,
    user_input          TEXT        NOT NULL DEFAULT '',
    assistant_output    TEXT        NOT NULL DEFAULT '',
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    sentiment           TEXT        NOT NULL DEFAULT 'neutral',
    entities            JSONB       NOT NULL DEFAULT '[]'
);

-- JOIN / WHERE session_id ORDER BY turn_id
CREATE INDEX IF NOT EXISTS idx_l2_turns_session_turn
    ON l2_working_turns (session_id, turn_id);


-- Entity-focus list per session (normalised)
CREATE TABLE IF NOT EXISTS l2_entity_focus (
    id                  BIGSERIAL   PRIMARY KEY,
    session_id          TEXT        NOT NULL
        REFERENCES l2_session_contexts (session_id) ON DELETE CASCADE,
    entity              TEXT        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_l2_entity_focus_session
    ON l2_entity_focus (session_id);


-- --------------------------------------------------------------------------
-- 3.  L3 – Versioned Semantic Profile
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS l3_profile_versions (
    user_id             TEXT        NOT NULL,
    version             INTEGER     NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    previous_version    INTEGER,
    metadata            JSONB       NOT NULL DEFAULT '{}',
    distill_status      TEXT        NOT NULL DEFAULT 'pending'
        CHECK (distill_status IN ('pending', 'completed', 'skipped', 'failed')),
    PRIMARY KEY (user_id, version)
);

-- WHERE user_id = ? ORDER BY version DESC  (latest_l3)
CREATE INDEX IF NOT EXISTS idx_l3_user_version
    ON l3_profile_versions (user_id, version DESC);

-- ORDER BY created_at  (timeline rendering)
CREATE INDEX IF NOT EXISTS idx_l3_created_at
    ON l3_profile_versions (created_at);


-- Profile fields per version
CREATE TABLE IF NOT EXISTS l3_profile_fields (
    id                  BIGSERIAL   PRIMARY KEY,
    user_id             TEXT        NOT NULL,
    version             INTEGER     NOT NULL,
    field_name          TEXT        NOT NULL,
    field_value         TEXT,                               -- serialised Any
    confidence          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id, version)
        REFERENCES l3_profile_versions (user_id, version) ON DELETE CASCADE,
    UNIQUE (user_id, version, field_name)
);

-- WHERE user_id = ? AND version = ?  (join back to version)
CREATE INDEX IF NOT EXISTS idx_l3_fields_uv
    ON l3_profile_fields (user_id, version);

-- WHERE confidence >= ?  (retrieval threshold)
CREATE INDEX IF NOT EXISTS idx_l3_fields_confidence
    ON l3_profile_fields (confidence);

-- WHERE field_name = ?  (rollback_field, aggregate_fields)
CREATE INDEX IF NOT EXISTS idx_l3_fields_name
    ON l3_profile_fields (field_name);


-- Evidence entries linked to a profile field
CREATE TABLE IF NOT EXISTS l3_field_evidence (
    id                  BIGSERIAL   PRIMARY KEY,
    field_id            BIGINT      NOT NULL
        REFERENCES l3_profile_fields (id) ON DELETE CASCADE,
    evidence_class      TEXT        NOT NULL
        CHECK (evidence_class IN (
            'explicit_declaration', 'direct_feedback',
            'behavioral_signal', 'statistical_inference'
        )),
    evidence_value      TEXT,
    confidence_hint     DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    source              TEXT        NOT NULL DEFAULT ''
);

-- JOIN l3_profile_fields.id = l3_field_evidence.field_id
CREATE INDEX IF NOT EXISTS idx_l3_evidence_field
    ON l3_field_evidence (field_id);

-- WHERE evidence_class = ?  (conflict resolution by class)
CREATE INDEX IF NOT EXISTS idx_l3_evidence_class
    ON l3_field_evidence (evidence_class);

-- ORDER BY occurred_at  (recency factor)
CREATE INDEX IF NOT EXISTS idx_l3_evidence_occurred
    ON l3_field_evidence (occurred_at);


-- Evidence refs per profile field
CREATE TABLE IF NOT EXISTS l3_field_evidence_refs (
    id                  BIGSERIAL   PRIMARY KEY,
    field_id            BIGINT      NOT NULL
        REFERENCES l3_profile_fields (id) ON DELETE CASCADE,
    source_layer        TEXT        NOT NULL,
    source_id           TEXT        NOT NULL,
    source_turn_id      INTEGER     NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_l3_evrefs_field
    ON l3_field_evidence_refs (field_id);

CREATE INDEX IF NOT EXISTS idx_l3_evrefs_turn
    ON l3_field_evidence_refs (source_turn_id);


-- Contradictions (structurally identical to evidence)
CREATE TABLE IF NOT EXISTS l3_field_contradictions (
    id                  BIGSERIAL   PRIMARY KEY,
    field_id            BIGINT      NOT NULL
        REFERENCES l3_profile_fields (id) ON DELETE CASCADE,
    evidence_class      TEXT        NOT NULL
        CHECK (evidence_class IN (
            'explicit_declaration', 'direct_feedback',
            'behavioral_signal', 'statistical_inference'
        )),
    evidence_value      TEXT,
    confidence_hint     DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    source              TEXT        NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_l3_contradictions_field
    ON l3_field_contradictions (field_id);


-- --------------------------------------------------------------------------
-- 4.  Standardised Memory Metadata
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_metadata (
    id                  BIGSERIAL   PRIMARY KEY,
    ref_table           TEXT        NOT NULL,               -- 'l1', 'l3', etc.
    ref_id              TEXT        NOT NULL,               -- PK of the source row
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    trace_id            TEXT        NOT NULL DEFAULT '',
    confidence          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    source_turn_id      INTEGER     NOT NULL DEFAULT -1
);

-- WHERE ref_table = ? AND ref_id = ?
CREATE INDEX IF NOT EXISTS idx_meta_ref
    ON memory_metadata (ref_table, ref_id);

-- WHERE trace_id = ?  (correlation)
CREATE INDEX IF NOT EXISTS idx_meta_trace
    ON memory_metadata (trace_id);

-- WHERE source_turn_id = ?
CREATE INDEX IF NOT EXISTS idx_meta_source_turn
    ON memory_metadata (source_turn_id);


-- --------------------------------------------------------------------------
-- 5.  Memory Mutation Events (Event Bus)
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_mutation_events (
    id                  BIGSERIAL   PRIMARY KEY,
    layer               TEXT        NOT NULL,
    operation           TEXT        NOT NULL,
    user_id             TEXT        NOT NULL,
    session_id          TEXT        NOT NULL,
    turn_id             INTEGER     NOT NULL,
    trace_id            TEXT        NOT NULL,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    before_payload      JSONB       NOT NULL DEFAULT '{}',
    after_payload       JSONB       NOT NULL DEFAULT '{}'
);

-- WHERE session_id = ? AND turn_id = ?  (for_turn, replay_turn)
CREATE INDEX IF NOT EXISTS idx_events_session_turn
    ON memory_mutation_events (session_id, turn_id);

-- WHERE user_id = ?
CREATE INDEX IF NOT EXISTS idx_events_user
    ON memory_mutation_events (user_id);

-- WHERE trace_id = ?
CREATE INDEX IF NOT EXISTS idx_events_trace
    ON memory_mutation_events (trace_id);

-- WHERE operation = ?  (distillation_requested / distillation_completed)
CREATE INDEX IF NOT EXISTS idx_events_operation
    ON memory_mutation_events (operation);

-- ORDER BY occurred_at  (replay_turn sort)
CREATE INDEX IF NOT EXISTS idx_events_occurred
    ON memory_mutation_events (occurred_at);

-- Composite for efficient replay: session + turn + timestamp ordering
CREATE INDEX IF NOT EXISTS idx_events_replay
    ON memory_mutation_events (session_id, turn_id, occurred_at);


-- --------------------------------------------------------------------------
-- 6.  Immutable Audit Log
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_events (
    id                  BIGSERIAL   PRIMARY KEY,
    event_type          TEXT        NOT NULL,
    actor               TEXT        NOT NULL,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    result              TEXT        NOT NULL,
    details             JSONB       NOT NULL DEFAULT '{}',
    prev_hash           TEXT        NOT NULL DEFAULT 'genesis',
    hash                TEXT        NOT NULL
);

-- WHERE event_type = ?
CREATE INDEX IF NOT EXISTS idx_audit_event_type
    ON audit_events (event_type);

-- WHERE actor = ?
CREATE INDEX IF NOT EXISTS idx_audit_actor
    ON audit_events (actor);

-- ORDER BY occurred_at  (chain verification, timeline)
CREATE INDEX IF NOT EXISTS idx_audit_occurred
    ON audit_events (occurred_at);

-- WHERE hash = ?  (chain look-up)
CREATE INDEX IF NOT EXISTS idx_audit_hash
    ON audit_events (hash);


-- --------------------------------------------------------------------------
-- 7.  Retry Queue
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS retry_queue (
    key                 TEXT        PRIMARY KEY,
    operation           TEXT        NOT NULL,
    payload             JSONB       NOT NULL DEFAULT '{}',
    attempts            INTEGER     NOT NULL DEFAULT 1,
    last_error          TEXT        NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- WHERE operation = ?  (list_records filter)
CREATE INDEX IF NOT EXISTS idx_retry_operation
    ON retry_queue (operation);

-- ORDER BY updated_at  (list_records sort)
CREATE INDEX IF NOT EXISTS idx_retry_updated
    ON retry_queue (updated_at);


-- --------------------------------------------------------------------------
-- 8.  Episodic Vectors  (Qdrant adapter mirror)
-- --------------------------------------------------------------------------
-- This table supports the local-fallback episodic store.  In production the
-- vector column would be replaced by a pgvector extension column, but the
-- idempotency and metadata columns are always useful.

CREATE TABLE IF NOT EXISTS episodic_vectors (
    record_id           TEXT        PRIMARY KEY,
    idempotency_key     TEXT        NOT NULL UNIQUE,
    user_id             TEXT        NOT NULL,
    session_id          TEXT        NOT NULL,
    turn_id             INTEGER     NOT NULL,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    sentiment           TEXT        NOT NULL DEFAULT 'neutral',
    vector              JSONB       NOT NULL DEFAULT '[]',  -- List[float] serialised
    metadata            JSONB       NOT NULL DEFAULT '{}'
);

-- WHERE user_id = ?  (search_dialogs, delete_user_scope)
CREATE INDEX IF NOT EXISTS idx_episodic_user
    ON episodic_vectors (user_id);

-- WHERE user_id = ? AND sentiment = ?
CREATE INDEX IF NOT EXISTS idx_episodic_user_sentiment
    ON episodic_vectors (user_id, sentiment);

-- WHERE user_id = ? AND occurred_at BETWEEN ? AND ?
CREATE INDEX IF NOT EXISTS idx_episodic_user_occurred
    ON episodic_vectors (user_id, occurred_at);

-- WHERE idempotency_key = ?  (upsert dedup – covered by UNIQUE)


-- --------------------------------------------------------------------------
-- 9.  Graph Edge Facts  (Neo4j adapter mirror)
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS graph_edge_facts (
    id                  BIGSERIAL   PRIMARY KEY,
    user_id             TEXT        NOT NULL,
    trait_name          TEXT        NOT NULL,
    trait_value          TEXT,
    confidence          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    evidence_count      INTEGER     NOT NULL DEFAULT 0,
    UNIQUE (user_id, trait_name)
);

-- WHERE user_id = ?  (latest_profile_version, delete_user_scope)
CREATE INDEX IF NOT EXISTS idx_graph_user
    ON graph_edge_facts (user_id);

-- WHERE confidence >= ?  (retrieval threshold)
CREATE INDEX IF NOT EXISTS idx_graph_confidence
    ON graph_edge_facts (confidence);

-- ORDER BY updated_at DESC  (recency ranking)
CREATE INDEX IF NOT EXISTS idx_graph_updated
    ON graph_edge_facts (updated_at DESC);


-- Semantic version tracking per user
CREATE TABLE IF NOT EXISTS semantic_version_tracker (
    user_id             TEXT        PRIMARY KEY,
    latest_version      INTEGER     NOT NULL DEFAULT 0
);
"""


def generate_schema_sql() -> str:
    """Return the full DDL string for the Persona AI database."""
    return SCHEMA_SQL
