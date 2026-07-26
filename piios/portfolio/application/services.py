from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from piios.portfolio.application.dto import ConcentrationMetricsDTO, ExposureItemDTO
from piios.portfolio.domain.entities import DataQualityIssue, Holding, PortfolioSnapshot, ProposedTradeImpact
from piios.portfolio.domain.enums import CountryMode, DataIssueSeverity, ExposureBasis
from piios.portfolio.domain.value_objects import Money


DECIMAL_ZERO = Decimal("0")
DECIMAL_HUNDRED = Decimal("100")
DECIMAL_ONE = Decimal("1")


def q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PositionValue:
    holding: Holding
    value_reporting: Decimal


class PortfolioAnalyticsService:
    def __init__(self, stale_price_hours: int = 72) -> None:
        self.stale_price_hours = stale_price_hours

    def _resolve_fx(self, from_ccy: str, to_ccy: str, fx_rates: dict[str, Decimal]) -> Decimal | None:
        if from_ccy == to_ccy:
            return DECIMAL_ONE
        direct = fx_rates.get(f"{from_ccy}/{to_ccy}")
        if direct is not None:
            return Decimal(str(direct))
        inverse = fx_rates.get(f"{to_ccy}/{from_ccy}")
        if inverse not in (None, DECIMAL_ZERO):
            return DECIMAL_ONE / Decimal(str(inverse))
        return None

    def _holding_key(self, holding: Holding) -> str:
        exchange = holding.security.identifier.exchange or "NA"
        return f"{holding.security.identifier.ticker}:{exchange}"

    def _cash_total_reporting(self, snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal]) -> Decimal:
        reporting = snapshot.portfolio.reporting_currency.code
        total = DECIMAL_ZERO
        for cash in snapshot.portfolio.cash_balances:
            fx = self._resolve_fx(cash.balance.currency.code, reporting, fx_rates)
            if fx is not None:
                total += cash.balance.amount * fx
        return total

    def _position_values(
        self,
        snapshot: PortfolioSnapshot,
        fx_rates: dict[str, Decimal],
        basis: ExposureBasis,
    ) -> tuple[list[PositionValue], Decimal, list[DataQualityIssue]]:
        values: list[PositionValue] = []
        issues: list[DataQualityIssue] = []
        reporting = snapshot.portfolio.reporting_currency.code

        for holding in snapshot.portfolio.holdings:
            if basis == ExposureBasis.LISTED_EQUITY and not holding.security.is_listed_equity:
                continue
            if basis == ExposureBasis.LIQUID_INVESTABLE and not holding.security.is_liquid:
                continue

            original = holding.market_value_original
            fx = self._resolve_fx(original.currency.code, reporting, fx_rates)
            if fx is None:
                issues.append(
                    DataQualityIssue(
                        severity=DataIssueSeverity.WARNING,
                        code="MISSING_FX_RATE",
                        message=(
                            f"Missing FX rate for {original.currency.code}/{reporting} "
                            f"for holding {holding.holding_id}"
                        ),
                        field_name="currency",
                    )
                )
                continue

            converted = original.amount * fx
            values.append(PositionValue(holding=holding, value_reporting=converted))

            if not holding.security.sector:
                issues.append(
                    DataQualityIssue(
                        severity=DataIssueSeverity.WARNING,
                        code="MISSING_SECTOR",
                        message=f"Missing sector for {holding.security.identifier.ticker}",
                        field_name="sector",
                    )
                )
            if not holding.security.economic_country:
                issues.append(
                    DataQualityIssue(
                        severity=DataIssueSeverity.WARNING,
                        code="MISSING_ECONOMIC_COUNTRY",
                        message=f"Missing economic country for {holding.security.identifier.ticker}",
                        field_name="economic_country",
                    )
                )
            if holding.price_as_of_utc:
                age = datetime.now(timezone.utc) - holding.price_as_of_utc.replace(tzinfo=timezone.utc)
                if age > timedelta(hours=self.stale_price_hours):
                    issues.append(
                        DataQualityIssue(
                            severity=DataIssueSeverity.WARNING,
                            code="STALE_PRICE",
                            message=f"Stale price for {holding.security.identifier.ticker} ({age.days}d old)",
                            field_name="price_as_of_utc",
                        )
                    )

        securities_total = sum((row.value_reporting for row in values), DECIMAL_ZERO)

        if basis in (ExposureBasis.TOTAL_NET_WORTH, ExposureBasis.LIQUID_INVESTABLE):
            for cash in snapshot.portfolio.cash_balances:
                fx = self._resolve_fx(cash.balance.currency.code, reporting, fx_rates)
                if fx is None:
                    issues.append(
                        DataQualityIssue(
                            severity=DataIssueSeverity.WARNING,
                            code="MISSING_FX_RATE",
                            message=f"Missing FX rate for cash {cash.balance.currency.code}/{reporting}",
                            field_name="currency",
                        )
                    )
                    continue

        cash_total = DECIMAL_ZERO
        if basis in (ExposureBasis.TOTAL_NET_WORTH, ExposureBasis.LIQUID_INVESTABLE):
            for cash in snapshot.portfolio.cash_balances:
                fx = self._resolve_fx(cash.balance.currency.code, reporting, fx_rates)
                if fx is not None:
                    cash_total += cash.balance.amount * fx

        total = securities_total + cash_total
        return values, total, issues

    def total_portfolio_value(
        self,
        snapshot: PortfolioSnapshot,
        fx_rates: dict[str, Decimal],
        basis: ExposureBasis = ExposureBasis.TOTAL_NET_WORTH,
    ) -> tuple[Decimal, list[DataQualityIssue]]:
        _, total, issues = self._position_values(snapshot, fx_rates, basis)
        return q2(total), issues

    def value_by_account(
        self,
        snapshot: PortfolioSnapshot,
        fx_rates: dict[str, Decimal],
        basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
    ) -> tuple[dict[str, Decimal], list[DataQualityIssue]]:
        rows, _, issues = self._position_values(snapshot, fx_rates, basis)
        grouped: dict[str, Decimal] = defaultdict(lambda: DECIMAL_ZERO)
        for row in rows:
            grouped[row.holding.account_id] += row.value_reporting
        return {k: q2(v) for k, v in grouped.items()}, issues

    def value_by_bucket(
        self,
        snapshot: PortfolioSnapshot,
        fx_rates: dict[str, Decimal],
        basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
    ) -> tuple[dict[str, Decimal], list[DataQualityIssue]]:
        rows, _, issues = self._position_values(snapshot, fx_rates, basis)
        grouped: dict[str, Decimal] = defaultdict(lambda: DECIMAL_ZERO)
        for row in rows:
            grouped[row.holding.bucket.value] += row.value_reporting
        return {k: q2(v) for k, v in grouped.items()}, issues

    def _exposure_by_dimension(
        self,
        snapshot: PortfolioSnapshot,
        fx_rates: dict[str, Decimal],
        dimension: str,
        basis: ExposureBasis,
        country_mode: CountryMode = CountryMode.LISTING,
    ) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
        rows, total, issues = self._position_values(snapshot, fx_rates, basis)
        grouped: dict[str, Decimal] = defaultdict(lambda: DECIMAL_ZERO)

        for row in rows:
            sec = row.holding.security
            if dimension == "country":
                key = sec.listing_country if country_mode == CountryMode.LISTING else sec.economic_country
            elif dimension == "currency":
                key = sec.trading_currency.code
            elif dimension == "asset_class":
                key = sec.asset_class
            elif dimension == "sector":
                key = sec.sector or "UNKNOWN"
            elif dimension == "industry":
                key = sec.industry or "UNKNOWN"
            elif dimension == "theme":
                key = sec.theme or "UNKNOWN"
            elif dimension == "account":
                key = row.holding.account_id
            elif dimension == "bucket":
                key = row.holding.bucket.value
            else:
                key = "UNKNOWN"
            grouped[key] += row.value_reporting

        if total == DECIMAL_ZERO:
            return [], issues

        items = [
            ExposureItemDTO(key=key, value_reporting=q2(value), weight_pct=q2((value / total) * DECIMAL_HUNDRED))
            for key, value in grouped.items()
        ]
        items.sort(key=lambda x: x.value_reporting, reverse=True)
        return items, issues

    def asset_class_exposure(self, snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal], basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
        return self._exposure_by_dimension(snapshot, fx_rates, "asset_class", basis)

    def country_exposure(
        self,
        snapshot: PortfolioSnapshot,
        fx_rates: dict[str, Decimal],
        country_mode: CountryMode,
        basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
    ) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
        return self._exposure_by_dimension(snapshot, fx_rates, "country", basis, country_mode)

    def currency_exposure(self, snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal], basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
        return self._exposure_by_dimension(snapshot, fx_rates, "currency", basis)

    def sector_exposure(self, snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal], basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
        return self._exposure_by_dimension(snapshot, fx_rates, "sector", basis)

    def industry_exposure(self, snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal], basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
        return self._exposure_by_dimension(snapshot, fx_rates, "industry", basis)

    def theme_exposure(self, snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal], basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
        return self._exposure_by_dimension(snapshot, fx_rates, "theme", basis)

    def position_weights(self, snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal], basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE) -> tuple[dict[str, Decimal], list[DataQualityIssue]]:
        rows, total, issues = self._position_values(snapshot, fx_rates, basis)
        if total == DECIMAL_ZERO:
            return {}, issues
        weights = {self._holding_key(row.holding): q2((row.value_reporting / total) * DECIMAL_HUNDRED) for row in rows}
        return weights, issues

    def top_holdings(self, snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal], limit: int = 10, basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE) -> tuple[list[ExposureItemDTO], list[DataQualityIssue]]:
        rows, total, issues = self._position_values(snapshot, fx_rates, basis)
        if total == DECIMAL_ZERO:
            return [], issues
        ranked = sorted(rows, key=lambda row: row.value_reporting, reverse=True)[:limit]
        items = [
            ExposureItemDTO(
                key=self._holding_key(row.holding),
                value_reporting=q2(row.value_reporting),
                weight_pct=q2((row.value_reporting / total) * DECIMAL_HUNDRED),
            )
            for row in ranked
        ]
        return items, issues

    def valuation_breakdown(
        self,
        snapshot: PortfolioSnapshot,
        fx_rates: dict[str, Decimal],
        basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE,
    ) -> tuple[dict[str, Decimal], list[DataQualityIssue]]:
        rows, _, issues = self._position_values(snapshot, fx_rates, basis)
        reporting = snapshot.portfolio.reporting_currency.code
        current_value = sum((row.value_reporting for row in rows), DECIMAL_ZERO)
        cost_value = DECIMAL_ZERO

        for row in rows:
            if row.holding.cost_basis is None:
                continue
            fx = self._resolve_fx(row.holding.cost_basis.unit_cost.currency.code, reporting, fx_rates)
            if fx is None:
                issues.append(
                    DataQualityIssue(
                        severity=DataIssueSeverity.WARNING,
                        code="MISSING_FX_RATE",
                        message=f"Missing FX for cost basis of {self._holding_key(row.holding)}",
                        field_name="cost_basis",
                    )
                )
                continue
            cost_value += row.holding.cost_basis.unit_cost.amount * row.holding.quantity.value * fx

        unrealized = current_value - cost_value
        return {
            "current_market_value_reporting": q2(current_value),
            "original_cost_value_reporting": q2(cost_value),
            "unrealized_pnl_reporting": q2(unrealized),
        }, issues

    def concentration_metrics(self, snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal], basis: ExposureBasis = ExposureBasis.LIQUID_INVESTABLE) -> tuple[ConcentrationMetricsDTO, list[DataQualityIssue]]:
        weights, issues = self.position_weights(snapshot, fx_rates, basis)
        fractions = [Decimal(str(v)) / DECIMAL_HUNDRED for v in weights.values()]
        hhi_fraction = sum((w * w for w in fractions), DECIMAL_ZERO)
        sorted_weights = sorted((Decimal(str(v)) for v in weights.values()), reverse=True)
        top_1 = sorted_weights[0] if sorted_weights else DECIMAL_ZERO
        top_5 = sum(sorted_weights[:5], DECIMAL_ZERO)
        top_10 = sum(sorted_weights[:10], DECIMAL_ZERO)
        return (
            ConcentrationMetricsDTO(
                hhi_fraction=q2(hhi_fraction),
                hhi_basis_points=q2(hhi_fraction * Decimal("10000")),
                top_1_weight_pct=q2(top_1),
                top_5_weight_pct=q2(top_5),
                top_10_weight_pct=q2(top_10),
            ),
            issues,
        )

    def cash_percentage(self, snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal]) -> tuple[Decimal, list[DataQualityIssue]]:
        _, total, issues = self._position_values(snapshot, fx_rates, ExposureBasis.TOTAL_NET_WORTH)
        if total == DECIMAL_ZERO:
            return DECIMAL_ZERO, issues
        cash_total = self._cash_total_reporting(snapshot, fx_rates)
        return q2((cash_total / total) * DECIMAL_HUNDRED), issues

    def listed_equity_percentage(self, snapshot: PortfolioSnapshot, fx_rates: dict[str, Decimal]) -> tuple[Decimal, list[DataQualityIssue]]:
        _, listed_total, issues_1 = self._position_values(snapshot, fx_rates, ExposureBasis.LISTED_EQUITY)
        _, net_worth_total, issues_2 = self._position_values(snapshot, fx_rates, ExposureBasis.TOTAL_NET_WORTH)
        if net_worth_total == DECIMAL_ZERO:
            return DECIMAL_ZERO, issues_1 + issues_2
        return q2((listed_total / net_worth_total) * DECIMAL_HUNDRED), issues_1 + issues_2

    def proposed_purchase_impact(
        self,
        snapshot: PortfolioSnapshot,
        fx_rates: dict[str, Decimal],
        command_amount: Money,
        proposed_country: str,
        proposed_sector: str | None,
        proposed_theme: str | None,
        proposed_ticker: str,
    ) -> ProposedTradeImpact:
        before_total, before_issues = self.total_portfolio_value(snapshot, fx_rates, ExposureBasis.TOTAL_NET_WORTH)
        currency = snapshot.portfolio.reporting_currency.code
        fx = self._resolve_fx(command_amount.currency.code, currency, fx_rates)
        issues = list(before_issues)
        if fx is None:
            issues.append(
                DataQualityIssue(
                    severity=DataIssueSeverity.ERROR,
                    code="MISSING_PROPOSED_TRADE_FX",
                    message=f"Missing FX for proposed allocation {command_amount.currency.code}/{currency}",
                    field_name="proposed_allocation.amount",
                )
            )
            converted = DECIMAL_ZERO
        else:
            converted = command_amount.amount * fx

        after_total = before_total + converted

        country_before, _ = self.country_exposure(snapshot, fx_rates, CountryMode.LISTING)
        sector_before, _ = self.sector_exposure(snapshot, fx_rates)
        theme_before, _ = self.theme_exposure(snapshot, fx_rates)
        weights_before, _ = self.position_weights(snapshot, fx_rates)

        def to_map(items: list[ExposureItemDTO]) -> dict[str, Decimal]:
            return {item.key: Decimal(str(item.weight_pct)) for item in items}

        country_after = to_map(country_before)
        sector_after = to_map(sector_before)
        theme_after = to_map(theme_before)

        if after_total > DECIMAL_ZERO:
            delta_pct = q2((converted / after_total) * DECIMAL_HUNDRED)
            country_after[proposed_country] = q2(country_after.get(proposed_country, DECIMAL_ZERO) + delta_pct)
            if proposed_sector:
                sector_after[proposed_sector] = q2(sector_after.get(proposed_sector, DECIMAL_ZERO) + delta_pct)
            if proposed_theme:
                theme_after[proposed_theme] = q2(theme_after.get(proposed_theme, DECIMAL_ZERO) + delta_pct)

        position_after = dict(weights_before)
        if after_total > DECIMAL_ZERO:
            proposed_weight = q2((converted / after_total) * DECIMAL_HUNDRED)
            for key, value in list(position_after.items()):
                position_after[key] = q2((Decimal(str(value)) * before_total) / after_total)
            position_after[proposed_ticker] = proposed_weight

        country_delta = {key: q2(country_after.get(key, DECIMAL_ZERO) - to_map(country_before).get(key, DECIMAL_ZERO)) for key in set(country_after) | set(to_map(country_before))}
        sector_delta = {key: q2(sector_after.get(key, DECIMAL_ZERO) - to_map(sector_before).get(key, DECIMAL_ZERO)) for key in set(sector_after) | set(to_map(sector_before))}
        theme_delta = {key: q2(theme_after.get(key, DECIMAL_ZERO) - to_map(theme_before).get(key, DECIMAL_ZERO)) for key in set(theme_after) | set(to_map(theme_before))}
        position_delta = {key: q2(position_after.get(key, DECIMAL_ZERO) - Decimal(str(weights_before.get(key, DECIMAL_ZERO)))) for key in set(position_after) | set(weights_before)}

        _, listed_total_before_raw, _ = self._position_values(snapshot, fx_rates, ExposureBasis.LISTED_EQUITY)
        _, net_total_before_raw, _ = self._position_values(snapshot, fx_rates, ExposureBasis.TOTAL_NET_WORTH)
        cash_total_before_raw = self._cash_total_reporting(snapshot, fx_rates)
        listed_before_raw = ((listed_total_before_raw / net_total_before_raw) * DECIMAL_HUNDRED) if net_total_before_raw else DECIMAL_ZERO
        cash_before_raw = ((cash_total_before_raw / net_total_before_raw) * DECIMAL_HUNDRED) if net_total_before_raw else DECIMAL_ZERO

        listed_after = q2(((listed_total_before_raw + converted) / after_total) * DECIMAL_HUNDRED) if after_total else DECIMAL_ZERO
        cash_after = q2((cash_total_before_raw / after_total) * DECIMAL_HUNDRED) if after_total else DECIMAL_ZERO

        return ProposedTradeImpact(
            reporting_currency=currency,
            proposed_amount=q2(converted),
            before_total_value=q2(before_total),
            after_total_value=q2(after_total),
            listed_equity_pct_before=q2(listed_before_raw),
            listed_equity_pct_after=q2(listed_after),
            cash_pct_before=q2(cash_before_raw),
            cash_pct_after=q2(cash_after),
            country_concentration_delta=country_delta,
            sector_concentration_delta=sector_delta,
            theme_concentration_delta=theme_delta,
            position_weight_delta=position_delta,
            issues=issues,
        )
