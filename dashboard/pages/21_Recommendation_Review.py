import streamlit as st

from lib import api_client as api
from lib import ui

st.set_page_config(page_title="PIIOS — Recommendation Review", layout="wide")
ui.page_header("Recommendation Review")

st.info(
    "This screen shows **Recommendation Proposals** only — model-generated, advisory suggestions. "
    "A proposal becomes a **Human Decision** only after a reviewer acts on it (see the Decisions page). "
    "Neither a proposal nor a decision ever executes a trade — PIIOS has no broker connectivity.",
    icon="ℹ️",
)

recos = api.get_recommendations()


def _list(data):
    tickers = sorted({r.ticker for r in data})
    statuses = sorted({r.status for r in data})
    cols = st.columns(2)
    ticker_filter = cols[0].multiselect("Ticker", tickers)
    status_filter = cols[1].multiselect("Status", statuses)

    filtered = [r for r in data if (not ticker_filter or r.ticker in ticker_filter)
                and (not status_filter or r.status in status_filter)]
    st.caption(f"Showing {len(filtered)} of {len(data)} recommendation proposals.")

    for r in filtered:
        with st.expander(f"{r.ticker} — {ui.status_badge(r.status)} · confidence {r.confidence_score:.0f} · portfolio fit {r.portfolio_fit_score:.0f}"):
            st.caption(f"Recommendation Proposal · id `{r.recommendation_id}` · bucket {r.portfolio_bucket} · "
                       f"model {r.model_version} · created {r.created_at} · updated {r.updated_at}")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Bull case**")
                st.write(r.bull_case)
                st.markdown("**Why now**")
                st.write(r.why_now)
            with c2:
                st.markdown("**Bear case**")
                st.write(r.bear_case)
                st.markdown("**Why not now**")
                st.write(r.why_not_now)
            st.markdown("**Thesis invalidation trigger**")
            st.write(r.thesis_invalidation_trigger)
            st.markdown("**Position size suggestion (advisory)**")
            st.write(f"{r.position_size_suggestion} · time horizon: {r.time_horizon}")
            st.markdown("**Rationale**")
            st.write(r.rationale)
            if r.source_links:
                st.markdown("**Sources**")
                for link in r.source_links:
                    st.write(f"- {link}")
            st.caption(f"Data freshness: {r.data_freshness_timestamp} · source: {r.data_source} · "
                       f"approved by: {r.approved_by or '—'}")


ui.render(recos, _list, empty_message="No recommendation proposals currently available.")

st.divider()
ui.api_gap_notice(
    "Structured supporting claims/evidence, a valuation summary object, quantified portfolio-impact and "
    "risk-impact figures, an explicit uncertainties list, traceability status, replay-verification status, "
    "and a proposal version number are part of the Wave 2B decision-intelligence work and are not yet merged "
    "into this branch. Only the fields above (bull/bear case, why-now/why-not-now, invalidation trigger, "
    "confidence, portfolio fit, rationale, sources) are backed by a real backend contract today."
)
