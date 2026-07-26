import streamlit as st
import pandas as pd

from lib.api_client import get


SECTOR_FALLBACKS = {
	"AAPL": "Tech",
	"MSFT": "AI SaaS",
	"NVDA": "Data Centre",
	"AMZN": "Consumption",
	"GOOGL": "Tech",
	"META": "Tech",
	"AVGO": "Data Centre",
	"TSLA": "Mobility",
	"BRK-B": "Consumption",
	"JPM": "Tech",
	"V": "Tech",
	"MA": "Tech",
	"LLY": "Consumption",
	"UNH": "Consumption",
	"XOM": "Petro",
	"WMT": "Consumption",
	"JNJ": "Consumption",
	"PG": "Consumption",
	"HD": "Consumption",
	"MRK": "Consumption",
	"COST": "Consumption",
	"ABBV": "Consumption",
	"KO": "Consumption",
	"BAC": "Tech",
	"PEP": "Consumption",
	"AMD": "Data Centre",
	"ADBE": "AI SaaS",
	"CRM": "AI SaaS",
	"NFLX": "Tech",
	"CVX": "Petro",
	"ORCL": "AI SaaS",
	"TMO": "Consumption",
	"ACN": "AI SaaS",
	"MCD": "Consumption",
	"DHR": "Consumption",
	"ABT": "Consumption",
	"LIN": "Agri",
	"CSCO": "Tech",
	"WFC": "Tech",
	"INTU": "AI SaaS",
	"CMCSA": "Consumption",
	"QCOM": "Tech",
	"TXN": "Data Centre",
	"PM": "Consumption",
	"IBM": "Tech",
	"GE": "Mobility",
	"INTC": "Data Centre",
	"CAT": "Agri",
	"GS": "Tech",
	"AMAT": "Data Centre",
	"RTX": "Mobility",
	"SPGI": "Tech",
	"BKNG": "Consumption",
	"NOW": "AI SaaS",
	"BLK": "Tech",
	"PGR": "Consumption",
	"LOW": "Consumption",
	"ISRG": "Mobility",
	"MU": "Data Centre",
	"UBER": "Mobility",
	"PANW": "AI SaaS",
	"ANET": "Data Centre",
	"ETN": "Mobility",
	"DE": "Agri",
	"LRCX": "Data Centre",
	"SYK": "Consumption",
	"ADP": "AI SaaS",
	"TJX": "Consumption",
	"GILD": "Consumption",
	"VRTX": "Consumption",
}


def sector_for_ticker(ticker: str) -> str:
	return SECTOR_FALLBACKS.get(ticker, "Diversified")


def action_badge(action: str) -> str:
	lower = action.lower()
	if "buy" in lower or "accumulate" in lower:
		color = "#15803d"
	elif "sell" in lower or "reduce" in lower:
		color = "#b91c1c"
	else:
		color = "#475569"
	return f'<span style="background:{color};color:white;padding:0.2rem 0.55rem;border-radius:999px;font-size:0.78rem;white-space:nowrap;">{action}</span>'

st.title("Stock Scorecard")
payload = get("/recommendations/top?limit=100")
st.metric("Live Feed Source", "Yahoo Finance")
st.caption("Sector-aware scorecard built from the live ranked recommendations feed.")

stock_scores = pd.DataFrame(payload)
if stock_scores.empty:
	st.info("No stock scores available right now.")
else:
	if "sector" not in stock_scores.columns:
		stock_scores["sector"] = stock_scores["ticker"].map(sector_for_ticker)
	display_df = stock_scores[[col for col in ["ticker", "sector", "score", "recommended_action", "daily_pct", "weekly_pct", "close", "volume_ratio"] if col in stock_scores.columns]].copy()
	st.caption("Columns shown: ticker, sector, score, recommended action, daily return.")
	st.text(display_df.to_string(index=False))
	st.table(display_df)
