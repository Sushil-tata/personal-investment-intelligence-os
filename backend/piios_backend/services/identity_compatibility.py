from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from piios_backend.schemas.portfolio import Holding
from piios_backend.schemas.recommendation import Recommendation
from piios_backend.schemas.thesis import InvestmentThesis
from piios_backend.services.identity import BackendIdentityService


def enrich_holding_identity_non_breaking(holding: Holding, service: BackendIdentityService) -> dict:
    result = service.resolve(
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
    return {
        "holding_id": holding.holding_id,
        "legacy_ticker": holding.ticker,
        "display_name": holding.name,
        "company_id": result["candidates"][0]["company_id"] if result["candidates"] else None,
        "security_id": result["candidates"][0]["security_id"] if result["candidates"] else None,
        "listing_id": result["candidates"][0]["listing_id"] if result["candidates"] else None,
        "resolution_status": result["status"],
        "warnings": result["warnings"],
    }


def enrich_recommendation_identity_non_breaking(item: Recommendation, service: BackendIdentityService) -> dict:
    result = service.resolve(
        SimpleNamespace(
            company_id=None,
            security_id=None,
            listing_id=None,
            isin=None,
            exchange=None,
            ticker=item.ticker,
            provider=None,
            provider_identifier=None,
            legacy_asset_id=item.recommendation_id,
            legacy_ticker=item.ticker,
            company_name=None,
            jurisdiction=None,
            trading_currency=None,
            effective_date=date.today(),
        )
    )
    return {
        "recommendation_id": item.recommendation_id,
        "legacy_ticker": item.ticker,
        "company_id": result["candidates"][0]["company_id"] if result["candidates"] else None,
        "security_id": result["candidates"][0]["security_id"] if result["candidates"] else None,
        "listing_id": result["candidates"][0]["listing_id"] if result["candidates"] else None,
        "resolution_status": result["status"],
        "warnings": result["warnings"],
    }


def enrich_thesis_identity_non_breaking(item: InvestmentThesis, service: BackendIdentityService) -> dict:
    result = service.resolve(
        SimpleNamespace(
            company_id=None,
            security_id=None,
            listing_id=None,
            isin=None,
            exchange=None,
            ticker=item.ticker,
            provider=None,
            provider_identifier=None,
            legacy_asset_id=item.thesis_id,
            legacy_ticker=item.ticker,
            company_name=None,
            jurisdiction=None,
            trading_currency=None,
            effective_date=date.today(),
        )
    )
    return {
        "thesis_id": item.thesis_id,
        "legacy_ticker": item.ticker,
        "company_id": result["candidates"][0]["company_id"] if result["candidates"] else None,
        "security_id": result["candidates"][0]["security_id"] if result["candidates"] else None,
        "listing_id": result["candidates"][0]["listing_id"] if result["candidates"] else None,
        "resolution_status": result["status"],
        "warnings": result["warnings"],
    }
