import pandas as pd
import streamlit as st

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

st.title("Top Recommendations")
st.caption("Live ranked recommendations from market feed, advisory-only")

limit = st.slider("Rows", min_value=10, max_value=100, value=50, step=5)
all_rows = get("/recommendations/top?limit=100")
sector_options = ["All"] + sorted({row.get("sector") or sector_for_ticker(row.get("ticker", "")) for row in all_rows})
sector = st.selectbox("Sector", sector_options, index=0)

query = f"/recommendations/top?limit={limit}"
if sector != "All":
    query += f"&sector={sector}"

payload = get(query)

if not payload:
    st.info("No recommendations available.")
else:
    df = pd.DataFrame(payload)
    if "sector" not in df.columns:
        df["sector"] = df["ticker"].map(sector_for_ticker)
    summary = df["recommended_action"].value_counts().to_dict()
    cols = st.columns(4)
    cols[0].metric("Buy / accumulate", int(sum(count for action, count in summary.items() if "buy" in action.lower() or "accumulate" in action.lower())))
    cols[1].metric("Hold", int(sum(count for action, count in summary.items() if "hold" in action.lower())))
    cols[2].metric("Reduce / sell", int(sum(count for action, count in summary.items() if "sell" in action.lower() or "reduce" in action.lower())))
    cols[3].metric("Rows", len(df))

    st.caption("Sector is shown as the second column in the table below.")
    display_df = df[[col for col in ["ticker", "sector", "score", "recommended_action", "daily_pct", "weekly_pct", "close", "volume_ratio"] if col in df.columns]].copy()
    st.dataframe(display_df, use_container_width=True)
    st.bar_chart(df.set_index("ticker")["score"])
