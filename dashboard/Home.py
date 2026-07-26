import streamlit as st
from lib.api_client import get

st.set_page_config(page_title="PIIOS", layout="wide")
st.title("Personal Investment Intelligence OS")
st.caption("Advisory-only and research-only system. No execution capabilities.")

portfolio = get("/portfolio")
reco = get("/recommendations")

st.metric("Portfolio Snapshots", len(portfolio))
st.metric("Recommendations", len(reco))
st.write("Advisory boundary active for all outputs.")
