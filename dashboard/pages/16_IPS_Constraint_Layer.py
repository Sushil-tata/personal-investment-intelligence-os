import pandas as pd
import streamlit as st

from lib.api_client import get

st.title("IPS Constraint Layer")
st.caption("Policy rules and constraint monitoring")

payload = get("/ips/constraints")
rows = payload.get("constraints", [])
if not rows:
    st.info("No IPS constraints found.")
else:
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
