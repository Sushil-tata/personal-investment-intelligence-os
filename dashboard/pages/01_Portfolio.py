import pandas as pd
import streamlit as st

from lib import api_client as api
from lib import components as ui

st.set_page_config(page_title="PIIOS — Portfolio & Holdings", layout="wide")
ui.inject_base_styles()
ui.page_header("Portfolio & Holdings")

snapshots = api.get_portfolio()
holdings = api.get_holdings()

ui.section_header("Portfolio Snapshots", "By owner, as currently persisted by the backend.")


def _snapshots_table(data):
    df = pd.DataFrame([{"Snapshot": s.snapshot_id, "Owner": s.owner, "Total Value": s.total_value,
                         "Holdings Count": len(s.holdings)} for s in data])
    ui.kpi_row([
        ui.KPIItem("Snapshots", str(len(data))),
        ui.KPIItem("Total Value", f"${df['Total Value'].sum():,.0f}"),
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)


ui.render(snapshots, _snapshots_table)

st.divider()
ui.section_header("Allocation", "Real allocation percentages from the backend's PortfolioLayersService, by dimension.")

alloc_tabs = st.tabs(["Asset Class", "Sector", "Geography", "Bucket", "Currency"])
dims = ["asset_class", "sector", "geography", "bucket"]

for tab, dim in zip(alloc_tabs[:4], dims):
    with tab:
        alloc = api.get_allocation(dimension=dim)

        def _alloc(data, dim=dim):
            labels = [i.key for i in data.items]
            values = [i.percentage for i in data.items]
            col1, col2 = st.columns([1, 1])
            with col1:
                ui.allocation_donut(labels, values, title=dim.replace("_", " ").title())
            with col2:
                for item in sorted(data.items, key=lambda i: i.percentage, reverse=True):
                    ui.portfolio_allocation_card(dim.replace("_", " ").title(), item.key, item.market_value, item.percentage)

        ui.render(alloc, _alloc)

with alloc_tabs[4]:
    currency = api.get_currency_exposure()

    def _currency(data):
        labels = [i.currency for i in data.items]
        values = [i.percentage for i in data.items]
        col1, col2 = st.columns([1, 1])
        with col1:
            ui.allocation_donut(labels, values, title="Currency")
        with col2:
            for item in sorted(data.items, key=lambda i: i.percentage, reverse=True):
                ui.portfolio_allocation_card("Currency", item.currency, item.market_value, item.percentage)

    ui.render(currency, _currency)

st.divider()
ui.section_header("Concentration Summary", "Largest positions by market value, from real holdings data — no risk model applied.")


def _concentration(data):
    total = sum(h.market_value for h in data)
    if total <= 0:
        ui.empty_state_card("No holdings market value to summarise.")
        return
    ranked = sorted(data, key=lambda h: h.market_value, reverse=True)
    top = ranked[:5]
    largest = top[0]
    ui.kpi_row([
        ui.KPIItem("Largest Position", largest.ticker, help=f"${largest.market_value:,.0f}"),
        ui.KPIItem("Largest Position %", f"{(largest.market_value / total) * 100:.1f}%"),
        ui.KPIItem("Top 5 Positions %", f"{sum(h.market_value for h in top) / total * 100:.1f}%"),
    ])
    df = pd.DataFrame([{"Ticker": h.ticker, "Name": h.name, "Market Value": h.market_value,
                         "% of Portfolio": h.market_value / total * 100} for h in top])
    st.dataframe(df, use_container_width=True, hide_index=True)


ui.render(holdings, _concentration)

st.divider()
ui.section_header("Diversification Summary", "Distinct categories represented across holdings — counts only, no diversification score computed.")


def _diversification(data):
    ui.kpi_row([
        ui.KPIItem("Distinct Tickers", str(len({h.ticker for h in data}))),
        ui.KPIItem("Distinct Sectors", str(len({h.sector for h in data}))),
        ui.KPIItem("Distinct Geographies", str(len({h.geography for h in data}))),
        ui.KPIItem("Distinct Currencies", str(len({h.currency for h in data}))),
    ])
    ui.disabled_card("Diversification / concentration risk score", "A formal diversification or concentration "
                      "risk metric (e.g. Herfindahl-Hirschman Index) is not computed by the backend and is "
                      "intentionally not calculated in the frontend — only category counts are shown above.")


ui.render(holdings, _diversification)

st.divider()
ui.section_header("Consolidated Holdings", "Filterable, sortable view across all holdings currently known to the backend.")


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
