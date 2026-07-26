"""recommendation review queue fields

Revision ID: 0002_recommendation_review_queue
Revises: 0001_initial_schema
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_recommendation_review_queue"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recommendations", sa.Column("status", sa.String(), nullable=True, server_default="DRAFT"))
    op.add_column("recommendations", sa.Column("approved_by", sa.String(), nullable=True))
    op.add_column("recommendations", sa.Column("updated_at", sa.String(), nullable=True))
    op.add_column("recommendations", sa.Column("portfolio_bucket", sa.String(), nullable=True))
    op.add_column("recommendations", sa.Column("portfolio_fit_score", sa.Float(), nullable=True))
    op.add_column("recommendations", sa.Column("source_documents", sa.Text(), nullable=True))
    op.add_column("graph_runs", sa.Column("updated_at", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("graph_runs", "updated_at")
    op.drop_column("recommendations", "source_documents")
    op.drop_column("recommendations", "portfolio_fit_score")
    op.drop_column("recommendations", "portfolio_bucket")
    op.drop_column("recommendations", "updated_at")
    op.drop_column("recommendations", "approved_by")
    op.drop_column("recommendations", "status")
