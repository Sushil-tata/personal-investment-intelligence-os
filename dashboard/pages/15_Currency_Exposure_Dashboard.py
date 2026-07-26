import pandas as pd
import streamlit as st

from lib.api_client import get

st.title("Currency Exposure Dashboard")
st.caption("Currency concentration and diversification visibility")

payload = get("/portfolio/currency-exposure")
rows = payload.get("items", [])
if not rows:
    st.info("No currency exposure data available.")
else:
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    st.bar_chart(df.set_index("currency")["percentage"])
