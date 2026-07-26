import streamlit as st
import requests

from lib.api_client import API_BASE

st.title("LangGraph Run Monitor")

ticker = st.text_input("Ticker", value="NVDA")
approve = st.checkbox("Human approve", value=False)
if st.button("Run Graph"):
    response = requests.post(
        f"{API_BASE}/graph/run",
        json={"ticker": ticker, "requested_by": "dashboard", "approve": approve},
        timeout=30,
    )
    response.raise_for_status()
    run = response.json()
    st.write(run)
    status = requests.get(f"{API_BASE}/graph/status", params={"run_id": run["run_id"]}, timeout=30)
    status.raise_for_status()
    st.json(status.json())
