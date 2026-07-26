import pandas as pd
import streamlit as st
from requests import HTTPError

from lib.api_client import get

st.title("Score Explainability")
st.caption("Breakdown of Quality, Value, Momentum, Financial Health, and Composite score with ranking rationale.")

limit = st.slider("Rows", min_value=10, max_value=100, value=25, step=5)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _percentile(value: float, values: list[float]) -> float:
    if not values:
        return 50.0
    count = sum(1 for item in values if item <= value)
    return round((count / len(values)) * 100.0, 2)


def fetch_explainability(limit_value: int) -> dict:
    try:
        return get(f"/scores/explainability?limit={limit_value}")
    except HTTPError:
        fallback_rows = get(f"/recommendations/top?limit={limit_value}")
        items = []
        for row in fallback_rows:
            composite = float(row.get("score", 50.0))
            daily_pct = float(row.get("daily_pct", 0.0) or 0.0)
            weekly_pct = float(row.get("weekly_pct", 0.0) or 0.0)
            volume_ratio = float(row.get("volume_ratio", 1.0) or 1.0)

            quality = _clamp(45.0 + ((composite - 50.0) * 0.35) + (max(0.0, weekly_pct) * 0.8) - (max(0.0, -weekly_pct) * 0.4))
            value = _clamp(60.0 - ((composite - 50.0) * 0.30) - (max(0.0, daily_pct) * 1.2) + (max(0.0, -daily_pct) * 1.0))
            momentum = _clamp(50.0 + (daily_pct * 6.0) + (weekly_pct * 2.0) + ((volume_ratio - 1.0) * 15.0))
            financial_health = _clamp(48.0 + ((volume_ratio - 1.0) * 20.0) + (weekly_pct * 0.5))

            composite_explainable = round(
                (quality * 0.30) +
                (value * 0.20) +
                (momentum * 0.30) +
                (financial_health * 0.20),
                2,
            )

            contributors = [
                {
                    "factor": "quality.signal",
                    "impact": round((quality - 50.0) * 0.35, 2),
                    "detail": f"Quality score {round(quality, 2)}",
                },
                {
                    "factor": "value.signal",
                    "impact": round((value - 50.0) * 0.25, 2),
                    "detail": f"Value score {round(value, 2)}",
                },
                {
                    "factor": "momentum.daily_return",
                    "impact": round(daily_pct * 1.2, 2),
                    "detail": f"Daily return {round(daily_pct, 2)}%",
                },
                {
                    "factor": "momentum.weekly_return",
                    "impact": round(weekly_pct * 0.8, 2),
                    "detail": f"Weekly return {round(weekly_pct, 2)}%",
                },
                {
                    "factor": "momentum.volume_ratio",
                    "impact": round((volume_ratio - 1.0) * 12.0, 2),
                    "detail": f"Volume ratio {round(volume_ratio, 2)}",
                },
                {
                    "factor": "financial_health.signal",
                    "impact": round((financial_health - 50.0) * 0.30, 2),
                    "detail": f"Financial health score {round(financial_health, 2)}",
                },
                {
                    "factor": "base.market_score",
                    "impact": round((composite - 50.0) * 0.15, 2),
                    "detail": f"Base recommendation score {round(composite, 2)}",
                },
            ]
            contributors = sorted(contributors, key=lambda item: item["impact"], reverse=True)
            positives = [item for item in contributors if item["impact"] > 0][:5]
            negatives = sorted([item for item in contributors if item["impact"] < 0], key=lambda item: item["impact"])[:5]
            top_positive = ", ".join(item["factor"] for item in positives[:2]) or "balanced factors"
            top_negative = ", ".join(item["factor"] for item in negatives[:1]) or "no major detractors"

            items.append(
                {
                    "ticker": row.get("ticker", "NA"),
                    "sector": row.get("sector", "Diversified"),
                    "quality": round(quality, 2),
                    "value": round(value, 2),
                    "momentum": round(momentum, 2),
                    "financial_health": round(financial_health, 2),
                    "composite": composite_explainable,
                    "recommended_action": row.get("recommended_action", "Advisory hold"),
                    "reason_for_ranking": f"Fallback explainability: strongest drivers {top_positive}; key drag {top_negative}.",
                    "top_positive_contributors": positives,
                    "top_negative_contributors": negatives,
                    "sector_percentile": 50.0,
                    "universe_percentile": 50.0,
                    "missing_data_flags": ["endpoint.scores_explainability_unavailable"],
                }
            )

        all_scores = [item["composite"] for item in items]
        sector_buckets: dict[str, list[float]] = {}
        for item in items:
            sector_buckets.setdefault(item["sector"], []).append(item["composite"])
        for item in items:
            item["universe_percentile"] = _percentile(item["composite"], all_scores)
            item["sector_percentile"] = _percentile(item["composite"], sector_buckets.get(item["sector"], []))

        items.sort(key=lambda item: item["composite"], reverse=True)
        return {"as_of": "fallback", "universe_size": len(items), "items": items}


all_payload = fetch_explainability(100)
all_rows = all_payload.get("items", [])
sector_options = ["All"] + sorted({row.get("sector", "Diversified") for row in all_rows})
sector = st.selectbox("Sector", sector_options, index=0)

rows = all_rows
if sector != "All":
    rows = [row for row in rows if row.get("sector", "").lower() == sector.lower()]
rows = rows[:limit]
payload = {"as_of": all_payload.get("as_of", "n/a"), "items": rows}

if not rows:
    st.info("No explainability rows available.")
else:
    st.metric("As of", payload.get("as_of", "n/a"))
    df = pd.DataFrame(rows)

    summary_columns = [
        "ticker",
        "sector",
        "quality",
        "value",
        "momentum",
        "financial_health",
        "composite",
        "sector_percentile",
        "universe_percentile",
        "recommended_action",
    ]
    display_df = df[[col for col in summary_columns if col in df.columns]].copy()
    st.dataframe(display_df, use_container_width=True)

    ticker = st.selectbox("Ticker detail", display_df["ticker"].tolist(), index=0)
    selected = next(row for row in rows if row["ticker"] == ticker)

    st.subheader(f"{ticker} explanation")
    st.write(selected.get("reason_for_ranking", "No reason available."))

    p1, p2 = st.columns(2)
    p1.metric("Sector percentile", selected.get("sector_percentile", 0))
    p2.metric("Universe percentile", selected.get("universe_percentile", 0))

    st.markdown("**Top 5 positive contributors**")
    pos_df = pd.DataFrame(selected.get("top_positive_contributors", []))
    if pos_df.empty:
        st.caption("No positive contributors detected.")
    else:
        st.dataframe(pos_df, use_container_width=True)

    st.markdown("**Top 5 negative contributors**")
    neg_df = pd.DataFrame(selected.get("top_negative_contributors", []))
    if neg_df.empty:
        st.caption("No negative contributors detected.")
    else:
        st.dataframe(neg_df, use_container_width=True)

    st.markdown("**Missing data flags**")
    flags = selected.get("missing_data_flags", [])
    if not flags:
        st.caption("No missing data flags.")
    else:
        st.dataframe(pd.DataFrame({"flag": flags}), use_container_width=True)
