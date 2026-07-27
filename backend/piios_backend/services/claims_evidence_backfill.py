from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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


@dataclass(frozen=True)
class OwnerReviewItem:
    item_type: str
    reference_id: str
    reason_code: str
    details: dict[str, object]


@dataclass(frozen=True)
class BackfillResult:
    dry_run: bool
    created_claims: int
    created_sources: int
    created_evidence_items: int
    created_interpretations: int
    created_provenance: int
    owner_review_items: list[OwnerReviewItem]


_CLAIM_RULES: tuple[tuple[str, str], ...] = (
    ("core_thesis", "thesis"),
    ("bull_case", "bull_case"),
    ("bear_case", "bear_case"),
    ("why_now", "why_now"),
    ("why_not_now", "why_not_now"),
    ("invalidation_trigger", "invalidation_trigger"),
)

_RD_TOKEN_RE = re.compile(r"^rd(\d+)$", re.IGNORECASE)


def run_claims_evidence_backfill(session: Session, dry_run: bool = True) -> BackfillResult:
    owner_review_items: list[OwnerReviewItem] = []
    created_claims = 0
    created_sources = 0
    created_evidence_items = 0
    created_interpretations = 0
    created_provenance = 0

    legacy_theses = list(session.exec(select(InvestmentThesisEntity)).all())
    versions_by_id = {row.version_id: row for row in session.exec(select(ThesisVersionEntity)).all()}
    research_docs_by_id = {row.id: row for row in session.exec(select(ResearchDocument)).all()}

    for legacy in legacy_theses:
        version_id = f"{legacy.thesis_id}:v1"
        version = versions_by_id.get(version_id)
        if version is None:
            owner_review_items.append(
                OwnerReviewItem(
                    item_type="THESIS",
                    reference_id=legacy.thesis_id,
                    reason_code="THESIS_VERSION_BINDING_FAILURE",
                    details={"expected_version_id": version_id},
                )
            )
            continue

        extracted_claims: list[tuple[str, str]] = []
        for claim_key, field_name in _CLAIM_RULES:
            text_value = getattr(legacy, field_name, "")
            if isinstance(text_value, str) and text_value.strip():
                extracted_claims.append((claim_key, text_value.strip()))

        normalized_counts = {}
        for claim_key, claim_text in extracted_claims:
            token = claim_text.lower().strip()
            normalized_counts[token] = normalized_counts.get(token, 0) + 1
        for token, count in normalized_counts.items():
            if count > 1:
                owner_review_items.append(
                    OwnerReviewItem(
                        item_type="CLAIM",
                        reference_id=legacy.thesis_id,
                        reason_code="DUPLICATE_CANDIDATE",
                        details={"normalized_claim_text": token, "count": count},
                    )
                )

        claim_ids: list[str] = []
        for claim_key, claim_text in extracted_claims:
            claim_id = f"cl:{legacy.thesis_id}:v1:{claim_key}"
            if _exists(session, ThesisClaimEntity, "claim_id", claim_id):
                claim_ids.append(claim_id)
                continue
            claim_row = ThesisClaimEntity(
                claim_id=claim_id,
                thesis_version_id=version_id,
                thesis_id=legacy.thesis_id,
                claim_key=claim_key,
                claim_text=claim_text,
                claim_type="legacy_extracted",
                status="ACTIVE",
                active_from=_now_iso(),
                active_to=None,
                created_at=_now_iso(),
                updated_at=_now_iso(),
            )
            claim_ids.append(claim_id)
            if not dry_run:
                session.add(claim_row)
                _create_provenance_if_missing(
                    session,
                    provenance_id=f"prov:create:THESIS_CLAIM:{claim_id}",
                    entity_type="THESIS_CLAIM",
                    entity_id=claim_id,
                    action="BACKFILL_CREATE",
                    actor_reference="claims_evidence_backfill",
                    ingestion_method="batch_backfill",
                    source_system="legacy_thesis",
                    extraction_method="deterministic_field_map",
                    model_name=None,
                    model_version=None,
                    payload_hash=_hash_text(claim_text),
                )
                created_provenance += 1
            created_claims += 1

        source_tokens = _parse_source_documents(legacy.source_documents)
        for token in source_tokens:
            match = _RD_TOKEN_RE.match(token)
            if not match:
                owner_review_items.append(
                    OwnerReviewItem(
                        item_type="EVIDENCE",
                        reference_id=token,
                        reason_code="INCOMPLETE_PROVENANCE",
                        details={"reason": "non_deterministic_source_token", "thesis_id": legacy.thesis_id},
                    )
                )
                continue

            doc_id = int(match.group(1))
            doc = research_docs_by_id.get(doc_id)
            if doc is None:
                owner_review_items.append(
                    OwnerReviewItem(
                        item_type="EVIDENCE",
                        reference_id=token,
                        reason_code="UNMATCHED_EVIDENCE",
                        details={"reason": "research_document_missing", "thesis_id": legacy.thesis_id},
                    )
                )
                continue

            source_id = f"src:research_document:{doc_id}"
            if not _exists(session, EvidenceSourceEntity, "source_id", source_id):
                source_row = EvidenceSourceEntity(
                    source_id=source_id,
                    source_type="RESEARCH",
                    publisher=doc.source,
                    url=doc.url,
                    source_system="legacy_research_document",
                    published_at=doc.timestamp,
                    retrieved_at=_now_iso(),
                    credibility_tier="B",
                    created_at=_now_iso(),
                )
                if not dry_run:
                    session.add(source_row)
                    _create_provenance_if_missing(
                        session,
                        provenance_id=f"prov:create:EVIDENCE_SOURCE:{source_id}",
                        entity_type="EVIDENCE_SOURCE",
                        entity_id=source_id,
                        action="BACKFILL_CREATE",
                        actor_reference="claims_evidence_backfill",
                        ingestion_method="batch_backfill",
                        source_system="legacy_research_document",
                        extraction_method="deterministic_rdid_map",
                        model_name=None,
                        model_version=None,
                        payload_hash=_hash_text(f"{doc.title}|{doc.source}|{doc.url}"),
                    )
                    created_provenance += 1
                created_sources += 1

            for claim_id in claim_ids:
                evidence_id = f"ev:{claim_id}:{doc_id}"
                if not _exists(session, EvidenceItemEntity, "evidence_id", evidence_id):
                    metadata = {
                        "legacy_reference": token,
                        "research_document_id": doc_id,
                        "incomplete_metadata": False,
                    }
                    item_row = EvidenceItemEntity(
                        evidence_id=evidence_id,
                        source_id=source_id,
                        title=doc.title,
                        excerpt=doc.content[:500],
                        content_hash=_hash_text(f"{doc.title}|{doc.content}|{doc.timestamp}"),
                        as_of_date=doc.timestamp,
                        metadata_json=json.dumps(metadata, sort_keys=True),
                        created_at=_now_iso(),
                    )
                    if not dry_run:
                        session.add(item_row)
                        _create_provenance_if_missing(
                            session,
                            provenance_id=f"prov:create:EVIDENCE_ITEM:{evidence_id}",
                            entity_type="EVIDENCE_ITEM",
                            entity_id=evidence_id,
                            action="BACKFILL_CREATE",
                            actor_reference="claims_evidence_backfill",
                            ingestion_method="batch_backfill",
                            source_system="legacy_research_document",
                            extraction_method="deterministic_rdid_map",
                            model_name=None,
                            model_version=None,
                            payload_hash=_hash_text(doc.content),
                        )
                        created_provenance += 1
                    created_evidence_items += 1

                interp_id = f"interp:{claim_id}:{evidence_id}:supports"
                if not _exists(session, ClaimEvidenceInterpretationEntity, "interpretation_id", interp_id):
                    interp_row = ClaimEvidenceInterpretationEntity(
                        interpretation_id=interp_id,
                        claim_id=claim_id,
                        evidence_id=evidence_id,
                        relation="SUPPORTS",
                        strength="medium",
                        note="Deterministic backfill from legacy thesis source_documents",
                        effective_from=_now_iso(),
                        effective_to=None,
                        supersedes_interpretation_id=None,
                        superseded_by_interpretation_id=None,
                        created_at=_now_iso(),
                    )
                    if not dry_run:
                        session.add(interp_row)
                        _create_provenance_if_missing(
                            session,
                            provenance_id=f"prov:create:CLAIM_EVIDENCE_INTERPRETATION:{interp_id}",
                            entity_type="CLAIM_EVIDENCE_INTERPRETATION",
                            entity_id=interp_id,
                            action="BACKFILL_CREATE",
                            actor_reference="claims_evidence_backfill",
                            ingestion_method="batch_backfill",
                            source_system="legacy_research_document",
                            extraction_method="deterministic_claim_source_link",
                            model_name=None,
                            model_version=None,
                            payload_hash=_hash_text(interp_id),
                        )
                        created_provenance += 1
                    created_interpretations += 1

    if not dry_run:
        session.commit()

    return BackfillResult(
        dry_run=dry_run,
        created_claims=created_claims,
        created_sources=created_sources,
        created_evidence_items=created_evidence_items,
        created_interpretations=created_interpretations,
        created_provenance=created_provenance,
        owner_review_items=owner_review_items,
    )


