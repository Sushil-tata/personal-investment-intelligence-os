from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json

from piios.decision_contracts.application.recommendation_reconstruction_service import (
    ReconstructionError,
    RecommendationReconstructionService,
)
from piios.decision_contracts.application.recommendation_replay_verification_service import (
    RecommendationReplayVerificationService,
)
from piios.decision_contracts.domain.decision import InvestmentDecision
from piios.decision_contracts.domain.enums import DecisionState
from piios.decision_contracts.infrastructure.repository_protocols import (
    InvestmentDecisionRepositoryProtocol,
    RecommendationProposalRepositoryProtocol,
    RecommendationProposalVersionRepositoryProtocol,
    RecommendationSnapshotRepositoryProtocol,
    RecommendationTraceRepositoryProtocol,
)
from piios.thesis.infrastructure.claim_evidence_repository_protocols import (
    EvidenceItemRepositoryProtocol,
    ThesisClaimRepositoryProtocol,
)
from piios.thesis.infrastructure.repository_protocols import ThesisVersionRepositoryProtocol


class DiagnosticStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DiagnosticSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class DiagnosticCheck:
    code: str
    status: DiagnosticStatus
    severity: DiagnosticSeverity
    message: str
    related_entity_type: str
    related_entity_id: str | None
    remediation_hint: str | None = None


@dataclass(frozen=True)
class TraceabilityDiagnostic:
    proposal_id: str | None
    proposal_version_id: str
    overall_status: DiagnosticStatus
    checks: tuple[DiagnosticCheck, ...]
    diagnostic_codes: tuple[str, ...]
    severity: DiagnosticSeverity
    generated_at: datetime


@dataclass(frozen=True)
class ConfidenceComponent:
    name: str
    value: float | None
    status: DiagnosticStatus
    source: str
    explanation: str


@dataclass(frozen=True)
class ConfidenceDiagnostic:
    proposal_version_id: str
    authoritative_confidence: float | None
    components: tuple[ConfidenceComponent, ...]
    limitations: tuple[str, ...]
    generated_at: datetime


@dataclass(frozen=True)
class DecisionLineageDiagnostic:
    decision_id: str
    proposal_id: str | None
    proposal_version_id: str
    decision_state: str
    decision_meaning: str
    overall_status: DiagnosticStatus
    checks: tuple[DiagnosticCheck, ...]
    diagnostic_codes: tuple[str, ...]
    severity: DiagnosticSeverity
    generated_at: datetime


@dataclass(frozen=True)
class GovernanceReviewItem:
    review_item_id: str
    proposal_id: str | None
    proposal_version_id: str
    decision_id: str | None
    reason_code: str
    severity: DiagnosticSeverity
    status: str
    created_at: datetime
    source_diagnostic: str
    summary: str


@dataclass(frozen=True)
class GovernanceReviewBacklog:
    proposal_version_id: str
    items: tuple[GovernanceReviewItem, ...]
    generated_at: datetime


class DiagnosticsServiceError(Exception):
    pass


class DiagnosticsRepositoryError(DiagnosticsServiceError):
    pass


