import pandas as pd
import streamlit as st

from lib.api_client import get

st.title("Net Worth Engine")
st.caption("Advisory-only consolidated net worth analytics")

payload = get("/portfolio/net-worth")
col1, col2, col3 = st.columns(3)
col1.metric("Total Assets", f"{payload['total_assets']:.2f}")
col2.metric("Total Liabilities", f"{payload['total_liabilities']:.2f}")
col3.metric("Net Worth", f"{payload['net_worth']:.2f}")

st.subheader("Breakdown")
st.dataframe(pd.DataFrame(payload.get("breakdown", [])), use_container_width=True)
