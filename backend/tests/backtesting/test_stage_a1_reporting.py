from __future__ import annotations

from datetime import date

from piios_backend.backtesting.models import FactorSnapshot, ForwardReturnPoint, HorizonSummary, MonthlyResult, PortfolioMembership
from piios_backend.backtesting.runner import StageA1BacktestRunner


def _monthly_result(
    as_of: date,
    *,
    ic20: float,
    ic60: float,
    spread20: float,
    spread60: float,
    top20_20d: float,
    top20_60d: float,
    net20: float,
    net60: float,
) -> MonthlyResult:
    factor_rows = [
        FactorSnapshot(ticker="A.NS", as_of=as_of, eligibility="ELIGIBLE", reason=None, return_6m_pct=10.0, return_12m_pct=12.0, realized_volatility=0.1, price_risk_signal_score=1.0),
        FactorSnapshot(ticker="B.NS", as_of=as_of, eligibility="ELIGIBLE", reason=None, return_6m_pct=8.0, return_12m_pct=9.0, realized_volatility=0.2, price_risk_signal_score=0.5),
        FactorSnapshot(ticker="C.NS", as_of=as_of, eligibility="ELIGIBLE", reason=None, return_6m_pct=-2.0, return_12m_pct=-3.0, realized_volatility=0.4, price_risk_signal_score=-0.5),
    ]
    memberships = [
        PortfolioMembership(ticker="A.NS", rank=1, decile=10, top10=True, top20=True, top_decile=True, bottom_decile=False),
        PortfolioMembership(ticker="B.NS", rank=2, decile=9, top10=True, top20=True, top_decile=False, bottom_decile=False),
        PortfolioMembership(ticker="C.NS", rank=3, decile=1, top10=False, top20=False, top_decile=False, bottom_decile=True),
    ]
    forward_rows = [
        ForwardReturnPoint(ticker="A.NS", as_of=as_of, horizon_days=20, gross_return=top20_20d, net_return=net20),
        ForwardReturnPoint(ticker="B.NS", as_of=as_of, horizon_days=20, gross_return=top20_20d, net_return=net20),
        ForwardReturnPoint(ticker="C.NS", as_of=as_of, horizon_days=20, gross_return=top20_20d - spread20, net_return=net20 - spread20),
        ForwardReturnPoint(ticker="A.NS", as_of=as_of, horizon_days=60, gross_return=top20_60d, net_return=net60),
        ForwardReturnPoint(ticker="B.NS", as_of=as_of, horizon_days=60, gross_return=top20_60d, net_return=net60),
        ForwardReturnPoint(ticker="C.NS", as_of=as_of, horizon_days=60, gross_return=top20_60d - spread60, net_return=net60 - spread60),
    ]
    return MonthlyResult(
        as_of=as_of,
        eligible_count=3,
        ineligible_count=0,
        eligibility_counts={"ELIGIBLE": 3},
        rank_ic_by_horizon={20: ic20, 60: ic60},
        memberships=memberships,
        factor_rows=factor_rows,
        forward_rows=forward_rows,
    )


def _summaries(*, mean_ic_20: float, mean_ic_60: float, ci20_lower: float, ci60_lower: float, spread20: float, spread60: float, top20_20d: float, top20_60d: float, net20: float, net60: float) -> list[HorizonSummary]:
    return [
        HorizonSummary(horizon_days=5, mean_ic=0.0, median_ic=0.0, ic_std=0.0, ic_positive_month_pct=0.0, ic_count=1, ic_ci_90=None, top_decile_return=0.0, bottom_decile_return=0.0, top_minus_bottom_spread=0.0, spread_ci_90=None, top20_excess_return=0.0, top20_net_excess_return=0.0, top20_excess_ci_90=None),
        HorizonSummary(horizon_days=20, mean_ic=mean_ic_20, median_ic=0.0, ic_std=0.0, ic_positive_month_pct=0.0, ic_count=1, ic_ci_90=type("CI", (), {"lower": ci20_lower, "upper": 1.0})(), top_decile_return=0.0, bottom_decile_return=0.0, top_minus_bottom_spread=spread20, spread_ci_90=None, top20_excess_return=top20_20d, top20_net_excess_return=net20, top20_excess_ci_90=None),
        HorizonSummary(horizon_days=60, mean_ic=mean_ic_60, median_ic=0.0, ic_std=0.0, ic_positive_month_pct=0.0, ic_count=1, ic_ci_90=type("CI", (), {"lower": ci60_lower, "upper": 1.0})(), top_decile_return=0.0, bottom_decile_return=0.0, top_minus_bottom_spread=spread60, spread_ci_90=None, top20_excess_return=top20_60d, top20_net_excess_return=net60, top20_excess_ci_90=None),
        HorizonSummary(horizon_days=120, mean_ic=0.0, median_ic=0.0, ic_std=0.0, ic_positive_month_pct=0.0, ic_count=1, ic_ci_90=None, top_decile_return=0.0, bottom_decile_return=0.0, top_minus_bottom_spread=0.0, spread_ci_90=None, top20_excess_return=0.0, top20_net_excess_return=0.0, top20_excess_ci_90=None),
    ]


