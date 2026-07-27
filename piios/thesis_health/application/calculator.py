from __future__ import annotations

import json
from datetime import datetime

from piios.thesis.domain.claims import ClaimEvidenceInterpretation, InterpretationRelation, ThesisClaim
from piios.thesis.domain.evidence import EvidenceItem, EvidenceSource
from piios.thesis.domain.provenance import ProvenanceRecord
from piios.thesis_health.domain.entities import ThesisHealthSnapshot


class ThesisHealthCalculator:
    def calculate(
        self,
        thesis_version_id: str,
        computation_version: str,
        computed_at: datetime,
        claims: tuple[ThesisClaim, ...],
        evidence_items: tuple[EvidenceItem, ...],
        evidence_sources: tuple[EvidenceSource, ...],
        interpretations: tuple[ClaimEvidenceInterpretation, ...],
        provenance_records: tuple[ProvenanceRecord, ...],
    ) -> ThesisHealthSnapshot:
        claim_ids = {item.claim_id for item in claims if item.thesis_version_id == thesis_version_id}
        active_interpretations = tuple(
            sorted(
                [
                    row
                    for row in interpretations
                    if row.claim_id in claim_ids and row.effective_to is None
                ],
                key=lambda row: (row.claim_id, row.interpretation_id),
            )
        )

        evidence_by_id = {row.evidence_id: row for row in evidence_items}
        source_by_id = {row.source_id: row for row in evidence_sources}

        linked_evidence_ids = tuple(sorted({row.evidence_id for row in active_interpretations}))
        linked_evidence = tuple(evidence_by_id[row] for row in linked_evidence_ids if row in evidence_by_id)

        evidence_freshness = self._compute_evidence_freshness(linked_evidence, computed_at)
        evidence_quality = self._compute_evidence_quality(linked_evidence, source_by_id)
        supporting_strength = self._compute_interpretation_strength(active_interpretations, InterpretationRelation.SUPPORTS)
        contradictory_strength = self._compute_interpretation_strength(active_interpretations, InterpretationRelation.CONTRADICTS)
        provenance_completeness = self._compute_provenance_completeness(
            provenance_records=provenance_records,
            claim_ids=claim_ids,
            evidence_ids=set(linked_evidence_ids),
            interpretation_ids={row.interpretation_id for row in active_interpretations},
        )

        thesis_health_index = round(
            (
                evidence_freshness
                + evidence_quality
                + supporting_strength
                + (1.0 - contradictory_strength)
                + provenance_completeness
            )
            / 5.0,
            6,
        )

        return ThesisHealthSnapshot(
            thesis_version_id=thesis_version_id,
            computation_version=computation_version,
            computed_at=computed_at,
            evidence_freshness=evidence_freshness,
            evidence_quality=evidence_quality,
            supporting_strength=supporting_strength,
            contradictory_strength=contradictory_strength,
            provenance_completeness=provenance_completeness,
            thesis_health_index=thesis_health_index,
        )

    def _compute_evidence_freshness(self, evidence_items: tuple[EvidenceItem, ...], computed_at: datetime) -> float:
        if not evidence_items:
            return 0.0

        values: list[float] = []
        for row in evidence_items:
            ref_ts = _parse_reference_datetime(row)
            age_days = max(0.0, (computed_at - ref_ts).total_seconds() / 86400.0)
            values.append(max(0.0, 1.0 - (age_days / 365.0)))
        return round(sum(values) / len(values), 6)

    def _compute_evidence_quality(
        self,
        evidence_items: tuple[EvidenceItem, ...],
        source_by_id: dict[str, EvidenceSource],
    ) -> float:
        if not evidence_items:
            return 0.0

        values: list[float] = []
        for row in evidence_items:
            source = source_by_id.get(row.source_id)
            tier_score = _credibility_tier_score(source.credibility_tier if source else None)
            metadata_score = _metadata_quality_score(row.metadata_json)
            if metadata_score is None:
                values.append(tier_score)
            else:
                values.append((tier_score + metadata_score) / 2.0)
        return round(sum(values) / len(values), 6)

    def _compute_interpretation_strength(
        self,
        interpretations: tuple[ClaimEvidenceInterpretation, ...],
        relation: InterpretationRelation,
    ) -> float:
        rows = [row for row in interpretations if row.relation == relation]
        if not rows:
            return 0.0
        values = [_strength_score(row.strength) for row in rows]
        return round(sum(values) / len(values), 6)

    def _compute_provenance_completeness(
        self,
        provenance_records: tuple[ProvenanceRecord, ...],
        claim_ids: set[str],
        evidence_ids: set[str],
        interpretation_ids: set[str],
    ) -> float:
        target_ids = claim_ids | evidence_ids | interpretation_ids
        if not target_ids:
            return 0.0

        relevant = [row for row in provenance_records if row.entity_id in target_ids]
        if not relevant:
            return 0.0

        complete_count = 0
        for row in relevant:
            if all(
                [
                    row.actor_type.strip(),
                    row.actor_reference.strip(),
                    row.ingestion_method.strip(),
                    row.source_system.strip(),
                    row.extraction_method.strip(),
                ]
            ):
                complete_count += 1
        return round(complete_count / len(relevant), 6)


def _parse_reference_datetime(evidence: EvidenceItem) -> datetime:
    if evidence.as_of_date:
        raw = evidence.as_of_date
        if len(raw) == 10:
            raw = f"{raw}T00:00:00+00:00"
        return datetime.fromisoformat(raw)
    return evidence.created_at


def _credibility_tier_score(tier: str | None) -> float:
    mapping = {
        "A": 1.0,
        "B": 0.8,
        "C": 0.6,
        "D": 0.4,
        "E": 0.2,
    }
    if tier is None:
        return 0.5
    return mapping.get(tier.upper(), 0.5)


def _metadata_quality_score(metadata_json: str) -> float | None:
    try:
        payload = json.loads(metadata_json)
    except Exception:
        return None

    raw = payload.get("quality_score")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None

    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _strength_score(value: str) -> float:
    normalized = value.strip().lower()
    mapping = {
        "low": 0.33,
        "medium": 0.66,
        "high": 1.0,
    }
    return mapping.get(normalized, 0.5)