def write_backfill_reports(result: BackfillResult, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"claims_evidence_backfill_{'dry_run' if result.dry_run else 'apply'}_{ts}.json"
    md_path = out_dir / f"claims_evidence_backfill_{'dry_run' if result.dry_run else 'apply'}_{ts}.md"

    payload = {
        "generated_at": _now_iso(),
        "dry_run": result.dry_run,
        "created_claims": result.created_claims,
        "created_sources": result.created_sources,
        "created_evidence_items": result.created_evidence_items,
        "created_interpretations": result.created_interpretations,
        "created_provenance": result.created_provenance,
        "owner_review_items": [
            {
                "item_type": row.item_type,
                "reference_id": row.reference_id,
                "reason_code": row.reason_code,
                "details": row.details,
            }
            for row in result.owner_review_items
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    counts = {}
    for item in result.owner_review_items:
        counts[item.reason_code] = counts.get(item.reason_code, 0) + 1

    lines = [
        "# Wave 2A.3 Claims & Evidence Backfill Summary",
        "",
        f"Generated at (UTC): {payload['generated_at']}",
        f"Dry run: {result.dry_run}",
        "",
        "## Created Objects",
        f"- claims: {result.created_claims}",
        f"- evidence sources: {result.created_sources}",
        f"- evidence items: {result.created_evidence_items}",
        f"- claim-evidence interpretations: {result.created_interpretations}",
        f"- provenance records: {result.created_provenance}",
        "",
        "## Owner Review Queue",
    ]
    if counts:
        for reason, count in sorted(counts.items()):
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- none")

    lines.extend([
        "",
        "## Notes",
        "- Backfill is idempotent via deterministic IDs and existence checks.",
        "- Ambiguity and incomplete lineage are preserved for owner review.",
        "- No automatic conflict resolution or destructive legacy updates are performed.",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def _exists(session: Session, model, attr: str, value: str) -> bool:
    statement = select(model).where(getattr(model, attr) == value)
    return session.exec(statement).first() is not None


def _create_provenance_if_missing(
    session: Session,
    provenance_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_reference: str,
    ingestion_method: str,
    source_system: str,
    extraction_method: str,
    model_name: str | None,
    model_version: str | None,
    payload_hash: str | None,
) -> None:
    if _exists(session, ProvenanceRecordEntity, "provenance_id", provenance_id):
        return
    session.add(
        ProvenanceRecordEntity(
            provenance_id=provenance_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_type="SYSTEM",
            actor_reference=actor_reference,
            ingestion_method=ingestion_method,
            source_system=source_system,
            extraction_method=extraction_method,
            model_name=model_name,
            model_version=model_version,
            payload_hash=payload_hash,
            created_at=_now_iso(),
        )
    )


def _parse_source_documents(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