def test_signal_state_requires_all_has_edge_checks() -> None:
    runner = StageA1BacktestRunner()
    year_diag = {
        "best_year_share_of_total_positive_excess_60d": 0.25,
        "best_year_removed_positive": True,
    }
    naive = [{"horizon_days": 20, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 60, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 120, "excess_vs_eligible_universe_net": 0.0}]
    checks = runner._build_signal_checks(_summaries(mean_ic_20=0.05, mean_ic_60=0.06, ci20_lower=0.01, ci60_lower=0.02, spread20=0.02, spread60=0.03, top20_20d=0.01, top20_60d=0.02, net20=0.005, net60=0.01), year_diag, naive)
    assert checks["FINAL_STATE"] == "PRICE_SIGNAL_HAS_EDGE"
    assert checks["IC_POSITIVE"] is True
    assert checks["IC_CI_PASS"] is True
    assert checks["TOP_BOTTOM_PASS"] is True
    assert checks["TOP20_20D_PASS"] is True
    assert checks["TOP20_60D_PASS"] is True
    assert checks["NET_COST_PASS"] is True
    assert checks["NOT_SINGLE_YEAR_DRIVEN"] is True


def test_signal_state_fails_when_20d_top20_fails() -> None:
    runner = StageA1BacktestRunner()
    year_diag = {"best_year_share_of_total_positive_excess_60d": 0.25, "best_year_removed_positive": True}
    naive = [{"horizon_days": 20, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 60, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 120, "excess_vs_eligible_universe_net": 0.0}]
    checks = runner._build_signal_checks(_summaries(mean_ic_20=0.05, mean_ic_60=0.06, ci20_lower=0.01, ci60_lower=0.02, spread20=0.02, spread60=0.03, top20_20d=-0.01, top20_60d=0.02, net20=0.005, net60=0.01), year_diag, naive)
    assert checks["FINAL_STATE"] != "PRICE_SIGNAL_HAS_EDGE"
    assert checks["TOP20_20D_PASS"] is False


def test_signal_state_fails_when_60d_top20_fails() -> None:
    runner = StageA1BacktestRunner()
    year_diag = {"best_year_share_of_total_positive_excess_60d": 0.25, "best_year_removed_positive": True}
    naive = [{"horizon_days": 20, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 60, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 120, "excess_vs_eligible_universe_net": 0.0}]
    checks = runner._build_signal_checks(_summaries(mean_ic_20=0.05, mean_ic_60=0.06, ci20_lower=0.01, ci60_lower=0.02, spread20=0.02, spread60=0.03, top20_20d=0.01, top20_60d=-0.02, net20=0.005, net60=0.01), year_diag, naive)
    assert checks["FINAL_STATE"] != "PRICE_SIGNAL_HAS_EDGE"
    assert checks["TOP20_60D_PASS"] is False


def test_signal_state_fails_when_ci_condition_fails() -> None:
    runner = StageA1BacktestRunner()
    year_diag = {"best_year_share_of_total_positive_excess_60d": 0.25, "best_year_removed_positive": True}
    naive = [{"horizon_days": 20, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 60, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 120, "excess_vs_eligible_universe_net": 0.0}]
    checks = runner._build_signal_checks(_summaries(mean_ic_20=0.05, mean_ic_60=0.06, ci20_lower=-0.01, ci60_lower=-0.02, spread20=0.02, spread60=0.03, top20_20d=0.01, top20_60d=0.02, net20=0.005, net60=0.01), year_diag, naive)
    assert checks["FINAL_STATE"] != "PRICE_SIGNAL_HAS_EDGE"
    assert checks["IC_CI_PASS"] is False


def test_signal_state_fails_when_net_cost_condition_fails() -> None:
    runner = StageA1BacktestRunner()
    year_diag = {"best_year_share_of_total_positive_excess_60d": 0.25, "best_year_removed_positive": True}
    naive = [{"horizon_days": 20, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 60, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 120, "excess_vs_eligible_universe_net": 0.0}]
    checks = runner._build_signal_checks(_summaries(mean_ic_20=0.05, mean_ic_60=0.06, ci20_lower=0.01, ci60_lower=0.02, spread20=0.02, spread60=0.03, top20_20d=0.01, top20_60d=0.02, net20=-0.001, net60=0.01), year_diag, naive)
    assert checks["FINAL_STATE"] != "PRICE_SIGNAL_HAS_EDGE"
    assert checks["NET_COST_PASS"] is False


