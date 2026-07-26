import pandas as pd
import streamlit as st

from lib.api_client import get

st.title("Asset Allocation Dashboard")
st.caption("Allocation view by dimension")

dimension = st.selectbox("Dimension", ["asset_class", "sector", "theme", "bucket", "geography"], index=0)
payload = get(f"/portfolio/allocation?dimension={dimension}")
rows = payload.get("items", [])
if not rows:
    st.info("No allocation data available.")
else:
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    st.bar_chart(df.set_index("key")["percentage"])
