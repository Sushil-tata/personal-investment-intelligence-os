from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

# Ensure piios package (repo-root level) is importable from backend runtime.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from piios.portfolio.application.services import PortfolioAnalyticsService
from piios.portfolio.domain.enums import CountryMode, ExposureBasis
from piios.portfolio.domain.value_objects import Money
from piios.portfolio.infrastructure.legacy_adapter import from_legacy_holdings
from piios_backend.core.config import settings
from piios_backend.services.in_memory_store import store
from piios_backend.services.portfolio_layers import PortfolioLayersService


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Mismatch:
    metric: str
    path: str
    mismatch_type: str
    legacy_value: Any
    new_value: Any
    tolerance: float | None = None


_last_report: dict[str, Any] | None = None


def _to_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _money_close(left: Any, right: Any, tolerance: Decimal) -> bool:
    return abs(_to_decimal(left) - _to_decimal(right)) <= tolerance


def _pct_close(left: Any, right: Any, tolerance: Decimal) -> bool:
    return abs(_to_decimal(left) - _to_decimal(right)) <= tolerance


def _legacy_exposure_map(dimension: str) -> dict[str, dict[str, Any]]:
    service = PortfolioLayersService(session=None)  # type: ignore[arg-type]
    payload = service.allocation(dimension).model_dump()
    return {
        row["key"]: {
            "value_reporting": row["market_value"],
            "weight_pct": row["percentage"],
        }
        for row in payload["items"]
    }


def _legacy_currency_exposure_map() -> dict[str, dict[str, Any]]:
    service = PortfolioLayersService(session=None)  # type: ignore[arg-type]
    payload = service.currency_exposure().model_dump()
    return {
        row["currency"]: {
            "value_reporting": row["market_value"],
            "weight_pct": row["percentage"],
        }
        for row in payload["items"]
    }


def _legacy_position_weights() -> dict[str, Decimal]:
    total = sum((_to_decimal(item.market_value) for item in store.holdings), Decimal("0"))
    if total == Decimal("0"):
        return {}
    weights: dict[str, Decimal] = {}
    for item in store.holdings:
        key = f"{item.ticker}:NA"
        weights[key] = (_to_decimal(item.market_value) / total) * Decimal("100")
    return weights


def _legacy_hhi(weights: dict[str, Decimal]) -> Decimal:
    return sum(((w / Decimal("100")) ** 2 for w in weights.values()), Decimal("0"))


def _legacy_top_holdings(limit: int = 10) -> list[dict[str, Any]]:
    total = sum((_to_decimal(item.market_value) for item in store.holdings), Decimal("0"))
    if total == Decimal("0"):
        return []
    rows = sorted(store.holdings, key=lambda x: x.market_value, reverse=True)[:limit]
    return [
        {
            "key": f"{row.ticker}:NA",
            "value_reporting": _to_decimal(row.market_value),
            "weight_pct": (_to_decimal(row.market_value) / total) * Decimal("100"),
        }
        for row in rows
    ]


def _legacy_proposed_trade_impact(proposed_amount_usd: Decimal) -> dict[str, Any]:
    weights_before = _legacy_position_weights()
    total_before = sum((_to_decimal(item.market_value) for item in store.holdings), Decimal("0"))
    total_after = total_before + proposed_amount_usd

    # Legacy has no dedicated proposed-trade endpoint; use deterministic baseline over current holdings.
    position_after = {
        key: ((value / Decimal("100")) * total_before / total_after) * Decimal("100")
        for key, value in weights_before.items()
    } if total_after > 0 else dict(weights_before)
    position_after["NVDA:NASDAQ"] = (proposed_amount_usd / total_after) * Decimal("100") if total_after > 0 else Decimal("0")

    position_delta = {
        key: position_after.get(key, Decimal("0")) - weights_before.get(key, Decimal("0"))
        for key in set(position_after) | set(weights_before)
    }
    return {
        "proposed_amount": proposed_amount_usd,
        "before_total_value": total_before,
        "after_total_value": total_after,
        "position_weight_delta": position_delta,
    }


