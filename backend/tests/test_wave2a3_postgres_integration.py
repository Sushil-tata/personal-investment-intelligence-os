from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

from piios_backend.core.config import settings


REVISION_WAVE2A3 = "0007_claims_evidence_provenance"
REVISION_WAVE2A2 = "0006_thesis_versioned_domain"
REVISION_HEAD = "head"


def _alembic_config(db_url: str) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


@pytest.fixture(scope="module")
def pg_engine():
    config = _alembic_config(settings.db_url)
    command.upgrade(config, REVISION_WAVE2A3)
    engine = create_engine(settings.db_url)
    try:
        yield engine
    finally:
        # Restore shared test DB to head so later modules are independent of execution order.
        command.upgrade(config, REVISION_HEAD)


def _seed_thesis_root_and_version(conn: sa.Connection, thesis_id: str) -> str:
    conn.execute(
        sa.text(
            """
            INSERT INTO thesis_roots (
                thesis_id, ticker, lifecycle_status, current_version_number,
                created_at, updated_at, closed_reason, closed_at
            ) VALUES (
                :thesis_id, 'NVDA', 'RESEARCHED', 1,
                '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', NULL, NULL
            )
            """
        ),
        {"thesis_id": thesis_id},
    )

    version_id = f"{thesis_id}:v1"
    conn.execute(
        sa.text(
            """
            INSERT INTO thesis_versions (
                version_id, thesis_id, version_number,
                asset_name, theme, bucket, thesis,
                bull_case, bear_case, why_now, why_not_now,
                invalidation_trigger, valuation_notes, expected_holding_period,
                source_documents, confidence_score, status, created_at
            ) VALUES (
                :version_id, :thesis_id, 1,
                'NVIDIA', 'AI Infrastructure', 'Strategic Alpha', 'Core thesis',
                'Bull', 'Bear', 'Why now', 'Why not now',
                'Invalidation', 'Valuation', '2-5 years',
                :source_documents, 78.0, 'ACTIVE', '2026-01-01T00:00:00+00:00'
            )
            """
        ),
        {"version_id": version_id, "thesis_id": thesis_id, "source_documents": '["rd901"]'},
    )
    return version_id


