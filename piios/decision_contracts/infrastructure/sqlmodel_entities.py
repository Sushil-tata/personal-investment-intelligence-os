from __future__ import annotations

from typing import Optional

from sqlalchemy import Column, ForeignKey, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


class RecommendationProposalEntity(SQLModel, table=True):
    __tablename__ = "decision_recommendation_proposals"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_decision_recommendation_proposals_proposal_id"),
        Index("ix_decision_recommendation_proposals_target", "target_type", "target_key"),
        Index("ix_decision_recommendation_proposals_scope", "scope"),
        Index("ix_decision_recommendation_proposals_status", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_id: str
    target_type: str
    target_key: str
    scope: str
    status: str
    created_at: str
    updated_at: str


class RecommendationProposalVersionEntity(SQLModel, table=True):
    __tablename__ = "decision_recommendation_proposal_versions"
    __table_args__ = (
        UniqueConstraint(
            "proposal_version_id",
            name="uq_decision_recommendation_proposal_versions_proposal_version_id",
        ),
        UniqueConstraint(
            "proposal_id",
            "version_number",
            name="uq_decision_recommendation_proposal_versions_number",
        ),
        UniqueConstraint("snapshot_id", name="uq_decision_recommendation_proposal_versions_snapshot_id"),
        Index("ix_decision_recommendation_proposal_versions_proposal_id", "proposal_id"),
        Index("ix_decision_recommendation_proposal_versions_created_at", "created_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_version_id: str
    proposal_id: str = Field(foreign_key="decision_recommendation_proposals.proposal_id")
    version_number: int
    status: str
    created_at: str
    snapshot_id: str
    action: str
    action_note: str | None = None
    action_min_weight: float | None = None
    action_max_weight: float | None = None
    company_quality: float
    valuation_attractiveness: float
    portfolio_suitability: float
    recommendation_confidence: float
    relationship_confidence: float
    expected_return: float
    overall_confidence: float
    priority_level: str
    priority_score: float
    required_human_review: bool
    supersedes_version_id: str | None = None


class RecommendationInputSnapshotEntity(SQLModel, table=True):
    __tablename__ = "decision_recommendation_input_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_id", name="uq_decision_recommendation_input_snapshots_snapshot_id"),
        UniqueConstraint(
            "proposal_version_id",
            name="uq_decision_recommendation_input_snapshots_proposal_version_id",
        ),
        Index("ix_decision_recommendation_input_snapshots_hash", "input_hash"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_id: str
    proposal_version_id: str = Field(
        foreign_key="decision_recommendation_proposal_versions.proposal_version_id"
    )
    captured_at: str
    canonical_payload_json: str
    input_hash: str


class RecommendationReasonEntity(SQLModel, table=True):
    __tablename__ = "decision_recommendation_reasons"
    __table_args__ = (
        UniqueConstraint("reason_id", name="uq_decision_recommendation_reasons_reason_id"),
        Index("ix_decision_recommendation_reasons_version_rank", "proposal_version_id", "rank"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    reason_id: str
    proposal_version_id: str = Field(
        foreign_key="decision_recommendation_proposal_versions.proposal_version_id"
    )
    rank: int
    reason_type: str
    weight: float
    reason_code: str
    detail_json: str


class RecommendationClaimLinkEntity(SQLModel, table=True):
    __tablename__ = "decision_recommendation_claim_links"
    __table_args__ = (
        UniqueConstraint("claim_link_id", name="uq_decision_recommendation_claim_links_claim_link_id"),
        Index("ix_decision_recommendation_claim_links_version", "proposal_version_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    claim_link_id: str
    proposal_version_id: str = Field(
        foreign_key="decision_recommendation_proposal_versions.proposal_version_id"
    )
    claim_id: str = Field(foreign_key="thesis_claims.claim_id")
    contribution_weight: float
    role: str


class RecommendationEvidenceLinkEntity(SQLModel, table=True):
    __tablename__ = "decision_recommendation_evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "evidence_link_id",
            name="uq_decision_recommendation_evidence_links_evidence_link_id",
        ),
        Index("ix_decision_recommendation_evidence_links_version", "proposal_version_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    evidence_link_id: str
    proposal_version_id: str = Field(
        foreign_key="decision_recommendation_proposal_versions.proposal_version_id"
    )
    evidence_id: str = Field(foreign_key="evidence_items.evidence_id")
    interpretation_id: str | None = Field(
        default=None,
        foreign_key="claim_evidence_interpretations.interpretation_id",
    )
    freshness_days: int
    quality_score: float
    conflict_flag: bool


class RecommendationTraceEntity(SQLModel, table=True):
    __tablename__ = "decision_recommendation_traces"
    __table_args__ = (
        UniqueConstraint("trace_id", name="uq_decision_recommendation_traces_trace_id"),
        UniqueConstraint(
            "proposal_version_id",
            name="uq_decision_recommendation_traces_proposal_version_id",
        ),
        UniqueConstraint(
            "execution_identity",
            name="uq_decision_recommendation_traces_execution_identity",
        ),
        Index("ix_decision_recommendation_traces_snapshot", "input_snapshot_id"),
        Index("ix_decision_recommendation_traces_status", "execution_status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    trace_id: str
    proposal_id: str = Field(
        sa_column=Column(
            "proposal_id",
            ForeignKey("decision_recommendation_proposals.proposal_id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    proposal_version_id: str = Field(
        sa_column=Column(
            "proposal_version_id",
            ForeignKey("decision_recommendation_proposal_versions.proposal_version_id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    input_snapshot_id: str = Field(
        sa_column=Column(
            "input_snapshot_id",
            ForeignKey("decision_recommendation_input_snapshots.snapshot_id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    engine_name: str
    engine_version: str
    policy_version: str
    strategy_version: str
    execution_identity: str
    computation_started_at: str
    computation_completed_at: str
    trace_schema_version: str
    execution_status: str
    is_authoritative: bool
    created_at: str


class RecommendationTraceEntryEntity(SQLModel, table=True):
    __tablename__ = "decision_recommendation_trace_entries"
    __table_args__ = (
        UniqueConstraint("entry_id", name="uq_decision_recommendation_trace_entries_entry_id"),
        UniqueConstraint(
            "trace_id",
            "sequence_number",
            name="uq_decision_recommendation_trace_entries_trace_seq",
        ),
        Index("ix_decision_recommendation_trace_entries_trace", "trace_id"),
        Index("ix_decision_recommendation_trace_entries_type", "entry_type"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    entry_id: str
    trace_id: str = Field(foreign_key="decision_recommendation_traces.trace_id")
    sequence_number: int
    entry_type: str
    component_name: str
    component_version: str
    status: str
    input_references_json: str
    output_references_json: str
    rule_evaluations_json: str
    numeric_outputs_json: str
    categorical_outputs_json: str
    warning_codes_json: str
    created_at: str


class InvestmentDecisionEntity(SQLModel, table=True):
    __tablename__ = "decision_investment_decisions"
    __table_args__ = (
        UniqueConstraint("decision_id", name="uq_decision_investment_decisions_decision_id"),
        Index("ix_decision_investment_decisions_version", "proposal_version_id", "decided_at"),
        Index("ix_decision_investment_decisions_state", "state"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    decision_id: str
    proposal_version_id: str = Field(
        foreign_key="decision_recommendation_proposal_versions.proposal_version_id"
    )
    state: str
    reason_code: str
    decided_at: str
    reason_text: str | None = None
    decided_by: str | None = None
    preferred_alternative_target_key: str | None = None
    modified_action: str | None = None
    modified_action_note: str | None = None
    modified_action_min_weight: float | None = None
    modified_action_max_weight: float | None = None
    modified_position_min_weight: float | None = None
    modified_position_max_weight: float | None = None
