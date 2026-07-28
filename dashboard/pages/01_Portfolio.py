import pandas as pd
import streamlit as st

from lib import api_client as api
from lib import ui

st.set_page_config(page_title="PIIOS — Portfolio & Holdings", layout="wide")
ui.page_header("Portfolio & Holdings")

snapshots = api.get_portfolio()
holdings = api.get_holdings()

st.subheader("Portfolio Snapshots (by Owner)")


def _snapshots_table(data):
    df = pd.DataFrame([{"Snapshot": s.snapshot_id, "Owner": s.owner, "Total Value": s.total_value,
                         "Holdings Count": len(s.holdings)} for s in data])
    st.dataframe(df, use_container_width=True, hide_index=True)


ui.render(snapshots, _snapshots_table)

st.divider()
st.subheader("Consolidated Holdings")
st.caption("Filterable, sortable view across all holdings currently known to the backend.")


def _holdings_table(data):
    df = pd.DataFrame([{
        "Ticker": h.ticker, "Name": h.name, "Quantity": h.quantity, "Market Value": h.market_value,
        "Bucket": h.bucket, "Asset Class": h.asset_class, "Sector": h.sector, "Geography": h.geography,
        "Currency": h.currency, "Theme": h.theme,
    } for h in data])

    filter_cols = st.columns(4)
    bucket_filter = filter_cols[0].multiselect("Bucket", sorted(df["Bucket"].dropna().unique()))
    asset_class_filter = filter_cols[1].multiselect("Asset Class", sorted(df["Asset Class"].dropna().unique()))
    geography_filter = filter_cols[2].multiselect("Geography", sorted(df["Geography"].dropna().unique()))
    currency_filter = filter_cols[3].multiselect("Currency", sorted(df["Currency"].dropna().unique()))

    filtered = df.copy()
    if bucket_filter:
        filtered = filtered[filtered["Bucket"].isin(bucket_filter)]
    if asset_class_filter:
        filtered = filtered[filtered["Asset Class"].isin(asset_class_filter)]
    if geography_filter:
        filtered = filtered[filtered["Geography"].isin(geography_filter)]
    if currency_filter:
        filtered = filtered[filtered["Currency"].isin(currency_filter)]

    st.dataframe(filtered.sort_values("Market Value", ascending=False), use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(filtered)} of {len(df)} holdings · total market value ${filtered['Market Value'].sum():,.0f}")


ui.render(holdings, _holdings_table)

st.divider()
ui.api_gap_notice(
    "No household/family-member/account/broker-custodian hierarchy, cash balances, transaction history, or "
    "tax-lot detail is exposed by the backend yet — this page shows portfolio snapshots and flat holdings only. "
    "See the Family Portfolio Registry page for the household layer that does exist."
)
