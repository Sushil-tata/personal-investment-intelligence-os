import pandas as pd
import streamlit as st

from lib import api_client as api
from lib import ui

st.set_page_config(page_title="PIIOS — Investment Recommendations", layout="wide")
ui.page_header("Investment Recommendations", "Deploy capital with transparent advisory-only rationale and guardrails.")

st.caption(
    "Question addressed: how to deploy USD 5,000 now given India concentration, existing US mega-cap exposure, "
    "a 10-15 year horizon, and a moderate-high risk profile."
)

controls = st.columns(4)
amount = controls[0].number_input("Investable amount (USD)", min_value=100.0, max_value=500000.0, value=5000.0, step=100.0)
mode = controls[1].selectbox("Market-data mode", options=["auto", "live", "cached", "development_seed"], index=0)
use_demo = controls[2].checkbox("Use deterministic demo portfolio", value=True)
snapshot = controls[3].text_input("Portfolio snapshot id (optional)", value="")

if st.button("Generate Recommendation", type="primary"):
    result = api.generate_investment_recommendation(
        investable_amount=float(amount),
        market_data_mode=mode,
        use_demo_portfolio=use_demo,
        portfolio_snapshot_id=snapshot or None,
    )
    st.session_state["wave3_recommendation_result"] = result

result = st.session_state.get("wave3_recommendation_result")
if result is None:
    st.info("Generate a recommendation to view summary, allocations, rationale, risks, and limitations.")
    st.stop()

if not result.ok:
    st.error(result.error)
    st.stop()

data = result.data

summary = st.columns(5)
summary[0].metric("Deploy Amount", f"${data.investable_amount:,.0f}")
summary[1].metric("Allocation Total", f"${data.allocation_total:,.0f}")
summary[2].metric("Overall Confidence", f"{data.overall_confidence:.2f}")
summary[3].metric("Provider / Mode", f"{data.market_data_provider} / {data.market_data_mode}")
summary[4].metric("Status", data.status)

st.caption(f"As of {data.as_of_timestamp} · input freshness {data.input_freshness} · allocation delta {data.allocation_difference:+.2f} USD")

st.subheader("Portfolio Observations")
for obs in data.portfolio_observations:
    sev = ui.severity_badge(obs.severity)
    st.write(f"{sev} **{obs.code}** — {obs.detail}")

st.subheader("Allocation")
allocation_rows = []
for row in data.recommendations:
    allocation_rows.append(
        {
            "Action": row.action,
            "Ticker": row.ticker,
            "Instrument": row.instrument_name,
            "Current Value": row.current_value,
            "Proposed Allocation": row.proposed_allocation,
            "Proposed Total": row.proposed_total_value,
            "Post Weight": row.post_weight,
            "Score": row.score,
            "Confidence": row.confidence,
            "Role": row.portfolio_role,
            "Mode": row.market_data_mode,
        }
    )

allocation_df = pd.DataFrame(allocation_rows)
if not allocation_df.empty:
    st.dataframe(allocation_df, use_container_width=True, hide_index=True)
    st.caption(
        f"Actionable allocation total: ${allocation_df[allocation_df['Action'].isin(['BUY', 'ADD'])]['Proposed Allocation'].sum():,.2f}"
    )

st.subheader("Recommendation Detail")
for row in data.recommendations:
    with st.expander(f"{row.ticker} · {row.action} · score {row.score:.1f} · confidence {row.confidence:.2f}"):
        st.write(f"**Role:** {row.portfolio_role}")
        st.write(f"**Why:** {row.rationale}")
        st.write(f"**Diversification contribution:** {row.diversification_contribution}")
        st.write(f"**Market data:** {row.market_data_provider} / {row.market_data_mode}")
        st.write(f"**Market data as-of:** {row.market_data_as_of or 'unavailable'}")
        if row.fallback_reason:
            st.warning(f"Fallback reason: {row.fallback_reason}")
        if row.unavailable_inputs:
            st.info("Unavailable inputs: " + ", ".join(row.unavailable_inputs))
        st.markdown("**Risks**")
        for risk in row.risks:
            st.write(f"- {risk}")
        st.markdown("**Conditions that can change this recommendation**")
        for item in row.conditions_to_change:
            st.write(f"- {item}")
        st.markdown("**Evidence**")
        for ev in row.evidence:
            st.write(f"- {ev.code}: {ev.detail} ({ev.source})")

st.subheader("Warnings & Limitations")
st.warning("Advisory-only. No automatic trading, no broker integration, and human approval required.")
for limitation in data.limitations:
    st.write(f"{ui.severity_badge(limitation.severity)} **{limitation.code}** — {limitation.detail}")

if any(r.market_data_mode == "DEVELOPMENT_SEED" for r in data.recommendations if r.action in {"BUY", "ADD"}):
    st.warning("Seeded-data warning: at least one actionable recommendation uses DEVELOPMENT_SEED market inputs.")
if any(r.is_stale for r in data.recommendations if r.action in {"BUY", "ADD"}):
    st.warning("Stale-data warning: at least one actionable recommendation is based on stale/cached data.")

ui.advisory_banner()
