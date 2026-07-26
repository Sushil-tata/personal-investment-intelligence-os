import pandas as pd
import streamlit as st

from lib.api_client import get

st.title("Investment Thesis Registry")
st.caption("Advisory-only thesis tracking and lifecycle visibility")

theses = get("/theses")
if not theses:
    st.info("No investment theses found.")
else:
    df = pd.DataFrame(theses)
    st.dataframe(
        df[
            [
                "thesis_id",
                "ticker",
                "asset_name",
                "theme",
                "bucket",
                "status",
                "confidence_score",
                "updated_at",
            ]
        ],
        use_container_width=True,
    )

selected = st.selectbox("Select thesis", options=[item["thesis_id"] for item in theses] if theses else [])
if selected:
    detail = next(item for item in theses if item["thesis_id"] == selected)
    st.subheader(f"{detail['ticker']} - {detail['asset_name']}")
    st.write("Thesis")
    st.write(detail["thesis"])
    st.write("Bull case")
    st.write(detail["bull_case"])
    st.write("Bear case")
    st.write(detail["bear_case"])
    st.write("Invalidation trigger")
    st.write(detail["invalidation_trigger"])
