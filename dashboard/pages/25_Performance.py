import streamlit as st

from lib import components as ui

st.set_page_config(page_title="PIIOS — Performance", layout="wide")
ui.inject_base_styles()
ui.page_header("Performance")

st.info("No performance endpoint exists in the backend on this branch. Every section below is an honest, "
        "disabled placeholder — nothing is fabricated or estimated.", icon="ℹ️")

ui.section_header("Performance Summary")
ui.disabled_card("Total / realised / unrealised / income return", "Not exposed by the backend.")

ui.section_header("Time-Weighted Return (TWR)")
ui.disabled_card("TWR", "Not computed or exposed by the backend.")

ui.section_header("Money-Weighted Return (XIRR)")
ui.disabled_card("XIRR", "Not computed or exposed by the backend.")

ui.section_header("Attribution")
ui.disabled_card("Return attribution by asset class / sector / geography / currency / security",
                  "Not exposed by the backend.")

ui.section_header("Benchmark Comparison")
ui.disabled_card("Benchmark comparison", "No benchmark series or comparison endpoint exists.")

ui.section_header("Drawdown")
ui.disabled_card("Drawdown", "Not computed or exposed by the backend.")

ui.section_header("Contributions")
ui.disabled_card("Cash-flow contributions to return", "Not exposed by the backend.")

st.divider()
ui.api_gap_notice(
    "No performance or returns endpoint of any kind exists in the backend on this branch. See "
    "dashboard/API_CONTRACT_REQUESTS.md for the concrete endpoint/DTO specification needed to build this page."
)
