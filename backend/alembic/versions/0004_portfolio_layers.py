"""add family registry and portfolio governance layers

Revision ID: 0004_portfolio_layers
Revises: 0003_theses_and_drift_linkage
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_portfolio_layers"
down_revision = "0003_theses_and_drift_linkage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "family_portfolio_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("member_id", sa.String(), nullable=False),
        sa.Column("member_name", sa.String(), nullable=False),
        sa.Column("relation", sa.String(), nullable=False),
        sa.Column("base_currency", sa.String(), nullable=False),
    )

    op.create_table(
        "ips_constraints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("constraint_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("rule_type", sa.String(), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "instrument_master",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("asset_class", sa.String(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("data_source", sa.String(), nullable=False),
    )

    op.create_table(
        "data_trust_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("trust_tier", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("freshness_sla_hours", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("data_trust_sources")
    op.drop_table("instrument_master")
    op.drop_table("ips_constraints")
    op.drop_table("family_portfolio_members")
