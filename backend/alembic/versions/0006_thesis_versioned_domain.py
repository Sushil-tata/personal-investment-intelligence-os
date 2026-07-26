"""add versioned thesis domain tables and backfill

Revision ID: 0006_thesis_versioned_domain
Revises: 0005_identity_master_tables
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_thesis_versioned_domain"
down_revision = "0005_identity_master_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "thesis_roots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("thesis_id", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("lifecycle_status", sa.String(), nullable=False),
        sa.Column("current_version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.Column("closed_reason", sa.String(), nullable=True),
        sa.Column("closed_at", sa.String(), nullable=True),
        sa.UniqueConstraint("thesis_id", name="uq_thesis_roots_thesis_id"),
    )
    op.create_index("ix_thesis_roots_ticker", "thesis_roots", ["ticker"])
    op.create_index("ix_thesis_roots_status", "thesis_roots", ["lifecycle_status"])

    op.create_table(
        "thesis_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("version_id", sa.String(), nullable=False),
        sa.Column("thesis_id", sa.String(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("asset_name", sa.String(), nullable=False),
        sa.Column("theme", sa.String(), nullable=False),
        sa.Column("bucket", sa.String(), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("bull_case", sa.Text(), nullable=False),
        sa.Column("bear_case", sa.Text(), nullable=False),
        sa.Column("why_now", sa.Text(), nullable=False),
        sa.Column("why_not_now", sa.Text(), nullable=False),
        sa.Column("invalidation_trigger", sa.Text(), nullable=False),
        sa.Column("valuation_notes", sa.Text(), nullable=False),
        sa.Column("expected_holding_period", sa.String(), nullable=False),
        sa.Column("source_documents", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("version_id", name="uq_thesis_versions_version_id"),
        sa.UniqueConstraint("thesis_id", "version_number", name="uq_thesis_versions_thesis_version_number"),
        sa.ForeignKeyConstraint(["thesis_id"], ["thesis_roots.thesis_id"], name="fk_thesis_versions_thesis_id"),
    )
    op.create_index("ix_thesis_versions_thesis_id", "thesis_versions", ["thesis_id"])
    op.create_index("ix_thesis_versions_status", "thesis_versions", ["status"])

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT
                thesis_id,
                ticker,
                asset_name,
                theme,
                bucket,
                thesis,
                bull_case,
                bear_case,
                why_now,
                why_not_now,
                invalidation_trigger,
                valuation_notes,
                expected_holding_period,
                source_documents,
                confidence_score,
                status,
                created_at,
                updated_at
            FROM investment_theses
            """
        )
    ).mappings().all()

    for row in rows:
        archived = row["status"] == "ARCHIVED"
        conn.execute(
            sa.text(
                """
                INSERT INTO thesis_roots (
                    thesis_id, ticker, lifecycle_status, current_version_number,
                    created_at, updated_at, closed_reason, closed_at
                )
                VALUES (
                    :thesis_id, :ticker, :lifecycle_status, 1,
                    :created_at, :updated_at, :closed_reason, :closed_at
                )
                """
            ),
            {
                "thesis_id": row["thesis_id"],
                "ticker": row["ticker"],
                "lifecycle_status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "closed_reason": "legacy_archived" if archived else None,
                "closed_at": row["updated_at"] if archived else None,
            },
        )

        conn.execute(
            sa.text(
                """
                INSERT INTO thesis_versions (
                    version_id, thesis_id, version_number,
                    asset_name, theme, bucket, thesis,
                    bull_case, bear_case, why_now, why_not_now,
                    invalidation_trigger, valuation_notes, expected_holding_period,
                    source_documents, confidence_score, status, created_at
                )
                VALUES (
                    :version_id, :thesis_id, 1,
                    :asset_name, :theme, :bucket, :thesis,
                    :bull_case, :bear_case, :why_now, :why_not_now,
                    :invalidation_trigger, :valuation_notes, :expected_holding_period,
                    :source_documents, :confidence_score, :status, :created_at
                )
                """
            ),
            {
                "version_id": f"{row['thesis_id']}:v1",
                "thesis_id": row["thesis_id"],
                "asset_name": row["asset_name"],
                "theme": row["theme"],
                "bucket": row["bucket"],
                "thesis": row["thesis"],
                "bull_case": row["bull_case"],
                "bear_case": row["bear_case"],
                "why_now": row["why_now"],
                "why_not_now": row["why_not_now"],
                "invalidation_trigger": row["invalidation_trigger"],
                "valuation_notes": row["valuation_notes"],
                "expected_holding_period": row["expected_holding_period"],
                "source_documents": row["source_documents"],
                "confidence_score": row["confidence_score"],
                "status": row["status"],
                "created_at": row["created_at"],
            },
        )


def downgrade() -> None:
    op.drop_index("ix_thesis_versions_status", table_name="thesis_versions")
    op.drop_index("ix_thesis_versions_thesis_id", table_name="thesis_versions")
    op.drop_table("thesis_versions")

    op.drop_index("ix_thesis_roots_status", table_name="thesis_roots")
    op.drop_index("ix_thesis_roots_ticker", table_name="thesis_roots")
    op.drop_table("thesis_roots")
