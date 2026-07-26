import streamlit as st
from lib.api_client import get

st.title("Portfolio")
st.json(get("/portfolio"))
