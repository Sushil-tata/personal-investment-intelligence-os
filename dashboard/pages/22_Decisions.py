import streamlit as st

from lib import api_client as api
from lib import ui

st.set_page_config(page_title="PIIOS — Decisions", layout="wide")
ui.page_header("Decisions")

st.info(
    "This screen captures a **Human Decision** on a Recommendation Proposal. A decision is not a trade — "
    "PIIOS remains advisory-only and has no execution capability.",
    icon="ℹ️",
)

STATUS_OPTIONS = ["DRAFT", "RESEARCHED", "RISK_CHECKED", "PENDING_REVIEW", "APPROVED", "ARCHIVED"]

recos = api.get_recommendation_queue()


def _decision_ui(data):
    if not data:
        st.info("No recommendations are currently awaiting review.")
        return

    options = {f"{r.ticker} — {ui.status_badge(r.status)} (id {r.recommendation_id})": r for r in data}
    choice = st.selectbox("Select a recommendation proposal", list(options.keys()))
    reco = options[choice]

    with st.expander("Proposal detail", expanded=True):
        st.write(f"**Bull case:** {reco.bull_case}")
        st.write(f"**Bear case:** {reco.bear_case}")
        st.write(f"**Position size suggestion:** {reco.position_size_suggestion}")
        st.write(f"**Confidence:** {reco.confidence_score:.0f} · **Portfolio fit:** {reco.portfolio_fit_score:.0f}")

    st.subheader("Record a decision")
    with st.form(key=f"decision_form_{reco.recommendation_id}"):
        new_status = st.selectbox("Decision status (maps to the backend's recommendation status field)", STATUS_OPTIONS,
                                   index=STATUS_OPTIONS.index(reco.status) if reco.status in STATUS_OPTIONS else 0)
        reviewer = st.text_input("Reviewer (your name)")
        st.text_area("Rationale / override reason (for your own records)", disabled=True,
                      help="Not supported by the backend yet — see the gap notice below. Nothing typed here is saved.")
        st.number_input("Position size actually approved (for your own records)", min_value=0.0, disabled=True,
                         help="Not supported by the backend yet — see the gap notice below. Nothing typed here is saved.")
        submitted = st.form_submit_button("Submit decision")

    if submitted:
        result = api.update_recommendation_status(reco.recommendation_id, new_status, reviewer or None)
        if result.ok:
            st.success(f"Status updated to {new_status} for {reco.ticker}. Reviewer recorded as approved_by="
                       f"'{reviewer or None}'. Rerun the page to see the updated queue.")
        else:
            st.error(f"Decision was not saved: {result.error}")


ui.render(recos, _decision_ui)

st.divider()
ui.api_gap_notice(
    "The backend exposes a single generic status field (`PATCH /recommendations/{id}/status`, values DRAFT / "
    "RESEARCHED / RISK_CHECKED / PENDING_REVIEW / APPROVED / ARCHIVED) plus an `approved_by` string — that is "
    "all a decision can persist today. There is no support yet for: accept-vs-partially-accept-vs-reject-vs-"
    "defer-vs-request-further-research as distinct decision types, a captured rationale or override reason, "
    "a specific approved position size, a linked proposal *version*, or an immutable decision history/audit "
    "trail. The disabled fields above are shown so the intended richer workflow is visible, but nothing typed "
    "into them is sent to the backend or persisted anywhere — that would mean inventing a substitute backend "
    "contract, which this frontend must not do."
)
