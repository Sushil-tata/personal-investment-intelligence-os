from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from piios_backend.models.entities import (
    ClaimEvidenceInterpretationEntity,
    EvidenceItemEntity,
    EvidenceSourceEntity,
    InvestmentThesisEntity,
    ProvenanceRecordEntity,
    ResearchDocument,
    ThesisClaimEntity,
    ThesisVersionEntity,
)


def run_claims_evidence_shadow_diagnostics(session: Session, stale_after_days: int = 365) -> dict[str, object]:
    legacy_theses = list(session.exec(select(InvestmentThesisEntity)).all())
    legacy_research = list(session.exec(select(ResearchDocument)).all())

    claims = list(session.exec(select(ThesisClaimEntity)).all())
    evidence_items = list(session.exec(select(EvidenceItemEntity)).all())
    evidence_sources = list(session.exec(select(EvidenceSourceEntity)).all())
    interpretations = list(session.exec(select(ClaimEvidenceInterpretationEntity)).all())
    provenance = list(session.exec(select(ProvenanceRecordEntity)).all())
    thesis_versions = {row.version_id: row for row in session.exec(select(ThesisVersionEntity)).all()}

    claim_by_version: dict[str, list[ThesisClaimEntity]] = defaultdict(list)
    for claim in claims:
        claim_by_version[claim.thesis_version_id].append(claim)

    matched_records: list[dict[str, object]] = []
    missing_claims: list[dict[str, str]] = []
    thesis_version_binding_failures: list[dict[str, str]] = []

    for legacy in legacy_theses:
        version_id = f"{legacy.thesis_id}:v1"
        linked_claims = claim_by_version.get(version_id, [])
        if linked_claims:
            matched_records.append(
                {
                    "thesis_id": legacy.thesis_id,
                    "version_id": version_id,
                    "matched_claim_count": len(linked_claims),
                }
            )
        else:
            missing_claims.append({"thesis_id": legacy.thesis_id, "version_id": version_id})

    for claim in claims:
        version = thesis_versions.get(claim.thesis_version_id)
        if version is None:
            thesis_version_binding_failures.append(
                {
                    "claim_id": claim.claim_id,
                    "reason": "missing_thesis_version",
                    "thesis_version_id": claim.thesis_version_id,
                }
            )
            continue
        if claim.thesis_id and claim.thesis_id != version.thesis_id:
            thesis_version_binding_failures.append(
                {
                    "claim_id": claim.claim_id,
                    "reason": "thesis_id_mismatch",
                    "thesis_id": claim.thesis_id,
                    "version_thesis_id": version.thesis_id,
                }
            )

    linked_evidence_ids = {row.evidence_id for row in interpretations}
    unmatched_evidence = [
        {"evidence_id": row.evidence_id, "source_id": row.source_id}
        for row in evidence_items
        if row.evidence_id not in linked_evidence_ids
    ]

    active_interp_by_claim: dict[str, list[ClaimEvidenceInterpretationEntity]] = defaultdict(list)
    for row in interpretations:
        if row.effective_to is None:
            active_interp_by_claim[row.claim_id].append(row)

    conflicting_evidence: list[dict[str, object]] = []
    for claim_id, rows in active_interp_by_claim.items():
        active_rel = {row.relation for row in rows}
        if "SUPPORTS" in active_rel and "CONTRADICTS" in active_rel:
            conflicting_evidence.append(
                {
                    "claim_id": claim_id,
                    "active_relations": sorted(active_rel),
                    "interpretation_ids": [row.interpretation_id for row in rows],
                }
            )

    required_fields = ("actor_type", "actor_reference", "ingestion_method", "source_system", "extraction_method")
    incomplete_provenance = []
    for row in provenance:
        payload = {
            "actor_type": row.actor_type,
            "actor_reference": row.actor_reference,
            "ingestion_method": row.ingestion_method,
            "source_system": row.source_system,
            "extraction_method": row.extraction_method,
        }
        missing = [key for key in required_fields if not payload.get(key)]
        if missing:
            incomplete_provenance.append(
                {
                    "provenance_id": row.provenance_id,
                    "entity_type": row.entity_type,
                    "entity_id": row.entity_id,
                    "missing_fields": missing,
                }
            )

    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=stale_after_days)
    stale_evidence = []
    for row in evidence_items:
        stale_reference = row.as_of_date or row.created_at
        try:
            ref_dt = datetime.fromisoformat(stale_reference)
        except Exception:
            continue
        if ref_dt < stale_cutoff:
            stale_evidence.append({"evidence_id": row.evidence_id, "as_of": stale_reference})

    duplicate_candidates: list[dict[str, object]] = []
    claim_dupe_key = Counter((row.thesis_version_id, row.claim_text.strip().lower()) for row in claims)
    for key, count in claim_dupe_key.items():
        if count > 1:
            duplicate_candidates.append(
                {
                    "type": "claim_text_duplicate",
                    "thesis_version_id": key[0],
                    "normalized_claim_text": key[1],
                    "count": count,
                }
            )

    evidence_dupe_key = Counter((row.source_id, row.title.strip().lower(), row.as_of_date) for row in evidence_items)
    for key, count in evidence_dupe_key.items():
        if count > 1:
            duplicate_candidates.append(
                {
                    "type": "evidence_candidate_duplicate",
                    "source_id": key[0],
                    "title": key[1],
                    "as_of_date": key[2],
                    "count": count,
                }
            )

    # Legacy research overlap heuristic (read-only): by deterministic rd<ID> pattern.
    legacy_research_ids = {f"rd{row.id}" for row in legacy_research if row.id is not None}
    overlap_matched = 0
    for legacy in legacy_theses:
        try:
            refs = json.loads(legacy.source_documents)
        except Exception:
            refs = []
        overlap_matched += sum(1 for token in refs if token in legacy_research_ids)

    return {
        "enabled": True,
        "matched_records": matched_records,
        "missing_claims": missing_claims,
        "unmatched_evidence": unmatched_evidence,
        "conflicting_evidence": conflicting_evidence,
        "incomplete_provenance": incomplete_provenance,
        "stale_evidence": stale_evidence,
        "duplicate_candidates": duplicate_candidates,
        "thesis_version_binding_failures": thesis_version_binding_failures,
        "legacy_research_overlap_matches": overlap_matched,
    }
