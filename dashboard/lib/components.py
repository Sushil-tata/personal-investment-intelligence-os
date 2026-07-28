"""Institutional design-system component library for the PIIOS dashboard.

Every page should build its layout from these building blocks rather than
hand-rolling st.markdown/HTML snippets, so that a Bloomberg-Terminal /
Aladdin / family-office look stays consistent across all ~28 pages.

Colour and spacing choices are documented in dashboard/DESIGN_GUIDELINES.md
and must be changed there first, then here — this file is the single
implementation of that design system, not a place to invent new one-off
styles per page.

None of these components perform any investment calculation. They only
format and lay out values that are handed to them.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Iterable

import streamlit as st
from matplotlib import pyplot as plt

from lib.ui import (  # re-exported for a single import surface
    ADVISORY_BOUNDARY,
    advisory_banner,
    api_gap_notice,
    page_header,
    render,
    severity_badge,
    status_badge,
)

__all__ = [
    "ADVISORY_BOUNDARY", "advisory_banner", "api_gap_notice", "page_header", "render",
    "severity_badge", "status_badge",
    "inject_base_styles", "section_header", "KPIItem", "kpi_row", "metric_tile",
    "confidence_badge", "confidence_tone", "risk_badge", "pending_badge",
    "empty_state_card", "error_state_card", "loading_skeleton", "disabled_card",
    "TimelineEvent", "timeline", "audit_timeline", "decision_timeline",
    "confidence_breakdown_card", "evidence_card", "recommendation_card",
    "portfolio_allocation_card", "governance_issue_card", "pipeline_flow", "allocation_donut",
]

_STYLE_INJECTED_KEY = "_piios_base_styles_injected"


def inject_base_styles() -> None:
    """Idempotent per-session CSS injection. Call once near the top of
    every page, right after st.set_page_config()."""
    if st.session_state.get(_STYLE_INJECTED_KEY):
        return
    st.session_state[_STYLE_INJECTED_KEY] = True
    st.markdown(
        """
        <style>
        .piios-section-header {
            border-bottom: 2px solid #0B1F3A;
            padding-bottom: 0.35rem;
            margin: 1.4rem 0 0.9rem 0;
        }
        .piios-section-header h3 {
            margin: 0;
            color: #0B1F3A;
            font-weight: 700;
            letter-spacing: 0.01em;
        }
        .piios-section-header p {
            margin: 0.15rem 0 0 0;
            color: #5B6472;
            font-size: 0.86rem;
        }
        .piios-card {
            border: 1px solid #D9DEE4;
            border-radius: 6px;
            padding: 0.9rem 1.1rem;
            margin-bottom: 0.7rem;
            background-color: #FFFFFF;
        }
        .piios-card.disabled {
            background-color: #F4F5F7;
            color: #8A93A0;
            border-style: dashed;
        }
        .piios-card.error {
            background-color: #FCEEEE;
            border-color: #B3261E;
        }
        .piios-card.empty {
            background-color: #F7F8FA;
            border-style: dashed;
        }
        .piios-card-title {
            font-weight: 700;
            font-size: 0.95rem;
            color: #0B1F3A;
            margin-bottom: 0.25rem;
        }
        .piios-badge {
            display: inline-block;
            padding: 0.08rem 0.55rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            white-space: nowrap;
        }
        .piios-metric-tile {
            border: 1px solid #D9DEE4;
            border-radius: 6px;
            padding: 0.7rem 0.9rem;
            background-color: #FBFCFD;
        }
        .piios-metric-tile .label {
            font-size: 0.78rem;
            color: #5B6472;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .piios-metric-tile .value {
            font-size: 1.35rem;
            font-weight: 700;
            color: #0B1F3A;
        }
        .piios-metric-tile .sublabel {
            font-size: 0.78rem;
            color: #8A93A0;
        }
        .piios-timeline-item {
            border-left: 3px solid #1F4E79;
            padding: 0.15rem 0 0.15rem 0.9rem;
            margin-bottom: 0.6rem;
        }
        .piios-timeline-item.future {
            border-left: 3px dashed #B7BEC8;
            color: #8A93A0;
        }
        .piios-timeline-time {
            font-size: 0.76rem;
            color: #8A93A0;
        }
        .piios-skeleton {
            height: 1rem;
            border-radius: 4px;
            background: linear-gradient(90deg, #EDEFF2 25%, #E2E5E9 37%, #EDEFF2 63%);
            background-size: 400% 100%;
            margin-bottom: 0.5rem;
        }
        .piios-pipeline {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin: 0.6rem 0 1rem 0;
        }
        .piios-pipeline-step {
            border: 1px solid #D9DEE4;
            border-radius: 999px;
            padding: 0.3rem 0.9rem;
            font-size: 0.82rem;
            font-weight: 600;
            color: #0B1F3A;
            background: #FFFFFF;
        }
        .piios-pipeline-step.disabled {
            color: #B7BEC8;
            border-style: dashed;
            background: #F7F8FA;
        }
        .piios-pipeline-arrow {
            color: #8A93A0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str | None = None) -> None:
    subtitle_html = f"<p>{html.escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f'<div class="piios-section-header"><h3>{html.escape(title)}</h3>{subtitle_html}</div>',
        unsafe_allow_html=True,
    )


@dataclass
class KPIItem:
    label: str
    value: str
    help: str | None = None
    delta: str | None = None


def kpi_row(items: Iterable[KPIItem]) -> None:
    items = list(items)
    cols = st.columns(len(items)) if items else []
    for col, item in zip(cols, items):
        with col:
            st.metric(item.label, item.value, delta=item.delta, help=item.help)


def metric_tile(label: str, value: str, sublabel: str | None = None) -> None:
    sub_html = f'<div class="sublabel">{html.escape(sublabel)}</div>' if sublabel else ""
    st.markdown(
        f'<div class="piios-metric-tile"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def confidence_tone(score: float) -> tuple[str, str]:
    """Returns (label, hex colour) for a 0-100 confidence score. Bands are
    documented in DESIGN_GUIDELINES.md — change the doc first if these move."""
    if score >= 75:
        return "High", "#1E7145"
    if score >= 50:
        return "Medium", "#B4690E"
    return "Low", "#B3261E"


def confidence_badge(score: float) -> str:
    label, color = confidence_tone(score)
    return (
        f'<span class="piios-badge" style="background:{color}22;color:{color};">'
        f'{label} confidence · {score:.0f}</span>'
    )


def risk_badge(severity: str) -> str:
    s = (severity or "").upper()
    colors = {
        "HIGH": "#B3261E", "CRITICAL": "#B3261E",
        "MEDIUM": "#B4690E", "MODERATE": "#B4690E", "WARNING": "#B4690E",
        "LOW": "#1E7145", "MINOR": "#1E7145",
    }
    color = colors.get(s, "#5B6472")
    return f'<span class="piios-badge" style="background:{color}22;color:{color};">{html.escape(severity or "N/A")}</span>'


def pending_badge(text: str = "Backend capability pending") -> None:
    st.markdown(
        f'<span class="piios-badge" style="background:#5B647222;color:#5B6472;">⏳ {html.escape(text)}</span>',
        unsafe_allow_html=True,
    )


def empty_state_card(message: str) -> None:
    st.markdown(f'<div class="piios-card empty">📭 {html.escape(message)}</div>', unsafe_allow_html=True)


def error_state_card(message: str) -> None:
    st.markdown(f'<div class="piios-card error">⚠️ {html.escape(message)}</div>', unsafe_allow_html=True)


def loading_skeleton(rows: int = 3) -> None:
    st.markdown("".join(f'<div class="piios-skeleton" style="width:{92 - (i * 7) % 30}%;"></div>' for i in range(rows)),
                unsafe_allow_html=True)


def disabled_card(title: str, note: str = "Awaiting backend support") -> None:
    st.markdown(
        f'<div class="piios-card disabled"><div class="piios-card-title">{html.escape(title)}</div>'
        f'<div>🔒 {html.escape(note)}</div></div>',
        unsafe_allow_html=True,
    )


@dataclass
class TimelineEvent:
    label: str
    timestamp: str | None = None
    detail: str | None = None
    future: bool = False


def timeline(events: Iterable[TimelineEvent]) -> None:
    for event in events:
        cls = "piios-timeline-item future" if event.future else "piios-timeline-item"
        time_html = f'<div class="piios-timeline-time">{html.escape(event.timestamp)}</div>' if event.timestamp else ""
        detail_html = f'<div>{html.escape(event.detail)}</div>' if event.detail else ""
        st.markdown(
            f'<div class="{cls}"><b>{html.escape(event.label)}</b>{time_html}{detail_html}</div>',
            unsafe_allow_html=True,
        )


def audit_timeline(events: Iterable[TimelineEvent]) -> None:
    """Same rendering as timeline(); kept as a distinct name so pages can
    express intent (audit trail vs. general timeline vs. decision timeline)
    even while the visual treatment is identical today."""
    timeline(events)


def decision_timeline(events: Iterable[TimelineEvent]) -> None:
    timeline(events)


def confidence_breakdown_card(overall_score: float, components: dict[str, float] | None = None) -> None:
    st.markdown(f'<div class="piios-card"><div class="piios-card-title">Confidence</div>'
                f'{confidence_badge(overall_score)}</div>', unsafe_allow_html=True)
    if components:
        for name, value in components.items():
            st.progress(min(max(value / 100, 0.0), 1.0), text=f"{name}: {value:.0f}")
    else:
        disabled_card("Confidence component breakdown", "Backend returns only a single overall confidence score today.")


def evidence_card(title: str, source: str | None, timestamp: str | None, credibility: float | None, url: str | None) -> None:
    cred_html = ""
    if credibility is not None:
        tone_label, tone_color = confidence_tone(credibility)
        cred_html = f'<span class="piios-badge" style="background:{tone_color}22;color:{tone_color};">Credibility {credibility:.0f}</span>'
    link_html = f'<div><a href="{html.escape(url)}" target="_blank">{html.escape(url)}</a></div>' if url else ""
    st.markdown(
        f'<div class="piios-card"><div class="piios-card-title">{html.escape(title)}</div>'
        f'<div>{html.escape(source or "Unknown source")} · {html.escape(timestamp or "—")} {cred_html}</div>'
        f'{link_html}</div>',
        unsafe_allow_html=True,
    )


def recommendation_card(ticker: str, status: str, confidence: float, portfolio_fit: float, one_liner: str) -> None:
    st.markdown(
        f'<div class="piios-card"><div class="piios-card-title">{html.escape(ticker)} '
        f'{status_badge(status)}</div><div>{confidence_badge(confidence)} '
        f'<span class="piios-badge" style="background:#1F4E7922;color:#1F4E79;">Portfolio fit {portfolio_fit:.0f}</span></div>'
        f'<div style="margin-top:0.35rem;">{html.escape(one_liner)}</div></div>',
        unsafe_allow_html=True,
    )


def portfolio_allocation_card(dimension: str, key: str, market_value: float, percentage: float) -> None:
    st.markdown(
        f'<div class="piios-card"><div class="piios-card-title">{html.escape(key)}</div>'
        f'<div style="color:#5B6472;font-size:0.8rem;">{html.escape(dimension)}</div>'
        f'<div class="value" style="font-size:1.15rem;font-weight:700;color:#0B1F3A;">${market_value:,.0f} · {percentage:.1f}%</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def governance_issue_card(title: str, severity: str, status: str, detail: str) -> None:
    st.markdown(
        f'<div class="piios-card"><div class="piios-card-title">{html.escape(title)} {risk_badge(severity)}</div>'
        f'<div>{status_badge(status)}</div><div style="margin-top:0.35rem;">{html.escape(detail)}</div></div>',
        unsafe_allow_html=True,
    )


def pipeline_flow(steps: Iterable[tuple[str, bool]]) -> None:
    """Renders a horizontal pipeline, e.g. Recommendation -> Human Decision
    -> Future Execution, with disabled/future steps visually muted."""
    parts = []
    steps = list(steps)
    for i, (label, disabled) in enumerate(steps):
        cls = "piios-pipeline-step disabled" if disabled else "piios-pipeline-step"
        parts.append(f'<span class="{cls}">{html.escape(label)}</span>')
        if i < len(steps) - 1:
            parts.append('<span class="piios-pipeline-arrow">→</span>')
    st.markdown(f'<div class="piios-pipeline">{"".join(parts)}</div>', unsafe_allow_html=True)

_DONUT_PALETTE = ["#0B1F3A", "#1F4E79", "#3D7EA6", "#7FA8C9", "#B7BEC8", "#8A93A0", "#5B6472", "#D9DEE4"]


def allocation_donut(labels: list[str], values: list[float], title: str | None = None):
    """Renders a real donut chart from backend-provided allocation values —
    labels/values are plotted as-is, nothing is derived or estimated."""
    if not labels or not values or sum(values) <= 0:
        empty_state_card("No allocation data to chart.")
        return
    fig, ax = plt.subplots(figsize=(4, 4))
    colors = [_DONUT_PALETTE[i % len(_DONUT_PALETTE)] for i in range(len(labels))]
    wedges, _ = ax.pie(values, colors=colors, startangle=90, wedgeprops={"width": 0.4, "edgecolor": "white"})
    ax.legend(wedges, [f"{lbl} ({val:.1f}%)" for lbl, val in zip(labels, values)],
              loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=8, frameon=False)
    if title:
        ax.set_title(title, fontsize=11, color="#0B1F3A", fontweight="bold")
    fig.patch.set_alpha(0)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)
