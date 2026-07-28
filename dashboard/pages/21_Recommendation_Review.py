import streamlit as st

from lib import api_client as api
from lib import components as ui

st.set_page_config(page_title="PIIOS — Recommendation Review", layout="wide")
ui.inject_base_styles()
ui.page_header("Recommendation Review", "Investment memo view of a real Wave 2B Recommendation Proposal Version.")

st.info(
    "Every item on this page is a **Recommendation Proposal** — a model-generated, advisory suggestion. "
    "It becomes a **Human Decision** only after a reviewer acts on it (see the Decisions page). "
    "**Future Execution** is not available — PIIOS has no broker connectivity anywhere in this system.",
    icon="ℹ️",
)
ui.pipeline_flow([("Recommendation Proposal", False), ("Human Decision", False), ("Future Execution", True)])

pv_id = ui.proposal_version_id_input()

if not pv_id:
    ui.empty_state_card("Enter a Proposal Version ID above to open its investment memo.")
    st.stop()

pv_result = api.get_proposal_version(pv_id)

if not pv_result.ok:
    ui.error_state_card(f"Could not load proposal version '{pv_id}'. {pv_result.error}")
    ui.retry_button(key="retry_pv")
    st.stop()

pv = pv_result.data
proposal_result = api.get_proposal(pv.proposal_id)

ui.section_header("Executive Summary")
ui.kpi_row([
    ui.KPIItem("Status", pv.status),
    ui.KPIItem("Proposed Action", pv.action),
    ui.KPIItem("Priority", f"{pv.priority_level} ({pv.priority_score:.2f})"),
    ui.KPIItem("Confidence", f"{pv.authoritative_confidence:.2f}"),
    ui.KPIItem("Human Review Required", "Yes" if pv.required_human_review else "No"),
])
if proposal_result.ok:
    st.caption(f"Target: {proposal_result.data.target_type} `{proposal_result.data.target_key}` · "
               f"scope: {proposal_result.data.scope} · proposal status: {proposal_result.data.status}")
else:
    ui.unavailable_state_card(f"Proposal-level detail unavailable: {proposal_result.error}")

ui.section_header("Recommendation", "The advisory recommendation itself — never a trade, order, or execution instruction.")
c1, c2 = st.columns(2)
with c1:
    ui.metric_tile("Advisory Recommendation", pv.action)
    ui.metric_tile("Action Note", pv.action_note or "Unavailable from current persisted data")
with c2:
    weight_range = (f"{pv.action_min_weight:.2f} – {pv.action_max_weight:.2f}"
                     if pv.action_min_weight is not None and pv.action_max_weight is not None
                     else "Unavailable from current persisted data")
    ui.metric_tile("Proposed Weight Range (advisory)", weight_range)

ui.section_header("Proposal Version")
pc1, pc2 = st.columns(2)
with pc1:
    ui.metric_tile("Proposal Version", ui.proposal_version_label(pv.proposal_version_id, pv.version_number))
    ui.metric_tile("Snapshot", pv.snapshot_id)
with pc2:
    ui.metric_tile("Created", pv.created_at)
    ui.metric_tile("Supersedes Version", pv.supersedes_version_id or "This is the first version")

ui.section_header("Investment Thesis")
ui.unavailable_state_card("Unavailable from current persisted data")
st.caption("The proposal-version detail links to a snapshot_id but the decision-contracts API does not expose "
           "a read endpoint for the underlying thesis narrative.")

ui.section_header("Supporting Claims")
ui.unavailable_state_card("Unavailable from current persisted data")

ui.section_header("Supporting Evidence")
ui.unavailable_state_card("Unavailable from current persisted data")

ui.section_header("Confidence", "Rendered exactly as returned — the frontend never recomputes confidence.")
confidence_result = api.get_confidence_diagnostic(pv_id)


def _confidence(data):
    if data.authoritative_confidence is not None:
        st.markdown(f"**Authoritative confidence:** {data.authoritative_confidence:.2f}")
    else:
        ui.unavailable_state_card("Unavailable from current persisted data")
    for comp in data.components:
        ui.confidence_component_card(comp.name, comp.value, comp.status, comp.source, comp.explanation)
    if data.limitations:
        st.caption("Limitations: " + "; ".join(data.limitations))


ui.render(confidence_result, _confidence)

ui.section_header("Traceability")
traceability_result = api.get_traceability_diagnostic(pv_id)


def _traceability(data):
    st.markdown(f"**Overall status:** {ui.diagnostic_status_badge(data.overall_status)}  "
                f"**Severity:** {ui.diagnostic_severity_badge(data.severity)}", unsafe_allow_html=True)
    for check in data.checks:
        with st.expander(f"{check.code} — {check.status}"):
            st.markdown(f"{ui.diagnostic_status_badge(check.status)} {ui.diagnostic_severity_badge(check.severity)}",
                        unsafe_allow_html=True)
            st.write(check.message)
            if check.related_entity_id:
                st.caption(f"Related: {check.related_entity_type} `{check.related_entity_id}`")
            if check.remediation_hint:
                st.caption(f"Remediation: {check.remediation_hint}")
    return data


_traceability_data = None
if traceability_result.ok and not traceability_result.is_empty:
    _traceability_data = _traceability(traceability_result.data)
else:
    ui.render(traceability_result, _traceability, empty_message="No traceability checks recorded.")

ui.section_header("Replay", "Replay verification is surfaced as a traceability check, not a separate endpoint.")
_replay_check = None
if _traceability_data is not None:
    _replay_check = next((c for c in _traceability_data.checks if "REPLAY" in c.code.upper()), None)
if _replay_check is not None:
    st.markdown(f"{ui.diagnostic_status_badge(_replay_check.status)} {ui.diagnostic_severity_badge(_replay_check.severity)}",
                unsafe_allow_html=True)
    st.write(_replay_check.message)
else:
    ui.unavailable_state_card("Unavailable from current persisted data")

ui.section_header("Human Decision")
latest_result = api.get_latest_decision_for_proposal_version(pv_id)


def _latest(data):
    if data is None:
        ui.empty_state_card("No human decision has been recorded for this proposal version yet.")
        return
    label = "Request Further Research" if data.decision_meaning == "REQUEST_RESEARCH" else data.decision_meaning
    st.markdown(f"**Latest decision:** {label}")
    st.write(f"Reviewer: {data.decided_by or '—'} · Decided at: {data.decided_at}")
    st.write(f"Reason: {data.reason_code}" + (f" — {data.reason_text}" if data.reason_text else ""))


ui.render(latest_result, _latest, empty_message="No human decision has been recorded for this proposal version yet.")
st.caption("Full decision history and the decision-capture form are on the Decisions page.")

ui.section_header("Governance Flags")
backlog_result = api.get_governance_backlog(pv_id)


def _backlog(data):
    if not data.items:
        st.success("No governance review items flagged for this proposal version.")
        return
    for item in data.items:
        ui.governance_review_card(item.review_item_id, item.reason_code, item.severity, item.status,
                                   item.summary, item.source_diagnostic, item.created_at)


ui.render(backlog_result, _backlog, empty_message="No governance review items flagged for this proposal version.")

st.divider()
ui.advisory_banner()