def test_signal_state_fails_when_one_year_drives_result() -> None:
    runner = StageA1BacktestRunner()
    year_diag = {"best_year_share_of_total_positive_excess_60d": 0.75, "best_year_removed_positive": False}
    naive = [{"horizon_days": 20, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 60, "excess_vs_eligible_universe_net": 0.0}, {"horizon_days": 120, "excess_vs_eligible_universe_net": 0.0}]
    checks = runner._build_signal_checks(_summaries(mean_ic_20=0.05, mean_ic_60=0.06, ci20_lower=0.01, ci60_lower=0.02, spread20=0.02, spread60=0.03, top20_20d=0.01, top20_60d=0.02, net20=0.005, net60=0.01), year_diag, naive)
    assert checks["FINAL_STATE"] != "PRICE_SIGNAL_HAS_EDGE"
    assert checks["NOT_SINGLE_YEAR_DRIVEN"] is False


def test_naive_benchmark_uses_only_t_data_for_selection() -> None:
    runner = StageA1BacktestRunner()
    as_of = date(2024, 1, 31)
    monthly = _monthly_result(as_of, ic20=0.05, ic60=0.06, spread20=0.02, spread60=0.03, top20_20d=0.01, top20_60d=0.02, net20=0.005, net60=0.01)
    # Future return values change, but the selection rule only uses factor rows at T.
    monthly.forward_rows = [
        ForwardReturnPoint(ticker="A.NS", as_of=as_of, horizon_days=20, gross_return=10.0, net_return=9.9),
        ForwardReturnPoint(ticker="B.NS", as_of=as_of, horizon_days=20, gross_return=-10.0, net_return=-10.1),
        ForwardReturnPoint(ticker="C.NS", as_of=as_of, horizon_days=20, gross_return=0.0, net_return=0.0),
    ]
    monthly2 = _monthly_result(as_of, ic20=0.05, ic60=0.06, spread20=0.02, spread60=0.03, top20_20d=0.01, top20_60d=0.02, net20=0.005, net60=0.01)
    monthly2.forward_rows = [
        ForwardReturnPoint(ticker="A.NS", as_of=as_of, horizon_days=20, gross_return=-999.0, net_return=-999.0),
        ForwardReturnPoint(ticker="B.NS", as_of=as_of, horizon_days=20, gross_return=999.0, net_return=999.0),
        ForwardReturnPoint(ticker="C.NS", as_of=as_of, horizon_days=20, gross_return=0.0, net_return=0.0),
    ]
    rows1 = runner._build_naive_benchmark([monthly])
    rows2 = runner._build_naive_benchmark([monthly2])
    assert rows1[0]["mean_selected_securities_per_month"] == rows2[0]["mean_selected_securities_per_month"]


def test_year_table_uses_all_year_labels_present_in_monthly_results() -> None:
    runner = StageA1BacktestRunner()
    today_year = date.today().year
    months = [
        _monthly_result(date(2018, 1, 31), ic20=0.01, ic60=0.02, spread20=0.01, spread60=0.02, top20_20d=0.01, top20_60d=0.02, net20=0.01, net60=0.02),
        _monthly_result(date(2019, 1, 31), ic20=0.01, ic60=0.02, spread20=0.01, spread60=0.02, top20_20d=0.01, top20_60d=0.02, net20=0.01, net60=0.02),
        _monthly_result(date(2020, 1, 31), ic20=0.01, ic60=0.02, spread20=0.01, spread60=0.02, top20_20d=0.01, top20_60d=0.02, net20=0.01, net60=0.02),
        _monthly_result(date(2021, 1, 31), ic20=0.01, ic60=0.02, spread20=0.01, spread60=0.02, top20_20d=0.01, top20_60d=0.02, net20=0.01, net60=0.02),
        _monthly_result(date(today_year, 1, 31), ic20=0.01, ic60=0.02, spread20=0.01, spread60=0.02, top20_20d=0.01, top20_60d=0.02, net20=0.01, net60=0.02),
    ]
    year_rows, diagnostics = runner._build_year_table(months)
    labels = {row["calendar_year"] for row in year_rows}
    expected = {"2018", "2019", "2020", "2021", f"{today_year} YTD"}
    assert labels == expected
    assert set(diagnostics["year_labels_in_scope"]) == expected
    assert diagnostics["best_year"] is not None