def test_wave2a3_postgres_fk_uniqueness_and_indexes(pg_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    thesis_id = f"t_pg_fk_{suffix}"

    with pg_engine.begin() as conn:
        version_id = _seed_thesis_root_and_version(conn, thesis_id)

        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO thesis_claims (
                        claim_id, thesis_version_id, thesis_id, claim_key, claim_text,
                        claim_type, status, active_from, active_to, created_at, updated_at
                    ) VALUES (
                        :claim_id, 'missing_version:v1', :thesis_id, 'k1', 'Bad FK claim',
                        'fundamental', 'ACTIVE', :ts, NULL, :ts, :ts
                    )
                    """
                ),
                {"claim_id": f"cl_bad_fk_{suffix}", "thesis_id": thesis_id, "ts": "2026-01-02T00:00:00+00:00"},
            )
        sp.rollback()

        conn.execute(
            sa.text(
                """
                INSERT INTO thesis_claims (
                    claim_id, thesis_version_id, thesis_id, claim_key, claim_text,
                    claim_type, status, active_from, active_to, created_at, updated_at
                ) VALUES (
                    :claim_id, :version_id, :thesis_id, 'k1', 'Valid claim',
                    'fundamental', 'ACTIVE', :ts, NULL, :ts, :ts
                )
                """
            ),
            {
                "claim_id": f"cl_valid_{suffix}",
                "version_id": version_id,
                "thesis_id": thesis_id,
                "ts": "2026-01-02T00:00:00+00:00",
            },
        )

        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO thesis_claims (
                        claim_id, thesis_version_id, thesis_id, claim_key, claim_text,
                        claim_type, status, active_from, active_to, created_at, updated_at
                    ) VALUES (
                        :claim_id, :version_id, :thesis_id, 'k2', 'Duplicate claim id',
                        'fundamental', 'ACTIVE', :ts, NULL, :ts, :ts
                    )
                    """
                ),
                {
                    "claim_id": f"cl_valid_{suffix}",
                    "version_id": version_id,
                    "thesis_id": thesis_id,
                    "ts": "2026-01-02T00:00:00+00:00",
                },
            )
        sp.rollback()

        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO thesis_claims (
                        claim_id, thesis_version_id, thesis_id, claim_key, claim_text,
                        claim_type, status, active_from, active_to, created_at, updated_at
                    ) VALUES (
                        :claim_id, :version_id, :thesis_id, 'k1', 'Duplicate key within version',
                        'fundamental', 'ACTIVE', :ts, NULL, :ts, :ts
                    )
                    """
                ),
                {
                    "claim_id": f"cl_dup_key_{suffix}",
                    "version_id": version_id,
                    "thesis_id": thesis_id,
                    "ts": "2026-01-02T00:00:00+00:00",
                },
            )
        sp.rollback()

        conn.execute(
            sa.text(
                """
                INSERT INTO evidence_sources (
                    source_id, source_type, publisher, url, source_system,
                    published_at, retrieved_at, credibility_tier, created_at
                ) VALUES (
                    :source_id, 'RESEARCH', 'Research Desk', 'https://example.com/rd', 'postgres_test',
                    '2026-01-01T00:00:00+00:00', '2026-01-02T00:00:00+00:00', 'A', '2026-01-02T00:00:00+00:00'
                )
                """
            ),
            {"source_id": f"src_{suffix}"},
        )

        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO evidence_items (
                        evidence_id, source_id, title, excerpt, content_hash, as_of_date, metadata_json, created_at
                    ) VALUES (
                        :evidence_id, 'missing_source', 'Bad source FK', 'x', 'h0', '2026-01-02', '{}',
                        '2026-01-02T00:00:00+00:00'
                    )
                    """
                ),
                {"evidence_id": f"ev_bad_fk_{suffix}"},
            )
        sp.rollback()

        conn.execute(
            sa.text(
                """
                INSERT INTO evidence_items (
                    evidence_id, source_id, title, excerpt, content_hash, as_of_date, metadata_json, created_at
                ) VALUES (
                    :evidence_id, :source_id, 'Valid evidence', 'excerpt', 'h1', '2026-01-02', :metadata_json,
                    '2026-01-02T00:00:00+00:00'
                )
                """
            ),
            {
                "evidence_id": f"ev_valid_{suffix}",
                "source_id": f"src_{suffix}",
                "metadata_json": '{"k":"v"}',
            },
        )

        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO claim_evidence_interpretations (
                        interpretation_id, claim_id, evidence_id, relation, strength, note,
                        effective_from, effective_to, supersedes_interpretation_id,
                        superseded_by_interpretation_id, created_at
                    ) VALUES (
                        :interpretation_id, 'missing_claim', :evidence_id, 'SUPPORTS', 'medium', NULL,
                        :ts, NULL, NULL, NULL, :ts
                    )
                    """
                ),
                {
                    "interpretation_id": f"int_bad_claim_{suffix}",
                    "evidence_id": f"ev_valid_{suffix}",
                    "ts": "2026-01-02T00:00:00+00:00",
                },
            )
        sp.rollback()

        sp = conn.begin_nested()
        with pytest.raises(IntegrityError):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO claim_evidence_interpretations (
                        interpretation_id, claim_id, evidence_id, relation, strength, note,
                        effective_from, effective_to, supersedes_interpretation_id,
                        superseded_by_interpretation_id, created_at
                    ) VALUES (
                        :interpretation_id, :claim_id, 'missing_evidence', 'SUPPORTS', 'medium', NULL,
                        :ts, NULL, NULL, NULL, :ts
                    )
                    """
                ),
                {
                    "interpretation_id": f"int_bad_ev_{suffix}",
                    "claim_id": f"cl_valid_{suffix}",
                    "ts": "2026-01-02T00:00:00+00:00",
                },
            )
        sp.rollback()

        conn.execute(
            sa.text(
                """
                INSERT INTO claim_evidence_interpretations (
                    interpretation_id, claim_id, evidence_id, relation, strength, note,
                    effective_from, effective_to, supersedes_interpretation_id,
                    superseded_by_interpretation_id, created_at
                ) VALUES (
                    :interpretation_id, :claim_id, :evidence_id, 'SUPPORTS', 'medium', NULL,
                    :ts, NULL, NULL, NULL, :ts
                )
                """
            ),
            {
                "interpretation_id": f"int_valid_{suffix}",
                "claim_id": f"cl_valid_{suffix}",
                "evidence_id": f"ev_valid_{suffix}",
                "ts": "2026-01-02T00:00:00+00:00",
            },
        )

    insp = inspect(pg_engine)
    claim_indexes = {row["name"] for row in insp.get_indexes("thesis_claims")}
    assert "ix_thesis_claims_thesis_version_id" in claim_indexes
    assert "ix_thesis_claims_thesis_id" in claim_indexes
    assert "ix_thesis_claims_status" in claim_indexes

    interp_indexes = {row["name"] for row in insp.get_indexes("claim_evidence_interpretations")}
    assert "ix_claim_evidence_interp_claim_active" in interp_indexes
    assert "ix_claim_evidence_interp_evidence_id" in interp_indexes
    assert "ix_claim_evidence_interp_supersedes" in interp_indexes


