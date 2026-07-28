"""enforce investment decision state invariants at persistence layer

Revision ID: 0011_w2b_m5_decision_invariants
Revises: 0010_w2b1_audit_immutability
Create Date: 2026-07-28
"""

from alembic import op


revision = "0011_w2b_m5_decision_invariants"
down_revision = "0010_w2b1_audit_immutability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("decision_investment_decisions") as batch_op:
        batch_op.create_check_constraint(
            "ck_decision_modified_requires_payload",
            "state != 'MODIFIED' OR modified_action IS NOT NULL OR (modified_position_min_weight IS NOT NULL AND modified_position_max_weight IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_decision_non_modified_forbids_payload",
            "state = 'MODIFIED' OR (modified_action IS NULL AND modified_action_note IS NULL AND modified_action_min_weight IS NULL AND modified_action_max_weight IS NULL AND modified_position_min_weight IS NULL AND modified_position_max_weight IS NULL)",
        )
        batch_op.create_check_constraint(
            "ck_decision_overridden_requires_alternative",
            "state != 'OVERRIDDEN' OR (preferred_alternative_target_key IS NOT NULL AND trim(preferred_alternative_target_key) != '')",
        )
        batch_op.create_check_constraint(
            "ck_decision_non_overridden_forbids_alternative",
            "state = 'OVERRIDDEN' OR preferred_alternative_target_key IS NULL",
        )
        batch_op.create_check_constraint(
            "ck_decision_modified_action_weight_pair",
            "(modified_action_min_weight IS NULL AND modified_action_max_weight IS NULL) OR (modified_action_min_weight IS NOT NULL AND modified_action_max_weight IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_decision_modified_position_weight_pair",
            "(modified_position_min_weight IS NULL AND modified_position_max_weight IS NULL) OR (modified_position_min_weight IS NOT NULL AND modified_position_max_weight IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_decision_modified_action_weight_order",
            "modified_action_min_weight IS NULL OR modified_action_max_weight IS NULL OR modified_action_min_weight <= modified_action_max_weight",
        )
        batch_op.create_check_constraint(
            "ck_decision_modified_position_weight_order",
            "modified_position_min_weight IS NULL OR modified_position_max_weight IS NULL OR modified_position_min_weight <= modified_position_max_weight",
        )


def downgrade() -> None:
    with op.batch_alter_table("decision_investment_decisions") as batch_op:
        batch_op.drop_constraint("ck_decision_modified_position_weight_order", type_="check")
        batch_op.drop_constraint("ck_decision_modified_action_weight_order", type_="check")
        batch_op.drop_constraint("ck_decision_modified_position_weight_pair", type_="check")
        batch_op.drop_constraint("ck_decision_modified_action_weight_pair", type_="check")
        batch_op.drop_constraint("ck_decision_non_overridden_forbids_alternative", type_="check")
        batch_op.drop_constraint("ck_decision_overridden_requires_alternative", type_="check")
        batch_op.drop_constraint("ck_decision_non_modified_forbids_payload", type_="check")
        batch_op.drop_constraint("ck_decision_modified_requires_payload", type_="check")