def _to_map(items: list[Any]) -> dict[str, dict[str, Any]]:
    return {
        item.key: {
            "value_reporting": _to_decimal(item.value_reporting),
            "weight_pct": _to_decimal(item.weight_pct),
        }
        for item in items
    }


def _new_metrics(fx_rates: dict[str, Decimal], proposed_amount_usd: Decimal) -> dict[str, Any]:
    snapshot = from_legacy_holdings(store.holdings, reporting_currency="USD")
    service = PortfolioAnalyticsService()

    total_value, _ = service.total_portfolio_value(snapshot, fx_rates, ExposureBasis.TOTAL_NET_WORTH)
    listed_equity_value, _ = service.total_portfolio_value(snapshot, fx_rates, ExposureBasis.LISTED_EQUITY)
    cash_pct, _ = service.cash_percentage(snapshot, fx_rates)

    country_listing, _ = service.country_exposure(snapshot, fx_rates, CountryMode.LISTING)
    country_economic, _ = service.country_exposure(snapshot, fx_rates, CountryMode.ECONOMIC)
    currency, _ = service.currency_exposure(snapshot, fx_rates)
    sector, _ = service.sector_exposure(snapshot, fx_rates)
    theme, _ = service.theme_exposure(snapshot, fx_rates)

    position_weights, _ = service.position_weights(snapshot, fx_rates)
    concentration, _ = service.concentration_metrics(snapshot, fx_rates)
    top_holdings, _ = service.top_holdings(snapshot, fx_rates)

    impact = service.proposed_purchase_impact(
        snapshot=snapshot,
        fx_rates=fx_rates,
        command_amount=Money.from_value(proposed_amount_usd, "USD"),
        proposed_country="United States",
        proposed_sector="Technology",
        proposed_theme="AI Infrastructure",
        proposed_ticker="NVDA:NASDAQ",
    )

    return {
        "total_value": total_value,
        "cash_value": (cash_pct / Decimal("100")) * total_value,
        "listed_equity_value": listed_equity_value,
        "country_exposure_listing": _to_map(country_listing),
        "country_exposure_economic": _to_map(country_economic),
        "currency_exposure": _to_map(currency),
        "sector_exposure": _to_map(sector),
        "theme_exposure": _to_map(theme),
        "position_weights": {k: _to_decimal(v) for k, v in position_weights.items()},
        "hhi": _to_decimal(concentration.hhi_fraction),
        "top_holdings": {
            item.key: {
                "value_reporting": _to_decimal(item.value_reporting),
                "weight_pct": _to_decimal(item.weight_pct),
            }
            for item in top_holdings
        },
        "proposed_trade_impact": {
            "proposed_amount": _to_decimal(impact.proposed_amount),
            "before_total_value": _to_decimal(impact.before_total_value),
            "after_total_value": _to_decimal(impact.after_total_value),
            "position_weight_delta": {k: _to_decimal(v) for k, v in impact.position_weight_delta.items()},
        },
    }


def _legacy_metrics(proposed_amount_usd: Decimal) -> dict[str, Any]:
    service = PortfolioLayersService(session=None)  # type: ignore[arg-type]
    net = service.net_worth().model_dump()
    weights = _legacy_position_weights()

    return {
        "total_value": _to_decimal(net["total_assets"]),
        "cash_value": Decimal("0"),
        "listed_equity_value": _to_decimal(net["total_assets"]),
        "country_exposure_listing": _legacy_exposure_map("geography"),
        "country_exposure_economic": _legacy_exposure_map("geography"),
        "currency_exposure": _legacy_currency_exposure_map(),
        "sector_exposure": _legacy_exposure_map("sector"),
        "theme_exposure": _legacy_exposure_map("theme"),
        "position_weights": weights,
        "hhi": _legacy_hhi(weights),
        "top_holdings": {
            row["key"]: {
                "value_reporting": row["value_reporting"],
                "weight_pct": row["weight_pct"],
            }
            for row in _legacy_top_holdings()
        },
        "proposed_trade_impact": _legacy_proposed_trade_impact(proposed_amount_usd),
    }


