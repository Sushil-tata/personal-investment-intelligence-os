import uuid

import pandas as pd
import streamlit as st

from lib import api_client as api
from lib import components as ui

st.set_page_config(page_title="PIIOS — Decisions", layout="wide")
ui.inject_base_styles()
ui.page_header("Decisions", "Human decision capture on real Wave 2B Recommendation Proposal Versions.")

ui.pipeline_flow([("Recommendation Proposal", False), ("Human Decision", False), ("Future Execution", True)])
st.caption("A decision is never a trade, order, or execution instruction. Future Execution is not available — "
           "PIIOS remains advisory-only.")

DECISION_TYPE_LABELS = {
    "ACCEPT": "Accept",
    "REJECT": "Reject",
    "MODIFIED": "Modify",
    "OVERRIDDEN": "Override",
    "DEFERRED": "Defer",
    "REQUEST_RESEARCH": "Request Further Research",
}
DECISION_MEANING_LABELS = {**DECISION_TYPE_LABELS, "ACCEPTED": "Accepted", "REJECTED": "Rejected"}

pv_id = ui.proposal_version_id_input()

if not pv_id:
    ui.empty_state_card("Enter a Proposal Version ID above to review and capture decisions.")
    st.stop()

pv_result = api.get_proposal_version(pv_id)
if not pv_result.ok:
    ui.error_state_card(f"Could not load proposal version '{pv_id}'. {pv_result.error}")
    ui.retry_button(key="retry_pv_decisions")
    st.stop()

pv = pv_result.data

ui.section_header("Proposal Snapshot")
ui.kpi_row([
    ui.KPIItem("Proposal ID", pv.proposal_id),
    ui.KPIItem("Proposal Version", ui.proposal_version_label(pv.proposal_version_id, pv.version_number)),
    ui.KPIItem("Proposed Action", pv.action),
    ui.KPIItem("Confidence", f"{pv.authoritative_confidence:.2f}"),
])

# Flash message pattern: a successful submission calls st.rerun() so the
# Latest Decision / History sections below reflect the just-captured
# decision. st.rerun() aborts the current script run immediately, so the
# success message must be stashed in session_state and rendered here, on
# the fresh run, rather than inline where it was produced.
_flash = st.session_state.pop("piios_decision_flash", None)
if _flash:
    if _flash["kind"] == "success":
        st.success(_flash["message"])
    else:
        st.info(_flash["message"])

ui.section_header("Latest Decision")
latest_result = api.get_latest_decision_for_proposal_version(pv_id)


def _render_decision_row(d, is_latest: bool) -> dict:
    meaning = DECISION_MEANING_LABELS.get(d.decision_meaning, d.decision_meaning)
    return {
        "Latest": "⭐" if is_latest else "",
        "Decision ID": d.decision_id,
        "Decision Meaning": meaning,
        "State": d.state,
        "Reviewer": d.decided_by or "—",
        "Timestamp": d.decided_at,
        "Reason Code": d.reason_code,
    }


latest_decision = None
if latest_result.ok:
    latest_decision = latest_result.data
    if latest_decision is None:
        ui.empty_state_card("No human decision has been recorded for this proposal version yet.")
    else:
        row = _render_decision_row(latest_decision, True)
        st.dataframe(pd.DataFrame([row]), use_container_width=True, hide_index=True)
        if latest_decision.reason_text:
            st.caption(f"Reason detail: {latest_decision.reason_text}")
else:
    ui.error_state_card(f"Could not load the latest decision. {latest_result.error}")

ui.section_header("Full Decision History", "Immutable — a correction is always a new decision record, never an edit of a prior one.")
history_result = api.list_decisions_for_proposal_version(pv_id)


def _history(data):
    if not data:
        ui.empty_state_card("No decisions recorded yet for this proposal version.")
        return
    latest_id = latest_decision.decision_id if latest_decision else None
    rows = [_render_decision_row(d, d.decision_id == latest_id) for d in data]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(f"{len(data)} decision(s) on record. Immutable history — no decision here can be edited or deleted.")