def test_wave2a3_postgres_supersession_history_jsonb_and_provenance_append_only(pg_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    thesis_id = f"t_pg_sup_{suffix}"

    with pg_engine.begin() as conn:
        version_id = _seed_thesis_root_and_version(conn, thesis_id)

        conn.execute(
            sa.text(
                """
                INSERT INTO thesis_claims (
                    claim_id, thesis_version_id, thesis_id, claim_key, claim_text,
                    claim_type, status, active_from, active_to, created_at, updated_at
                ) VALUES (
                    :claim_id, :version_id, :thesis_id, 'k1', 'Claim with history',
                    'fundamental', 'ACTIVE', :ts, NULL, :ts, :ts
                )
                """
            ),
            {
                "claim_id": f"cl_hist_{suffix}",
                "version_id": version_id,
                "thesis_id": thesis_id,
                "ts": "2026-01-03T00:00:00+00:00",
            },
        )

        conn.execute(
            sa.text(
                """
                INSERT INTO evidence_sources (
                    source_id, source_type, publisher, url, source_system,
                    published_at, retrieved_at, credibility_tier, created_at
                ) VALUES (
                    :source_id, 'RESEARCH', 'Research Desk', NULL, 'postgres_test',
                    NULL, :ts, 'A', :ts
                )
                """
            ),
            {"source_id": f"src_hist_{suffix}", "ts": "2026-01-03T00:00:00+00:00"},
        )

        metadata = {"kind": "filing", "confidence": 0.81, "tags": ["nvda", "earnings"]}
        conn.execute(
            sa.text(
                """
                INSERT INTO evidence_items (
                    evidence_id, source_id, title, excerpt, content_hash, as_of_date, metadata_json, created_at
                ) VALUES (
                    :evidence_id, :source_id, 'Evidence with metadata', 'excerpt', 'hash', '2026-01-03', :metadata_json,
                    :ts
                )
                """
            ),
            {
                "evidence_id": f"ev_hist_{suffix}",
                "source_id": f"src_hist_{suffix}",
                "metadata_json": json.dumps(metadata),
                "ts": "2026-01-03T00:00:00+00:00",
            },
        )

        conn.execute(
            sa.text(
                """
                INSERT INTO claim_evidence_interpretations (
                    interpretation_id, claim_id, evidence_id, relation, strength, note,
                    effective_from, effective_to, supersedes_interpretation_id,
                    superseded_by_interpretation_id, created_at
                ) VALUES (
                    :interpretation_id, :claim_id, :evidence_id, 'SUPPORTS', 'medium', 'initial',
                    :ts, NULL, NULL, NULL, :ts
                )
                """
            ),
            {
                "interpretation_id": f"int_hist_1_{suffix}",
                "claim_id": f"cl_hist_{suffix}",
                "evidence_id": f"ev_hist_{suffix}",
                "ts": "2026-01-03T00:00:00+00:00",
            },
        )

        conn.execute(
            sa.text(
                """
                INSERT INTO claim_evidence_interpretations (
                    interpretation_id, claim_id, evidence_id, relation, strength, note,
                    effective_from, effective_to, supersedes_interpretation_id,
                    superseded_by_interpretation_id, created_at
                ) VALUES (
                    :interpretation_id, :claim_id, :evidence_id, 'CONTRADICTS', 'high', 'new evidence',
                    :ts2, NULL, :prev_id, NULL, :ts2
                )
                """
            ),
            {
                "interpretation_id": f"int_hist_2_{suffix}",
                "claim_id": f"cl_hist_{suffix}",
                "evidence_id": f"ev_hist_{suffix}",
                "prev_id": f"int_hist_1_{suffix}",
                "ts2": "2026-01-04T00:00:00+00:00",
            },
        )

        conn.execute(
            sa.text(
                """
                UPDATE claim_evidence_interpretations
                SET effective_to = :ts2, superseded_by_interpretation_id = :next_id
                WHERE interpretation_id = :prev_id
                """
            ),
            {
                "ts2": "2026-01-04T00:00:00+00:00",
                "next_id": f"int_hist_2_{suffix}",
                "prev_id": f"int_hist_1_{suffix}",
            },
        )

        rows = conn.execute(
            sa.text(
                """
                SELECT interpretation_id, relation, effective_to, supersedes_interpretation_id, superseded_by_interpretation_id
                FROM claim_evidence_interpretations
                WHERE claim_id = :claim_id
                ORDER BY interpretation_id
                """
            ),
            {"claim_id": f"cl_hist_{suffix}"},
        ).mappings().all()

        assert len(rows) == 2
        first = next(row for row in rows if row["interpretation_id"] == f"int_hist_1_{suffix}")
        second = next(row for row in rows if row["interpretation_id"] == f"int_hist_2_{suffix}")
        assert first["effective_to"] is not None
        assert first["superseded_by_interpretation_id"] == f"int_hist_2_{suffix}"
        assert second["effective_to"] is None
        assert second["supersedes_interpretation_id"] == f"int_hist_1_{suffix}"

        # Validate JSON/JSONB behavior on metadata_json content.
        kind = conn.execute(
            sa.text(
                """
                SELECT metadata_json::jsonb ->> 'kind' AS kind
                FROM evidence_items
                WHERE evidence_id = :evidence_id
                """
            ),
            {"evidence_id": f"ev_hist_{suffix}"},
        ).scalar_one()
        assert kind == "filing"

        conn.execute(
            sa.text(
                """
                INSERT INTO provenance_records (
                    provenance_id, entity_type, entity_id, action, actor_type, actor_reference,
                    ingestion_method, source_system, extraction_method, model_name, model_version,
                    payload_hash, created_at
                ) VALUES (
                    :provenance_id, 'THESIS_CLAIM', :entity_id, 'CREATE', 'SYSTEM', 'postgres_test',
                    'manual', 'postgres_test', 'deterministic', NULL, NULL, NULL, :ts
                )
                """
            ),
            {
                "provenance_id": f"prov_1_{suffix}",
                "entity_id": f"cl_hist_{suffix}",
                "ts": "2026-01-03T00:00:00+00:00",
            },
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO provenance_records (
                    provenance_id, entity_type, entity_id, action, actor_type, actor_reference,
                    ingestion_method, source_system, extraction_method, model_name, model_version,
                    payload_hash, created_at
                ) VALUES (
                    :provenance_id, 'THESIS_CLAIM', :entity_id, 'REVIEWED', 'SYSTEM', 'postgres_test',
                    'manual', 'postgres_test', 'manual_review', NULL, NULL, NULL, :ts2
                )
                """
            ),
            {
                "provenance_id": f"prov_2_{suffix}",
                "entity_id": f"cl_hist_{suffix}",
                "ts2": "2026-01-04T00:00:00+00:00",
            },
        )

        prov_count = conn.execute(
            sa.text(
                """
                SELECT COUNT(*)
                FROM provenance_records
                WHERE entity_type = 'THESIS_CLAIM' AND entity_id = :entity_id
                """
            ),
            {"entity_id": f"cl_hist_{suffix}"},
        ).scalar_one()
        assert prov_count == 2


def test_wave2a3_postgres_migration_upgrade_downgrade_reupgrade() -> None:
    config = _alembic_config(settings.db_url)

    command.upgrade(config, REVISION_WAVE2A3)
    engine = create_engine(settings.db_url)
    insp = inspect(engine)
    names = set(insp.get_table_names())
    assert "thesis_claims" in names
    assert "evidence_sources" in names
    assert "evidence_items" in names
    assert "claim_evidence_interpretations" in names
    assert "provenance_records" in names

    command.downgrade(config, REVISION_WAVE2A2)
    insp_down = inspect(engine)
    names_down = set(insp_down.get_table_names())
    assert "thesis_claims" not in names_down
    assert "evidence_sources" not in names_down
    assert "evidence_items" not in names_down
    assert "claim_evidence_interpretations" not in names_down
    assert "provenance_records" not in names_down

    command.upgrade(config, REVISION_WAVE2A3)
    insp_up = inspect(engine)
    names_up = set(insp_up.get_table_names())
    assert "thesis_claims" in names_up
    assert "evidence_sources" in names_up
    assert "evidence_items" in names_up
    assert "claim_evidence_interpretations" in names_up
    assert "provenance_records" in names_up
