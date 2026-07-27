from __future__ import annotations

from collections import defaultdict

from piios_backend.schemas.operations import ResearchDocumentResponse
from piios_backend.schemas.thesis import InvestmentThesis


def project_claims_evidence_overlap_for_thesis(
    thesis: InvestmentThesis,
    claims: list[dict],
    interpretations: list[dict],
    evidence_items: list[dict],
    evidence_sources: list[dict],
) -> dict[str, object]:
    by_claim: dict[str, list[dict]] = defaultdict(list)
    by_evidence: dict[str, dict] = {row["evidence_id"]: row for row in evidence_items}
    by_source: dict[str, dict] = {row["source_id"]: row for row in evidence_sources}

    for item in interpretations:
        by_claim[item["claim_id"]].append(item)

    claim_rows: list[dict[str, object]] = []
    for claim in claims:
        linked = by_claim.get(claim["claim_id"], [])
        supports = [row["evidence_id"] for row in linked if row.get("relation") == "SUPPORTS" and row.get("effective_to") is None]
        contradicts = [
            row["evidence_id"] for row in linked if row.get("relation") == "CONTRADICTS" and row.get("effective_to") is None
        ]
        claim_rows.append(
            {
                "claim_id": claim["claim_id"],
                "claim_key": claim["claim_key"],
                "claim_text": claim["claim_text"],
                "status": claim["status"],
                "supports_evidence_ids": supports,
                "contradicts_evidence_ids": contradicts,
            }
        )

    evidence_rows: list[dict[str, object]] = []
    seen = set()
    for claim in claim_rows:
        for evidence_id in claim["supports_evidence_ids"] + claim["contradicts_evidence_ids"]:
            if evidence_id in seen or evidence_id not in by_evidence:
                continue
            seen.add(evidence_id)
            evidence = by_evidence[evidence_id]
            source = by_source.get(evidence["source_id"], {})
            evidence_rows.append(
                {
                    "evidence_id": evidence_id,
                    "title": evidence["title"],
                    "source": source.get("publisher"),
                    "source_system": source.get("source_system"),
                    "url": source.get("url"),
                    "as_of_date": evidence.get("as_of_date"),
                }
            )

    return {
        "thesis_id": thesis.thesis_id,
        "ticker": thesis.ticker,
        # Explicitly preserve legacy rationale/source fields untouched.
        "legacy_rationale": thesis.thesis,
        "legacy_source_documents": list(thesis.source_documents),
        "claims_overlap": claim_rows,
        "evidence_overlap": evidence_rows,
    }


def project_evidence_to_legacy_research_documents(evidence_items: list[dict], evidence_sources: list[dict]) -> list[ResearchDocumentResponse]:
    by_source = {row["source_id"]: row for row in evidence_sources}
    rows: list[ResearchDocumentResponse] = []
    for evidence in evidence_items:
        source = by_source.get(evidence["source_id"], {})
        rows.append(
            ResearchDocumentResponse(
                title=evidence.get("title") or "Evidence item",
                source=source.get("publisher") or source.get("source_system") or "Unknown",
                timestamp=source.get("published_at") or source.get("retrieved_at") or evidence["created_at"],
                url=source.get("url") or "",
                credibility_score=80.0,
                extracted_entities=[],
                related_ticker_theme="",
            )
        )
    return rows
