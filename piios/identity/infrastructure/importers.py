from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from piios.identity.application.commands import (
    CreateCompanyCommand,
    CreateListingCommand,
    CreateSecurityCommand,
)
from piios.identity.domain.enums import SecurityType


@dataclass(frozen=True)
class LegacyIdentityRow:
    legacy_source: str
    legacy_record_id: str
    ticker: str | None
    exchange: str | None
    currency: str | None
    name: str | None


def build_seed_company_command(company_id: str, legal_name: str, country_code: str, active_from: date) -> CreateCompanyCommand:
    return CreateCompanyCommand(
        company_id=company_id,
        legal_name=legal_name,
        common_name=legal_name,
        company_type="CORPORATE",
        jurisdiction_of_incorporation=country_code,
        primary_economic_country=country_code,
        sector=None,
        industry=None,
        active_from=active_from,
        active_to=None,
    )


def build_seed_security_command(security_id: str, issuer_company_id: str, name: str, active_from: date) -> CreateSecurityCommand:
    return CreateSecurityCommand(
        security_id=security_id,
        issuer_company_id=issuer_company_id,
        issuer_name=None,
        security_type=SecurityType.ORDINARY_EQUITY,
        security_name=name,
        issue_currency="USD",
        issue_date=None,
        maturity_date=None,
        share_class_or_seniority=None,
        economic_exposure_type="EQUITY",
        active_from=active_from,
        active_to=None,
    )


def build_seed_listing_command(listing_id: str, security_id: str, exchange: str, ticker: str, currency: str, country: str, active_from: date) -> CreateListingCommand:
    return CreateListingCommand(
        listing_id=listing_id,
        security_id=security_id,
        exchange_code=exchange,
        ticker=ticker,
        trading_currency=currency,
        listing_country=country,
        is_primary_listing=True,
        lot_size=None,
        price_source_symbol=None,
        active_from=active_from,
        active_to=None,
    )
