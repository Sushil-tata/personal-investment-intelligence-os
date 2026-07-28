import pandas as pd
import streamlit as st

from lib import api_client as api
from lib import ui

st.set_page_config(page_title="PIIOS — Rebalancing", layout="wide")
ui.page_header("Rebalancing")

ui.advisory_banner()
st.caption("All items below are advisory suggestions only. There is no broker connectivity and no trade "
           "execution anywhere in PIIOS.")

targets = api.get_portfolio_targets()
drift = api.get_portfolio_drift()

st.subheader("Policy Targets & Thresholds")


def _targets(data):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Targets**")
        st.json(data.targets)
    with c2:
        st.markdown("**Thresholds**")
        st.json(data.thresholds)


ui.render(targets, _targets)

st.divider()
st.subheader("Current Drift & Recommended Advisory Action")


def _drift_table(data):
    df = pd.DataFrame([{
        "Dimension": i.dimension, "Key": i.key, "Target %": i.target_percentage, "Actual %": i.actual_percentage,
        "Drift %": i.drift_percentage, "Drift Amount": i.drift_amount, "Severity": i.severity,
        "Recommended Action (advisory)": i.recommended_action,
    } for i in data.items])
    severities = sorted(df["Severity"].dropna().unique())
    severity_filter = st.multiselect("Severity", severities)
    filtered = df[df["Severity"].isin(severity_filter)] if severity_filter else df
    st.dataframe(filtered.sort_values("Drift %", key=abs, ascending=False), use_container_width=True, hide_index=True)
    st.caption(f"Generated at {data.generated_at}")


ui.render(drift, _drift_table)

st.divider()
ui.api_gap_notice(
    "The backend currently exposes drift-vs-target percentages and a free-text recommended action per "
    "dimension — it does not yet expose concrete proposed trade tickets (buy/sell instrument + quantity), "
    "cash impact, risk impact of the proposed rebalance, or tax estimates. Constraint-violation detail beyond "
    "the drift severity label is also not available. This page therefore stops at showing drift and the "
    "backend's own advisory-action text, rather than synthesizing trade tickets or tax figures in the "
    "frontend."
)
