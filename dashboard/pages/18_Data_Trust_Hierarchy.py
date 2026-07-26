import pandas as pd
import streamlit as st

from lib.api_client import get

st.title("Data Trust Hierarchy")
st.caption("Source quality tiers for portfolio intelligence")

payload = get("/data-trust/hierarchy")
rows = payload.get("hierarchy", [])
if not rows:
    st.info("No data trust hierarchy entries found.")
else:
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    st.bar_chart(df.set_index("source_name")["score"])
