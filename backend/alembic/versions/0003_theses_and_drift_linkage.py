"""add investment theses and recommendation thesis linkage

Revision ID: 0003_theses_and_drift_linkage
Revises: 0002_recommendation_review_queue
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_theses_and_drift_linkage"
down_revision = "0002_recommendation_review_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recommendations", sa.Column("thesis_id", sa.String(), nullable=True))

    op.create_table(
        "investment_theses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("thesis_id", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
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
        sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("investment_theses")
    op.drop_column("recommendations", "thesis_id")
