from __future__ import annotations

from datetime import datetime, timezone

from piios.thesis.domain.claims import ClaimEvidenceInterpretation, ClaimStatus, InterpretationRelation, ThesisClaim
from piios.thesis.domain.evidence import EvidenceItem, EvidenceSource, EvidenceSourceType
from piios.thesis.domain.provenance import ProvenanceRecord
from piios.thesis_health.application.calculator import ThesisHealthCalculator


def _claim(claim_id: str = "cl1") -> ThesisClaim:
    now = datetime(2026, 7, 27, tzinfo=timezone.utc)
    return ThesisClaim(
        claim_id=claim_id,
        thesis_version_id="t1:v1",
        thesis_id="t1",
        claim_key="core",
        claim_text="Core thesis",
        claim_type="fundamental",
        status=ClaimStatus.ACTIVE,
        active_from=now,
        active_to=None,
        created_at=now,
        updated_at=now,
    )


def _source(source_id: str = "src1", credibility_tier: str = "A") -> EvidenceSource:
    now = datetime(2026, 7, 27, tzinfo=timezone.utc)
    return EvidenceSource(
        source_id=source_id,
        source_type=EvidenceSourceType.RESEARCH,
        publisher="Desk",
        url=None,
        source_system="test",
        published_at=now,
        retrieved_at=now,
        credibility_tier=credibility_tier,
        created_at=now,
    )


def _evidence(evidence_id: str = "ev1", source_id: str = "src1", as_of_date: str = "2026-07-20") -> EvidenceItem:
    now = datetime(2026, 7, 27, tzinfo=timezone.utc)
    return EvidenceItem(
        evidence_id=evidence_id,
        source_id=source_id,
        title="Evidence",
        excerpt="x",
        content_hash="h",
        as_of_date=as_of_date,
        metadata_json='{"quality_score": 0.9}',
        created_at=now,
    )


def _interp(
    interpretation_id: str,
    relation: InterpretationRelation,
    claim_id: str = "cl1",
    evidence_id: str = "ev1",
) -> ClaimEvidenceInterpretation:
    now = datetime(2026, 7, 27, tzinfo=timezone.utc)
    return ClaimEvidenceInterpretation(
        interpretation_id=interpretation_id,
        claim_id=claim_id,
        evidence_id=evidence_id,
        relation=relation,
        strength="high" if relation == InterpretationRelation.SUPPORTS else "medium",
        note=None,
        effective_from=now,
        effective_to=None,
        supersedes_interpretation_id=None,
        superseded_by_interpretation_id=None,
        created_at=now,
    )


def _provenance(entity_type: str, entity_id: str, complete: bool = True) -> ProvenanceRecord:
    now = datetime(2026, 7, 27, tzinfo=timezone.utc)
    return ProvenanceRecord(
        provenance_id=f"prov:{entity_id}",
        entity_type=entity_type,
        entity_id=entity_id,
        action="CREATE",
        actor_type="SYSTEM" if complete else "",
        actor_reference="seed" if complete else "",
        ingestion_method="manual" if complete else "",
        source_system="test" if complete else "",
        extraction_method="deterministic" if complete else "",
        model_name=None,
        model_version=None,
        payload_hash=None,
        created_at=now,
    )


def test_thesis_health_calculator_is_deterministic() -> None:
    calculator = ThesisHealthCalculator()
    computed_at = datetime(2026, 7, 27, tzinfo=timezone.utc)

    claims = (_claim(),)
    evidence = (_evidence(),)
    sources = (_source(),)
    interpretations = (
        _interp("i_support", InterpretationRelation.SUPPORTS),
        _interp("i_contradict", InterpretationRelation.CONTRADICTS),
    )
    provenance = (
        _provenance("THESIS_CLAIM", "cl1"),
        _provenance("EVIDENCE_ITEM", "ev1"),
        _provenance("CLAIM_EVIDENCE_INTERPRETATION", "i_support"),
        _provenance("CLAIM_EVIDENCE_INTERPRETATION", "i_contradict"),
    )

    first = calculator.calculate(
        thesis_version_id="t1:v1",
        computation_version="wave2b-th-v1",
        computed_at=computed_at,
        claims=claims,
        evidence_items=evidence,
        evidence_sources=sources,
        interpretations=interpretations,
        provenance_records=provenance,
    )

    second = calculator.calculate(
        thesis_version_id="t1:v1",
        computation_version="wave2b-th-v1",
        computed_at=computed_at,
        claims=claims,
        evidence_items=evidence,
        evidence_sources=sources,
        interpretations=tuple(reversed(interpretations)),
        provenance_records=tuple(reversed(provenance)),
    )

    assert first == second


def test_thesis_health_calculator_handles_empty_inputs() -> None:
    calculator = ThesisHealthCalculator()
    snapshot = calculator.calculate(
        thesis_version_id="t1:v1",
        computation_version="wave2b-th-v1",
        computed_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        claims=tuple(),
        evidence_items=tuple(),
        evidence_sources=tuple(),
        interpretations=tuple(),
        provenance_records=tuple(),
    )

    assert snapshot.evidence_freshness == 0.0
    assert snapshot.evidence_quality == 0.0
    assert snapshot.supporting_strength == 0.0
    assert snapshot.contradictory_strength == 0.0
    assert snapshot.provenance_completeness == 0.0
    assert snapshot.thesis_health_index == 0.2


def test_thesis_health_calculator_provenance_completeness_partial() -> None:
    calculator = ThesisHealthCalculator()
    snapshot = calculator.calculate(
        thesis_version_id="t1:v1",
        computation_version="wave2b-th-v1",
        computed_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        claims=(_claim(),),
        evidence_items=(_evidence(),),
        evidence_sources=(_source(),),
        interpretations=(_interp("i_support", InterpretationRelation.SUPPORTS),),
        provenance_records=(
            _provenance("THESIS_CLAIM", "cl1", complete=True),
            _provenance("EVIDENCE_ITEM", "ev1", complete=False),
            _provenance("CLAIM_EVIDENCE_INTERPRETATION", "i_support", complete=True),
        ),
    )

    assert snapshot.provenance_completeness == 0.666667


def test_thesis_health_calculator_support_and_contradiction_strengths() -> None:
    calculator = ThesisHealthCalculator()
    snapshot = calculator.calculate(
        thesis_version_id="t1:v1",
        computation_version="wave2b-th-v1",
        computed_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        claims=(_claim(),),
        evidence_items=(_evidence(),),
        evidence_sources=(_source(),),
        interpretations=(
            _interp("i_support", InterpretationRelation.SUPPORTS),
            _interp("i_contradict", InterpretationRelation.CONTRADICTS),
        ),
        provenance_records=tuple(),
    )

    assert snapshot.supporting_strength == 1.0
    assert snapshot.contradictory_strength == 0.66
