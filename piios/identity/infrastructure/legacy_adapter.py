from __future__ import annotations

from datetime import date

from piios.identity.application.dto import IdentitySubjectReference
from piios.identity.application.queries import ResolveIdentityQuery
from piios.identity.application.resolution import IdentityResolutionService


def build_legacy_subject_reference(
    *,
    resolver: IdentityResolutionService,
    legacy_source: str,
    legacy_record_id: str,
    ticker: str | None,
    exchange: str | None,
    trading_currency: str | None,
    effective_date: date,
) -> tuple[IdentitySubjectReference | None, list[str]]:
    if not ticker:
        return None, ["missing ticker in legacy source"]

    result = resolver.resolve(
        ResolveIdentityQuery(
            ticker=ticker,
            exchange=exchange,
            trading_currency=trading_currency,
            legacy_ticker=ticker,
            effective_date=effective_date,
        )
    )

    if not result.candidates:
        return None, [f"{legacy_source}:{legacy_record_id} unresolved identity"]

    first = result.candidates[0]
    return (
        IdentitySubjectReference(
            company=None,
            security=None,
            listing=None,
        ),
        [f"{legacy_source}:{legacy_record_id} resolved via {first.match_basis}"] + result.warnings,
    )
