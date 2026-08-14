from __future__ import annotations

from datetime import date

import pandas as pd

from piios_backend.core.universe_loader import load_india_universe


DATA_PENDING_STRATEGIES = {
    "PH_PH_MH_RS_V1": "OWN_HISTORY_PROFIT_SERIES_NOT_AVAILABLE",
}

_FIFTY_TWO_WEEK_WINDOW = 252
_RECENT_ACTIVITY_WINDOW = 20
_MIN_RECENT_OBSERVATIONS = 15
_NEAR_HIGH_THRESHOLD_PCT = -7.0
_MAX_POSITIONS = 5


def select_52w_high_allocations(
    provider: object,
    *,
    as_of_date: date,
    universe: list[str] | None = None,
) -> tuple[dict[str, float], list[dict[str, object]]]:
    universe = universe or load_india_universe()
    as_of_ts = pd.Timestamp(as_of_date)
    candidates: list[dict[str, object]] = []

    for ticker in universe:
        series = provider.close_series(ticker)
        if series.empty:
            continue

        history = series[series.index <= as_of_ts]
        if len(history) < _FIFTY_TWO_WEEK_WINDOW:
            continue

        trailing_year = history.tail(_FIFTY_TWO_WEEK_WINDOW)
        recent_window = history.tail(_RECENT_ACTIVITY_WINDOW)
        if len(recent_window) < _MIN_RECENT_OBSERVATIONS:
            continue

        latest_close = float(history.iloc[-1])
        high_52w = float(trailing_year.max())
        if high_52w <= 0.0:
            continue

        distance_pct = ((latest_close / high_52w) - 1.0) * 100.0
        if distance_pct < _NEAR_HIGH_THRESHOLD_PCT:
            continue

        candidates.append(
            {
                "ticker": ticker,
                "latest_close": round(latest_close, 6),
                "high_52w": round(high_52w, 6),
                "distance_from_52w_high_pct": round(distance_pct, 6),
                "is_new_52w_high": latest_close >= high_52w,
                "recent_observation_count": int(len(recent_window)),
            }
        )

    candidates.sort(
        key=lambda item: (
            not bool(item["is_new_52w_high"]),
            abs(float(item["distance_from_52w_high_pct"])),
            -float(item["latest_close"]),
        )
    )

    selected = candidates[:_MAX_POSITIONS]
    if not selected:
        return {}, []

    equal_weight = 1.0 / len(selected)
    allocations = {str(item["ticker"]): equal_weight for item in selected}
    components = [
        {
            **item,
            "rank": index + 1,
            "selected": True,
            "weight": round(equal_weight, 8),
        }
        for index, item in enumerate(selected)
    ]
    return allocations, components