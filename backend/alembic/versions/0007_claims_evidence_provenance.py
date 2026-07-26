"""add claims, evidence, interpretation history, and provenance tables

Revision ID: 0007_claims_evidence_provenance
Revises: 0006_thesis_versioned_domain
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_claims_evidence_provenance"
down_revision = "0006_thesis_versioned_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "thesis_claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("claim_id", sa.String(), nullable=False),
        sa.Column("thesis_version_id", sa.String(), nullable=False),
        sa.Column("thesis_id", sa.String(), nullable=True),
        sa.Column("claim_key", sa.String(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("active_from", sa.String(), nullable=False),
        sa.Column("active_to", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("claim_id", name="uq_thesis_claims_claim_id"),
        sa.UniqueConstraint("thesis_version_id", "claim_key", name="uq_thesis_claims_version_claim_key"),
        sa.ForeignKeyConstraint(["thesis_version_id"], ["thesis_versions.version_id"], name="fk_thesis_claims_thesis_version_id"),
        sa.ForeignKeyConstraint(["thesis_id"], ["thesis_roots.thesis_id"], name="fk_thesis_claims_thesis_id"),
    )
    op.create_index("ix_thesis_claims_thesis_version_id", "thesis_claims", ["thesis_version_id"])
    op.create_index("ix_thesis_claims_thesis_id", "thesis_claims", ["thesis_id"])
    op.create_index("ix_thesis_claims_status", "thesis_claims", ["status"])

    op.create_table(
        "evidence_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("publisher", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("source_system", sa.String(), nullable=False),
        sa.Column("published_at", sa.String(), nullable=True),
        sa.Column("retrieved_at", sa.String(), nullable=False),
        sa.Column("credibility_tier", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("source_id", name="uq_evidence_sources_source_id"),
    )
    op.create_index("ix_evidence_sources_type", "evidence_sources", ["source_type"])
    op.create_index("ix_evidence_sources_system", "evidence_sources", ["source_system"])

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("evidence_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("as_of_date", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("evidence_id", name="uq_evidence_items_evidence_id"),
        sa.ForeignKeyConstraint(["source_id"], ["evidence_sources.source_id"], name="fk_evidence_items_source_id"),
    )
    op.create_index("ix_evidence_items_source_id", "evidence_items", ["source_id"])
    op.create_index("ix_evidence_items_content_hash", "evidence_items", ["content_hash"])
    op.create_index("ix_evidence_items_as_of_date", "evidence_items", ["as_of_date"])

    op.create_table(
        "claim_evidence_interpretations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("interpretation_id", sa.String(), nullable=False),
        sa.Column("claim_id", sa.String(), nullable=False),
        sa.Column("evidence_id", sa.String(), nullable=False),
        sa.Column("relation", sa.String(), nullable=False),
        sa.Column("strength", sa.String(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.String(), nullable=False),
        sa.Column("effective_to", sa.String(), nullable=True),
        sa.Column("supersedes_interpretation_id", sa.String(), nullable=True),
        sa.Column("superseded_by_interpretation_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("interpretation_id", name="uq_claim_evidence_interpretations_interpretation_id"),
        sa.ForeignKeyConstraint(["claim_id"], ["thesis_claims.claim_id"], name="fk_claim_evidence_interp_claim_id"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence_items.evidence_id"], name="fk_claim_evidence_interp_evidence_id"),
        sa.ForeignKeyConstraint(
            ["supersedes_interpretation_id"],
            ["claim_evidence_interpretations.interpretation_id"],
            name="fk_claim_evidence_interp_supersedes_id",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_interpretation_id"],
            ["claim_evidence_interpretations.interpretation_id"],
            name="fk_claim_evidence_interp_superseded_by_id",
        ),
    )
    op.create_index("ix_claim_evidence_interp_claim_active", "claim_evidence_interpretations", ["claim_id", "effective_to"])
    op.create_index("ix_claim_evidence_interp_evidence_id", "claim_evidence_interpretations", ["evidence_id"])
    op.create_index(
        "ix_claim_evidence_interp_supersedes",
        "claim_evidence_interpretations",
        ["supersedes_interpretation_id"],
    )

    op.create_table(
        "provenance_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("provenance_id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_type", sa.String(), nullable=False),
        sa.Column("actor_reference", sa.String(), nullable=False),
        sa.Column("ingestion_method", sa.String(), nullable=False),
        sa.Column("source_system", sa.String(), nullable=False),
        sa.Column("extraction_method", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("model_version", sa.String(), nullable=True),
        sa.Column("payload_hash", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("provenance_id", name="uq_provenance_records_provenance_id"),
    )
    op.create_index("ix_provenance_records_entity", "provenance_records", ["entity_type", "entity_id"])
    op.create_index("ix_provenance_records_source_system", "provenance_records", ["source_system"])


def downgrade() -> None:
    op.drop_index("ix_provenance_records_source_system", table_name="provenance_records")
    op.drop_index("ix_provenance_records_entity", table_name="provenance_records")
    op.drop_table("provenance_records")

    op.drop_index("ix_claim_evidence_interp_supersedes", table_name="claim_evidence_interpretations")
    op.drop_index("ix_claim_evidence_interp_evidence_id", table_name="claim_evidence_interpretations")
    op.drop_index("ix_claim_evidence_interp_claim_active", table_name="claim_evidence_interpretations")
    op.drop_table("claim_evidence_interpretations")

    op.drop_index("ix_evidence_items_as_of_date", table_name="evidence_items")
    op.drop_index("ix_evidence_items_content_hash", table_name="evidence_items")
    op.drop_index("ix_evidence_items_source_id", table_name="evidence_items")
    op.drop_table("evidence_items")

    op.drop_index("ix_evidence_sources_system", table_name="evidence_sources")
    op.drop_index("ix_evidence_sources_type", table_name="evidence_sources")
    op.drop_table("evidence_sources")

    op.drop_index("ix_thesis_claims_status", table_name="thesis_claims")
    op.drop_index("ix_thesis_claims_thesis_id", table_name="thesis_claims")
    op.drop_index("ix_thesis_claims_thesis_version_id", table_name="thesis_claims")
    op.drop_table("thesis_claims")
