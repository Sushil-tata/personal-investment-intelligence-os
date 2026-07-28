import streamlit as st

from lib import api_client as api
from lib import ui

st.set_page_config(page_title="PIIOS — Overview", layout="wide")
ui.page_header("Personal Investment Intelligence OS", "Overview — advisory-only and research-only. No execution capabilities.")

col1, col2, col3, col4 = st.columns(4)

net_worth = api.get_net_worth()
portfolio = api.get_portfolio()
drift = api.get_portfolio_drift()
reco_queue = api.get_recommendation_queue()
watchlist = api.get_watchlist()
ips = api.get_ips_constraints()

with col1:
    if net_worth.ok and not net_worth.is_empty:
        st.metric("Net Worth", f"${net_worth.data.net_worth:,.0f}")
    elif not net_worth.ok:
        st.metric("Net Worth", "—")
    else:
        st.metric("Net Worth", "$0")

with col2:
    if portfolio.ok and not portfolio.is_empty:
        total = sum(s.total_value for s in portfolio.data)
        st.metric("Total Portfolio Value", f"${total:,.0f}", help=f"Across {len(portfolio.data)} snapshot(s)")
    else:
        st.metric("Total Portfolio Value", "—")

with col3:
    if reco_queue.ok:
        st.metric("Recommendations Awaiting Review", len(reco_queue.data) if reco_queue.data else 0)
    else:
        st.metric("Recommendations Awaiting Review", "—")

with col4:
    if watchlist.ok:
        st.metric("Watchlist Ideas", len(watchlist.data) if watchlist.data else 0)
    else:
        st.metric("Watchlist Ideas", "—")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Net Worth Breakdown")
    def _net_worth_table(data):
        import pandas as pd
        st.dataframe(
            pd.DataFrame([{"Category": b.category, "Value": b.value} for b in data.breakdown]),
            use_container_width=True, hide_index=True,
        )
        st.caption(f"Total assets ${data.total_assets:,.0f} · total liabilities ${data.total_liabilities:,.0f}")
    ui.render(net_worth, _net_worth_table)

    st.subheader("Rebalancing Alerts")
    def _drift_alerts(data):
        high = [i for i in data.items if i.severity.upper() == "HIGH"]
        if not high:
            st.success("No high-severity drift detected.")
        else:
            for item in high[:5]:
                st.warning(f"**{item.dimension} / {item.key}** — drift {item.drift_percentage:+.1f}pp · {item.recommended_action}")
        st.caption("Full detail in Portfolio Drift Dashboard / Rebalancing.")
    ui.render(drift, _drift_alerts)

with right:
    st.subheader("Governance Signals")
    def _ips_table(data):
        breached = [c for c in data.constraints if not c.enabled or c.severity.upper() in ("HIGH", "CRITICAL")]
        st.write(f"{len(data.constraints)} IPS constraints tracked.")
        if breached:
            for c in breached[:5]:
                st.warning(f"**{c.name}** — {c.rule_type} threshold {c.threshold_value} ({ui.severity_badge(c.severity)})")
        else:
            st.success("No elevated-severity IPS constraints flagged.")
    ui.render(ips, _ips_table)
    ui.api_gap_notice(
        "A general-purpose governance backlog (replay mismatches, stale evidence, traceability gaps, "
        "overdue decision reviews) is not yet available from the backend on this branch. This card shows "
        "only what identity/IPS data currently exists."
    )

    st.subheader("Recommendations Snapshot")
    def _reco_table(data):
        if not data:
            st.info("No recommendations currently in the queue.")
            return
        for r in data[:5]:
            st.write(f"**{r.ticker}** — {ui.status_badge(r.status)} · confidence {r.confidence_score:.0f} · fit {r.portfolio_fit_score:.0f}")
        st.caption("Full detail in Recommendation Review. All items are proposals, not decisions or executions.")
    ui.render(reco_queue, _reco_table)

st.divider()
ui.advisory_banner()
