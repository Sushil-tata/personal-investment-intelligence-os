from __future__ import annotations

from decimal import Decimal

from piios.portfolio.infrastructure.legacy_adapter import from_legacy_holdings, to_legacy_allocation, to_legacy_currency_exposure, to_legacy_net_worth
from piios_backend.services.in_memory_store import store
from piios_backend.services.portfolio_layers import PortfolioLayersService


def _normalize_items(items: list[dict], key_field: str) -> list[dict]:
    return sorted(items, key=lambda row: row[key_field])


def _assert_items_close(left: list[dict], right: list[dict], key_field: str) -> None:
    left_rows = _normalize_items(left, key_field)
    right_rows = _normalize_items(right, key_field)
    assert len(left_rows) == len(right_rows)
    for lrow, rrow in zip(left_rows, right_rows, strict=True):
        assert lrow[key_field] == rrow[key_field]
        assert round(float(lrow["market_value"]), 2) == round(float(rrow["market_value"]), 2)
        assert abs(round(float(lrow["percentage"]), 2) - round(float(rrow["percentage"]), 2)) <= 0.01


def test_legacy_equivalence_allocation_and_currency() -> None:
    snapshot = from_legacy_holdings(store.holdings, reporting_currency="USD")
    fx = {"USD/USD": Decimal("1"), "INR/USD": Decimal("1")}

    legacy_service = PortfolioLayersService(session=None)  # type: ignore[arg-type]
    legacy_allocation = legacy_service.allocation("asset_class").model_dump()
    new_allocation = to_legacy_allocation(snapshot, fx, "asset_class")

    assert round(legacy_allocation["total_value"], 2) == round(new_allocation["total_value"], 2)
    _assert_items_close(legacy_allocation["items"], new_allocation["items"], "key")

    legacy_currency = legacy_service.currency_exposure().model_dump()
    new_currency = to_legacy_currency_exposure(snapshot, fx)

    assert round(legacy_currency["total_value"], 2) == round(new_currency["total_value"], 2)
    _assert_items_close(legacy_currency["items"], new_currency["items"], "currency")


def test_legacy_equivalence_net_worth() -> None:
    snapshot = from_legacy_holdings(store.holdings, reporting_currency="USD")
    fx = {"USD/USD": Decimal("1"), "INR/USD": Decimal("1")}

    legacy_service = PortfolioLayersService(session=None)  # type: ignore[arg-type]
    legacy_net = legacy_service.net_worth().model_dump()
    new_net = to_legacy_net_worth(snapshot, fx)

    assert round(legacy_net["net_worth"], 2) == round(new_net["net_worth"], 2)
