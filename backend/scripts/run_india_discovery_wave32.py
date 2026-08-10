from __future__ import annotations

import json
from pathlib import Path

from piios_backend.schemas.recommendation import RecommendationGenerateRequest
from piios_backend.services.recommendation_mvp import RecommendationMVPService

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / "runtime" / "wave32_india_discovery.json"


def _fmt(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _table(rows, headers):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    sep = " | "
    out = [sep.join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    out.append(sep.join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        out.append(sep.join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(out)


def _naive_screen(top_ranked):
    rows = []
    for r in top_ranked:
        quality = r.get("quality")
        growth = r.get("growth")
        momentum = r.get("momentum")
        valuation = r.get("valuation")
        if not all(isinstance(x, (int, float)) for x in [quality, growth, momentum, valuation]):
            continue
        if quality >= 60 and growth >= 60 and momentum >= 55 and valuation >= 50:
            rows.append(r)
    rows.sort(key=lambda x: (float(x.get("quality") or 0) + float(x.get("growth") or 0) + float(x.get("momentum") or 0) + float(x.get("valuation") or 0)), reverse=True)
    return rows


def main() -> None:
    svc = RecommendationMVPService()
    req = RecommendationGenerateRequest(
        investable_amount=5000.0,
        market_data_mode="live",
        use_demo_portfolio=False,
        eligible_markets=["India"],
        base_currency="USD",
    )
    result = svc.generate(req)

    top_ranked = [r for r in result.top_ranked_candidates if r.get("market") == "India"]
    top_discovery = sorted(top_ranked, key=lambda r: (float(r.get("discovery_score") or 0), float(r.get("combined_recommendation_score") or 0)), reverse=True)

    mid = [r for r in top_discovery if r.get("market_cap_bucket") == "MID" and r.get("discovery_status") in {"DISCOVER", "RESEARCH"}][:10]
    small = [r for r in top_discovery if r.get("market_cap_bucket") in {"SMALL", "MICRO_OR_UNKNOWN"} and r.get("discovery_status") in {"DISCOVER", "RESEARCH"}][:10]

    top20 = top_discovery[:20]
    top10_deep = top_discovery[:10]

    naive = _naive_screen(top_ranked)
    naive_top = naive[:20]
    piios_tickers = {r["ticker"] for r in top20}
    naive_tickers = {r["ticker"] for r in naive_top}

    overlap = sorted(piios_tickers.intersection(naive_tickers))
    piios_only = sorted(piios_tickers - naive_tickers)
    naive_only = sorted(naive_tickers - piios_tickers)

    print("\\n=== A. Expanded Universe & Provider Quality ===")
    india_stats = result.data_quality_summary.get("market_retrieval_stats", {}).get("India", {})
    print(json.dumps({
        "configured": result.universe_summary["markets"]["India"]["total_seed"],
        "eligible": result.universe_summary["markets"]["India"]["eligible"],
        "partial": result.universe_summary["markets"]["India"]["partial"],
        "ineligible": result.universe_summary["markets"]["India"]["ineligible"],
        "coverage": india_stats,
        "size_counts_top_ranked": result.screening_summary.get("discovery_size_counts", {}),
    }, indent=2))

    print("\\n=== B. Top 20 Discovery Candidates ===")
    rows = []
    for i, r in enumerate(top20, start=1):
        rows.append([
            i,
            r.get("ticker"),
            r.get("company"),
            r.get("market_cap_bucket"),
            r.get("sector") or "-",
            _fmt(r.get("discovery_score")),
            _fmt(r.get("security_attractiveness_score")),
            _fmt(r.get("evidence_coverage")),
            f"{r.get('liquidity_status')}({_fmt(r.get('liquidity_score'))})",
            _fmt(r.get("confidence")),
            r.get("discovery_status"),
        ])
    print(_table(rows, ["Rank", "Ticker", "Company", "Size", "Sector", "Discovery", "Attract", "Evidence", "Liquidity", "Confidence", "Status"]))

    print("\\n=== C. Top 10 Mid-Cap Research Candidates ===")
    rows = []
    for i, r in enumerate(mid, start=1):
        rows.append([i, r.get("ticker"), r.get("company"), _fmt(r.get("discovery_score")), _fmt(r.get("combined_recommendation_score")), r.get("discovery_status")])
    print(_table(rows, ["Rank", "Ticker", "Company", "Discovery", "Combined", "Status"]))

    print("\\n=== D. Top 10 Small-Cap Research Candidates ===")
    rows = []
    for i, r in enumerate(small, start=1):
        rows.append([i, r.get("ticker"), r.get("company"), r.get("market_cap_bucket"), _fmt(r.get("discovery_score")), _fmt(r.get("combined_recommendation_score")), r.get("discovery_status")])
    print(_table(rows, ["Rank", "Ticker", "Company", "Size", "Discovery", "Combined", "Status"]))

    print("\\n=== E. Deep Dive Top 10 Discoveries ===")
    rows = []
    for r in top10_deep:
        rows.append([
            r.get("ticker"),
            r.get("company"),
            r.get("market_cap_bucket"),
            _fmt(r.get("market_cap")),
            _fmt(r.get("quality")),
            _fmt(r.get("growth")),
            _fmt(r.get("valuation")),
            _fmt(r.get("momentum")),
            _fmt(r.get("risk")),
            _fmt(r.get("discovery_score")),
            _fmt(r.get("security_attractiveness_score")),
            _fmt(r.get("portfolio_suitability_score")),
            _fmt(r.get("confidence")),
            ",".join(r.get("discovery_reason_codes") or []),
            ",".join(r.get("challenge_flags") or []),
        ])
    print(_table(rows, ["Ticker", "Company", "Size", "MCap", "Q", "G", "V", "M", "R", "Disc", "Attr", "Suit", "Conf", "WhatChanged", "Risks"]))

    print("\\n=== F. Naive Screener Comparison ===")
    print(json.dumps({
        "naive_count": len(naive_top),
        "overlap": overlap,
        "piios_only": piios_only,
        "naive_only": naive_only,
    }, indent=2))

    print("\\n=== G. Risk/Liquidity Challenge Snapshot ===")
    challenge_rows = []
    for r in top20:
        challenge_rows.append([r.get("ticker"), r.get("liquidity_status"), r.get("investability_status"), ",".join(r.get("challenge_flags") or [])])
    print(_table(challenge_rows, ["Ticker", "Liquidity", "Investability", "Challenges"]))

    payload = {
        "response": result.model_dump(),
        "top20_discovery": top20,
        "top10_mid": mid,
        "top10_small": small,
        "top10_deep": top10_deep,
        "naive_top20": naive_top,
        "comparison": {"overlap": overlap, "piios_only": piios_only, "naive_only": naive_only},
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2))
    print(f"\\nSaved full discovery payload to {OUT_JSON}")


if __name__ == "__main__":
    main()
