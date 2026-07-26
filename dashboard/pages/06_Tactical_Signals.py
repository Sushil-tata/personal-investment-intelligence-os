import streamlit as st
from lib.api_client import get

st.title("Tactical Signals")
st.json(get("/tactical-signals"))