ui.render(history_result, _history)

st.divider()
ui.section_header("Record a Decision")

if "piios_decision_client_request_id" not in st.session_state:
    st.session_state["piios_decision_client_request_id"] = str(uuid.uuid4())
if "piios_last_decision_id" not in st.session_state:
    st.session_state["piios_last_decision_id"] = None

with st.form(key=f"decision_form_{pv_id}"):
    decision_type = st.selectbox(
        "Decision", list(DECISION_TYPE_LABELS.keys()),
        format_func=lambda k: DECISION_TYPE_LABELS[k],
    )
    reviewer = st.text_input("Reviewer (your name)")
    reason_code = st.text_input("Reason code (optional)",
                                 help="If left blank for Request Further Research, the backend fills in "
                                      "REQUEST_RESEARCH automatically.")
    reason_text = st.text_area("Reason detail (optional)")

    st.markdown("**Reject-only fields**")
    preferred_alt = st.text_input("Preferred alternative target key", disabled=decision_type != "REJECT",
                                   help="Only applies to Reject decisions.")

    st.markdown("**Modify-only fields**")
    is_modify = decision_type == "MODIFIED"
    modified_action = st.text_input("Modified action", disabled=not is_modify)
    modified_action_note = st.text_input("Modified action note", disabled=not is_modify)
    mc1, mc2 = st.columns(2)
    with mc1:
        modified_action_min = st.number_input("Modified action min weight", value=0.0, disabled=not is_modify)
        modified_position_min = st.number_input("Modified position min weight", value=0.0, disabled=not is_modify)
    with mc2:
        modified_action_max = st.number_input("Modified action max weight", value=0.0, disabled=not is_modify)
        modified_position_max = st.number_input("Modified position max weight", value=0.0, disabled=not is_modify)

    submitted = st.form_submit_button("Submit decision")

if submitted:
    if not reviewer:
        ui.error_state_card("Reviewer is required before a decision can be recorded.")
    else:
        result = api.capture_decision(
            proposal_version_id=pv_id,
            decision_type=decision_type,
            reviewer=reviewer,
            reason_code=reason_code or None,
            reason_text=reason_text or None,
            preferred_alternative_target_key=preferred_alt if decision_type == "REJECT" and preferred_alt else None,
            modified_action=modified_action if is_modify and modified_action else None,
            modified_action_note=modified_action_note if is_modify and modified_action_note else None,
            modified_action_min_weight=modified_action_min if is_modify else None,
            modified_action_max_weight=modified_action_max if is_modify else None,
            modified_position_min_weight=modified_position_min if is_modify else None,
            modified_position_max_weight=modified_position_max if is_modify else None,
            client_request_id=st.session_state["piios_decision_client_request_id"],
        )
        if result.ok:
            was_duplicate = st.session_state["piios_last_decision_id"] == result.data.decision_id
            if was_duplicate:
                st.session_state["piios_decision_flash"] = {
                    "kind": "info",
                    "message": f"This decision was already recorded (idempotent request) — decision_id "
                               f"`{result.data.decision_id}` was returned, no duplicate was created.",
                }
            else:
                meaning = DECISION_MEANING_LABELS.get(result.data.decision_meaning, result.data.decision_meaning)
                st.session_state["piios_decision_flash"] = {
                    "kind": "success",
                    "message": f"Decision recorded: {meaning} (decision_id `{result.data.decision_id}`).",
                }
                st.session_state["piios_last_decision_id"] = result.data.decision_id
                st.session_state["piios_decision_client_request_id"] = str(uuid.uuid4())
            st.rerun()
        else:
            ui.error_state_card(f"Decision was not saved. {result.error}")

st.caption("Resubmitting the form without changes reuses the same idempotency key, so it will never create a "
           "duplicate decision — the backend returns the existing record instead.")

st.divider()
ui.api_gap_notice(
    "There is no list/discovery endpoint for proposals or proposal versions — this page only works against an "
    "already-known Proposal Version ID. See dashboard/FRONTEND_INTEGRATION_NOTES.md."
)
