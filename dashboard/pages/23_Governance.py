import pandas as pd
import streamlit as st

from lib import api_client as api
from lib import components as ui

st.set_page_config(page_title="PIIOS — Governance Console", layout="wide")
ui.inject_base_styles()
ui.page_header("Governance Console", "Traceability, review, and data-quality posture across the platform.")

tabs = st.tabs([
    "Traceability", "Replay", "Confidence Components", "Decision Lineage", "Governance Review Queue",
    "IPS Compliance", "Identity Resolution", "Data Quality", "Evidence Completeness",
])

# --- Wave 2B live diagnostics (proposal-version scoped) ---------------------
with tabs[0]:
    ui.section_header("Traceability")
    pv_id = ui.proposal_version_id_input(key="gov_pv_trace")
    if not pv_id:
        ui.empty_state_card("Enter a Proposal Version ID above to view its traceability diagnostic.")
    else:
        result = api.get_traceability_diagnostic(pv_id)

        def _trace(data):
            st.markdown(f"**Overall status:** {ui.diagnostic_status_badge(data.overall_status)}  "
                        f"**Severity:** {ui.diagnostic_severity_badge(data.severity)}", unsafe_allow_html=True)
            for check in data.checks:
                with st.expander(f"{check.code} — {check.status}"):
                    st.markdown(f"{ui.diagnostic_status_badge(check.status)} {ui.diagnostic_severity_badge(check.severity)}",
                                unsafe_allow_html=True)
                    st.write(check.message)
                    if check.remediation_hint:
                        st.caption(f"Remediation: {check.remediation_hint}")
            return data

        _trace_data_holder = {}
        if result.ok and not result.is_empty:
            _trace_data_holder["data"] = _trace(result.data)
        else:
            ui.render(result, _trace, empty_message="No traceability checks recorded for this proposal version.")

with tabs[1]:
    ui.section_header("Replay", "Surfaced as a traceability check, not a separate endpoint.")
    pv_id_replay = ui.proposal_version_id_input(key="gov_pv_replay")
    if not pv_id_replay:
        ui.empty_state_card("Enter a Proposal Version ID above to view its replay status.")
    else:
        trace_result = api.get_traceability_diagnostic(pv_id_replay)
        if trace_result.ok and not trace_result.is_empty:
            replay_check = next((c for c in trace_result.data.checks if "REPLAY" in c.code.upper()), None)
            if replay_check is not None:
                st.markdown(f"{ui.diagnostic_status_badge(replay_check.status)} {ui.diagnostic_severity_badge(replay_check.severity)}",
                            unsafe_allow_html=True)
                st.write(replay_check.message)
                if replay_check.remediation_hint:
                    st.caption(f"Remediation: {replay_check.remediation_hint}")
            else:
                ui.unavailable_state_card("Unavailable from current persisted data")
        elif not trace_result.ok:
            ui.error_state_card(f"Could not load traceability diagnostic. {trace_result.error}")
        else:
            ui.unavailable_state_card("Unavailable from current persisted data")

with tabs[2]:
    ui.section_header("Confidence Components", "Rendered exactly as returned — never recomputed by the frontend.")
    pv_id_conf = ui.proposal_version_id_input(key="gov_pv_conf")
    if not pv_id_conf:
        ui.empty_state_card("Enter a Proposal Version ID above to view its confidence components.")
    else:
        conf_result = api.get_confidence_diagnostic(pv_id_conf)

        def _conf(data):
            if data.authoritative_confidence is not None:
                st.markdown(f"**Authoritative confidence:** {data.authoritative_confidence:.2f}")
            else:
                ui.unavailable_state_card("Unavailable from current persisted data")
            for comp in data.components:
                ui.confidence_component_card(comp.name, comp.value, comp.status, comp.source, comp.explanation)
            if data.limitations:
                st.caption("Limitations: " + "; ".join(data.limitations))

        ui.render(conf_result, _conf)

