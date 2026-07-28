import streamlit as st

from lib import api_client as api
from lib import components as ui

st.set_page_config(page_title="PIIOS — Decisions", layout="wide")
ui.inject_base_styles()
ui.page_header("Decisions", "Human decision capture on Recommendation Proposals.")

ui.pipeline_flow([("Recommendation Proposal", False), ("Human Decision", False), ("Future Execution", True)])
st.caption("A decision is never a trade. PIIOS remains advisory-only and has no execution capability — the "
           "final pipeline step above is permanently disabled.")

STATUS_OPTIONS = ["DRAFT", "RESEARCHED", "RISK_CHECKED", "PENDING_REVIEW", "APPROVED", "ARCHIVED"]
STATUS_MEANING = {
    "DRAFT": "Proposal generated, not yet reviewed by any human.",
    "RESEARCHED": "Supporting research has been attached or reviewed.",
    "RISK_CHECKED": "Reviewed against portfolio risk/IPS constraints.",
    "PENDING_REVIEW": "Awaiting an explicit human accept/reject decision.",
    "APPROVED": "A human has approved this proposal for the advisory record.",
    "ARCHIVED": "Rejected, superseded, or otherwise closed out.",
}

recos = api.get_recommendation_queue()


def _decision_ui(data):
    if not data:
        ui.empty_state_card("No recommendations are currently awaiting review.")
        return

    options = {f"{r.ticker} — {r.status} (id {r.recommendation_id})": r for r in data}
    choice = st.selectbox("Select a recommendation proposal", list(options.keys()))
    reco = options[choice]

    ui.section_header("Proposal")
    ui.recommendation_card(reco.ticker, reco.status, reco.confidence_score, reco.portfolio_fit_score, reco.bull_case)

    ui.section_header("Decision Status & Meaning")
    st.write(f"Current status: {ui.status_badge(reco.status)}")
    st.caption(STATUS_MEANING.get(reco.status, "—"))

    ui.section_header("Reviewer")
    ui.metric_tile("Approved By", reco.approved_by or "—")

    ui.section_header("Timeline")
    ui.decision_timeline([
        ui.TimelineEvent("Proposal created", reco.created_at),
        ui.TimelineEvent("Proposal last updated", reco.updated_at),
        ui.TimelineEvent("Human decision recorded here", None, f"Reviewer: {reco.approved_by or 'pending'}"),
        ui.TimelineEvent("Trade execution", None, "Not available — advisory-only product", future=True),
    ])

    ui.section_header("Record a Decision")
    with st.form(key=f"decision_form_{reco.recommendation_id}"):
        new_status = st.selectbox("Decision status (maps to the backend's recommendation status field)",
                                   STATUS_OPTIONS,
                                   index=STATUS_OPTIONS.index(reco.status) if reco.status in STATUS_OPTIONS else 0)
        st.caption(STATUS_MEANING.get(new_status, ""))
        reviewer = st.text_input("Reviewer (your name)")
        st.text_area("Rationale / override reason (for your own records)", disabled=True,
                      help="Not supported by the backend yet. Nothing typed here is saved.")
        st.number_input("Position size actually approved (for your own records)", min_value=0.0, disabled=True,
                         help="Not supported by the backend yet. Nothing typed here is saved.")
        submitted = st.form_submit_button("Submit decision")

    if submitted:
        result = api.update_recommendation_status(reco.recommendation_id, new_status, reviewer or None)
        if result.ok:
            st.success(f"Status updated to {new_status} for {reco.ticker}. Reviewer recorded as "
                       f"approved_by='{reviewer or None}'. Rerun the page to see the updated queue.")
        else:
            ui.error_state_card(f"Decision was not saved: {result.error}")

    ui.section_header("Audit History")
    ui.disabled_card("Immutable decision history", "The backend persists only the current status/approver — "
                      "not a full, versioned, immutable history of every decision made on this proposal.")

    ui.section_header("Diagnostic Summary")
    ui.disabled_card("Decision diagnostics", "Diagnostics such as time-to-decision, reviewer workload, or "
                      "decisions overridden after risk checks are not computed by the backend yet.")


ui.render(recos, _decision_ui)

st.divider()
ui.api_gap_notice(
    "The backend exposes a single generic status field plus an optional approver name — that is all a "
    "decision can persist today. Distinct decision types (accept / partially accept / reject / defer / "
    "request further research / override), a captured rationale or override reason, a specific approved "
    "position size, a proposal-version-linked decision, and an immutable decision audit trail are not yet "
    "available. See dashboard/API_CONTRACT_REQUESTS.md for the concrete contract this page needs."
)
