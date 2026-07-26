import pandas as pd
import streamlit as st

from lib.api_client import get

st.title("Instrument Master")
st.caption("Canonical instrument definitions and source lineage")

payload = get("/instruments")
rows = payload.get("instruments", [])
if not rows:
    st.info("No instruments found.")
else:
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
