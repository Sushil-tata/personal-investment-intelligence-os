import streamlit as st
from lib.api_client import get

st.title("Allocation")
portfolio = get("/portfolio")
if portfolio:
    st.write(portfolio[0])
else:
    st.write("No data")
