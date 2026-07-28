"""Shared, consistent page chrome and state rendering for every PIIOS page.

Centralising this avoids each of the 20+ pages inventing its own loading /
error / empty visual language, and keeps the advisory-only messaging and
"Recommendation vs. Decision vs. Execution" labelling identical everywhere
it appears.
"""
from __future__ import annotations

from typing import Callable, TypeVar

import streamlit as st

from lib.api_client import ApiResult

T = TypeVar("T")

ADVISORY_BOUNDARY = (
    "Advisory-only and research-only. No broker integration, no order placement, "
    "no auto-trading, no margin/leverage execution, and no broker credential storage."
)


def page_header(title: str, caption: str | None = None) -> None:
    st.title(title)
    st.caption(caption or ADVISORY_BOUNDARY)


def advisory_banner() -> None:
    st.info(f"⚠️ {ADVISORY_BOUNDARY}", icon="⚠️")


def api_gap_notice(text: str) -> None:
    """Standard box for documenting a missing/partial backend contract
    directly on the screen it affects, instead of silently omitting data
    or inventing a substitute. Always pair with an entry in API_GAPS.md."""
    st.warning(f"API gap: {text}\n\nSee `dashboard/API_GAPS.md` for details.")


def render(result: ApiResult, on_success: Callable[[T], None], empty_message: str = "No data returned by the backend.") -> None:
    """Render an ApiResult consistently: error state, empty state, or the
    caller's success renderer. Pages should route every API call through
    this so failure modes look the same across the whole app."""
    if not result.ok:
        st.error(f"Could not load this data. {result.error}")
        return
    if result.is_empty:
        st.info(empty_message)
        return
    on_success(result.data)


def severity_badge(severity: str) -> str:
    s = (severity or "").upper()
    if s in ("HIGH", "CRITICAL"):
        return f"🔴 {severity}"
    if s in ("MEDIUM", "MODERATE", "WARN", "WARNING"):
        return f"🟠 {severity}"
    if s in ("LOW", "MINOR"):
        return f"🟡 {severity}"
    return f"⚪ {severity}"


def status_badge(status: str) -> str:
    s = (status or "").upper()
    mapping = {
        "APPROVED": "🟢 APPROVED",
        "PENDING_REVIEW": "🟠 PENDING_REVIEW",
        "RISK_CHECKED": "🔵 RISK_CHECKED",
        "RESEARCHED": "🔵 RESEARCHED",
        "DRAFT": "⚪ DRAFT",
        "ARCHIVED": "⚫ ARCHIVED",
    }
    return mapping.get(s, s)
