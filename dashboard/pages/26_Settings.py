import streamlit as st

from lib import ui
from lib.api_client import API_BASE, get_health

st.set_page_config(page_title="PIIOS — Settings", layout="wide")
ui.page_header("Settings")

st.subheader("Backend Connection")
st.write(f"API base URL: `{API_BASE}`")
st.caption("Configured via the `PIIOS_API_BASE` environment variable; defaults to http://127.0.0.1:8000/api/v1.")

health = get_health()
if health.ok:
    st.success(f"Backend reachable — status: {health.data.status}, product: {health.data.product}")
else:
    st.error(f"Backend not reachable: {health.error}")

st.divider()
st.subheader("Product Boundary")
ui.advisory_banner()

st.divider()
st.subheader("About")
st.write(
    "PIIOS (Personal Investment Intelligence OS) frontend — a modular Streamlit dashboard that renders data "
    "exclusively from the backend's REST API. It performs no investment calculations, holds no execution "
    "capability, and does not duplicate backend business logic."
)
