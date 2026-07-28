import streamlit as st

from lib import api_client as api
from lib import components as ui

st.set_page_config(page_title="PIIOS — Recommendation Review", layout="wide")
ui.inject_base_styles()
ui.page_header("Recommendation Review", "Investment memo view of a single Recommendation Proposal.")

st.info(
    "Every item on this page is a **Recommendation Proposal** — a model-generated, advisory suggestion. "
    "It becomes a **Human Decision** only after a reviewer acts on it (see the Decisions page), and PIIOS "
    "never executes trades — there is no broker connectivity anywhere in this system.",
    icon="ℹ️",
)

recos = api.get_recommendations()


def _render(data):
    tickers = sorted({r.ticker for r in data})
    statuses = sorted({r.status for r in data})
    cols = st.columns(2)
    ticker_filter = cols[0].multiselect("Ticker", tickers)
    status_filter = cols[1].multiselect("Status", statuses)
    filtered = [r for r in data if (not ticker_filter or r.ticker in ticker_filter)
                and (not status_filter or r.status in status_filter)]
    st.caption(f"Showing {len(filtered)} of {len(data)} recommendation proposals.")

    if not filtered:
        ui.empty_state_card("No recommendation proposals match the current filters.")
        return

    options = {f"{r.ticker} — {r.status} (id {r.recommendation_id})": r for r in filtered}
    choice = st.selectbox("Open a proposal", list(options.keys()))
    r = options[choice]

    ui.section_header("Executive Summary")
    ui.kpi_row([
        ui.KPIItem("Status", r.status),
        ui.KPIItem("Confidence", f"{r.confidence_score:.0f}/100"),
        ui.KPIItem("Portfolio Fit", f"{r.portfolio_fit_score:.0f}/100"),
        ui.KPIItem("Time Horizon", r.time_horizon),
    ])
    ui.recommendation_card(r.ticker, r.status, r.confidence_score, r.portfolio_fit_score, r.why_now)

    ui.section_header("Recommendation", "Advisory position-size suggestion and bucket placement.")
    c1, c2 = st.columns(2)
    with c1:
        ui.metric_tile("Portfolio Bucket", r.portfolio_bucket)
    with c2:
        ui.metric_tile("Position Size Suggestion (advisory)", r.position_size_suggestion)
    st.caption("No discrete buy/sell/hold action field exists on this model — the recommendation is expressed "
               "as narrative bull/bear case and an advisory sizing suggestion, not a coded action.")

    ui.section_header("Investment Thesis")
    tc1, tc2 = st.columns(2)
    with tc1:
        st.markdown("**Bull case**")
        st.write(r.bull_case)
        st.markdown("**Why now**")
        st.write(r.why_now)
    with tc2:
        st.markdown("**Bear case**")
        st.write(r.bear_case)
        st.markdown("**Why not now**")
        st.write(r.why_not_now)
    st.markdown("**Rationale**")
    st.write(r.rationale)

    ui.section_header("Supporting Claims")
    ui.disabled_card("Structured supporting claims", "The backend does not yet persist discrete, individually "
                      "scored claims for a recommendation — only the narrative bull/bear case above.")

    ui.section_header("Supporting Evidence")
    if r.source_documents or r.source_links:
        for doc in r.source_documents:
            ui.evidence_card(doc, r.data_source, r.data_freshness_timestamp, None, None)
        for link in r.source_links:
            ui.evidence_card(link, r.data_source, r.data_freshness_timestamp, None, link)
        st.caption("Per-item credibility scoring is only available on the separate Research Feed page, not at "
                   "the recommendation-evidence level.")
    else:
        ui.empty_state_card("No source documents or links attached to this proposal.")

    ui.section_header("Valuation Summary")
    ui.disabled_card("Valuation summary", "No valuation fields (fair value, target price, multiple analysis) "
                      "are exposed by the backend for recommendations today.")

    ui.section_header("Risk Summary")
    ui.metric_tile("Thesis Invalidation Trigger", r.thesis_invalidation_trigger)
    ui.disabled_card("Quantified risk impact", "Marginal/component risk contribution, VaR impact, and beta "
                      "impact of taking this position are not exposed by the backend. See the Risk Console "
                      "for the portfolio-level limits that do exist.")

    ui.section_header("Portfolio Impact")
    ui.disabled_card("Quantified portfolio impact", "A dollar or percentage portfolio-impact figure for "
                      "accepting this proposal is not exposed by the backend. Portfolio Fit Score (shown "
                      "above, 0-100) is the closest available signal today.")

    ui.section_header("Confidence")
    ui.confidence_breakdown_card(r.confidence_score)

    ui.section_header("Human Decision")
    ui.pipeline_flow([("Recommendation Proposal", False), ("Human Decision", False), ("Future Execution", True)])
    st.markdown(f"Current status: {ui.status_badge(r.status)}", unsafe_allow_html=True)
    st.write(f"Approved by: {r.approved_by or '—'}")
    st.caption("Use the Decisions page to record or change a human decision on this proposal.")

    ui.section_header("Audit Information")
    ac1, ac2 = st.columns(2)
    with ac1:
        ui.metric_tile("Recommendation ID", r.recommendation_id)
        ui.metric_tile("Model Version", r.model_version)
    with ac2:
        ui.metric_tile("Created", r.created_at, sublabel=f"Updated {r.updated_at}")
        ui.metric_tile("Data Freshness", r.data_freshness_timestamp, sublabel=f"Source: {r.data_source}")
    ui.disabled_card("Traceability & replay verification", "Trace-linked evidence, canonical input snapshots, "
                      "and replay-verification (PASS/FAIL) status are part of the Wave 2B decision-intelligence "
                      "engine, which is not yet merged into this branch.")


ui.render(recos, _render, empty_message="No recommendation proposals currently available.")

st.divider()
ui.api_gap_notice(
    "Structured supporting claims/evidence, a valuation summary object, quantified portfolio-impact and "
    "risk-impact figures, an explicit uncertainties list, traceability status, replay-verification status, "
    "and a proposal version number are not yet available on this branch. See dashboard/API_CONTRACT_REQUESTS.md "
    "for the concrete endpoint/DTO specification needed to close these gaps."
)