def _compare_mapping_metric(
    metric: str,
    legacy_map: dict[str, Any],
    new_map: dict[str, Any],
    money_tol: Decimal,
    pct_tol: Decimal,
    mismatches: list[Mismatch],
) -> None:
    legacy_keys = set(legacy_map.keys())
    new_keys = set(new_map.keys())
    if legacy_keys != new_keys:
        mismatches.append(
            Mismatch(
                metric=metric,
                path=f"{metric}.keys",
                mismatch_type="classification_mismatch",
                legacy_value=sorted(legacy_keys),
                new_value=sorted(new_keys),
            )
        )

    for key in sorted(legacy_keys & new_keys):
        lrow = legacy_map[key]
        nrow = new_map[key]
        if isinstance(lrow, dict) and isinstance(nrow, dict):
            for subkey in sorted(set(lrow.keys()) | set(nrow.keys())):
                if subkey not in lrow or subkey not in nrow:
                    mismatches.append(
                        Mismatch(
                            metric=metric,
                            path=f"{metric}.{key}.{subkey}",
                            mismatch_type="missing_field",
                            legacy_value=lrow.get(subkey),
                            new_value=nrow.get(subkey),
                        )
                    )
                    continue
                if subkey in {"value_reporting", "proposed_amount", "before_total_value", "after_total_value"}:
                    if not _money_close(lrow[subkey], nrow[subkey], money_tol):
                        mismatches.append(
                            Mismatch(
                                metric=metric,
                                path=f"{metric}.{key}.{subkey}",
                                mismatch_type="money_mismatch",
                                legacy_value=lrow[subkey],
                                new_value=nrow[subkey],
                                tolerance=float(money_tol),
                            )
                        )
                elif subkey in {"weight_pct"}:
                    if not _pct_close(lrow[subkey], nrow[subkey], pct_tol):
                        mismatches.append(
                            Mismatch(
                                metric=metric,
                                path=f"{metric}.{key}.{subkey}",
                                mismatch_type="percentage_mismatch",
                                legacy_value=lrow[subkey],
                                new_value=nrow[subkey],
                                tolerance=float(pct_tol),
                            )
                        )
                elif lrow[subkey] != nrow[subkey]:
                    mismatches.append(
                        Mismatch(
                            metric=metric,
                            path=f"{metric}.{key}.{subkey}",
                            mismatch_type="exact_mismatch",
                            legacy_value=lrow[subkey],
                            new_value=nrow[subkey],
                        )
                    )
        else:
            if metric == "position_weights":
                if not _pct_close(lrow, nrow, pct_tol):
                    mismatches.append(
                        Mismatch(
                            metric=metric,
                            path=f"{metric}.{key}",
                            mismatch_type="percentage_mismatch",
                            legacy_value=lrow,
                            new_value=nrow,
                            tolerance=float(pct_tol),
                        )
                    )
            elif lrow != nrow:
                mismatches.append(
                    Mismatch(
                        metric=metric,
                        path=f"{metric}.{key}",
                        mismatch_type="exact_mismatch",
                        legacy_value=lrow,
                        new_value=nrow,
                    )
                )


