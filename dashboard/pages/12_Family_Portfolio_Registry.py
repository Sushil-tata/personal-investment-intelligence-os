import pandas as pd
import streamlit as st

from lib.api_client import get

st.title("Family Portfolio Registry")
st.caption("Household-level portfolio ownership and base currency mapping")

payload = get("/family/portfolios")
rows = payload.get("households", [])
if not rows:
    st.info("No family portfolio records available.")
else:
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
