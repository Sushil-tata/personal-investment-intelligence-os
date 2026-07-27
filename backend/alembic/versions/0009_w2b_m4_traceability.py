"""add wave2b m4 recommendation traceability tables

Revision ID: 0009_w2b_m4_traceability
Revises: 0008_wave2b_m2_sqlmodel_persist
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_w2b_m4_traceability"
down_revision = "0008_wave2b_m2_sqlmodel_persist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_recommendation_traces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("proposal_id", sa.String(), nullable=False),
        sa.Column("proposal_version_id", sa.String(), nullable=False),
        sa.Column("input_snapshot_id", sa.String(), nullable=False),
        sa.Column("engine_name", sa.String(), nullable=False),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("policy_version", sa.String(), nullable=False),
        sa.Column("strategy_version", sa.String(), nullable=False),
        sa.Column("execution_identity", sa.String(), nullable=False),
        sa.Column("computation_started_at", sa.String(), nullable=False),
        sa.Column("computation_completed_at", sa.String(), nullable=False),
        sa.Column("trace_schema_version", sa.String(), nullable=False),
        sa.Column("execution_status", sa.String(), nullable=False),
        sa.Column("is_authoritative", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("trace_id", name="uq_decision_recommendation_traces_trace_id"),
        sa.UniqueConstraint(
            "proposal_version_id",
            name="uq_decision_recommendation_traces_proposal_version_id",
        ),
        sa.UniqueConstraint(
            "execution_identity",
            name="uq_decision_recommendation_traces_execution_identity",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["decision_recommendation_proposals.proposal_id"],
            name="fk_decision_recommendation_traces_proposal_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_version_id"],
            ["decision_recommendation_proposal_versions.proposal_version_id"],
            name="fk_decision_recommendation_traces_proposal_version_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["input_snapshot_id"],
            ["decision_recommendation_input_snapshots.snapshot_id"],
            name="fk_decision_recommendation_traces_input_snapshot_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_decision_recommendation_traces_snapshot",
        "decision_recommendation_traces",
        ["input_snapshot_id"],
    )
    op.create_index(
        "ix_decision_recommendation_traces_status",
        "decision_recommendation_traces",
        ["execution_status"],
    )

    op.create_table(
        "decision_recommendation_trace_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("entry_id", sa.String(), nullable=False),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("component_name", sa.String(), nullable=False),
        sa.Column("component_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("input_references_json", sa.Text(), nullable=False),
        sa.Column("output_references_json", sa.Text(), nullable=False),
        sa.Column("rule_evaluations_json", sa.Text(), nullable=False),
        sa.Column("numeric_outputs_json", sa.Text(), nullable=False),
        sa.Column("categorical_outputs_json", sa.Text(), nullable=False),
        sa.Column("warning_codes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("entry_id", name="uq_decision_recommendation_trace_entries_entry_id"),
        sa.UniqueConstraint(
            "trace_id",
            "sequence_number",
            name="uq_decision_recommendation_trace_entries_trace_seq",
        ),
        sa.ForeignKeyConstraint(
            ["trace_id"],
            ["decision_recommendation_traces.trace_id"],
            name="fk_decision_recommendation_trace_entries_trace_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_decision_recommendation_trace_entries_trace",
        "decision_recommendation_trace_entries",
        ["trace_id"],
    )
    op.create_index(
        "ix_decision_recommendation_trace_entries_type",
        "decision_recommendation_trace_entries",
        ["entry_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_decision_recommendation_trace_entries_type",
        table_name="decision_recommendation_trace_entries",
    )
    op.drop_index(
        "ix_decision_recommendation_trace_entries_trace",
        table_name="decision_recommendation_trace_entries",
    )
    op.drop_table("decision_recommendation_trace_entries")

    op.drop_index(
        "ix_decision_recommendation_traces_status",
        table_name="decision_recommendation_traces",
    )
    op.drop_index(
        "ix_decision_recommendation_traces_snapshot",
        table_name="decision_recommendation_traces",
    )
    op.drop_table("decision_recommendation_traces")
