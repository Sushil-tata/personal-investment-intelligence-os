import pandas as pd
import streamlit as st

from lib.api_client import get

st.title("Portfolio Drift Dashboard")
st.caption("Advisory-only rebalancing intelligence; no trade execution")

targets = get("/portfolio/targets")
drift = get("/portfolio/drift")

st.subheader("Current Targets")
st.json(targets)

items = drift.get("items", [])
if not items:
    st.info("No drift data available.")
else:
    df = pd.DataFrame(items)
    st.subheader("Drift by Dimension")
    st.dataframe(
        df[
            [
                "dimension",
                "key",
                "target_percentage",
                "actual_percentage",
                "drift_percentage",
                "drift_amount",
                "severity",
                "recommended_action",
                "advisory_only",
            ]
        ],
        use_container_width=True,
    )

    st.subheader("High Severity Items")
    high = df[df["severity"] == "HIGH"]
    if high.empty:
        st.success("No high severity drifts currently detected.")
    else:
        st.dataframe(high[["dimension", "key", "drift_percentage", "recommended_action"]], use_container_width=True)
