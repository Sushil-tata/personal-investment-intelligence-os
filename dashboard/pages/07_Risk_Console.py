import streamlit as st
from lib.api_client import get

st.title("Risk Console")
st.json(get("/risk"))
