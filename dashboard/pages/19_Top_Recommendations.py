import pandas as pd
import streamlit as st

from lib import api_client as api

CACHE_TTL_SECONDS = 600  # 10 minutes: avoids re-running the live engine on every widget interaction.

st.title("Top Recommendations")
st.caption("Live ranked recommendations from the PIIOS discovery engine (real quality/growth/valuation/momentum/risk scoring), advisory-only.")


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Running PIIOS discovery engine on live market data...")
def _load_top_ranked(market: str) -> api.ApiResult:
    return api.generate_investment_recommendation(
        investable_amount=10000.0,
        market_data_mode="live",
        use_demo_portfolio=False,
        base_currency="USD",
        eligible_markets=[market],
    )


market = st.selectbox("Market", ["US", "India"], index=0)
limit = st.slider("Rows", min_value=10, max_value=100, value=50, step=5)

result = _load_top_ranked(market)
if not result.ok:
    st.error(result.error or "Unable to load recommendations.")
    st.stop()

data = result.data
all_candidates = data.top_ranked_candidates or []
if not all_candidates:
    st.info("No recommendations available. This can happen if live market data was unavailable for this market's universe.")
    st.stop()

st.caption(
    f"As of {data.as_of_timestamp} · data mode {data.market_data_mode} · provider {data.market_data_provider} "
    f"· input freshness {data.input_freshness}"
)
if data.market_data_mode and data.market_data_mode.upper() == "DEVELOPMENT_SEED":
    st.warning("This run used seeded/synthetic data, not live market data — treat scores as non-authoritative.")

sector_options = ["All"] + sorted({c.sector for c in all_candidates if c.sector})
sector = st.selectbox("Sector", sector_options, index=0)

filtered = all_candidates
if sector != "All":
    filtered = [c for c in filtered if c.sector == sector]

rows = filtered[:limit]

if not rows:
    st.info("No recommendations available for the selected sector.")
else:
    summary = {}
    for c in rows:
        summary[c.action] = summary.get(c.action, 0) + 1
    cols = st.columns(4)
    cols[0].metric("Buy / Add", sum(count for action, count in summary.items() if action in {"BUY", "ADD"}))
    cols[1].metric("Hold / Research", sum(count for action, count in summary.items() if action in {"HOLD", "RESEARCH"}))
    cols[2].metric("Reduce / Avoid", sum(count for action, count in summary.items() if action in {"REDUCE", "AVOID"}))
    cols[3].metric("Rows", len(rows))

    st.caption("Scores are the real PIIOS discovery engine factor scores (0-100), not a hardcoded or placeholder ranking.")
    table = pd.DataFrame(
        [
            {
                "Rank": c.rank,
                "Ticker": c.ticker,
                "Company": c.company,
                "Sector": c.sector or "Unknown",
                "Action": c.action,
                "Combined Score": c.combined_recommendation_score,
                "Quality": c.quality,
                "Growth": c.growth,
                "Valuation": c.valuation,
                "Momentum": c.momentum,
                "Risk": c.risk,
                "Confidence": c.confidence,
                "Price": c.current_price,
                "Currency": c.trading_currency,
            }
            for c in rows
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)
    if table["Combined Score"].notna().any():
        st.bar_chart(table.set_index("Ticker")["Combined Score"])

st.warning("Advisory-only. No automatic trading, no broker integration, and human approval required.")
