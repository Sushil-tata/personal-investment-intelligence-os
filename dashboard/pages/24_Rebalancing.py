import pandas as pd
import streamlit as st

from lib import api_client as api
from lib import components as ui

st.set_page_config(page_title="PIIOS — Rebalancing", layout="wide")
ui.inject_base_styles()
ui.page_header("Rebalancing")

ui.advisory_banner()
st.caption("All items below are advisory suggestions only. There is no broker connectivity and no trade "
           "execution anywhere in PIIOS.")

ui.pipeline_flow([
    ("Current Allocation", False), ("Target Allocation", False), ("Drift", False),
    ("Recommended Actions", False), ("Future Trade List", True), ("Future Tax Impact", True),
])

targets = api.get_portfolio_targets()
drift = api.get_portfolio_drift()

ui.section_header("Current Allocation → Target Allocation", "Policy targets and thresholds configured in the backend.")


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
ui.section_header("Drift", "Current drift of actual allocation away from policy targets.")


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
    return df


ui.render(drift, _drift_table)

st.divider()
ui.section_header("Recommended Actions", "The backend's own free-text advisory action per dimension — nothing is synthesized here.")


def _actions(data):
    high = [i for i in data.items if i.severity.upper() == "HIGH"]
    if not high:
        st.success("No high-severity drift currently requires action.")
    else:
        for item in high:
            ui.governance_issue_card(f"{item.dimension} / {item.key}", item.severity, "ACTION_SUGGESTED",
                                      item.recommended_action)


ui.render(drift, _actions)

st.divider()
ui.section_header("Future Trade List")
ui.disabled_card("Concrete proposed trade tickets", "The backend does not expose specific instrument + "
                  "quantity trade proposals to close the drift above — only the free-text advisory action "
                  "per dimension shown above.")

ui.section_header("Future Tax Impact")
ui.disabled_card("Tax impact of rebalancing", "No tax-lot or cost-basis data is exposed by the backend, so no "
                  "tax-impact estimate can be shown.")

st.divider()
ui.api_gap_notice(
    "The backend currently exposes drift-vs-target percentages and a free-text advisory action per "
    "dimension. There are no concrete proposed trade tickets, no cash-impact figure, no risk-impact-of-"
    "rebalance figure, and no tax estimate. See dashboard/API_CONTRACT_REQUESTS.md for the endpoints needed."
)