def compare_metrics(
    legacy: dict[str, Any],
    new: dict[str, Any],
    money_tolerance: Decimal,
    percentage_tolerance: Decimal,
) -> dict[str, Any]:
    mismatches: list[Mismatch] = []

    for scalar_metric in ("total_value", "cash_value", "listed_equity_value", "hhi"):
        if scalar_metric not in legacy or scalar_metric not in new:
            mismatches.append(
                Mismatch(
                    metric=scalar_metric,
                    path=scalar_metric,
                    mismatch_type="missing_metric",
                    legacy_value=legacy.get(scalar_metric),
                    new_value=new.get(scalar_metric),
                )
            )
            continue
        tol = money_tolerance if scalar_metric != "hhi" else percentage_tolerance
        if not _money_close(legacy[scalar_metric], new[scalar_metric], tol):
            mismatches.append(
                Mismatch(
                    metric=scalar_metric,
                    path=scalar_metric,
                    mismatch_type="scalar_mismatch",
                    legacy_value=legacy[scalar_metric],
                    new_value=new[scalar_metric],
                    tolerance=float(tol),
                )
            )

    for mapped_metric in (
        "country_exposure_listing",
        "country_exposure_economic",
        "currency_exposure",
        "sector_exposure",
        "theme_exposure",
        "position_weights",
        "top_holdings",
    ):
        _compare_mapping_metric(
            metric=mapped_metric,
            legacy_map=legacy.get(mapped_metric, {}),
            new_map=new.get(mapped_metric, {}),
            money_tol=money_tolerance,
            pct_tol=percentage_tolerance,
            mismatches=mismatches,
        )

    _compare_mapping_metric(
        metric="proposed_trade_impact.position_weight_delta",
        legacy_map=legacy.get("proposed_trade_impact", {}).get("position_weight_delta", {}),
        new_map=new.get("proposed_trade_impact", {}).get("position_weight_delta", {}),
        money_tol=money_tolerance,
        pct_tol=percentage_tolerance,
        mismatches=mismatches,
    )

    for scalar_field in ("proposed_amount", "before_total_value", "after_total_value"):
        lval = legacy.get("proposed_trade_impact", {}).get(scalar_field)
        nval = new.get("proposed_trade_impact", {}).get(scalar_field)
        if lval is None or nval is None:
            mismatches.append(
                Mismatch(
                    metric="proposed_trade_impact",
                    path=f"proposed_trade_impact.{scalar_field}",
                    mismatch_type="missing_field",
                    legacy_value=lval,
                    new_value=nval,
                )
            )
            continue
        if not _money_close(lval, nval, money_tolerance):
            mismatches.append(
                Mismatch(
                    metric="proposed_trade_impact",
                    path=f"proposed_trade_impact.{scalar_field}",
                    mismatch_type="money_mismatch",
                    legacy_value=lval,
                    new_value=nval,
                    tolerance=float(money_tolerance),
                )
            )

    return {
        "status": "mismatch" if mismatches else "match",
        "mismatch_count": len(mismatches),
        "mismatches": [m.__dict__ for m in mismatches],
    }


def run_dual_run_verification(
    fx_rates: dict[str, Decimal] | None = None,
    proposed_amount_usd: Decimal = Decimal("5000"),
    money_tolerance: Decimal | None = None,
    percentage_tolerance: Decimal | None = None,
) -> dict[str, Any]:
    effective_fx = fx_rates or {"USD/USD": Decimal("1"), "INR/USD": Decimal("1")}
    money_tol = money_tolerance or Decimal(str(settings.portfolio_dual_run_money_tolerance))
    pct_tol = percentage_tolerance or Decimal(str(settings.portfolio_dual_run_percentage_tolerance))

    legacy = _legacy_metrics(proposed_amount_usd)
    new = _new_metrics(effective_fx, proposed_amount_usd)
    result = compare_metrics(legacy, new, money_tol, pct_tol)
    result["metrics_compared"] = [
        "total_value",
        "cash_value",
        "listed_equity_value",
        "country_exposure_listing",
        "country_exposure_economic",
        "currency_exposure",
        "sector_exposure",
        "theme_exposure",
        "position_weights",
        "hhi",
        "top_holdings",
        "proposed_trade_impact",
    ]
    return result


def dual_run_enabled() -> bool:
    return settings.portfolio_dual_run_enabled and settings.env.lower() in {"dev", "test"}


def maybe_run_dual_run(trigger: str) -> None:
    global _last_report
    if not dual_run_enabled():
        return
    report = run_dual_run_verification()
    report["trigger"] = trigger
    _last_report = report
    if report["mismatch_count"] > 0:
        logger.warning("Portfolio dual-run mismatch count=%s trigger=%s", report["mismatch_count"], trigger)


def get_last_dual_run_report() -> dict[str, Any] | None:
    return _last_report
