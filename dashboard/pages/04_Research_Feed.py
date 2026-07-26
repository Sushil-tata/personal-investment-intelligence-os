import streamlit as st
from lib.api_client import get

st.title("Research Feed")
st.json(get("/research"))
