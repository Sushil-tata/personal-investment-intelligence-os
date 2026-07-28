import streamlit as st

from lib import ui

st.set_page_config(page_title="PIIOS — Performance", layout="wide")
ui.page_header("Performance")

st.info("This section is a placeholder. No performance data is fabricated below.", icon="ℹ️")

st.markdown(
    "Planned for this screen once backend support exists: total return, realised/unrealised return, income "
    "return, time-weighted return (TWR), money-weighted return (XIRR), benchmark comparison, and return "
    "attribution by asset class, sector, geography, currency, and individual security."
)

st.divider()
ui.api_gap_notice(
    "No performance or returns endpoint exists anywhere in the backend on this branch — there is no return, "
    "TWR, XIRR, benchmark, or attribution data to render. Per the frontend mandate, this screen does not "
    "compute any of these figures itself; it remains a clean placeholder until the backend exposes a "
    "performance contract."
)
