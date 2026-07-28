import pandas as pd
import streamlit as st

from lib import api_client as api
from lib import ui

st.set_page_config(page_title="PIIOS — Governance", layout="wide")
ui.page_header("Governance")

st.caption("Consolidated view of the governance-relevant signals the backend currently exposes: IPS constraint "
           "posture, data-source trust tiers, and identity-resolution issues.")

tab1, tab2, tab3 = st.tabs(["IPS Constraints", "Identity Resolution Issues", "Data Trust Hierarchy"])

with tab1:
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

with tab2:
    limit = st.slider("Max issues to fetch", 10, 500, 100, key="issues_limit")
    issues = api.get_resolution_issues(limit=limit)

    def _issues(data):
        statuses = sorted({i.status for i in data})
        status_filter = st.multiselect("Status", statuses, key="issue_status")
        filtered = [i for i in data if not status_filter or i.status in status_filter]
        st.caption(f"Showing {len(filtered)} of {len(data)} unresolved identity issues.")
        for issue in filtered[:100]:
            with st.expander(f"{issue.source_record_type} `{issue.source_record_id}` — {issue.status}"):
                st.write(f"**Reason:** {issue.reason}")
                st.write(f"**Recommended resolution:** {issue.recommended_resolution or '—'}")
                st.write(f"**Owner decision:** {issue.owner_decision or '—'} · "
                         f"**Reviewer:** {issue.reviewer or '—'} · **Reviewed at:** {issue.reviewed_at or '—'}")
                st.caption(f"Created {issue.created_at}")

    ui.render(issues, _issues, empty_message="No unresolved identity resolution issues.")

with tab3:
    trust = api.get_data_trust_hierarchy()

    def _trust(data):
        df = pd.DataFrame([{
            "Source": s.source_name, "Trust Tier": s.trust_tier, "Score": s.score,
            "Freshness SLA (hrs)": s.freshness_sla_hours,
        } for s in data.hierarchy])
        st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True, hide_index=True)

    ui.render(trust, _trust)

st.divider()
ui.api_gap_notice(
    "A general-purpose governance backlog — low-confidence recommendations, replay mismatches, stale evidence "
    "flags, missing-data diagnostics, policy violations, decisions awaiting review, overdue reviews, and "
    "traceability gaps, filterable by severity/status/portfolio/instrument/date — is not available from the "
    "backend on this branch (it depends on the not-yet-merged Wave 2B decision-intelligence/traceability work). "
    "This page surfaces only the governance-adjacent data that genuinely exists today: IPS constraints, "
    "identity-resolution issues, and data-source trust tiers."
)
