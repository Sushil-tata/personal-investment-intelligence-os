import pandas as pd
import streamlit as st

from lib import api_client as api
from lib import ui

st.set_page_config(page_title="PIIOS — Investment Recommendations", layout="wide")
ui.page_header("Investment Recommendations", "Real cross-market ranking and allocation with explicit evidence coverage.")

st.subheader("WHAT SHOULD I DO WITH USD 5,000?")

controls = st.columns(4)
amount = controls[0].number_input("Investable amount (USD)", min_value=100.0, max_value=500000.0, value=5000.0, step=100.0)
mode = controls[1].selectbox("Market-data mode", options=["auto", "live", "cached", "development_seed"], index=0)
use_demo = controls[2].checkbox("Use deterministic demo portfolio", value=True)
snapshot = controls[3].text_input("Portfolio snapshot id (optional)", value="")
selected_markets = st.multiselect("Eligible markets", options=["US", "India", "Singapore"], default=["US", "India", "Singapore"])

if st.button("Generate Recommendation", type="primary"):
    result = api.generate_investment_recommendation(
        investable_amount=float(amount),
        market_data_mode=mode,
        use_demo_portfolio=use_demo,
        portfolio_snapshot_id=snapshot or None,
        base_currency="USD",
        eligible_markets=selected_markets,
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

funded = [r for r in data.recommendations if r.action in {"BUY", "ADD"} and r.proposed_allocation > 0]

summary = st.columns(4)
summary[0].metric("Funded Capital", f"USD {data.allocation_total:,.2f}")
summary[1].metric("Residual Cash", f"USD {float(data.residual_cash or 0.0):,.2f}")
summary[2].metric("Overall Confidence", f"{data.overall_confidence:.2f}")
summary[3].metric("Data Mode", data.market_data_mode)

st.caption(f"As of {data.as_of_timestamp} · input freshness {data.input_freshness} · allocation delta {data.allocation_difference:+.2f} USD")

if funded:
    funded_rows = []
    lookup = {x.get("ticker"): x for x in data.actionable_recommendations}
    for row in funded:
        order = lookup.get(row.ticker, {})
        funded_rows.append(
            {
                "Ticker": row.ticker,
                "Market": next((c.market for c in data.top_ranked_candidates if c.ticker == row.ticker), "n/a"),
                "Action": row.action,
                "USD Allocation": row.proposed_allocation,
                "Local Amount": order.get("allocation_local"),
                "Units": order.get("units"),
                "Price": next((c.current_price for c in data.top_ranked_candidates if c.ticker == row.ticker), None),
                "Confidence": row.confidence,
            }
        )
    st.dataframe(pd.DataFrame(funded_rows), use_container_width=True, hide_index=True)
else:
    st.info("No BUY/ADD recommendation met confidence and evidence thresholds. Retain cash until evidence improves.")

if data.universe_summary is not None:
    st.subheader("WHY THESE?")
    u = data.universe_summary
    cols = st.columns(4)
    cols[0].metric("Total Candidates", int(u.total_candidates))
    cols[1].metric("Eligible", int(u.eligible_candidates))
    cols[2].metric("Partial", int(u.partial_candidates))
    cols[3].metric("Ineligible", int(u.ineligible_candidates))

    market_rows = []
    for market, stats in (u.markets or {}).items():
        market_rows.append(
            {
                "Market": market,
                "Seed": stats.get("total_seed", 0),
                "Eligible": stats.get("eligible", 0),
                "Partial": stats.get("partial", 0),
                "Ineligible": stats.get("ineligible", 0),
            }
        )
    if market_rows:
        st.dataframe(pd.DataFrame(market_rows), use_container_width=True, hide_index=True)

if data.top_ranked_candidates:
    st.subheader("TOP 15 CONSIDERED")
    top_rows = []
    for c in data.top_ranked_candidates[:15]:
        top_rows.append(
            {
                "Rank": c.rank,
                "Market": c.market,
                "Ticker": c.ticker,
                "Company": c.company,
                "Action": c.action,
                "Quality": c.quality,
                "Growth": c.growth,
                "Valuation": c.valuation,
                "Momentum": c.momentum,
                "Risk": c.risk,
                "Attractiveness": c.security_attractiveness_score,
                "Suitability": c.portfolio_suitability_score,
                "Combined": c.combined_recommendation_score,
                "Confidence": c.confidence,
                "Coverage": c.evidence_coverage,
                "Currency": c.trading_currency,
                "Price": c.current_price,
            }
        )
    st.dataframe(pd.DataFrame(top_rows), use_container_width=True, hide_index=True)

st.subheader("Portfolio Observations")
for obs in data.portfolio_observations:
    sev = ui.severity_badge(obs.severity)
    st.write(f"{sev} **{obs.code}** — {obs.detail}")

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

if data.actionable_recommendations:
    st.subheader("Funded BUY/ADD Recommendations")
    st.dataframe(pd.DataFrame(data.actionable_recommendations), use_container_width=True, hide_index=True)

if data.portfolio_before is not None and data.portfolio_after is not None:
    st.subheader("PORTFOLIO BEFORE/AFTER")
    exposure_cols = st.columns(2)
    exposure_cols[0].metric("Before Total", f"{data.portfolio_before.base_currency} {data.portfolio_before.total_value:,.0f}")
    exposure_cols[1].metric("After Total", f"{data.portfolio_after.base_currency} {data.portfolio_after.total_value:,.0f}")

    before_country = pd.DataFrame(data.portfolio_before.country_exposure)
    after_country = pd.DataFrame(data.portfolio_after.country_exposure)
    if not before_country.empty:
        st.markdown("**Country Exposure (Before)**")
        st.dataframe(before_country, use_container_width=True, hide_index=True)
    if not after_country.empty:
        st.markdown("**Country Exposure (After)**")
        st.dataframe(after_country, use_container_width=True, hide_index=True)

if data.data_quality_summary is not None:
    st.subheader("DATA QUALITY")
    dq = data.data_quality_summary
    st.write(f"Providers: {', '.join(dq.providers) if dq.providers else 'n/a'}")
    st.write(f"Portfolio total mismatch: {'Yes' if dq.portfolio_total_mismatch else 'No'}")
    if dq.market_retrieval_stats:
        st.markdown("**Market Retrieval Statistics**")
        stats_rows = []
        for market, stat in dq.market_retrieval_stats.items():
            stats_rows.append({"Market": market, **stat})
        st.dataframe(pd.DataFrame(stats_rows), use_container_width=True, hide_index=True)
    if dq.fx_availability:
        st.markdown("**FX Availability**")
        fx_rows = []
        for pair, stat in dq.fx_availability.items():
            fx_rows.append({"Pair": pair, **stat})
        st.dataframe(pd.DataFrame(fx_rows), use_container_width=True, hide_index=True)
    if dq.excluded_securities:
        st.dataframe(pd.DataFrame(dq.excluded_securities[:20]), use_container_width=True, hide_index=True)

if data.sensitivity is not None and data.sensitivity.scenarios:
    st.subheader("Sensitivity")
    st.write(f"Classification: {data.sensitivity.classification}")
    st.dataframe(pd.DataFrame(data.sensitivity.scenarios), use_container_width=True, hide_index=True)

st.subheader("Warnings & Limitations")
st.warning("Advisory-only. No automatic trading, no broker integration, and human approval required.")
for limitation in data.limitations:
    st.write(f"{ui.severity_badge(limitation.severity)} **{limitation.code}** — {limitation.detail}")

if any(r.market_data_mode == "DEVELOPMENT_SEED" for r in data.recommendations if r.action in {"BUY", "ADD"}):
    st.warning("Seeded-data warning: at least one actionable recommendation uses DEVELOPMENT_SEED market inputs.")
if any(r.is_stale for r in data.recommendations if r.action in {"BUY", "ADD"}):
    st.warning("Stale-data warning: at least one actionable recommendation is based on stale/cached data.")

ui.advisory_banner()
