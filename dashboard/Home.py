import streamlit as st

from lib import api_client as api
from lib import components as ui

st.set_page_config(page_title="PIIOS — Overview", layout="wide")
ui.inject_base_styles()
ui.page_header("Personal Investment Intelligence OS", "CIO Overview — advisory-only and research-only. No execution capabilities.")

net_worth = api.get_net_worth()
portfolio = api.get_portfolio()
drift = api.get_portfolio_drift()
reco_queue = api.get_recommendation_queue()
recos_all = api.get_recommendations()
watchlist = api.get_watchlist()
ips = api.get_ips_constraints()
tactical = api.get_tactical_signals()
issues = api.get_resolution_issues(limit=200)
allocation = api.get_allocation(dimension="asset_class")

# --- Row 1: top-line KPIs -------------------------------------------------
ui.section_header("Portfolio Snapshot")
r1 = st.columns(6)

with r1[0]:
    if net_worth.ok and not net_worth.is_empty:
        st.metric("Net Worth", f"${net_worth.data.net_worth:,.0f}")
    else:
        st.metric("Net Worth", "—")

with r1[1]:
    if portfolio.ok and not portfolio.is_empty:
        total = sum(s.total_value for s in portfolio.data)
        st.metric("Portfolio Value", f"${total:,.0f}")
    else:
        st.metric("Portfolio Value", "—")

with r1[2]:
    st.metric("Today's Change", "—", help="No daily/historical P&L endpoint exists in the backend yet.")

with r1[3]:
    st.metric("Recommendations", len(reco_queue.data) if reco_queue.ok and reco_queue.data else 0)

with r1[4]:
    gov_count = (len(issues.data) if issues.ok and issues.data else 0)
    st.metric("Governance Issues", gov_count, help="Unresolved identity-resolution issues.")

with r1[5]:
    if ips.ok and not ips.is_empty:
        elevated = [c for c in ips.data.constraints if c.severity.upper() in ("HIGH", "CRITICAL")]
        st.metric("IPS Status", "⚠️ Attention" if elevated else "✅ Clear", help=f"{len(ips.data.constraints)} constraints tracked")
    else:
        st.metric("IPS Status", "—")

st.divider()

# --- Row 2: allocation / drift / watchlists / tactical --------------------
ui.section_header("Positioning")
r2 = st.columns(4)

with r2[0]:
    st.markdown("**Allocation (Asset Class)**")

    def _alloc(data):
        labels = [i.key for i in data.items]
        values = [i.percentage for i in data.items]
        ui.allocation_donut(labels, values)

    ui.render(allocation, _alloc)

with r2[1]:
    st.markdown("**Drift Alerts**")

    def _drift_alerts(data):
        high = [i for i in data.items if i.severity.upper() == "HIGH"]
        if not high:
            st.success("No high-severity drift detected.")
        else:
            for item in high[:4]:
                st.warning(f"**{item.dimension} / {item.key}** — {item.drift_percentage:+.1f}pp")
        st.caption("Full detail in Rebalancing.")

    ui.render(drift, _drift_alerts)

with r2[2]:
    st.markdown("**Watchlists**")

    def _watchlist(data):
        st.metric("Ideas Tracked", len(data))
        for w in data[:4]:
            st.write(f"- {w.ticker}: {w.note}")

    ui.render(watchlist, _watchlist)

with r2[3]:
    st.markdown("**Tactical Signals**")

    def _tactical(data):
        st.metric("Active Signals", len(data))
        for s in data[:4]:
            st.write(f"- {s.ticker}: {s.status}")

    ui.render(tactical, _tactical)

st.divider()

# --- Row 3: recommendation queue / recent decisions / governance queue ----
ui.section_header("Decision Workflow")
r3 = st.columns(3)

with r3[0]:
    st.markdown("**Recommendation Queue**")

    def _queue(data):
        if not data:
            st.info("No recommendations currently in the queue.")
            return
        for r in data[:5]:
            ui.recommendation_card(r.ticker, r.status, r.confidence_score, r.portfolio_fit_score, r.why_now)
        st.caption("Full detail in Recommendation Review. All items are proposals, not decisions or executions.")

    ui.render(reco_queue, _queue)

with r3[1]:
    st.markdown("**Recent Decisions**")

    def _recent_decisions(data):
        decided = sorted([r for r in data if r.status in ("APPROVED", "ARCHIVED")],
                          key=lambda r: r.updated_at, reverse=True)
        if not decided:
            st.info("No recommendations have reached a decided status yet.")
            return
        for r in decided[:5]:
            st.write(f"{ui.status_badge(r.status)} **{r.ticker}** — updated {r.updated_at}")
        st.caption("Approximated from recommendation status changes — the backend has no dedicated decision "
                   "log yet (see API_GAPS.md).")

    ui.render(recos_all, _recent_decisions)

with r3[2]:
    st.markdown("**Governance Queue**")

    def _gov_queue(data):
        if not data:
            st.success("No unresolved identity-resolution issues.")
            return
        for issue in data[:5]:
            ui.governance_issue_card(f"{issue.source_record_type} `{issue.source_record_id}`", "MEDIUM",
                                      issue.status, issue.reason)
        st.caption("Full governance detail in the Governance Console.")

    ui.render(issues, _gov_queue)

st.divider()
ui.advisory_banner()
