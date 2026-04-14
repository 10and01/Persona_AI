"""Tests for the database schema DDL generation.

These tests validate that the schema SQL is well-formed and contains the
expected tables, columns, and indexes without requiring a live PostgreSQL
connection.
"""

from __future__ import annotations

import re
import unittest


class TestDatabaseSchema(unittest.TestCase):
    """Validate the generated DDL string."""

    @classmethod
    def setUpClass(cls) -> None:
        from persona_ai.database_schema import generate_schema_sql

        cls.sql = generate_schema_sql()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _table_names(self) -> list[str]:
        return re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", self.sql)

    def _index_names(self) -> list[str]:
        return re.findall(r"CREATE INDEX IF NOT EXISTS\s+(\w+)", self.sql)

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    EXPECTED_TABLES = [
        # L1
        "l1_dialog_records",
        "l1_evidence_refs",
        "l1_entities",
        # L2
        "l2_session_contexts",
        "l2_working_turns",
        "l2_entity_focus",
        # L3
        "l3_profile_versions",
        "l3_profile_fields",
        "l3_field_evidence",
        "l3_field_evidence_refs",
        "l3_field_contradictions",
        # Supporting
        "memory_metadata",
        "memory_mutation_events",
        "audit_events",
        "retry_queue",
        "episodic_vectors",
        "graph_edge_facts",
        "semantic_version_tracker",
    ]

    def test_all_expected_tables_present(self) -> None:
        tables = self._table_names()
        for expected in self.EXPECTED_TABLES:
            self.assertIn(expected, tables, f"Missing table: {expected}")

    def test_table_count(self) -> None:
        tables = self._table_names()
        self.assertEqual(len(tables), len(self.EXPECTED_TABLES))

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------

    EXPECTED_INDEXES = [
        # L1
        "idx_l1_user_id",
        "idx_l1_user_session_turn",
        "idx_l1_user_occurred",
        "idx_l1_sentiment",
        "idx_l1_session_turn",
        "idx_l1_distill_status",
        "idx_l1_evrefs_record",
        "idx_l1_evrefs_turn",
        "idx_l1_entities_record",
        "idx_l1_entities_entity",
        # L2
        "idx_l2_user_id",
        "idx_l2_updated_at",
        "idx_l2_turns_session_turn",
        "idx_l2_entity_focus_session",
        # L3
        "idx_l3_user_version",
        "idx_l3_created_at",
        "idx_l3_fields_uv",
        "idx_l3_fields_confidence",
        "idx_l3_fields_name",
        "idx_l3_evidence_field",
        "idx_l3_evidence_class",
        "idx_l3_evidence_occurred",
        "idx_l3_evrefs_field",
        "idx_l3_evrefs_turn",
        "idx_l3_contradictions_field",
        # Metadata
        "idx_meta_ref",
        "idx_meta_trace",
        "idx_meta_source_turn",
        # Events
        "idx_events_session_turn",
        "idx_events_user",
        "idx_events_trace",
        "idx_events_operation",
        "idx_events_occurred",
        "idx_events_replay",
        # Audit
        "idx_audit_event_type",
        "idx_audit_actor",
        "idx_audit_occurred",
        "idx_audit_hash",
        # Retry
        "idx_retry_operation",
        "idx_retry_updated",
        # Episodic
        "idx_episodic_user",
        "idx_episodic_user_sentiment",
        "idx_episodic_user_occurred",
        # Graph
        "idx_graph_user",
        "idx_graph_confidence",
        "idx_graph_updated",
    ]

    def test_all_expected_indexes_present(self) -> None:
        indexes = self._index_names()
        for expected in self.EXPECTED_INDEXES:
            self.assertIn(expected, indexes, f"Missing index: {expected}")

    def test_index_count(self) -> None:
        indexes = self._index_names()
        self.assertEqual(len(indexes), len(self.EXPECTED_INDEXES))

    # ------------------------------------------------------------------
    # Structural checks
    # ------------------------------------------------------------------

    def test_l1_has_user_id_column(self) -> None:
        self.assertIn("user_id", self.sql)

    def test_l1_has_session_id_column(self) -> None:
        self.assertIn("session_id", self.sql)

    def test_l1_has_sentiment_column(self) -> None:
        self.assertIn("sentiment", self.sql)

    def test_l1_has_distill_status_check(self) -> None:
        self.assertIn("CHECK (distill_status IN", self.sql)

    def test_l3_composite_primary_key(self) -> None:
        self.assertIn("PRIMARY KEY (user_id, version)", self.sql)

    def test_audit_hash_chain_columns(self) -> None:
        self.assertIn("prev_hash", self.sql)
        self.assertIn("hash", self.sql)

    def test_episodic_idempotency_unique(self) -> None:
        self.assertIn("idempotency_key", self.sql)
        self.assertRegex(self.sql, r"idempotency_key\s+TEXT\s+NOT NULL\s+UNIQUE")

    def test_retry_queue_primary_key(self) -> None:
        # The retry queue uses 'key' as PK.
        self.assertRegex(self.sql, r"key\s+TEXT\s+PRIMARY KEY")

    def test_graph_edge_facts_unique_constraint(self) -> None:
        self.assertIn("UNIQUE (user_id, trait_name)", self.sql)

    def test_evidence_class_check_constraint(self) -> None:
        self.assertIn("explicit_declaration", self.sql)
        self.assertIn("direct_feedback", self.sql)
        self.assertIn("behavioral_signal", self.sql)
        self.assertIn("statistical_inference", self.sql)

    def test_foreign_key_l1_evidence_refs(self) -> None:
        self.assertIn(
            "REFERENCES l1_dialog_records (record_id) ON DELETE CASCADE",
            self.sql,
        )

    def test_foreign_key_l3_profile_fields(self) -> None:
        self.assertIn(
            "REFERENCES l3_profile_versions (user_id, version) ON DELETE CASCADE",
            self.sql,
        )

    def test_no_duplicate_semicolons(self) -> None:
        # Catch accidental `;;` which breaks some migration runners.
        self.assertNotIn(";;", self.sql)

    # ------------------------------------------------------------------
    # Migrate module
    # ------------------------------------------------------------------

    def test_migrate_echo_mode(self) -> None:
        """--echo should return the SQL without connecting to a database."""
        import io
        import contextlib

        from persona_ai.migrate import run_migration

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run_migration(echo=True)

        output = buf.getvalue()
        self.assertIn("CREATE TABLE", output)
        self.assertIn("CREATE INDEX", output)


if __name__ == "__main__":
    unittest.main()
