from __future__ import annotations

import math


def compute_total_return_pct(ending_nav: float, contributed: float) -> float:
    if contributed <= 0:
        return 0.0
    return ((ending_nav / contributed) - 1.0) * 100.0


def compute_annualized_return_pct(total_return_pct: float, months: int) -> float:
    if months <= 0:
        return 0.0
    total_multiple = 1.0 + (total_return_pct / 100.0)
    if total_multiple <= 0:
        return -100.0
    years = months / 12.0
    if years <= 0:
        return 0.0
    return ((total_multiple ** (1.0 / years)) - 1.0) * 100.0


def compute_volatility_pct(monthly_returns: list[float]) -> float:
    if len(monthly_returns) < 2:
        return 0.0
    mean_ret = sum(monthly_returns) / len(monthly_returns)
    variance = sum((r - mean_ret) ** 2 for r in monthly_returns) / len(monthly_returns)
    monthly_vol = math.sqrt(variance)
    annualized_vol = monthly_vol * math.sqrt(12.0)
    return annualized_vol * 100.0


def compute_max_drawdown_pct(nav_path: list[float]) -> float:
    if not nav_path:
        return 0.0
    peak = nav_path[0]
    max_dd = 0.0
    for nav in nav_path:
        if nav > peak:
            peak = nav
        if peak <= 0:
            continue
        dd = (nav / peak) - 1.0
        if dd < max_dd:
            max_dd = dd
    return max_dd * 100.0
