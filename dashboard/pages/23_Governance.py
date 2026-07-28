import pandas as pd
import streamlit as st

from lib import api_client as api
from lib import components as ui

st.set_page_config(page_title="PIIOS — Governance Console", layout="wide")
ui.inject_base_styles()
ui.page_header("Governance Console", "Traceability, review, and data-quality posture across the platform.")

tabs = st.tabs([
    "Traceability", "Replay", "Diagnostics", "Confidence", "IPS Compliance",
    "Identity Resolution", "Data Quality", "Evidence Completeness", "Review Queue",
])

with tabs[0]:
    ui.section_header("Traceability")
    ui.disabled_card("Recommendation trace linkage", "Trace-linked evidence, claim references, and canonical "
                      "input snapshots are part of the Wave 2B decision-intelligence engine, not yet merged "
                      "into this branch.")

with tabs[1]:
    ui.section_header("Replay")
    ui.disabled_card("Replay verification", "PASS/FAIL replay verification against a recomputed recommendation "
                      "is not available — the replay-verification service is not yet merged into this branch.")

with tabs[2]:
    ui.section_header("Diagnostics")
    ui.disabled_card("General diagnostics feed", "A consolidated diagnostics feed (low-confidence flags, "
                      "stale-evidence flags, missing-data flags) does not exist as a single endpoint yet.")
    shadow = api.get_shadow_diagnostics()

    def _shadow(data):
        if not data.enabled:
            ui.empty_state_card("Shadow identity diagnostics are only enabled in dev/test environments.")
            return
        ui.kpi_row([
            ui.KPIItem("Checked Records", str(data.checked_records)),
            ui.KPIItem("Unresolved Records", str(data.unresolved_records)),
        ])
        for item in data.items[:20]:
            ui.governance_issue_card(
                f"{item.source_type} `{item.source_id}`", "MEDIUM" if item.warnings else "LOW",
                item.resolution_status, f"Legacy subject: {item.legacy_subject} · candidates: {item.candidate_count}",
            )

    ui.render(shadow, _shadow)

with tabs[3]:
    ui.section_header("Confidence", "Distribution of confidence scores across current recommendation proposals.")
    recos = api.get_recommendations()

    def _confidence(data):
        if not data:
            ui.empty_state_card("No recommendations to summarise.")
            return
        bands = {"High": 0, "Medium": 0, "Low": 0}
        for r in data:
            label, _ = ui.confidence_tone(r.confidence_score)
            bands[label] += 1
        avg = sum(r.confidence_score for r in data) / len(data)
        ui.kpi_row([
            ui.KPIItem("Average Confidence", f"{avg:.0f}/100"),
            ui.KPIItem("High Confidence", str(bands["High"])),
            ui.KPIItem("Medium Confidence", str(bands["Medium"])),
            ui.KPIItem("Low Confidence", str(bands["Low"])),
        ])
        st.caption("Bands are a frontend presentation grouping of the backend's own confidence_score field — "
                   "no new score is computed.")

    ui.render(recos, _confidence)

with tabs[4]:
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

with tabs[5]:
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

with tabs[6]:
    ui.section_header("Data Quality", "Source trust tiers and freshness SLAs from the data-trust hierarchy.")
    trust = api.get_data_trust_hierarchy()

    def _trust(data):
        df = pd.DataFrame([{
            "Source": s.source_name, "Trust Tier": s.trust_tier, "Score": s.score,
            "Freshness SLA (hrs)": s.freshness_sla_hours,
        } for s in data.hierarchy])
        st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True, hide_index=True)

    ui.render(trust, _trust)

with tabs[7]:
    ui.section_header("Evidence Completeness")
    ui.disabled_card("Evidence completeness scoring", "A per-recommendation or per-thesis evidence-completeness "
                      "metric (e.g. required evidence types present vs. missing) is not exposed by the backend.")

with tabs[8]:
    ui.section_header("Governance Review Queue")
    ui.disabled_card("Unified governance review queue", "A single queue combining overdue reviews, policy "
                      "violations, and traceability gaps across portfolios/instruments does not exist yet. "
                      "Use the IPS Compliance and Identity Resolution tabs above for the review-relevant data "
                      "that is genuinely available today.")

st.divider()
ui.api_gap_notice(
    "Traceability, replay verification, a consolidated diagnostics feed, evidence-completeness scoring, and a "
    "unified governance review queue all depend on the Wave 2B decision-intelligence/traceability engine, "
    "which is not merged into this branch. See dashboard/API_CONTRACT_REQUESTS.md for the endpoints and DTOs "
    "needed to close each gap."
)
