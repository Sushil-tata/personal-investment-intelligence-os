import streamlit as st

from lib import api_client as api
from lib import components as ui

st.set_page_config(page_title="PIIOS — Risk", layout="wide")
ui.inject_base_styles()
ui.page_header("Risk Console")

st.caption("All figures below are rendered exactly as returned by the backend, or are a direct comparison "
           "between two real backend values. The frontend performs no risk modelling of its own.")

risk = api.get_risk_limits()
holdings = api.get_holdings()

tabs = st.tabs([
    "Portfolio Limits", "Exposure", "Concentration", "Liquidity", "Currency",
    "Drawdown", "Tracking Error", "VaR", "Stress Testing",
])

with tabs[0]:
    ui.section_header("Portfolio Limits", "Static advisory position-limit thresholds configured in the backend.")

    def _limits(data):
        ui.kpi_row([
            ui.KPIItem("Max Position %", f"{data.get('max_position_pct')}%"),
            ui.KPIItem("Max Tactical %", f"{data.get('max_tactical_pct')}%"),
            ui.KPIItem("Max Single Ticker %", f"{data.get('max_single_ticker_pct')}%"),
        ])

    ui.render(risk, _limits)

with tabs[1]:
    ui.section_header("Exposure", "Current largest single-position exposure vs. the configured limit.")

    def _exposure(risk_data, holding_data):
        total = sum(h.market_value for h in holding_data)
        if total <= 0:
            ui.empty_state_card("No holdings to evaluate exposure against.")
            return
        largest = max(holding_data, key=lambda h: h.market_value)
        actual_pct = largest.market_value / total * 100
        limit_pct = risk_data.get("max_single_ticker_pct")
        breach = limit_pct is not None and actual_pct > limit_pct
        ui.kpi_row([
            ui.KPIItem("Largest Single Position", largest.ticker),
            ui.KPIItem("Actual %", f"{actual_pct:.1f}%"),
            ui.KPIItem("Limit %", f"{limit_pct}%" if limit_pct is not None else "—"),
        ])
        if breach:
            ui.error_state_card(f"{largest.ticker} exceeds the configured max single-ticker limit "
                                 f"({actual_pct:.1f}% > {limit_pct}%).")
        else:
            st.success("Largest position is within the configured single-ticker limit.")

    if risk.ok and holdings.ok:
        _exposure(risk.data, holdings.data)
    elif not risk.ok:
        ui.error_state_card(f"Could not load risk limits: {risk.error}")
    else:
        ui.error_state_card(f"Could not load holdings: {holdings.error}")

with tabs[2]:
    ui.section_header("Concentration", "Advisory limit breach check across all holdings, largest to smallest.")

    def _concentration(risk_data, holding_data):
        total = sum(h.market_value for h in holding_data)
        limit_pct = risk_data.get("max_single_ticker_pct")
        if total <= 0 or limit_pct is None:
            ui.empty_state_card("Insufficient data to compute concentration checks.")
            return
        breaches = [h for h in holding_data if h.market_value / total * 100 > limit_pct]
        if breaches:
            for h in sorted(breaches, key=lambda h: h.market_value, reverse=True):
                pct = h.market_value / total * 100
                ui.governance_issue_card(h.ticker, "HIGH", "LIMIT_BREACH",
                                          f"{pct:.1f}% of portfolio vs. {limit_pct}% limit")
        else:
            st.success("No single position exceeds the configured concentration limit.")

    if risk.ok and holdings.ok:
        _concentration(risk.data, holdings.data)
    else:
        ui.empty_state_card("Requires both risk limits and holdings to be available.")

with tabs[3]:
    ui.section_header("Liquidity")
    ui.disabled_card("Liquidity risk", "No liquidity classification (e.g. days-to-liquidate, ADV-based sizing) "
                      "is exposed by the backend.")

with tabs[4]:
    ui.section_header("Currency", "Real currency exposure from the backend's currency-exposure endpoint.")
    currency = api.get_currency_exposure()

    def _currency(data):
        labels = [i.currency for i in data.items]
        values = [i.percentage for i in data.items]
        col1, col2 = st.columns([1, 1])
        with col1:
            ui.allocation_donut(labels, values, title="Currency Exposure")
        with col2:
            for item in sorted(data.items, key=lambda i: i.percentage, reverse=True):
                ui.portfolio_allocation_card("Currency", item.currency, item.market_value, item.percentage)

    ui.render(currency, _currency)

with tabs[5]:
    ui.section_header("Drawdown")
    ui.disabled_card("Drawdown", "Historical or current drawdown figures are not computed or exposed by the "
                      "backend on this branch.")

with tabs[6]:
    ui.section_header("Tracking Error")
    ui.disabled_card("Tracking error", "No benchmark or tracking-error data is exposed by the backend.")

with tabs[7]:
    ui.section_header("Value at Risk (VaR)")
    ui.disabled_card("VaR / Expected Shortfall", "No VaR or Expected Shortfall model output is exposed by the "
                      "backend. This screen intentionally does not estimate these figures in the frontend.")

with tabs[8]:
    ui.section_header("Stress Testing")
    ui.disabled_card("Stress test scenarios", "No stress-test scenario results are exposed by the backend.")

st.divider()
ui.api_gap_notice(
    "The backend's /risk endpoint returns only three static position-limit percentages. Volatility, drawdown, "
    "beta, correlation, MCTR/CCTR, VaR, Expected Shortfall, tracking error, liquidity classification, and "
    "stress-test results are not computed or exposed anywhere in the backend on this branch. Exposure and "
    "Concentration above compare real holdings data against the real configured limit — they do not model "
    "risk. See dashboard/API_CONTRACT_REQUESTS.md for the endpoints needed to populate the disabled tabs."
)