class RecommendationDiagnosticsService:
    def __init__(
        self,
        proposal_repository: RecommendationProposalRepositoryProtocol,
        version_repository: RecommendationProposalVersionRepositoryProtocol,
        snapshot_repository: RecommendationSnapshotRepositoryProtocol,
        trace_repository: RecommendationTraceRepositoryProtocol,
        decision_repository: InvestmentDecisionRepositoryProtocol,
        reconstruction_service: RecommendationReconstructionService,
        replay_verification_service: RecommendationReplayVerificationService,
        thesis_version_repository: ThesisVersionRepositoryProtocol | None = None,
        thesis_claim_repository: ThesisClaimRepositoryProtocol | None = None,
        evidence_item_repository: EvidenceItemRepositoryProtocol | None = None,
    ) -> None:
        self._proposal_repository = proposal_repository
        self._version_repository = version_repository
        self._snapshot_repository = snapshot_repository
        self._trace_repository = trace_repository
        self._decision_repository = decision_repository
        self._reconstruction_service = reconstruction_service
        self._replay_verification_service = replay_verification_service
        self._thesis_version_repository = thesis_version_repository
        self._thesis_claim_repository = thesis_claim_repository
        self._evidence_item_repository = evidence_item_repository

    def diagnose_traceability(self, proposal_version_id: str) -> TraceabilityDiagnostic:
        generated_at = datetime.now(timezone.utc)
        checks: list[DiagnosticCheck] = []

        proposal_version = self._safe_repo_call(
            "version_repository.get",
            lambda: self._version_repository.get(proposal_version_id),
        )
        if proposal_version is None:
            checks.append(
                DiagnosticCheck(
                    code="PROPOSAL_VERSION_MISSING",
                    status=DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.CRITICAL,
                    message="proposal version not found",
                    related_entity_type="proposal_version",
                    related_entity_id=proposal_version_id,
                    remediation_hint="validate proposal version lifecycle and persistence",
                )
            )
            return self._traceability_result(None, proposal_version_id, checks, generated_at)

        checks.append(
            DiagnosticCheck(
                code="PROPOSAL_VERSION_EXISTS",
                status=DiagnosticStatus.PASS,
                severity=DiagnosticSeverity.INFO,
                message="proposal version exists",
                related_entity_type="proposal_version",
                related_entity_id=proposal_version_id,
            )
        )

        proposal = self._safe_repo_call(
            "proposal_repository.get",
            lambda: self._proposal_repository.get(proposal_version.proposal_id),
        )
        if proposal is None:
            checks.append(
                DiagnosticCheck(
                    code="PROPOSAL_MISSING",
                    status=DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.CRITICAL,
                    message="parent proposal missing for proposal version",
                    related_entity_type="proposal",
                    related_entity_id=proposal_version.proposal_id,
                    remediation_hint="repair proposal/proposal-version lineage",
                )
            )
            return self._traceability_result(None, proposal_version_id, checks, generated_at)

        checks.append(
            DiagnosticCheck(
                code="PROPOSAL_EXISTS",
                status=DiagnosticStatus.PASS,
                severity=DiagnosticSeverity.INFO,
                message="parent proposal exists",
                related_entity_type="proposal",
                related_entity_id=proposal.proposal_id,
            )
        )

        snapshot = self._safe_repo_call(
            "snapshot_repository.get_for_proposal_version",
            lambda: self._snapshot_repository.get_for_proposal_version(proposal_version_id),
        )
        if snapshot is None:
            checks.append(
                DiagnosticCheck(
                    code="SNAPSHOT_MISSING",
                    status=DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.HIGH,
                    message="input snapshot missing",
                    related_entity_type="snapshot",
                    related_entity_id=None,
                    remediation_hint="recreate persisted recommendation snapshot",
                )
            )
            return self._traceability_result(proposal.proposal_id, proposal_version_id, checks, generated_at)

        checks.append(
            DiagnosticCheck(
                code="SNAPSHOT_EXISTS",
                status=DiagnosticStatus.PASS,
                severity=DiagnosticSeverity.INFO,
                message="input snapshot exists",
                related_entity_type="snapshot",
                related_entity_id=snapshot.snapshot_id,
            )
        )

        if snapshot.canonical_payload_json.strip():
            checks.append(
                DiagnosticCheck(
                    code="CANONICAL_PAYLOAD_PRESENT",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="canonical payload exists",
                    related_entity_type="snapshot",
                    related_entity_id=snapshot.snapshot_id,
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    code="CANONICAL_PAYLOAD_MISSING",
                    status=DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.HIGH,
                    message="canonical payload is blank",
                    related_entity_type="snapshot",
                    related_entity_id=snapshot.snapshot_id,
                    remediation_hint="persist canonical snapshot payload",
                )
            )

        if snapshot.input_hash.strip():
            checks.append(
                DiagnosticCheck(
                    code="INPUT_HASH_PRESENT",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="deterministic input hash exists",
                    related_entity_type="snapshot",
                    related_entity_id=snapshot.snapshot_id,
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    code="INPUT_HASH_MISSING",
                    status=DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.HIGH,
                    message="deterministic input hash is blank",
                    related_entity_type="snapshot",
                    related_entity_id=snapshot.snapshot_id,
                    remediation_hint="repair snapshot hash persistence",
                )
            )

        try:
            lineage = self._reconstruction_service.reconstruct_by_proposal_version(proposal_version_id)
            checks.append(
                DiagnosticCheck(
                    code="RECONSTRUCTION_SUCCESS",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="reconstruction service succeeded",
                    related_entity_type="proposal_version",
                    related_entity_id=proposal_version_id,
                )
            )
        except ReconstructionError as exc:
            lineage = None
            checks.append(
                DiagnosticCheck(
                    code="RECONSTRUCTION_FAILED",
                    status=DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.HIGH,
                    message=f"reconstruction failed: {exc}",
                    related_entity_type="proposal_version",
                    related_entity_id=proposal_version_id,
                    remediation_hint="resolve missing or inconsistent lineage artifacts",
                )
            )

        try:
            replay = self._replay_verification_service.verify_by_proposal_version(proposal_version_id)
            if replay.status == "PASS":
                checks.append(
                    DiagnosticCheck(
                        code="REPLAY_VERIFICATION_PASS",
                        status=DiagnosticStatus.PASS,
                        severity=DiagnosticSeverity.INFO,
                        message="replay verification passed",
                        related_entity_type="proposal_version",
                        related_entity_id=proposal_version_id,
                    )
                )
            else:
                checks.append(
                    DiagnosticCheck(
                        code="REPLAY_VERIFICATION_FAIL",
                        status=DiagnosticStatus.FAIL,
                        severity=DiagnosticSeverity.HIGH,
                        message=f"replay verification failed with {len(replay.differences)} differences",
                        related_entity_type="proposal_version",
                        related_entity_id=proposal_version_id,
                        remediation_hint="inspect replay differences and persisted canonical payload",
                    )
                )
        except Exception as exc:
            checks.append(
                DiagnosticCheck(
                    code="REPLAY_VERIFICATION_UNAVAILABLE",
                    status=DiagnosticStatus.UNAVAILABLE,
                    severity=DiagnosticSeverity.MEDIUM,
                    message=f"replay verification unavailable: {exc}",
                    related_entity_type="proposal_version",
                    related_entity_id=proposal_version_id,
                    remediation_hint="retry replay diagnostics when repositories are healthy",
                )
            )

        thesis_version_id = None
        payload_claim_ids: list[str] = []
        payload_evidence_ids: list[str] = []
        if snapshot.canonical_payload_json.strip():
            try:
                payload = json.loads(snapshot.canonical_payload_json)
                thesis_version_id = str(payload.get("thesis_health", {}).get("thesis_version_id") or "") or None
                payload_claim_ids = sorted({str(row.get("claim_id")) for row in payload.get("claims", []) if row.get("claim_id")})
                payload_evidence_ids = sorted(
                    {str(row.get("evidence_id")) for row in payload.get("evidence", []) if row.get("evidence_id")}
                )
            except Exception:
                checks.append(
                    DiagnosticCheck(
                        code="CANONICAL_PAYLOAD_UNPARSEABLE",
                        status=DiagnosticStatus.FAIL,
                        severity=DiagnosticSeverity.HIGH,
                        message="canonical payload could not be parsed",
                        related_entity_type="snapshot",
                        related_entity_id=snapshot.snapshot_id,
                        remediation_hint="repair canonical payload serialization",
                    )
                )

        if thesis_version_id is None:
            checks.append(
                DiagnosticCheck(
                    code="THESIS_VERSION_UNAVAILABLE",
                    status=DiagnosticStatus.UNAVAILABLE,
                    severity=DiagnosticSeverity.LOW,
                    message="thesis version id unavailable from snapshot payload",
                    related_entity_type="thesis_version",
                    related_entity_id=None,
                )
            )
        elif self._thesis_version_repository is None:
            checks.append(
                DiagnosticCheck(
                    code="THESIS_VERSION_CHECK_UNAVAILABLE",
                    status=DiagnosticStatus.UNAVAILABLE,
                    severity=DiagnosticSeverity.LOW,
                    message="thesis version repository not configured",
                    related_entity_type="thesis_version",
                    related_entity_id=thesis_version_id,
                )
            )
        else:
            exists = self._safe_repo_call(
                "thesis_version_repository.get_by_version_id",
                lambda: self._thesis_version_repository.get_by_version_id(thesis_version_id),
            )
            checks.append(
                DiagnosticCheck(
                    code="THESIS_VERSION_EXISTS" if exists else "THESIS_VERSION_MISSING",
                    status=DiagnosticStatus.PASS if exists else DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.INFO if exists else DiagnosticSeverity.MEDIUM,
                    message="thesis version exists" if exists else "thesis version missing",
                    related_entity_type="thesis_version",
                    related_entity_id=thesis_version_id,
                    remediation_hint=None if exists else "backfill thesis version persistence",
                )
            )

        self._append_reference_checks(
            checks=checks,
            claim_ids=payload_claim_ids,
            evidence_ids=payload_evidence_ids,
        )

        decision_rows = self._safe_repo_call(
            "decision_repository.list_for_proposal_version",
            lambda: self._decision_repository.list_for_proposal_version(proposal_version_id),
        )
        mismatched = [row.decision_id for row in decision_rows if row.proposal_version_id != proposal_version_id]
        if mismatched:
            checks.append(
                DiagnosticCheck(
                    code="DECISION_LINKAGE_INVALID",
                    status=DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.HIGH,
                    message="one or more decisions have inconsistent proposal version linkage",
                    related_entity_type="decision",
                    related_entity_id=",".join(sorted(mismatched)),
                    remediation_hint="repair decision proposal version linkage",
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    code="DECISION_LINKAGE_VALID",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="all linked decisions reference this proposal version",
                    related_entity_type="proposal_version",
                    related_entity_id=proposal_version_id,
                )
            )

        if lineage is None:
            checks.append(
                DiagnosticCheck(
                    code="LINEAGE_ORPHAN_RISK",
                    status=DiagnosticStatus.WARNING,
                    severity=DiagnosticSeverity.MEDIUM,
                    message="lineage could not be fully validated because reconstruction failed",
                    related_entity_type="proposal_version",
                    related_entity_id=proposal_version_id,
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    code="LINEAGE_NO_ORPHAN_DETECTED",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="no orphaned lineage detected in reconstructed artifacts",
                    related_entity_type="proposal_version",
                    related_entity_id=proposal_version_id,
                )
            )

        return self._traceability_result(proposal.proposal_id, proposal_version_id, checks, generated_at)

    def diagnose_confidence(self, proposal_version_id: str) -> ConfidenceDiagnostic:
        generated_at = datetime.now(timezone.utc)
        components: list[ConfidenceComponent] = []
        limitations: list[str] = []

        proposal_version = self._safe_repo_call(
            "version_repository.get",
            lambda: self._version_repository.get(proposal_version_id),
        )
        if proposal_version is None:
            return ConfidenceDiagnostic(
                proposal_version_id=proposal_version_id,
                authoritative_confidence=None,
                components=tuple(
                    [
                        ConfidenceComponent(
                            name="authoritative_confidence",
                            value=None,
                            status=DiagnosticStatus.UNAVAILABLE,
                            source="proposal_version",
                            explanation="proposal version missing",
                        )
                    ]
                ),
                limitations=("proposal version missing",),
                generated_at=generated_at,
            )

        authoritative_confidence = proposal_version.confidence_breakdown.overall_confidence
        components.append(
            ConfidenceComponent(
                name="evidence_sufficiency",
                value=None,
                status=DiagnosticStatus.UNAVAILABLE,
                source="thesis_health_snapshot",
                explanation="requires thesis health snapshot payload",
            )
        )

        snapshot = self._safe_repo_call(
            "snapshot_repository.get_for_proposal_version",
            lambda: self._snapshot_repository.get_for_proposal_version(proposal_version_id),
        )

        thesis_health = None
        if snapshot is None:
            limitations.append("snapshot missing; thesis-health derived components unavailable")
        elif not snapshot.canonical_payload_json.strip():
            limitations.append("canonical payload missing; thesis-health derived components unavailable")
        else:
            try:
                payload = json.loads(snapshot.canonical_payload_json)
                thesis_health = payload.get("thesis_health", {})
            except Exception:
                limitations.append("canonical payload not parseable for confidence diagnostics")

        components = []
        if thesis_health is not None:
            components.extend(
                [
                    ConfidenceComponent(
                        name="evidence_sufficiency",
                        value=_to_float(thesis_health.get("supporting_strength")),
                        status=DiagnosticStatus.PASS,
                        source="snapshot.canonical_payload_json:thesis_health.supporting_strength",
                        explanation="supporting strength from persisted thesis-health snapshot",
                    ),
                    ConfidenceComponent(
                        name="evidence_freshness",
                        value=_to_float(thesis_health.get("evidence_freshness")),
                        status=DiagnosticStatus.PASS,
                        source="snapshot.canonical_payload_json:thesis_health.evidence_freshness",
                        explanation="evidence freshness from persisted thesis-health snapshot",
                    ),
                    ConfidenceComponent(
                        name="source_credibility",
                        value=_to_float(thesis_health.get("evidence_quality")),
                        status=DiagnosticStatus.PASS,
                        source="snapshot.canonical_payload_json:thesis_health.evidence_quality",
                        explanation="evidence quality from persisted thesis-health snapshot",
                    ),
                    ConfidenceComponent(
                        name="thesis_completeness",
                        value=_to_float(thesis_health.get("provenance_completeness")),
                        status=DiagnosticStatus.PASS,
                        source="snapshot.canonical_payload_json:thesis_health.provenance_completeness",
                        explanation="provenance completeness from persisted thesis-health snapshot",
                    ),
                    ConfidenceComponent(
                        name="contradiction_signal",
                        value=_to_float(thesis_health.get("contradictory_strength")),
                        status=DiagnosticStatus.PASS,
                        source="snapshot.canonical_payload_json:thesis_health.contradictory_strength",
                        explanation="contradictory strength from persisted thesis-health snapshot",
                    ),
                ]
            )
            freshness = _to_float(thesis_health.get("evidence_freshness"))
            if freshness is not None and freshness < 0.2:
                limitations.append("evidence freshness is low")
        else:
            for name in (
                "evidence_sufficiency",
                "evidence_freshness",
                "source_credibility",
                "thesis_completeness",
                "contradiction_signal",
            ):
                components.append(
                    ConfidenceComponent(
                        name=name,
                        value=None,
                        status=DiagnosticStatus.UNAVAILABLE,
                        source="snapshot",
                        explanation="component unavailable from persisted snapshot",
                    )
                )

        components.extend(
            [
                ConfidenceComponent(
                    name="valuation_support",
                    value=proposal_version.confidence_breakdown.dimensions.valuation_attractiveness,
                    status=DiagnosticStatus.PASS,
                    source="proposal_version.confidence_breakdown.dimensions.valuation_attractiveness",
                    explanation="valuation attractiveness from authoritative recommendation confidence",
                ),
                ConfidenceComponent(
                    name="model_rule_confidence",
                    value=proposal_version.confidence_breakdown.dimensions.recommendation_confidence,
                    status=DiagnosticStatus.PASS,
                    source="proposal_version.confidence_breakdown.dimensions.recommendation_confidence",
                    explanation="model/rule confidence from authoritative recommendation confidence",
                ),
            ]
        )

        try:
            replay = self._replay_verification_service.verify_by_proposal_version(proposal_version_id)
            components.append(
                ConfidenceComponent(
                    name="replay_integrity",
                    value=1.0 if replay.status == "PASS" else 0.0,
                    status=DiagnosticStatus.PASS if replay.status == "PASS" else DiagnosticStatus.WARNING,
                    source="RecommendationReplayVerificationService",
                    explanation="replay verification status projected as binary integrity indicator",
                )
            )
            if replay.status != "PASS":
                limitations.append("replay verification has mismatches")
        except Exception as exc:
            components.append(
                ConfidenceComponent(
                    name="replay_integrity",
                    value=None,
                    status=DiagnosticStatus.UNAVAILABLE,
                    source="RecommendationReplayVerificationService",
                    explanation=f"replay verification unavailable: {exc}",
                )
            )
            limitations.append("replay integrity unavailable")

        components.extend(
            [
                ConfidenceComponent(
                    name="risk_uncertainty",
                    value=None,
                    status=DiagnosticStatus.UNAVAILABLE,
                    source="not_persisted",
                    explanation="no persisted explicit risk-uncertainty component",
                ),
                ConfidenceComponent(
                    name="data_completeness",
                    value=None,
                    status=DiagnosticStatus.UNAVAILABLE,
                    source="not_persisted",
                    explanation="no persisted explicit data-completeness component",
                ),
            ]
        )

        for row in components:
            if row.status == DiagnosticStatus.UNAVAILABLE:
                limitations.append(f"{row.name} unavailable")

        components.sort(key=lambda row: row.name)
        limitations = sorted(set(limitations))

        return ConfidenceDiagnostic(
            proposal_version_id=proposal_version_id,
            authoritative_confidence=authoritative_confidence,
            components=tuple(components),
            limitations=tuple(limitations),
            generated_at=generated_at,
        )

    def diagnose_decision(self, decision_id: str) -> DecisionLineageDiagnostic:
        generated_at = datetime.now(timezone.utc)
        checks: list[DiagnosticCheck] = []

        decision = self._safe_repo_call("decision_repository.get", lambda: self._decision_repository.get(decision_id))
        if decision is None:
            checks.append(
                DiagnosticCheck(
                    code="DECISION_MISSING",
                    status=DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.CRITICAL,
                    message="decision not found",
                    related_entity_type="decision",
                    related_entity_id=decision_id,
                )
            )
            return self._decision_result(
                decision_id=decision_id,
                proposal_id=None,
                proposal_version_id="<unknown>",
                decision_state="<unknown>",
                decision_meaning="<unknown>",
                checks=checks,
                generated_at=generated_at,
            )

        proposal_version = self._safe_repo_call(
            "version_repository.get",
            lambda: self._version_repository.get(decision.proposal_version_id),
        )
        if proposal_version is None:
            checks.append(
                DiagnosticCheck(
                    code="DECISION_PROPOSAL_VERSION_MISSING",
                    status=DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.HIGH,
                    message="decision references missing proposal version",
                    related_entity_type="proposal_version",
                    related_entity_id=decision.proposal_version_id,
                )
            )
            proposal_id = None
        else:
            checks.append(
                DiagnosticCheck(
                    code="DECISION_PROPOSAL_VERSION_EXISTS",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="decision references existing proposal version",
                    related_entity_type="proposal_version",
                    related_entity_id=decision.proposal_version_id,
                )
            )
            proposal_id = proposal_version.proposal_id

        proposal = None
        if proposal_id is not None:
            proposal = self._safe_repo_call("proposal_repository.get", lambda: self._proposal_repository.get(proposal_id))
            if proposal is None:
                checks.append(
                    DiagnosticCheck(
                        code="DECISION_PARENT_PROPOSAL_MISSING",
                        status=DiagnosticStatus.FAIL,
                        severity=DiagnosticSeverity.HIGH,
                        message="decision parent proposal missing",
                        related_entity_type="proposal",
                        related_entity_id=proposal_id,
                    )
                )
            else:
                checks.append(
                    DiagnosticCheck(
                        code="DECISION_PARENT_PROPOSAL_EXISTS",
                        status=DiagnosticStatus.PASS,
                        severity=DiagnosticSeverity.INFO,
                        message="decision parent proposal exists",
                        related_entity_type="proposal",
                        related_entity_id=proposal_id,
                    )
                )

        if (decision.decided_by or "").strip():
            checks.append(
                DiagnosticCheck(
                    code="DECISION_REVIEWER_PRESENT",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="reviewer identity preserved",
                    related_entity_type="decision",
                    related_entity_id=decision.decision_id,
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    code="DECISION_REVIEWER_MISSING",
                    status=DiagnosticStatus.WARNING,
                    severity=DiagnosticSeverity.MEDIUM,
                    message="reviewer identity missing",
                    related_entity_type="decision",
                    related_entity_id=decision.decision_id,
                    remediation_hint="capture reviewer identity at decision capture boundary",
                )
            )

        if isinstance(decision.decided_at, datetime):
            checks.append(
                DiagnosticCheck(
                    code="DECISION_TIMESTAMP_PRESENT",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="decision timestamp preserved",
                    related_entity_type="decision",
                    related_entity_id=decision.decision_id,
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    code="DECISION_TIMESTAMP_INVALID",
                    status=DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.HIGH,
                    message="decision timestamp invalid",
                    related_entity_type="decision",
                    related_entity_id=decision.decision_id,
                )
            )

        try:
            InvestmentDecision(
                decision_id=decision.decision_id,
                proposal_version_id=decision.proposal_version_id,
                state=decision.state,
                reason_code=decision.reason_code,
                decided_at=decision.decided_at,
                reason_text=decision.reason_text,
                decided_by=decision.decided_by,
                preferred_alternative_target_key=decision.preferred_alternative_target_key,
                modified_action=decision.modified_action,
                modified_position_size=decision.modified_position_size,
            )
            checks.append(
                DiagnosticCheck(
                    code="DECISION_STATE_INVARIANTS_OK",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="decision state invariants satisfied",
                    related_entity_type="decision",
                    related_entity_id=decision.decision_id,
                )
            )
        except ValueError as exc:
            checks.append(
                DiagnosticCheck(
                    code="DECISION_STATE_INVARIANTS_FAIL",
                    status=DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.HIGH,
                    message=f"decision state invariants failed: {exc}",
                    related_entity_type="decision",
                    related_entity_id=decision.decision_id,
                )
            )

        if getattr(type(decision), "__dataclass_params__", None) is not None and type(decision).__dataclass_params__.frozen:
            checks.append(
                DiagnosticCheck(
                    code="DECISION_IMMUTABLE_REPRESENTATION",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="decision represented as immutable dataclass",
                    related_entity_type="decision",
                    related_entity_id=decision.decision_id,
                )
            )

        if decision.decision_id not in {decision.proposal_version_id, proposal_id or ""}:
            checks.append(
                DiagnosticCheck(
                    code="DECISION_DISTINCT_FROM_RECOMMENDATION",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="decision identity is distinct from recommendation identity",
                    related_entity_type="decision",
                    related_entity_id=decision.decision_id,
                )
            )

        if decision.decision_id.startswith(f"decision:{decision.proposal_version_id}:"):
            checks.append(
                DiagnosticCheck(
                    code="DECISION_IDEMPOTENT_CAPTURE_ID",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="decision id matches deterministic capture pattern",
                    related_entity_type="decision",
                    related_entity_id=decision.decision_id,
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    code="DECISION_IDEMPOTENT_CAPTURE_UNKNOWN",
                    status=DiagnosticStatus.NOT_APPLICABLE,
                    severity=DiagnosticSeverity.LOW,
                    message="decision id not in deterministic capture pattern",
                    related_entity_type="decision",
                    related_entity_id=decision.decision_id,
                )
            )

        decision_meaning = _decision_meaning(decision)
        if decision.state == DecisionState.DEFERRED and decision_meaning == "REQUEST_RESEARCH":
            checks.append(
                DiagnosticCheck(
                    code="REQUEST_RESEARCH_DISTINGUISHABLE",
                    status=DiagnosticStatus.PASS,
                    severity=DiagnosticSeverity.INFO,
                    message="request-research semantic distinguishable via reason_code",
                    related_entity_type="decision",
                    related_entity_id=decision.decision_id,
                )
            )

        return self._decision_result(
            decision_id=decision.decision_id,
            proposal_id=proposal_id,
            proposal_version_id=decision.proposal_version_id,
            decision_state=decision.state.value,
            decision_meaning=decision_meaning,
            checks=checks,
            generated_at=generated_at,
        )

    def list_decision_lineage_diagnostics_for_proposal_version(
        self,
        proposal_version_id: str,
    ) -> tuple[DecisionLineageDiagnostic, ...]:
        rows = self._safe_repo_call(
            "decision_repository.list_for_proposal_version",
            lambda: self._decision_repository.list_for_proposal_version(proposal_version_id),
        )
        diagnostics = [self.diagnose_decision(row.decision_id) for row in rows]
        diagnostics.sort(key=lambda row: (row.decision_id, row.generated_at.isoformat()))
        return tuple(diagnostics)

    def build_governance_review_backlog(self, proposal_version_id: str) -> GovernanceReviewBacklog:
        generated_at = datetime.now(timezone.utc)
        traceability = self.diagnose_traceability(proposal_version_id)
        confidence = self.diagnose_confidence(proposal_version_id)
        decisions = self.list_decision_lineage_diagnostics_for_proposal_version(proposal_version_id)

        items: dict[tuple[str, str | None, str], GovernanceReviewItem] = {}

        for check in traceability.checks:
            if check.status in {DiagnosticStatus.FAIL, DiagnosticStatus.WARNING, DiagnosticStatus.UNAVAILABLE}:
                reason = _backlog_reason_from_traceability_code(check.code)
                if reason is None:
                    continue
                item = _build_review_item(
                    proposal_id=traceability.proposal_id,
                    proposal_version_id=proposal_version_id,
                    decision_id=None,
                    reason_code=reason,
                    severity=_severity_from_diagnostic(check.severity),
                    source_diagnostic="traceability",
                    summary=check.message,
                    created_at=generated_at,
                )
                items[(item.reason_code, item.decision_id, item.source_diagnostic)] = item

        component_map = {row.name: row for row in confidence.components}
        replay_component = component_map.get("replay_integrity")
        if replay_component is not None and replay_component.status == DiagnosticStatus.WARNING:
            item = _build_review_item(
                proposal_id=traceability.proposal_id,
                proposal_version_id=proposal_version_id,
                decision_id=None,
                reason_code="REPLAY_MISMATCH",
                severity=DiagnosticSeverity.HIGH,
                source_diagnostic="confidence",
                summary="replay integrity indicates mismatch",
                created_at=generated_at,
            )
            items[(item.reason_code, item.decision_id, item.source_diagnostic)] = item

        evidence_freshness = component_map.get("evidence_freshness")
        if evidence_freshness is not None and evidence_freshness.value is not None and evidence_freshness.value < 0.2:
            item = _build_review_item(
                proposal_id=traceability.proposal_id,
                proposal_version_id=proposal_version_id,
                decision_id=None,
                reason_code="STALE_EVIDENCE",
                severity=DiagnosticSeverity.MEDIUM,
                source_diagnostic="confidence",
                summary="evidence freshness is below threshold",
                created_at=generated_at,
            )
            items[(item.reason_code, item.decision_id, item.source_diagnostic)] = item

        contradiction = component_map.get("contradiction_signal")
        if contradiction is not None and contradiction.value is not None and contradiction.value >= 0.6:
            item = _build_review_item(
                proposal_id=traceability.proposal_id,
                proposal_version_id=proposal_version_id,
                decision_id=None,
                reason_code="UNRESOLVED_CONTRADICTION",
                severity=DiagnosticSeverity.MEDIUM,
                source_diagnostic="confidence",
                summary="contradiction signal remains elevated",
                created_at=generated_at,
            )
            items[(item.reason_code, item.decision_id, item.source_diagnostic)] = item

        if confidence.authoritative_confidence is not None and confidence.authoritative_confidence < 0.5:
            item = _build_review_item(
                proposal_id=traceability.proposal_id,
                proposal_version_id=proposal_version_id,
                decision_id=None,
                reason_code="LOW_CONFIDENCE",
                severity=DiagnosticSeverity.MEDIUM,
                source_diagnostic="confidence",
                summary="authoritative recommendation confidence is low",
                created_at=generated_at,
            )
            items[(item.reason_code, item.decision_id, item.source_diagnostic)] = item

        backlog_relevant_unavailable = {
            "evidence_sufficiency",
            "evidence_freshness",
            "source_credibility",
            "thesis_completeness",
            "contradiction_signal",
            "replay_integrity",
        }
        if any(
            row.status == DiagnosticStatus.UNAVAILABLE and row.name in backlog_relevant_unavailable
            for row in confidence.components
        ):
            item = _build_review_item(
                proposal_id=traceability.proposal_id,
                proposal_version_id=proposal_version_id,
                decision_id=None,
                reason_code="CONFIDENCE_COMPONENT_UNAVAILABLE",
                severity=DiagnosticSeverity.LOW,
                source_diagnostic="confidence",
                summary="one or more confidence components unavailable",
                created_at=generated_at,
            )
            items[(item.reason_code, item.decision_id, item.source_diagnostic)] = item

        for decision in decisions:
            code = None
            severity = DiagnosticSeverity.MEDIUM
            if decision.decision_meaning == "REQUEST_RESEARCH":
                code = "REQUEST_RESEARCH_DECISION"
                severity = DiagnosticSeverity.HIGH
            elif decision.decision_state == DecisionState.DEFERRED.value:
                code = "DEFERRED_DECISION"
            elif decision.decision_state == DecisionState.OVERRIDDEN.value:
                code = "OVERRIDDEN_RECOMMENDATION"
            elif decision.decision_state == DecisionState.MODIFIED.value:
                code = "MODIFIED_RECOMMENDATION"

            if code is not None:
                item = _build_review_item(
                    proposal_id=decision.proposal_id,
                    proposal_version_id=decision.proposal_version_id,
                    decision_id=decision.decision_id,
                    reason_code=code,
                    severity=severity,
                    source_diagnostic="decision_lineage",
                    summary=f"decision requires governance review: {code}",
                    created_at=generated_at,
                )
                items[(item.reason_code, item.decision_id, item.source_diagnostic)] = item

            reviewer_missing = any(row.code == "DECISION_REVIEWER_MISSING" for row in decision.checks)
            if reviewer_missing:
                item = _build_review_item(
                    proposal_id=decision.proposal_id,
                    proposal_version_id=decision.proposal_version_id,
                    decision_id=decision.decision_id,
                    reason_code="MISSING_REVIEWER",
                    severity=DiagnosticSeverity.HIGH,
                    source_diagnostic="decision_lineage",
                    summary="decision is missing reviewer identity",
                    created_at=generated_at,
                )
                items[(item.reason_code, item.decision_id, item.source_diagnostic)] = item

        ordered = sorted(
            items.values(),
            key=lambda row: (
                _severity_rank(row.severity),
                row.reason_code,
                row.decision_id or "",
                row.review_item_id,
            ),
        )

        return GovernanceReviewBacklog(
            proposal_version_id=proposal_version_id,
            items=tuple(ordered),
            generated_at=generated_at,
        )

    @staticmethod
    def _safe_repo_call(label: str, call):
        try:
            return call()
        except DiagnosticsServiceError:
            raise
        except Exception as exc:
            raise DiagnosticsRepositoryError(f"repository failure at {label}") from exc

    @staticmethod
    def _traceability_result(
        proposal_id: str | None,
        proposal_version_id: str,
        checks: list[DiagnosticCheck],
        generated_at: datetime,
    ) -> TraceabilityDiagnostic:
        checks = sorted(checks, key=lambda row: row.code)
        status = _overall_status(checks)
        severity = _overall_severity(checks)
        return TraceabilityDiagnostic(
            proposal_id=proposal_id,
            proposal_version_id=proposal_version_id,
            overall_status=status,
            checks=tuple(checks),
            diagnostic_codes=tuple(row.code for row in checks),
            severity=severity,
            generated_at=generated_at,
        )

    @staticmethod
    def _decision_result(
        decision_id: str,
        proposal_id: str | None,
        proposal_version_id: str,
        decision_state: str,
        decision_meaning: str,
        checks: list[DiagnosticCheck],
        generated_at: datetime,
    ) -> DecisionLineageDiagnostic:
        checks = sorted(checks, key=lambda row: row.code)
        return DecisionLineageDiagnostic(
            decision_id=decision_id,
            proposal_id=proposal_id,
            proposal_version_id=proposal_version_id,
            decision_state=decision_state,
            decision_meaning=decision_meaning,
            overall_status=_overall_status(checks),
            checks=tuple(checks),
            diagnostic_codes=tuple(row.code for row in checks),
            severity=_overall_severity(checks),
            generated_at=generated_at,
        )

    def _append_reference_checks(
        self,
        checks: list[DiagnosticCheck],
        claim_ids: list[str],
        evidence_ids: list[str],
    ) -> None:
        if not claim_ids:
            checks.append(
                DiagnosticCheck(
                    code="CLAIM_REFERENCES_NOT_APPLICABLE",
                    status=DiagnosticStatus.NOT_APPLICABLE,
                    severity=DiagnosticSeverity.INFO,
                    message="no claim references found in canonical payload",
                    related_entity_type="claim",
                    related_entity_id=None,
                )
            )
        elif self._thesis_claim_repository is None:
            checks.append(
                DiagnosticCheck(
                    code="CLAIM_REFERENCE_CHECK_UNAVAILABLE",
                    status=DiagnosticStatus.UNAVAILABLE,
                    severity=DiagnosticSeverity.LOW,
                    message="claim repository not configured",
                    related_entity_type="claim",
                    related_entity_id=",".join(claim_ids),
                )
            )
        else:
            missing = [row for row in claim_ids if self._safe_repo_call("thesis_claim_repository.get", lambda: self._thesis_claim_repository.get(row)) is None]
            checks.append(
                DiagnosticCheck(
                    code="CLAIM_REFERENCES_EXIST" if not missing else "CLAIM_REFERENCES_MISSING",
                    status=DiagnosticStatus.PASS if not missing else DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.INFO if not missing else DiagnosticSeverity.MEDIUM,
                    message="all referenced claims exist" if not missing else "one or more referenced claims missing",
                    related_entity_type="claim",
                    related_entity_id=None if not missing else ",".join(sorted(missing)),
                    remediation_hint=None if not missing else "backfill missing claims",
                )
            )

        if not evidence_ids:
            checks.append(
                DiagnosticCheck(
                    code="EVIDENCE_REFERENCES_NOT_APPLICABLE",
                    status=DiagnosticStatus.NOT_APPLICABLE,
                    severity=DiagnosticSeverity.INFO,
                    message="no evidence references found in canonical payload",
                    related_entity_type="evidence",
                    related_entity_id=None,
                )
            )
        elif self._evidence_item_repository is None:
            checks.append(
                DiagnosticCheck(
                    code="EVIDENCE_REFERENCE_CHECK_UNAVAILABLE",
                    status=DiagnosticStatus.UNAVAILABLE,
                    severity=DiagnosticSeverity.LOW,
                    message="evidence repository not configured",
                    related_entity_type="evidence",
                    related_entity_id=",".join(evidence_ids),
                )
            )
        else:
            missing = [
                row
                for row in evidence_ids
                if self._safe_repo_call("evidence_item_repository.get", lambda: self._evidence_item_repository.get(row)) is None
            ]
            checks.append(
                DiagnosticCheck(
                    code="EVIDENCE_REFERENCES_EXIST" if not missing else "EVIDENCE_REFERENCES_MISSING",
                    status=DiagnosticStatus.PASS if not missing else DiagnosticStatus.FAIL,
                    severity=DiagnosticSeverity.INFO if not missing else DiagnosticSeverity.MEDIUM,
                    message="all referenced evidence exists" if not missing else "one or more referenced evidence items missing",
                    related_entity_type="evidence",
                    related_entity_id=None if not missing else ",".join(sorted(missing)),
                    remediation_hint=None if not missing else "backfill missing evidence items",
                )
            )


