import streamlit as st
from lib.api_client import get

st.title("Journal")
st.json(get("/journal"))
