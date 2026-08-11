from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import json
from statistics import median
from collections import defaultdict

import pandas as pd

from piios_backend.backtesting.data import (
    freeze_price_history,
    latest_complete_month_date,
    load_india_universe,
    monthly_ranking_dates,
)
from piios_backend.backtesting.metrics import (
    approx_effective_sample_size,
    bootstrap_ci_90,
    hit_rate,
    safe_mean,
    safe_median,
    safe_std,
)
from piios_backend.backtesting.models import FactorSnapshot, ForwardReturnPoint, HorizonSummary, MonthlyResult, PortfolioMembership
from piios_backend.backtesting.price_factor_engine import (
    PriceRiskFactorEngine,
    group_mean,
    liquidity_tx_cost_rate,
    membership_sets,
    row_by_ticker,
    spearman_rank_ic,
)


@dataclass(frozen=True)
class StageA1Config:
    start_date: date = date(2016, 1, 1)
    end_date: date = date.today()
    min_months: int = 36
    horizons: tuple[int, ...] = (5, 20, 60, 120)
    seed: int = 42
    bootstrap_iterations: int = 2000
    output_root: str = "backend/runtime/stage_a1"


class StageA1BacktestRunner:
    def __init__(self, config: StageA1Config | None = None) -> None:
        self.config = config or StageA1Config()
        self.engine = PriceRiskFactorEngine()

    def run(self) -> dict:
        tickers = load_india_universe()
        history = freeze_price_history(
            tickers,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
        )
        frames = history.by_ticker

        if not frames:
            raise RuntimeError("No ticker histories were retrieved for Stage A1")

        for ticker, frame in frames.items():
            frame.attrs["ticker"] = ticker

        all_dates = sorted({ts for frame in frames.values() for ts in frame.index})
        calendar = pd.DatetimeIndex(all_dates)
        if len(calendar) == 0:
            raise RuntimeError("No calendar dates available from frozen histories")

        last_complete = latest_complete_month_date(calendar, now=date.today())
        ranking_end = min(last_complete, self.config.end_date)
        ranking_dates = monthly_ranking_dates(calendar, self.config.start_date, ranking_end)

        monthly_results: list[MonthlyResult] = []
        for as_of in ranking_dates:
            snapshots = self.engine.factor_snapshots_at(as_of, frames)
            scored = self.engine.score_cross_section(snapshots)
            memberships = self.engine.build_memberships(scored)

            eligibility_counts: dict[str, int] = {}
            for row in scored:
                eligibility_counts[row.eligibility] = eligibility_counts.get(row.eligibility, 0) + 1

            forward_rows = []
            rank_ic_by_horizon: dict[int, float | None] = {}
            by_ticker = row_by_ticker(scored)
            members = membership_sets(memberships)

            for horizon in self.config.horizons:
                pairs: list[tuple[float, float]] = []
                for ticker, frame in frames.items():
                    point = self.engine.forward_return(
                        frame,
                        as_of,
                        horizon,
                        tx_cost_rate=liquidity_tx_cost_rate(
                            by_ticker.get(ticker).liquidity_status if ticker in by_ticker else "UNAVAILABLE",
                            by_ticker.get(ticker).liquidity_score if ticker in by_ticker else None,
                        ),
                    )
                    forward_rows.append(point)
                    row = by_ticker.get(ticker)
                    if row and isinstance(row.price_risk_signal_score, (int, float)) and isinstance(point.gross_return, (int, float)):
                        pairs.append((float(row.price_risk_signal_score), float(point.gross_return)))
                rank_ic_by_horizon[horizon] = spearman_rank_ic(pairs)

            monthly_results.append(
                MonthlyResult(
                    as_of=as_of,
                    eligible_count=eligibility_counts.get("ELIGIBLE", 0),
                    ineligible_count=sum(v for k, v in eligibility_counts.items() if k != "ELIGIBLE"),
                    eligibility_counts=eligibility_counts,
                    rank_ic_by_horizon=rank_ic_by_horizon,
                    memberships=memberships,
                    factor_rows=scored,
                    forward_rows=forward_rows,
                )
            )

        summaries = self._build_horizon_summaries(monthly_results)
        year_table, year_diagnostics = self._build_year_table(monthly_results)
        naive_benchmark = self._build_naive_benchmark(monthly_results)
        signal_checks = self._build_signal_checks(summaries, year_diagnostics, naive_benchmark)
        regime = self._regime_breakdown(monthly_results)
        diagnostics = self._diagnostics(monthly_results)
        signal_state = signal_checks["FINAL_STATE"]

        payload = {
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "start_date": self.config.start_date.isoformat(),
                "end_date": self.config.end_date.isoformat(),
                "min_months": self.config.min_months,
                "horizons": list(self.config.horizons),
                "seed": self.config.seed,
                "bootstrap_iterations": self.config.bootstrap_iterations,
            },
            "universe": {
                "ticker_count": len(tickers),
                "retrieved_count": len(history.by_ticker),
                "failure_count": len(history.failures),
                "provider": history.provider,
                "retrieval_timestamp": history.retrieval_timestamp,
            },
            "survivorship_bias_present": True,
            "first_ranking_date": monthly_results[0].as_of.isoformat() if monthly_results else None,
            "last_ranking_date": monthly_results[-1].as_of.isoformat() if monthly_results else None,
            "ranking_month_count": len(monthly_results),
            "signal_state": signal_state,
            "signal_checks": signal_checks,
            "year_table": year_table,
            "year_diagnostics": year_diagnostics,
            "naive_benchmark": naive_benchmark,
            "horizon_summaries": [asdict(s) for s in summaries],
            "regime_summaries": regime,
            "diagnostics": diagnostics,
            "history_failures": history.failures,
        }

        self._write_artifacts(payload, monthly_results)
        return payload

    def replay_from_artifacts(self, *, artifact_root: str | Path | None = None) -> dict:
        root = Path(artifact_root or self.config.output_root)
        factor_path = root / "factor_snapshots.csv"
        rank_path = root / "monthly_ranks.csv"
        forward_path = root / "forward_returns.csv"
        if not factor_path.exists() or not rank_path.exists() or not forward_path.exists():
            raise FileNotFoundError("Missing Stage A1 frozen CSV artifacts for replay")

        factor_df = pd.read_csv(factor_path)
        rank_df = pd.read_csv(rank_path)
        forward_df = pd.read_csv(forward_path)
        monthly_results = self._monthly_results_from_frames(factor_df, rank_df, forward_df)
        summaries = self._build_horizon_summaries(monthly_results)
        year_table, year_diagnostics = self._build_year_table(monthly_results)
        naive_benchmark = self._build_naive_benchmark(monthly_results)
        signal_checks = self._build_signal_checks(summaries, year_diagnostics, naive_benchmark)
        regime = self._regime_breakdown(monthly_results)
        diagnostics = self._diagnostics(monthly_results)
        payload = {
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "start_date": self.config.start_date.isoformat(),
                "end_date": self.config.end_date.isoformat(),
                "min_months": self.config.min_months,
                "horizons": list(self.config.horizons),
                "seed": self.config.seed,
                "bootstrap_iterations": self.config.bootstrap_iterations,
            },
            "survivorship_bias_present": True,
            "first_ranking_date": monthly_results[0].as_of.isoformat() if monthly_results else None,
            "last_ranking_date": monthly_results[-1].as_of.isoformat() if monthly_results else None,
            "ranking_month_count": len(monthly_results),
            "signal_state": signal_checks["FINAL_STATE"],
            "signal_checks": signal_checks,
            "year_table": year_table,
            "year_diagnostics": year_diagnostics,
            "naive_benchmark": naive_benchmark,
            "horizon_summaries": [asdict(s) for s in summaries],
            "regime_summaries": regime,
            "diagnostics": diagnostics,
            "history_failures": {},
            "replay_mode": True,
        }
        self._write_artifacts(payload, monthly_results)
        return payload

    def _build_horizon_summaries(self, monthly_results: list[MonthlyResult]) -> list[HorizonSummary]:
        summaries: list[HorizonSummary] = []
        for horizon in self.config.horizons:
            ics = [m.rank_ic_by_horizon.get(horizon) for m in monthly_results]
            usable_ics = [float(v) for v in ics if isinstance(v, (int, float))]

            top_decile_returns: list[float | None] = []
            bottom_decile_returns: list[float | None] = []
            spreads: list[float | None] = []
            top20_excess: list[float | None] = []
            top20_net_excess: list[float | None] = []

            for m in monthly_results:
                members = membership_sets(m.memberships)
                benchmark_all = members["full"]
                top_decile = members["top_decile"]
                bottom_decile = members["bottom_decile"]
                top20 = members["top20"]

                bench = group_mean(m.forward_rows, benchmark_all, horizon)
                topd = group_mean(m.forward_rows, top_decile, horizon)
                botd = group_mean(m.forward_rows, bottom_decile, horizon)
                top20_gross = group_mean(m.forward_rows, top20, horizon)
                top20_net = group_mean(m.forward_rows, top20, horizon, net=True)

                top_decile_returns.append(topd)
                bottom_decile_returns.append(botd)
                spreads.append((topd - botd) if isinstance(topd, (int, float)) and isinstance(botd, (int, float)) else None)
                top20_excess.append((top20_gross - bench) if isinstance(top20_gross, (int, float)) and isinstance(bench, (int, float)) else None)
                top20_net_excess.append((top20_net - bench) if isinstance(top20_net, (int, float)) and isinstance(bench, (int, float)) else None)

            summary = HorizonSummary(
                horizon_days=horizon,
                mean_ic=safe_mean(ics),
                median_ic=safe_median(ics),
                ic_std=safe_std(ics),
                ic_positive_month_pct=hit_rate(ics),
                ic_count=len(usable_ics),
                ic_ci_90=bootstrap_ci_90(
                    ics,
                    seed=self.config.seed + horizon,
                    iterations=self.config.bootstrap_iterations,
                    block_size=max(1, int(round(horizon / 20))),
                ),
                top_decile_return=safe_mean(top_decile_returns),
                bottom_decile_return=safe_mean(bottom_decile_returns),
                top_minus_bottom_spread=safe_mean(spreads),
                spread_ci_90=bootstrap_ci_90(
                    spreads,
                    seed=(self.config.seed * 3) + horizon,
                    iterations=self.config.bootstrap_iterations,
                    block_size=max(1, int(round(horizon / 20))),
                ),
                top20_excess_return=safe_mean(top20_excess),
                top20_net_excess_return=safe_mean(top20_net_excess),
                top20_excess_ci_90=bootstrap_ci_90(
                    top20_excess,
                    seed=(self.config.seed * 5) + horizon,
                    iterations=self.config.bootstrap_iterations,
                    block_size=max(1, int(round(horizon / 20))),
                ),
            )
            summaries.append(summary)
        return summaries

    def _regime_breakdown(self, monthly_results: list[MonthlyResult]) -> list[dict]:
        if not monthly_results:
            return []

        by_horizon: dict[int, dict[str, list[float | None]]] = {
            h: {"up": [], "down": [], "high": [], "low": []} for h in self.config.horizons
        }

        for m in monthly_results:
            members = membership_sets(m.memberships)
            benchmark_universe = members["full"]
            top20 = members["top20"]

            for horizon in self.config.horizons:
                bench = group_mean(m.forward_rows, benchmark_universe, horizon)
                top = group_mean(m.forward_rows, top20, horizon)
                excess = (top - bench) if isinstance(top, (int, float)) and isinstance(bench, (int, float)) else None
                if excess is None:
                    continue

                if isinstance(bench, (int, float)) and bench >= 0:
                    by_horizon[horizon]["up"].append(excess)
                else:
                    by_horizon[horizon]["down"].append(excess)

                row_map = row_by_ticker(m.factor_rows)
                vols = [row_map[t].realized_volatility for t in benchmark_universe if t in row_map and isinstance(row_map[t].realized_volatility, (int, float))]
                vol_median = median([float(v) for v in vols]) if vols else None
                if isinstance(vol_median, (int, float)) and vol_median >= 0.35:
                    by_horizon[horizon]["high"].append(excess)
                else:
                    by_horizon[horizon]["low"].append(excess)

        out = []
        for horizon, buckets in by_horizon.items():
            out.append(
                {
                    "horizon_days": horizon,
                    "up_market_excess": safe_mean(buckets["up"]),
                    "down_market_excess": safe_mean(buckets["down"]),
                    "high_vol_excess": safe_mean(buckets["high"]),
                    "low_vol_excess": safe_mean(buckets["low"]),
                    "up_n": len([v for v in buckets["up"] if isinstance(v, (int, float))]),
                    "down_n": len([v for v in buckets["down"] if isinstance(v, (int, float))]),
                    "high_n": len([v for v in buckets["high"] if isinstance(v, (int, float))]),
                    "low_n": len([v for v in buckets["low"] if isinstance(v, (int, float))]),
                }
            )
        return out

    def _diagnostics(self, monthly_results: list[MonthlyResult]) -> dict:
        if not monthly_results:
            return {
                "month_count": 0,
                "eligibility": {},
                "effective_sample_size": {},
            }

        eligibility_total: dict[str, int] = {}
        for m in monthly_results:
            for key, value in m.eligibility_counts.items():
                eligibility_total[key] = eligibility_total.get(key, 0) + int(value)

        effective_sample_size = {
            str(h): approx_effective_sample_size(len(monthly_results), h) for h in self.config.horizons
        }

        return {
            "month_count": len(monthly_results),
            "eligibility": eligibility_total,
            "effective_sample_size": effective_sample_size,
        }

    def _signal_state(self, summaries: list[HorizonSummary], month_count: int) -> str:
        if month_count < self.config.min_months:
            return "PRICE_SIGNAL_NO_EDGE"

        summary_20 = next((s for s in summaries if s.horizon_days == 20), None)
        summary_60 = next((s for s in summaries if s.horizon_days == 60), None)
        if summary_20 is None or summary_60 is None:
            return "PRICE_SIGNAL_NO_EDGE"

        ic20 = summary_20.mean_ic
        spread60 = summary_60.top_minus_bottom_spread
        net20 = summary_20.top20_net_excess_return

        has_edge = (
            isinstance(ic20, (int, float))
            and ic20 > 0.03
            and isinstance(spread60, (int, float))
            and spread60 > 0.01
            and isinstance(net20, (int, float))
            and net20 > 0.0
        )
        weak_edge = (
            isinstance(ic20, (int, float))
            and ic20 > 0.01
            and isinstance(spread60, (int, float))
            and spread60 > 0.0
        )

        if has_edge:
            return "PRICE_SIGNAL_HAS_EDGE"
        if weak_edge:
            return "PRICE_SIGNAL_WEAK"
        return "PRICE_SIGNAL_NO_EDGE"

    def _write_artifacts(self, payload: dict, monthly_results: list[MonthlyResult]) -> None:
        root = Path(self.config.output_root)
        root.mkdir(parents=True, exist_ok=True)

        summary_path = root / "stage_a1_summary.json"
        summary_path.write_text(json.dumps(payload, indent=2))

        factor_rows: list[dict] = []
        rank_rows: list[dict] = []
        forward_rows: list[dict] = []
        for m in monthly_results:
            for factor in m.factor_rows:
                factor_rows.append(
                    {
                        "as_of": m.as_of.isoformat(),
                        "ticker": factor.ticker,
                        "eligibility": factor.eligibility,
                        "reason": factor.reason,
                        "return_3m_pct": factor.return_3m_pct,
                        "return_6m_pct": factor.return_6m_pct,
                        "return_12m_pct": factor.return_12m_pct,
                        "realized_volatility": factor.realized_volatility,
                        "max_drawdown_pct": factor.max_drawdown_pct,
                        "distance_from_52w_high_pct": factor.distance_from_52w_high_pct,
                        "liquidity_score": factor.liquidity_score,
                        "liquidity_status": factor.liquidity_status,
                        "price_risk_signal_score": factor.price_risk_signal_score,
                    }
                )
            for member in m.memberships:
                rank_rows.append(
                    {
                        "as_of": m.as_of.isoformat(),
                        "ticker": member.ticker,
                        "rank": member.rank,
                        "decile": member.decile,
                        "top10": member.top10,
                        "top20": member.top20,
                        "top_decile": member.top_decile,
                        "bottom_decile": member.bottom_decile,
                    }
                )
            for point in m.forward_rows:
                forward_rows.append(
                    {
                        "as_of": point.as_of.isoformat(),
                        "ticker": point.ticker,
                        "horizon_days": point.horizon_days,
                        "gross_return": point.gross_return,
                        "net_return": point.net_return,
                    }
                )

        pd.DataFrame(factor_rows).to_csv(root / "factor_snapshots.csv", index=False)
        pd.DataFrame(rank_rows).to_csv(root / "monthly_ranks.csv", index=False)
        pd.DataFrame(forward_rows).to_csv(root / "forward_returns.csv", index=False)
        pd.DataFrame(payload["year_table"]).to_csv(root / "year_table.csv", index=False)
        pd.DataFrame(payload["naive_benchmark"]).to_csv(root / "naive_benchmark.csv", index=False)
        pd.DataFrame([payload["signal_checks"]]).to_csv(root / "signal_checks.csv", index=False)

    def _monthly_results_from_frames(self, factor_df: pd.DataFrame, rank_df: pd.DataFrame, forward_df: pd.DataFrame) -> list[MonthlyResult]:
        results: list[MonthlyResult] = []
        for as_of_str, rank_group in rank_df.groupby("as_of"):
            as_of = date.fromisoformat(as_of_str)
            factor_group = factor_df[factor_df["as_of"] == as_of_str]
            forward_group = forward_df[forward_df["as_of"] == as_of_str]
            factor_rows = [
                FactorSnapshot(
                    ticker=row["ticker"],
                    as_of=as_of,
                    eligibility=row["eligibility"],
                    reason=None if pd.isna(row.get("reason")) else row.get("reason"),
                    return_3m_pct=self._maybe_float(row.get("return_3m_pct")),
                    return_6m_pct=self._maybe_float(row.get("return_6m_pct")),
                    return_12m_pct=self._maybe_float(row.get("return_12m_pct")),
                    realized_volatility=self._maybe_float(row.get("realized_volatility")),
                    max_drawdown_pct=self._maybe_float(row.get("max_drawdown_pct")),
                    distance_from_52w_high_pct=self._maybe_float(row.get("distance_from_52w_high_pct")),
                    liquidity_score=self._maybe_float(row.get("liquidity_score")),
                    liquidity_status=str(row.get("liquidity_status") or "UNAVAILABLE"),
                    median_daily_value=self._maybe_float(row.get("median_daily_value")),
                    momentum_score=self._maybe_float(row.get("momentum_score")),
                    risk_score=self._maybe_float(row.get("risk_score")),
                    price_risk_signal_score=self._maybe_float(row.get("price_risk_signal_score")),
                )
                for _, row in factor_group.iterrows()
            ]
            memberships = [
                PortfolioMembership(
                    ticker=row["ticker"],
                    rank=int(row["rank"]),
                    decile=int(row["decile"]),
                    top10=bool(row["top10"]),
                    top20=bool(row["top20"]),
                    top_decile=bool(row["top_decile"]),
                    bottom_decile=bool(row["bottom_decile"]),
                )
                for _, row in rank_group.iterrows()
            ]
            forward_rows = [
                ForwardReturnPoint(
                    ticker=row["ticker"],
                    as_of=as_of,
                    horizon_days=int(row["horizon_days"]),
                    gross_return=self._maybe_float(row.get("gross_return")),
                    net_return=self._maybe_float(row.get("net_return")),
                )
                for _, row in forward_group.iterrows()
            ]
            eligibility_counts: dict[str, int] = {}
            for row in factor_rows:
                eligibility_counts[row.eligibility] = eligibility_counts.get(row.eligibility, 0) + 1
            rank_ic_by_horizon = {}
            for horizon in sorted({int(v) for v in forward_df["horizon_days"].dropna().unique()}):
                pairs: list[tuple[float, float]] = []
                factor_map = row_by_ticker(factor_rows)
                for point in forward_rows:
                    if point.horizon_days != horizon:
                        continue
                    factor_row = factor_map.get(point.ticker)
                    if factor_row and isinstance(factor_row.price_risk_signal_score, (int, float)) and isinstance(point.gross_return, (int, float)):
                        pairs.append((float(factor_row.price_risk_signal_score), float(point.gross_return)))
                rank_ic_by_horizon[horizon] = spearman_rank_ic(pairs)
            results.append(
                MonthlyResult(
                    as_of=as_of,
                    eligible_count=eligibility_counts.get("ELIGIBLE", 0),
                    ineligible_count=sum(v for k, v in eligibility_counts.items() if k != "ELIGIBLE"),
                    eligibility_counts=eligibility_counts,
                    rank_ic_by_horizon=rank_ic_by_horizon,
                    memberships=memberships,
                    factor_rows=factor_rows,
                    forward_rows=forward_rows,
                )
            )
        return results

    def _maybe_float(self, value: object) -> float | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _build_year_table(self, monthly_results: list[MonthlyResult]) -> tuple[list[dict], dict]:
        by_year: dict[str, list[MonthlyResult]] = defaultdict(list)
        for monthly in monthly_results:
            year = monthly.as_of.year
            label = f"{year} YTD" if year == date.today().year else str(year)
            by_year[label].append(monthly)

        ordered_labels = sorted(by_year.keys(), key=self._year_label_sort_key)
        year_rows: list[dict] = []

        all_positive_excess_60d: list[tuple[str, float]] = []
        year_totals_60d: dict[str, float] = {}
        for label, months in by_year.items():
            ics_20 = [m.rank_ic_by_horizon.get(20) for m in months if 20 in m.rank_ic_by_horizon]
            ics_60 = [m.rank_ic_by_horizon.get(60) for m in months if 60 in m.rank_ic_by_horizon]
            spread_60 = []
            top20_excess_60 = []
            top20_net_excess_60 = []
            positive_ic_months = 0

            for m in months:
                members = membership_sets(m.memberships)
                benchmark = members["full"]
                top20 = members["top20"]
                bench_60 = group_mean(m.forward_rows, benchmark, 60)
                top_60 = group_mean(m.forward_rows, top20, 60)
                top_net_60 = group_mean(m.forward_rows, top20, 60, net=True)
                bottom_60 = group_mean(m.forward_rows, members["bottom_decile"], 60)
                spread_60.append((top_60 - bottom_60) if isinstance(top_60, (int, float)) and isinstance(bottom_60, (int, float)) else None)
                top20_excess_60.append((top_60 - bench_60) if isinstance(top_60, (int, float)) and isinstance(bench_60, (int, float)) else None)
                top20_net_excess_60.append((top_net_60 - bench_60) if isinstance(top_net_60, (int, float)) and isinstance(bench_60, (int, float)) else None)

                ic20 = m.rank_ic_by_horizon.get(20)
                if isinstance(ic20, (int, float)) and ic20 > 0:
                    positive_ic_months += 1

            row = {
                "calendar_year": label,
                "ranking_months": len(months),
                "mean_ic_20d": safe_mean(ics_20),
                "mean_ic_60d": safe_mean(ics_60),
                "spread_60d": safe_mean(spread_60),
                "top20_excess_60d": safe_mean(top20_excess_60),
                "top20_net_excess_60d": safe_mean(top20_net_excess_60),
                "positive_ic_month_pct": (positive_ic_months / len(months)) if months else None,
            }
            year_rows.append(row)

            total_positive = sum(v for v in top20_excess_60 if isinstance(v, (int, float)) and v > 0)
            year_totals_60d[label] = total_positive
            all_positive_excess_60d.extend((label, v) for v in top20_excess_60 if isinstance(v, (int, float)) and v > 0)

        ordered_rows = [next((row for row in year_rows if row["calendar_year"] == label), None) for label in ordered_labels]
        ordered_rows = [row for row in ordered_rows if row is not None]
        total_positive_60d = sum(v for _, v in all_positive_excess_60d)
        best_year = max(year_totals_60d, key=year_totals_60d.get) if year_totals_60d else None
        best_year_positive = year_totals_60d.get(best_year, 0.0) if best_year else 0.0
        months_without_best_year = [month for label, months in by_year.items() if label != best_year for month in months]
        removed_year_excess = self._top20_excess_by_horizon(months_without_best_year, 60)
        diagnostics = {
            "year_labels_in_scope": ordered_labels,
            "best_year": best_year,
            "best_year_positive_excess_60d": best_year_positive,
            "best_year_share_of_total_positive_excess_60d": (best_year_positive / total_positive_60d) if total_positive_60d > 0 else None,
            "best_year_removed_60d_top20_excess": removed_year_excess,
            "best_year_removed_positive": removed_year_excess is not None and removed_year_excess > 0,
        }
        return ordered_rows, diagnostics

    def _year_label_sort_key(self, label: str) -> tuple[int, int]:
        # Format is either "YYYY" or "YYYY YTD".
        year_token = label.split(" ")[0]
        year_value = int(year_token)
        ytd_flag = 1 if label.endswith("YTD") else 0
        return (year_value, ytd_flag)

    def _top20_excess_by_horizon(self, monthly_results: list[MonthlyResult], horizon: int) -> float | None:
        values: list[float] = []
        for monthly in monthly_results:
            members = membership_sets(monthly.memberships)
            bench = group_mean(monthly.forward_rows, members["full"], horizon)
            top = group_mean(monthly.forward_rows, members["top20"], horizon)
            if isinstance(bench, (int, float)) and isinstance(top, (int, float)):
                values.append(float(top - bench))
        return safe_mean(values)

    def _build_naive_benchmark(self, monthly_results: list[MonthlyResult]) -> list[dict]:
        horizon_rows: list[dict] = []
        for horizon in self.config.horizons:
            gross_values: list[float | None] = []
            net_values: list[float | None] = []
            excess_gross_values: list[float | None] = []
            excess_net_values: list[float | None] = []
            hit_values: list[float | None] = []
            cohort_sizes: list[int] = []
            worst_cohort: float | None = None
            best_cohort: float | None = None

            for monthly in monthly_results:
                eligible = [row for row in monthly.factor_rows if row.eligibility == "ELIGIBLE"]
                vol_values = [float(row.realized_volatility) for row in eligible if isinstance(row.realized_volatility, (int, float))]
                vol_median = median(vol_values) if vol_values else None
                selected = [
                    row.ticker
                    for row in eligible
                    if isinstance(row.return_6m_pct, (int, float))
                    and isinstance(row.return_12m_pct, (int, float))
                    and isinstance(row.realized_volatility, (int, float))
                    and float(row.return_6m_pct) > 0
                    and float(row.return_12m_pct) > 0
                    and vol_median is not None
                    and float(row.realized_volatility) < float(vol_median)
                ]

                selected_set = set(selected)
                eligible_set = {row.ticker for row in eligible}
                bench_gross = group_mean(monthly.forward_rows, eligible_set, horizon)
                bench_net = group_mean(monthly.forward_rows, eligible_set, horizon, net=True)
                selected_gross = group_mean(monthly.forward_rows, selected_set, horizon)
                selected_net = group_mean(monthly.forward_rows, selected_set, horizon, net=True)

                gross_values.append(selected_gross)
                net_values.append(selected_net)
                excess_gross_values.append((selected_gross - bench_gross) if isinstance(selected_gross, (int, float)) and isinstance(bench_gross, (int, float)) else None)
                excess_net_values.append((selected_net - bench_net) if isinstance(selected_net, (int, float)) and isinstance(bench_net, (int, float)) else None)
                hit_values.append(1.0 if isinstance(selected_gross, (int, float)) and isinstance(bench_gross, (int, float)) and selected_gross > bench_gross else 0.0)
                cohort_sizes.append(len(selected_set))

                if isinstance(selected_gross, (int, float)):
                    worst_cohort = selected_gross if worst_cohort is None else min(worst_cohort, float(selected_gross))
                    best_cohort = selected_gross if best_cohort is None else max(best_cohort, float(selected_gross))

            horizon_rows.append(
                {
                    "horizon_days": horizon,
                    "mean_gross_return": safe_mean(gross_values),
                    "mean_net_return": safe_mean(net_values),
                    "excess_vs_eligible_universe_gross": safe_mean(excess_gross_values),
                    "excess_vs_eligible_universe_net": safe_mean(excess_net_values),
                    "hit_rate": safe_mean(hit_values),
                    "worst_cohort": worst_cohort,
                    "best_cohort": best_cohort,
                    "mean_selected_securities_per_month": safe_mean(cohort_sizes),
                }
            )
        return horizon_rows

    def _build_signal_checks(
        self,
        summaries: list[HorizonSummary],
        year_diagnostics: dict,
        naive_benchmark: list[dict],
    ) -> dict:
        summary_by_horizon = {summary.horizon_days: summary for summary in summaries}
        summary_5 = summary_by_horizon.get(5)
        summary_20 = summary_by_horizon.get(20)
        summary_60 = summary_by_horizon.get(60)
        summary_120 = summary_by_horizon.get(120)

        ic_positive = bool(
            summary_20 and summary_60 and isinstance(summary_20.mean_ic, (int, float)) and isinstance(summary_60.mean_ic, (int, float)) and summary_20.mean_ic > 0 and summary_60.mean_ic > 0
        )
        ic_ci_pass = bool(
            summary_20
            and summary_60
            and (
                (summary_20.ic_ci_90 is not None and summary_20.ic_ci_90.lower > 0)
                or (summary_60.ic_ci_90 is not None and summary_60.ic_ci_90.lower > 0)
            )
        )
        top_bottom_20 = bool(summary_20 and isinstance(summary_20.top_minus_bottom_spread, (int, float)) and summary_20.top_minus_bottom_spread > 0)
        top_bottom_60 = bool(summary_60 and isinstance(summary_60.top_minus_bottom_spread, (int, float)) and summary_60.top_minus_bottom_spread > 0)
        top_bottom_pass = top_bottom_20 and top_bottom_60
        top20_20d_pass = bool(summary_20 and isinstance(summary_20.top20_excess_return, (int, float)) and summary_20.top20_excess_return > 0)
        top20_60d_pass = bool(summary_60 and isinstance(summary_60.top20_excess_return, (int, float)) and summary_60.top20_excess_return > 0)
        net_cost_pass = bool(
            summary_20
            and summary_60
            and isinstance(summary_20.top20_net_excess_return, (int, float))
            and isinstance(summary_60.top20_net_excess_return, (int, float))
            and summary_20.top20_net_excess_return > 0
            and summary_60.top20_net_excess_return > 0
        )
        not_single_year_driven = bool(
            year_diagnostics.get("best_year_share_of_total_positive_excess_60d") is not None
            and year_diagnostics.get("best_year_share_of_total_positive_excess_60d") < 0.5
            and year_diagnostics.get("best_year_removed_positive")
        )

        has_edge = all([
            ic_positive,
            ic_ci_pass,
            top_bottom_pass,
            top20_20d_pass,
            top20_60d_pass,
            net_cost_pass,
            not_single_year_driven,
        ])
        weak_edge = any([
            ic_positive,
            ic_ci_pass,
            top_bottom_pass,
            top20_20d_pass,
            top20_60d_pass,
            net_cost_pass,
        ]) and not has_edge

        signal = "PRICE_SIGNAL_HAS_EDGE" if has_edge else "PRICE_SIGNAL_WEAK" if weak_edge else "PRICE_SIGNAL_NO_EDGE"
        naive_comparison = self._piios_vs_naive_by_horizon(summaries, naive_benchmark)
        return {
            "IC_POSITIVE": ic_positive,
            "IC_CI_PASS": ic_ci_pass,
            "TOP_BOTTOM_20D_PASS": top_bottom_20,
            "TOP_BOTTOM_60D_PASS": top_bottom_60,
            "TOP_BOTTOM_PASS": top_bottom_pass,
            "TOP20_20D_PASS": top20_20d_pass,
            "TOP20_60D_PASS": top20_60d_pass,
            "NET_COST_PASS": net_cost_pass,
            "NOT_SINGLE_YEAR_DRIVEN": not_single_year_driven,
            "SIGNAL_5D_MEAN_IC": summary_5.mean_ic if summary_5 else None,
            "SIGNAL_20D_MEAN_IC": summary_20.mean_ic if summary_20 else None,
            "SIGNAL_60D_MEAN_IC": summary_60.mean_ic if summary_60 else None,
            "SIGNAL_120D_MEAN_IC": summary_120.mean_ic if summary_120 else None,
            "FINAL_STATE": signal,
            "best_year_diagnostics": year_diagnostics,
            "piios_vs_naive_by_horizon": naive_comparison,
            "piios_vs_naive_statement": self._piios_vs_naive_statement(naive_comparison),
        }

    def _piios_vs_naive_by_horizon(self, summaries: list[HorizonSummary], naive_benchmark: list[dict]) -> list[dict]:
        summary_map = {summary.horizon_days: summary for summary in summaries}
        naive_map = {row["horizon_days"]: row for row in naive_benchmark}
        horizons = [5, 20, 60, 120]
        out: list[dict] = []
        for horizon in horizons:
            signal = summary_map.get(horizon)
            naive = naive_map.get(horizon)
            if not signal or not naive:
                continue
            signal_excess = signal.top20_net_excess_return if isinstance(signal.top20_net_excess_return, (int, float)) else None
            naive_excess = naive.get("excess_vs_eligible_universe_net")
            beats_naive = isinstance(signal_excess, (int, float)) and isinstance(naive_excess, (int, float)) and signal_excess > naive_excess
            out.append(
                {
                    "horizon_days": horizon,
                    "signal_top20_net_excess": signal_excess,
                    "naive_net_excess": naive_excess,
                    "beats_naive": beats_naive,
                }
            )
        return out

    def _piios_vs_naive_statement(self, comparisons: list[dict]) -> str:
        beats = [f"{row['horizon_days']}d" for row in comparisons if row.get("beats_naive") is True]
        underperforms = [f"{row['horizon_days']}d" for row in comparisons if row.get("beats_naive") is False]
        if not comparisons:
            return "No comparable horizons available"
        parts: list[str] = []
        if beats:
            parts.append("beats naive at " + "/".join(beats))
        if underperforms:
            parts.append("underperforms naive at " + "/".join(underperforms))
        return "; ".join(parts)