with tabs[3]:
    ui.section_header("Decision Lineage")
    decision_id = ui.decision_id_input(key="gov_decision_lineage")
    if not decision_id:
        ui.empty_state_card("Enter a Decision ID above to view its lineage diagnostic.")
    else:
        lineage_result = api.get_decision_lineage_diagnostic(decision_id)

        def _lineage(data):
            st.markdown(f"**Decision meaning:** {data.decision_meaning} · **State:** {data.decision_state}")
            st.markdown(f"**Overall status:** {ui.diagnostic_status_badge(data.overall_status)}  "
                        f"**Severity:** {ui.diagnostic_severity_badge(data.severity)}", unsafe_allow_html=True)
            for check in data.checks:
                with st.expander(f"{check.code} — {check.status}"):
                    st.markdown(f"{ui.diagnostic_status_badge(check.status)} {ui.diagnostic_severity_badge(check.severity)}",
                                unsafe_allow_html=True)
                    st.write(check.message)

        ui.render(lineage_result, _lineage, empty_message="No lineage checks recorded for this decision.")

with tabs[4]:
    ui.section_header("Governance Review Queue")
    pv_id_backlog = ui.proposal_version_id_input(key="gov_pv_backlog")
    if not pv_id_backlog:
        ui.empty_state_card("Enter a Proposal Version ID above to view its governance review queue.")
    else:
        backlog_result = api.get_governance_backlog(pv_id_backlog)

        def _backlog(data):
            if not data.items:
                st.success("No governance review items flagged for this proposal version.")
                return
            for item in data.items:
                ui.governance_review_card(item.review_item_id, item.reason_code, item.severity, item.status,
                                           item.summary, item.source_diagnostic, item.created_at)

        ui.render(backlog_result, _backlog, empty_message="No governance review items flagged for this proposal version.")

# --- Legacy, still-live governance-adjacent data ----------------------------
with tabs[5]:
    ui.section_header("IPS Compliance")
    ips = api.get_ips_constraints()

    def _ips(data):
        df = pd.DataFrame([{
            "Constraint": c.name, "Rule Type": c.rule_type, "Threshold": c.threshold_value,
            "Severity": c.severity, "Enabled": c.enabled,
        } for c in data.constraints])
        severities = sorted(df["Severity"].dropna().unique())
        severity_filter = st.multiselect("Severity", severities, key="ips_severity")
        filtered = df[df["Severity"].isin(severity_filter)] if severity_filter else df
        st.dataframe(filtered, use_container_width=True, hide_index=True)

    ui.render(ips, _ips)

with tabs[6]:
    ui.section_header("Identity Resolution")
    limit = st.slider("Max issues to fetch", 10, 500, 100, key="issues_limit")
    issues = api.get_resolution_issues(limit=limit)

    def _issues(data):
        statuses = sorted({i.status for i in data})
        status_filter = st.multiselect("Status", statuses, key="issue_status")
        filtered = [i for i in data if not status_filter or i.status in status_filter]
        st.caption(f"Showing {len(filtered)} of {len(data)} unresolved identity issues.")
        for issue in filtered[:100]:
            ui.governance_issue_card(
                f"{issue.source_record_type} `{issue.source_record_id}`", "MEDIUM", issue.status,
                f"{issue.reason} · recommended: {issue.recommended_resolution or '—'} · "
                f"reviewer: {issue.reviewer or '—'}",
            )

    ui.render(issues, _issues, empty_message="No unresolved identity resolution issues.")

with tabs[7]:
    ui.section_header("Data Quality", "Source trust tiers and freshness SLAs from the data-trust hierarchy.")
    trust = api.get_data_trust_hierarchy()

    def _trust(data):
        df = pd.DataFrame([{
            "Source": s.source_name, "Trust Tier": s.trust_tier, "Score": s.score,
            "Freshness SLA (hrs)": s.freshness_sla_hours,
        } for s in data.hierarchy])
        st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True, hide_index=True)

    ui.render(trust, _trust)

with tabs[8]:
    ui.section_header("Evidence Completeness")
    ui.unavailable_state_card("Unavailable from current persisted data")
    st.caption("A per-proposal-version evidence-completeness metric is not exposed by the decision-contracts API.")

st.divider()
ui.api_gap_notice(
    "Traceability, Replay, Confidence Components, and Governance Review Queue require an already-known Proposal "
    "Version ID; Decision Lineage requires an already-known Decision ID — there is no list/discovery endpoint "
    "for any of these. See dashboard/FRONTEND_INTEGRATION_NOTES.md."
)
