from __future__ import annotations

from datetime import date

from piios.identity.application.dto import IdentityResolutionResultDTO, ResolutionCandidateDTO
from piios.identity.application.queries import ResolveIdentityQuery
from piios.identity.domain.enums import IdentifierType, ResolutionStatus
from piios.identity.infrastructure.repository_protocols import IdentityResolutionQueryProtocol


class IdentityResolutionService:
    def __init__(self, query_service: IdentityResolutionQueryProtocol) -> None:
        self._query = query_service

    def resolve(self, query: ResolveIdentityQuery) -> IdentityResolutionResultDTO:
        effective_date = query.effective_date or date.today()

        internal = self._query.candidate_by_internal_ids(query.company_id, query.security_id, query.listing_id, effective_date)
        if internal is not None:
            return self._resolved([internal], effective_date)

        if query.isin:
            isin_rows = self._query.candidates_by_identifier(IdentifierType.ISIN, query.isin, effective_date)
            if query.provider_identifier and query.provider:
                provider_rows = self._query.candidates_by_identifier(
                    IdentifierType.PROVIDER_INTERNAL,
                    query.provider_identifier,
                    effective_date,
                    provider_or_authority=query.provider,
                )
                if isin_rows and provider_rows:
                    isin_keys = {(row.company_id, row.security_id, row.listing_id) for row in isin_rows}
                    provider_keys = {(row.company_id, row.security_id, row.listing_id) for row in provider_rows}
                    if isin_keys != provider_keys:
                        return IdentityResolutionResultDTO(
                            status=ResolutionStatus.CONFLICTING,
                            candidates=[self._to_dto(row) for row in isin_rows + provider_rows],
                            conflicts=["authoritative identifier conflicts with provider identifier"],
                            effective_date=effective_date,
                            requires_human_review=True,
                        )
            result = self._result_from_candidates(isin_rows, effective_date, allow_auto=True)
            if result.status != ResolutionStatus.UNRESOLVED:
                return result

        if query.provider_identifier and query.provider:
            provider_rows = self._query.candidates_by_identifier(
                IdentifierType.PROVIDER_INTERNAL,
                query.provider_identifier,
                effective_date,
                provider_or_authority=query.provider,
            )
            result = self._result_from_candidates(provider_rows, effective_date, allow_auto=True)
            if result.status != ResolutionStatus.UNRESOLVED:
                return result

        if query.exchange and query.ticker:
            exchange_rows = self._query.candidates_by_exchange_ticker(query.exchange, query.ticker, effective_date)
            if exchange_rows and query.effective_date is not None and query.effective_date < date.today():
                return IdentityResolutionResultDTO(
                    status=ResolutionStatus.HISTORICAL_MATCH,
                    candidates=[self._to_dto(item) for item in exchange_rows],
                    warnings=["resolved using historical listing period"],
                    effective_date=effective_date,
                )
            result = self._result_from_candidates(exchange_rows, effective_date, allow_auto=True)
            if result.status != ResolutionStatus.UNRESOLVED:
                return result

        if query.exchange and query.ticker and query.effective_date:
            historical = self._query.candidates_by_exchange_ticker(query.exchange, query.ticker, query.effective_date)
            if historical:
                dto_rows = [self._to_dto(item) for item in historical]
                return IdentityResolutionResultDTO(
                    status=ResolutionStatus.HISTORICAL_MATCH,
                    candidates=dto_rows,
                    warnings=["resolved using historical listing period"],
                    effective_date=effective_date,
                )

        if query.legacy_asset_id or query.legacy_ticker:
            legacy = self._query.legacy_mapping_candidate(query.legacy_asset_id, query.legacy_ticker, effective_date)
            if legacy is not None:
                return self._resolved([legacy], effective_date)

        if query.company_name and query.jurisdiction:
            rows = self._query.candidates_by_company_name_jurisdiction(query.company_name, query.jurisdiction, effective_date)
            result = self._result_from_candidates(rows, effective_date, allow_auto=False)
            if result.status != ResolutionStatus.UNRESOLVED:
                return result

        if query.ticker and query.trading_currency:
            rows = self._query.candidates_by_ticker_currency(query.ticker, query.trading_currency, effective_date)
            result = self._result_from_candidates(rows, effective_date, allow_auto=True)
            if result.status != ResolutionStatus.UNRESOLVED:
                return result

        if query.ticker:
            rows = []
            for currency in ("USD", "INR", "SGD", "HKD", "EUR", "GBP"):
                rows.extend(self._query.candidates_by_ticker_currency(query.ticker, currency, effective_date))
            deduped = []
            seen = set()
            for row in rows:
                key = (row.company_id, row.security_id, row.listing_id)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(row)

            if len(deduped) == 1:
                return IdentityResolutionResultDTO(
                    status=ResolutionStatus.RESOLVED,
                    candidates=[self._to_dto(deduped[0])],
                    warnings=["ticker-only heuristic used"],
                    effective_date=effective_date,
                )
            if len(deduped) > 1:
                return IdentityResolutionResultDTO(
                    status=ResolutionStatus.AMBIGUOUS,
                    candidates=[self._to_dto(row) for row in deduped],
                    warnings=["ticker-only match is ambiguous and requires review"],
                    effective_date=effective_date,
                    requires_human_review=True,
                )

        return IdentityResolutionResultDTO(
            status=ResolutionStatus.UNRESOLVED,
            effective_date=effective_date,
            warnings=["no deterministic identity candidate found"],
            requires_human_review=True,
        )

    def _result_from_candidates(
        self,
        candidates,
        effective_date: date,
        *,
        allow_auto: bool,
    ) -> IdentityResolutionResultDTO:
        if not candidates:
            return IdentityResolutionResultDTO(status=ResolutionStatus.UNRESOLVED, effective_date=effective_date)

        if len(candidates) == 1 and allow_auto:
            return self._resolved(candidates, effective_date)

        candidate_keys = {(row.company_id, row.security_id, row.listing_id) for row in candidates}
        if len(candidate_keys) > 1:
            return IdentityResolutionResultDTO(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=[self._to_dto(row) for row in candidates],
                warnings=["multiple plausible candidates"],
                effective_date=effective_date,
                requires_human_review=True,
            )

        # Same identity seen through multiple records is still deterministic.
        return self._resolved(candidates, effective_date)

    def _resolved(self, candidates, effective_date: date) -> IdentityResolutionResultDTO:
        return IdentityResolutionResultDTO(
            status=ResolutionStatus.RESOLVED,
            candidates=[self._to_dto(row) for row in candidates],
            effective_date=effective_date,
        )

    @staticmethod
    def _to_dto(candidate) -> ResolutionCandidateDTO:
        return ResolutionCandidateDTO(
            company_id=candidate.company_id,
            security_id=candidate.security_id,
            listing_id=candidate.listing_id,
            match_basis=candidate.match_basis,
            rule_strength=candidate.rule_strength,
            is_active=candidate.is_active,
            is_historical=candidate.is_historical,
        )
