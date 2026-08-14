from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from .models import StrategyDefinition, canonical_hash


class StrategyRegistry:
    """Append-only registry for immutable strategy versions."""

    def __init__(self) -> None:
        self._rows: dict[str, list[StrategyDefinition]] = {}

    def register(self, definition: StrategyDefinition) -> None:
        versions = self._rows.setdefault(definition.strategy_id, [])
        if versions and definition.version <= versions[-1].version:
            raise ValueError("strategy versions must be strictly increasing")
        versions.append(definition)

    def latest(self, strategy_id: str) -> StrategyDefinition:
        versions = self._rows.get(strategy_id) or []
        if not versions:
            raise KeyError(strategy_id)
        return versions[-1]

    def all_latest(self) -> list[StrategyDefinition]:
        return [rows[-1] for rows in self._rows.values() if rows]

    def all_versions(self) -> list[StrategyDefinition]:
        out: list[StrategyDefinition] = []
        for rows in self._rows.values():
            out.extend(rows)
        out.sort(key=lambda r: (r.strategy_id, r.version))
        return out

    def version_hash(self) -> str:
        payload = [asdict(row) for row in self.all_versions()]
        return canonical_hash({"registry": payload})


def default_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    defaults: Iterable[StrategyDefinition] = [
        StrategyDefinition(
            strategy_id="PIIOS_CORE",
            version=1,
            engine_version="WAVE_3_1_RECOMMENDATION_MVP",
            description="Prospective recommendation strategy with immutable decision ledger.",
            kind="CORE",
        ),
        StrategyDefinition(
            strategy_id="52W_HIGH_V1",
            version=1,
            engine_version="PRICE_HIGH_SIMPLE",
            description="Mechanical near-52-week-high challenger using only price-high proximity and basic investability filters.",
            kind="CHALLENGER",
        ),
        StrategyDefinition(
            strategy_id="NIFTY50_V1",
            version=1,
            engine_version="INDEX_BENCHMARK",
            description="India large-cap passive benchmark.",
            kind="BENCHMARK",
        ),
        StrategyDefinition(
            strategy_id="SP500_V1",
            version=1,
            engine_version="INDEX_BENCHMARK",
            description="US large-cap passive benchmark.",
            kind="BENCHMARK",
        ),
        StrategyDefinition(
            strategy_id="STI_V1",
            version=1,
            engine_version="INDEX_BENCHMARK",
            description="Singapore large-cap passive benchmark.",
            kind="BENCHMARK",
        ),
        StrategyDefinition(
            strategy_id="CASH_V1",
            version=1,
            engine_version="CASH_BENCHMARK",
            description="Cash-only baseline benchmark.",
            kind="BENCHMARK",
        ),
    ]
    for row in defaults:
        registry.register(row)
    return registry
