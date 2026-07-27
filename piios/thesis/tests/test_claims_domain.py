from datetime import datetime, timezone

from piios.thesis.domain.claims import ClaimEvidenceInterpretation, ClaimStatus, InterpretationRelation, ThesisClaim
from piios.thesis.domain.provenance import ProvenanceRecord


def test_claim_requires_thesis_version_link() -> None:
    now = datetime.now(timezone.utc)
    claim = ThesisClaim(
        claim_id="cl_1",
        thesis_version_id="t1:v1",
        thesis_id="t1",
        claim_key="margin_durability",
        claim_text="Gross margin should stay above peer median.",
        claim_type="fundamental",
        status=ClaimStatus.DRAFT,
        active_from=now,
        active_to=None,
        created_at=now,
        updated_at=now,
    )
    assert claim.thesis_version_id == "t1:v1"


def test_interpretation_supports_supersession_history_fields() -> None:
    now = datetime.now(timezone.utc)
    item = ClaimEvidenceInterpretation(
        interpretation_id="int_1",
        claim_id="cl_1",
        evidence_id="ev_1",
        relation=InterpretationRelation.SUPPORTS,
        strength="medium",
        note=None,
        effective_from=now,
        effective_to=None,
        supersedes_interpretation_id=None,
        superseded_by_interpretation_id=None,
        created_at=now,
    )
    assert item.effective_to is None


def test_provenance_contains_required_fields_for_ingestion_lineage() -> None:
    now = datetime.now(timezone.utc)
    prov = ProvenanceRecord(
        provenance_id="prov_1",
        entity_type="EVIDENCE_ITEM",
        entity_id="ev_1",
        action="CREATE",
        actor_type="SYSTEM",
        actor_reference="backfill_command",
        ingestion_method="batch",
        source_system="legacy_store",
        extraction_method="deterministic-map",
        model_name="embedder",
        model_version="v2",
        payload_hash="abc123",
        created_at=now,
    )
    assert prov.actor_type == "SYSTEM"
    assert prov.extraction_method == "deterministic-map"
