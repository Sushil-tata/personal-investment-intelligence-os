"""Unit tests for the shared component library (lib/components.py). These
run without Streamlit's script-execution context where possible (pure
functions) and via a minimal AppTest harness for render-only components."""
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib import components as ui

DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
_TMP_DIR = Path(tempfile.gettempdir())


def test_confidence_tone_bands():
    assert ui.confidence_tone(90)[0] == "High"
    assert ui.confidence_tone(75)[0] == "High"
    assert ui.confidence_tone(74.9)[0] == "Medium"
    assert ui.confidence_tone(50)[0] == "Medium"
    assert ui.confidence_tone(49.9)[0] == "Low"
    assert ui.confidence_tone(0)[0] == "Low"


def test_confidence_badge_contains_score():
    badge = ui.confidence_badge(82.4)
    assert "82" in badge
    assert "High" in badge


def test_risk_badge_maps_known_severities():
    assert "N/A" in ui.risk_badge("")
    high = ui.risk_badge("HIGH")
    assert "HIGH" in high


def test_kpi_item_defaults():
    item = ui.KPIItem(label="Net Worth", value="$100")
    assert item.help is None
    assert item.delta is None


def test_timeline_event_future_flag_default_false():
    event = ui.TimelineEvent(label="Created")
    assert event.future is False


def _render_component(fn_body: str) -> AppTest:
    script = "\n".join([
        "import streamlit as st",
        "from lib import components as ui",
        fn_body,
    ])
    script_path = _TMP_DIR / "_piios_component_harness.py"
    script_path.write_text(script)
    at = AppTest.from_file(str(script_path))
    at.run(timeout=15)
    return at


def test_section_header_renders_without_exception():
    at = _render_component('ui.inject_base_styles()\nui.section_header("Test Section", "subtitle")')
    assert not at.exception


def test_kpi_row_renders_without_exception():
    at = _render_component(
        'ui.kpi_row([ui.KPIItem("A", "1"), ui.KPIItem("B", "2")])'
    )
    assert not at.exception


def test_disabled_card_renders_without_exception():
    at = _render_component('ui.disabled_card("Feature", "Awaiting backend support")')
    assert not at.exception


def test_empty_and_error_state_cards_render_without_exception():
    at = _render_component('ui.empty_state_card("nothing here")\nui.error_state_card("broke")')
    assert not at.exception


def test_loading_skeleton_renders_without_exception():
    at = _render_component('ui.loading_skeleton(rows=4)')
    assert not at.exception


def test_pipeline_flow_renders_without_exception():
    at = _render_component(
        'ui.pipeline_flow([("Proposal", False), ("Decision", False), ("Execution", True)])'
    )
    assert not at.exception


def test_timeline_renders_without_exception():
    at = _render_component(
        'ui.timeline([ui.TimelineEvent("Created", "t1"), ui.TimelineEvent("Future step", None, "n/a", future=True)])'
    )
    assert not at.exception


def test_confidence_breakdown_card_without_components_shows_disabled_note():
    at = _render_component('ui.confidence_breakdown_card(72.0)')
    assert not at.exception


def test_confidence_breakdown_card_with_components_renders_progress():
    at = _render_component(
        'ui.confidence_breakdown_card(72.0, {"Evidence quality": 60.0, "Freshness": 80.0})'
    )
    assert not at.exception


def test_evidence_card_renders_without_exception():
    at = _render_component(
        'ui.evidence_card("Doc title", "internal", "2026-07-01", 80.0, "https://example.com")'
    )
    assert not at.exception


def test_recommendation_card_renders_without_exception():
    at = _render_component(
        'ui.recommendation_card("NVDA", "PENDING_REVIEW", 80.0, 70.0, "Strong AI capex tailwind.")'
    )
    assert not at.exception


def test_portfolio_allocation_card_renders_without_exception():
    at = _render_component(
        'ui.portfolio_allocation_card("asset_class", "Equity", 50000.0, 62.5)'
    )
    assert not at.exception


def test_governance_issue_card_renders_without_exception():
    at = _render_component(
        'ui.governance_issue_card("Identity gap", "MEDIUM", "OPEN", "Unresolved company mapping")'
    )
    assert not at.exception


def test_allocation_donut_with_empty_data_shows_empty_state():
    at = _render_component('ui.allocation_donut([], [])')
    assert not at.exception


def test_allocation_donut_with_data_renders_without_exception():
    at = _render_component('ui.allocation_donut(["Equity", "Bonds"], [70.0, 30.0])')
    assert not at.exception
