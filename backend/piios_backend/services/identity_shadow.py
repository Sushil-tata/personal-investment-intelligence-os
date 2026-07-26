from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from piios_backend.services.identity import BackendIdentityService
from piios_backend.services.in_memory_store import store


def build_shadow_identity_diagnostics(identity_service: BackendIdentityService) -> dict:
    items: list[dict] = []

    for holding in store.holdings:
        result = identity_service.resolve(
            SimpleNamespace(
                company_id=None,
                security_id=None,
                listing_id=None,
                isin=None,
                exchange=None,
                ticker=holding.ticker,
                provider=None,
                provider_identifier=None,
                legacy_asset_id=holding.holding_id,
                legacy_ticker=holding.ticker,
                company_name=None,
                jurisdiction=None,
                trading_currency=holding.currency,
                effective_date=date.today(),
            )
        )
        items.append(
            {
                "source_type": "holding",
                "source_id": holding.holding_id,
                "legacy_subject": holding.ticker,
                "resolution_status": result["status"],
                "candidate_count": len(result["candidates"]),
                "warnings": result["warnings"],
            }
        )

    for rec in store.recommendations:
        result = identity_service.resolve(
            SimpleNamespace(
                company_id=None,
                security_id=None,
                listing_id=None,
                isin=None,
                exchange=None,
                ticker=rec.ticker,
                provider=None,
                provider_identifier=None,
                legacy_asset_id=rec.recommendation_id,
                legacy_ticker=rec.ticker,
                company_name=None,
                jurisdiction=None,
                trading_currency=None,
                effective_date=date.today(),
            )
        )
        items.append(
            {
                "source_type": "recommendation",
                "source_id": rec.recommendation_id,
                "legacy_subject": rec.ticker,
                "resolution_status": result["status"],
                "candidate_count": len(result["candidates"]),
                "warnings": result["warnings"],
            }
        )

    for thesis in store.theses:
        result = identity_service.resolve(
            SimpleNamespace(
                company_id=None,
                security_id=None,
                listing_id=None,
                isin=None,
                exchange=None,
                ticker=thesis.ticker,
                provider=None,
                provider_identifier=None,
                legacy_asset_id=thesis.thesis_id,
                legacy_ticker=thesis.ticker,
                company_name=None,
                jurisdiction=None,
                trading_currency=None,
                effective_date=date.today(),
            )
        )
        items.append(
            {
                "source_type": "thesis",
                "source_id": thesis.thesis_id,
                "legacy_subject": thesis.ticker,
                "resolution_status": result["status"],
                "candidate_count": len(result["candidates"]),
                "warnings": result["warnings"],
            }
        )

    unresolved = [row for row in items if row["resolution_status"] != "RESOLVED"]
    return {
        "enabled": True,
        "checked_records": len(items),
        "unresolved_records": len(unresolved),
        "items": items,
    }
