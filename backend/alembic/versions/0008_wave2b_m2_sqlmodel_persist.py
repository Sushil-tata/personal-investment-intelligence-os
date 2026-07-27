"""add wave2b m2 sqlmodel persistence tables

Revision ID: 0008_wave2b_m2_sqlmodel_persist
Revises: 0007_claims_evidence_provenance
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_wave2b_m2_sqlmodel_persist"
down_revision = "0007_claims_evidence_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_recommendation_proposals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("proposal_id", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_key", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("proposal_id", name="uq_decision_recommendation_proposals_proposal_id"),
    )
    op.create_index(
        "ix_decision_recommendation_proposals_target",
        "decision_recommendation_proposals",
        ["target_type", "target_key"],
    )
    op.create_index(
        "ix_decision_recommendation_proposals_scope",
        "decision_recommendation_proposals",
        ["scope"],
    )
    op.create_index(
        "ix_decision_recommendation_proposals_status",
        "decision_recommendation_proposals",
        ["status"],
    )

    op.create_table(
        "decision_recommendation_proposal_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("proposal_version_id", sa.String(), nullable=False),
        sa.Column("proposal_id", sa.String(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("snapshot_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("action_note", sa.String(), nullable=True),
        sa.Column("action_min_weight", sa.Float(), nullable=True),
        sa.Column("action_max_weight", sa.Float(), nullable=True),
        sa.Column("company_quality", sa.Float(), nullable=False),
        sa.Column("valuation_attractiveness", sa.Float(), nullable=False),
        sa.Column("portfolio_suitability", sa.Float(), nullable=False),
        sa.Column("recommendation_confidence", sa.Float(), nullable=False),
        sa.Column("relationship_confidence", sa.Float(), nullable=False),
        sa.Column("expected_return", sa.Float(), nullable=False),
        sa.Column("overall_confidence", sa.Float(), nullable=False),
        sa.Column("priority_level", sa.String(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("required_human_review", sa.Boolean(), nullable=False),
        sa.Column("supersedes_version_id", sa.String(), nullable=True),
        sa.UniqueConstraint(
            "proposal_version_id",
            name="uq_dec_rec_prop_versions_prop_ver_id",
        ),
        sa.UniqueConstraint(
            "proposal_id",
            "version_number",
            name="uq_decision_recommendation_proposal_versions_number",
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            name="uq_decision_recommendation_proposal_versions_snapshot_id",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["decision_recommendation_proposals.proposal_id"],
            name="fk_decision_recommendation_proposal_versions_proposal_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_version_id"],
            ["decision_recommendation_proposal_versions.proposal_version_id"],
            name="fk_decision_recommendation_proposal_versions_supersedes",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_decision_recommendation_proposal_versions_proposal_id",
        "decision_recommendation_proposal_versions",
        ["proposal_id"],
    )
    op.create_index(
        "ix_decision_recommendation_proposal_versions_created_at",
        "decision_recommendation_proposal_versions",
        ["created_at"],
    )

    op.create_table(
        "decision_recommendation_input_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.String(), nullable=False),
        sa.Column("proposal_version_id", sa.String(), nullable=False),
        sa.Column("captured_at", sa.String(), nullable=False),
        sa.Column("canonical_payload_json", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=False),
        sa.UniqueConstraint(
            "snapshot_id",
            name="uq_decision_recommendation_input_snapshots_snapshot_id",
        ),
        sa.UniqueConstraint(
            "proposal_version_id",
            name="uq_decision_recommendation_input_snapshots_proposal_version_id",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_version_id"],
            ["decision_recommendation_proposal_versions.proposal_version_id"],
            name="fk_decision_recommendation_input_snapshots_proposal_version_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_decision_recommendation_input_snapshots_hash",
        "decision_recommendation_input_snapshots",
        ["input_hash"],
    )

    op.create_table(
        "decision_recommendation_reasons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("reason_id", sa.String(), nullable=False),
        sa.Column("proposal_version_id", sa.String(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("reason_type", sa.String(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("reason_code", sa.String(), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=False),
        sa.UniqueConstraint("reason_id", name="uq_decision_recommendation_reasons_reason_id"),
        sa.ForeignKeyConstraint(
            ["proposal_version_id"],
            ["decision_recommendation_proposal_versions.proposal_version_id"],
            name="fk_decision_recommendation_reasons_proposal_version_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_decision_recommendation_reasons_version_rank",
        "decision_recommendation_reasons",
        ["proposal_version_id", "rank"],
    )

    op.create_table(
        "decision_recommendation_claim_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("claim_link_id", sa.String(), nullable=False),
        sa.Column("proposal_version_id", sa.String(), nullable=False),
        sa.Column("claim_id", sa.String(), nullable=False),
        sa.Column("contribution_weight", sa.Float(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.UniqueConstraint(
            "claim_link_id",
            name="uq_decision_recommendation_claim_links_claim_link_id",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_version_id"],
            ["decision_recommendation_proposal_versions.proposal_version_id"],
            name="fk_decision_recommendation_claim_links_proposal_version_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["thesis_claims.claim_id"],
            name="fk_decision_recommendation_claim_links_claim_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_decision_recommendation_claim_links_version",
        "decision_recommendation_claim_links",
        ["proposal_version_id"],
    )

    op.create_table(
        "decision_recommendation_evidence_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("evidence_link_id", sa.String(), nullable=False),
        sa.Column("proposal_version_id", sa.String(), nullable=False),
        sa.Column("evidence_id", sa.String(), nullable=False),
        sa.Column("interpretation_id", sa.String(), nullable=True),
        sa.Column("freshness_days", sa.Integer(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("conflict_flag", sa.Boolean(), nullable=False),
        sa.UniqueConstraint(
            "evidence_link_id",
            name="uq_decision_recommendation_evidence_links_evidence_link_id",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_version_id"],
            ["decision_recommendation_proposal_versions.proposal_version_id"],
            name="fk_decision_recommendation_evidence_links_proposal_version_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence_items.evidence_id"],
            name="fk_decision_recommendation_evidence_links_evidence_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["interpretation_id"],
            ["claim_evidence_interpretations.interpretation_id"],
            name="fk_decision_recommendation_evidence_links_interpretation_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_decision_recommendation_evidence_links_version",
        "decision_recommendation_evidence_links",
        ["proposal_version_id"],
    )

    op.create_table(
        "decision_investment_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.String(), nullable=False),
        sa.Column("proposal_version_id", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("reason_code", sa.String(), nullable=False),
        sa.Column("decided_at", sa.String(), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.Column("preferred_alternative_target_key", sa.String(), nullable=True),
        sa.Column("modified_action", sa.String(), nullable=True),
        sa.Column("modified_action_note", sa.Text(), nullable=True),
        sa.Column("modified_action_min_weight", sa.Float(), nullable=True),
        sa.Column("modified_action_max_weight", sa.Float(), nullable=True),
        sa.Column("modified_position_min_weight", sa.Float(), nullable=True),
        sa.Column("modified_position_max_weight", sa.Float(), nullable=True),
        sa.UniqueConstraint("decision_id", name="uq_decision_investment_decisions_decision_id"),
        sa.ForeignKeyConstraint(
            ["proposal_version_id"],
            ["decision_recommendation_proposal_versions.proposal_version_id"],
            name="fk_decision_investment_decisions_proposal_version_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_decision_investment_decisions_version",
        "decision_investment_decisions",
        ["proposal_version_id", "decided_at"],
    )
    op.create_index(
        "ix_decision_investment_decisions_state",
        "decision_investment_decisions",
        ["state"],
    )

    op.create_table(
        "thesis_health_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.String(), nullable=False),
        sa.Column("thesis_version_id", sa.String(), nullable=False),
        sa.Column("computation_version", sa.String(), nullable=False),
        sa.Column("computed_at", sa.String(), nullable=False),
        sa.Column("evidence_freshness", sa.Float(), nullable=False),
        sa.Column("evidence_quality", sa.Float(), nullable=False),
        sa.Column("supporting_strength", sa.Float(), nullable=False),
        sa.Column("contradictory_strength", sa.Float(), nullable=False),
        sa.Column("provenance_completeness", sa.Float(), nullable=False),
        sa.Column("thesis_health_index", sa.Float(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint(
            "snapshot_id",
            name="uq_thesis_health_snapshots_snapshot_id",
        ),
        sa.UniqueConstraint(
            "thesis_version_id",
            "computation_version",
            "computed_at",
            name="uq_thesis_health_snapshots_version_computation_time",
        ),
        sa.ForeignKeyConstraint(
            ["thesis_version_id"],
            ["thesis_versions.version_id"],
            name="fk_thesis_health_snapshots_thesis_version_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_thesis_health_snapshots_thesis_version_id",
        "thesis_health_snapshots",
        ["thesis_version_id"],
    )
    op.create_index(
        "ix_thesis_health_snapshots_computed_at",
        "thesis_health_snapshots",
        ["computed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_thesis_health_snapshots_computed_at", table_name="thesis_health_snapshots")
    op.drop_index("ix_thesis_health_snapshots_thesis_version_id", table_name="thesis_health_snapshots")
    op.drop_table("thesis_health_snapshots")

    op.drop_index("ix_decision_investment_decisions_state", table_name="decision_investment_decisions")
    op.drop_index("ix_decision_investment_decisions_version", table_name="decision_investment_decisions")
    op.drop_table("decision_investment_decisions")

    op.drop_index("ix_decision_recommendation_evidence_links_version", table_name="decision_recommendation_evidence_links")
    op.drop_table("decision_recommendation_evidence_links")

    op.drop_index("ix_decision_recommendation_claim_links_version", table_name="decision_recommendation_claim_links")
    op.drop_table("decision_recommendation_claim_links")

    op.drop_index("ix_decision_recommendation_reasons_version_rank", table_name="decision_recommendation_reasons")
    op.drop_table("decision_recommendation_reasons")

    op.drop_index("ix_decision_recommendation_input_snapshots_hash", table_name="decision_recommendation_input_snapshots")
    op.drop_table("decision_recommendation_input_snapshots")

    op.drop_index(
        "ix_decision_recommendation_proposal_versions_created_at",
        table_name="decision_recommendation_proposal_versions",
    )
    op.drop_index(
        "ix_decision_recommendation_proposal_versions_proposal_id",
        table_name="decision_recommendation_proposal_versions",
    )
    op.drop_table("decision_recommendation_proposal_versions")

    op.drop_index("ix_decision_recommendation_proposals_status", table_name="decision_recommendation_proposals")
    op.drop_index("ix_decision_recommendation_proposals_scope", table_name="decision_recommendation_proposals")
    op.drop_index("ix_decision_recommendation_proposals_target", table_name="decision_recommendation_proposals")
    op.drop_table("decision_recommendation_proposals")
