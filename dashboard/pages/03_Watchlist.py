import streamlit as st
from lib.api_client import get

st.title("Watchlist")
st.json(get("/watchlist"))
