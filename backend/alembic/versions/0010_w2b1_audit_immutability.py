"""harden audit-trace foreign keys against parent delete cascades

Revision ID: 0010_w2b1_audit_immutability
Revises: 0009_w2b_m4_traceability
Create Date: 2026-07-28
"""

from alembic import op


revision = "0010_w2b1_audit_immutability"
down_revision = "0009_w2b_m4_traceability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("decision_recommendation_traces") as batch_op:
        batch_op.drop_constraint("fk_decision_recommendation_traces_proposal_id", type_="foreignkey")
        batch_op.drop_constraint("fk_decision_recommendation_traces_proposal_version_id", type_="foreignkey")
        batch_op.drop_constraint("fk_decision_recommendation_traces_input_snapshot_id", type_="foreignkey")

        batch_op.create_foreign_key(
            "fk_decision_recommendation_traces_proposal_id",
            "decision_recommendation_proposals",
            ["proposal_id"],
            ["proposal_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_decision_recommendation_traces_proposal_version_id",
            "decision_recommendation_proposal_versions",
            ["proposal_version_id"],
            ["proposal_version_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_decision_recommendation_traces_input_snapshot_id",
            "decision_recommendation_input_snapshots",
            ["input_snapshot_id"],
            ["snapshot_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("decision_recommendation_traces") as batch_op:
        batch_op.drop_constraint("fk_decision_recommendation_traces_proposal_id", type_="foreignkey")
        batch_op.drop_constraint("fk_decision_recommendation_traces_proposal_version_id", type_="foreignkey")
        batch_op.drop_constraint("fk_decision_recommendation_traces_input_snapshot_id", type_="foreignkey")

        batch_op.create_foreign_key(
            "fk_decision_recommendation_traces_proposal_id",
            "decision_recommendation_proposals",
            ["proposal_id"],
            ["proposal_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_decision_recommendation_traces_proposal_version_id",
            "decision_recommendation_proposal_versions",
            ["proposal_version_id"],
            ["proposal_version_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_decision_recommendation_traces_input_snapshot_id",
            "decision_recommendation_input_snapshots",
            ["input_snapshot_id"],
            ["snapshot_id"],
            ondelete="CASCADE",
        )
