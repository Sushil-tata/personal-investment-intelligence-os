import streamlit as st

from lib import api_client as api
from lib import ui

st.set_page_config(page_title="PIIOS — Risk", layout="wide")
ui.page_header("Risk")

st.caption("All figures below are rendered exactly as returned by the backend. The frontend performs no risk "
           "calculations of its own.")

risk = api.get_risk_limits()


def _limits(data):
    cols = st.columns(3)
    cols[0].metric("Max Position %", f"{data.get('max_position_pct')}%")
    cols[1].metric("Max Tactical %", f"{data.get('max_tactical_pct')}%")
    cols[2].metric("Max Single Ticker %", f"{data.get('max_single_ticker_pct')}%")


ui.render(risk, _limits)

st.divider()
ui.api_gap_notice(
    "The backend's /risk endpoint currently returns only three static position-limit percentages. "
    "Volatility, drawdown, beta, correlation, marginal/component contribution to risk (MCTR/CCTR), "
    "Value-at-Risk, Expected Shortfall, and stress-test results are not computed or exposed by the backend "
    "on this branch. This screen intentionally does not calculate or display placeholder values for any of "
    "those metrics — per the frontend mandate, risk figures are rendered only from backend data, never "
    "derived in the UI."
)