def _to_float(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _overall_status(checks: list[DiagnosticCheck]) -> DiagnosticStatus:
    statuses = {row.status for row in checks}
    if DiagnosticStatus.FAIL in statuses:
        return DiagnosticStatus.FAIL
    if DiagnosticStatus.WARNING in statuses:
        return DiagnosticStatus.WARNING
    if DiagnosticStatus.UNAVAILABLE in statuses:
        return DiagnosticStatus.UNAVAILABLE
    if DiagnosticStatus.NOT_APPLICABLE in statuses and statuses == {DiagnosticStatus.NOT_APPLICABLE}:
        return DiagnosticStatus.NOT_APPLICABLE
    return DiagnosticStatus.PASS


def _overall_severity(checks: list[DiagnosticCheck]) -> DiagnosticSeverity:
    if not checks:
        return DiagnosticSeverity.INFO
    return min((row.severity for row in checks), key=_severity_rank)


def _severity_rank(severity: DiagnosticSeverity) -> int:
    return {
        DiagnosticSeverity.CRITICAL: 0,
        DiagnosticSeverity.HIGH: 1,
        DiagnosticSeverity.MEDIUM: 2,
        DiagnosticSeverity.LOW: 3,
        DiagnosticSeverity.INFO: 4,
    }[severity]


def _decision_meaning(decision: InvestmentDecision) -> str:
    if decision.state == DecisionState.DEFERRED and decision.reason_code.strip().upper() == "REQUEST_RESEARCH":
        return "REQUEST_RESEARCH"
    return decision.state.value


def _severity_from_diagnostic(severity: DiagnosticSeverity) -> DiagnosticSeverity:
    return severity


def _build_review_item(
    proposal_id: str | None,
    proposal_version_id: str,
    decision_id: str | None,
    reason_code: str,
    severity: DiagnosticSeverity,
    source_diagnostic: str,
    summary: str,
    created_at: datetime,
) -> GovernanceReviewItem:
    identity = f"{proposal_version_id}|{decision_id or '-'}|{reason_code}|{source_diagnostic}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return GovernanceReviewItem(
        review_item_id=f"review:{proposal_version_id}:{digest}",
        proposal_id=proposal_id,
        proposal_version_id=proposal_version_id,
        decision_id=decision_id,
        reason_code=reason_code,
        severity=severity,
        status="OPEN",
        created_at=created_at,
        source_diagnostic=source_diagnostic,
        summary=summary,
    )


def _backlog_reason_from_traceability_code(code: str) -> str | None:
    mapping = {
        "REPLAY_VERIFICATION_FAIL": "REPLAY_MISMATCH",
        "SNAPSHOT_MISSING": "MISSING_SNAPSHOT",
        "CANONICAL_PAYLOAD_MISSING": "MISSING_CANONICAL_PAYLOAD",
        "INPUT_HASH_MISSING": "INPUT_HASH_MISSING",
        "RECONSTRUCTION_FAILED": "INCOMPLETE_LINEAGE",
        "CLAIM_REFERENCES_MISSING": "MISSING_SUPPORTING_CLAIMS",
        "EVIDENCE_REFERENCES_MISSING": "MISSING_SUPPORTING_EVIDENCE",
        "DECISION_LINKAGE_INVALID": "INVALID_DECISION_LINKAGE",
        "REPLAY_VERIFICATION_UNAVAILABLE": "DIAGNOSTIC_SERVICE_FAILURE",
        "THESIS_VERSION_MISSING": "MISSING_THESIS_VERSION",
    }
    return mapping.get(code)
