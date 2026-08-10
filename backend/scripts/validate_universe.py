"""Validate candidate universes using yfinance and produce a coverage report.

Usage:
    python backend/scripts/validate_universe.py

This script classifies each configured ticker into one of:
    - VALID
    - INVALID
    - STALE_DELISTED
    - PROVIDER_UNAVAILABLE

The output includes per-market transparency stats to support pure, non-patched
universe hygiene workflows.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "backend" / "piios_backend" / "data"
TICKER_ALLOWED = re.compile(r"^[A-Z0-9.-]+$")
MAX_STALE_DAYS = 14

VALID = "VALID"
INVALID = "INVALID"
STALE_DELISTED = "STALE_DELISTED"
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"


def load_universe(filename: str) -> list[str]:
    p = DATA_DIR / filename
    if not p.exists():
        return []
    lines = [l.strip() for l in p.read_text().splitlines() if l.strip()]
    return lines


def _sanitize_ticker(raw: str) -> str | None:
    ticker = str(raw).strip().upper()
    if not ticker:
        return None
    if " " in ticker or "(" in ticker or ")" in ticker:
        return None
    if not TICKER_ALLOWED.match(ticker):
        return None
    return ticker


def _provider_unavailable_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    signatures = [
        "timed out",
        "timeout",
        "temporar",
        "connection",
        "rate limit",
        "too many requests",
        "service unavailable",
        "forbidden",
    ]
    return any(sig in msg for sig in signatures)


def validate_ticker(raw_ticker: str) -> dict:
    ticker = _sanitize_ticker(raw_ticker)
    result = {
        "ticker": raw_ticker,
        "normalized_ticker": ticker,
        "provider": "yfinance",
        "status": INVALID,
        "reason": "invalid_symbol_format",
        "as_of": None,
        "name": None,
        "currency": None,
        "missing_fields": [],
        "eligible_for_screening": False,
    }
    if ticker is None:
        return result

    result["ticker"] = ticker
    result["reason"] = None
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        hist = tk.history(period="5d", interval="1d", timeout=6)

        if hist is None or hist.empty:
            result["status"] = STALE_DELISTED
            result["reason"] = "empty_history"
            result["missing_fields"].append("history")
        else:
            last_ts = hist.index[-1]
            result["as_of"] = last_ts.isoformat()
            age_days = (datetime.now(timezone.utc).date() - last_ts.date()).days
            if age_days > MAX_STALE_DAYS:
                result["status"] = STALE_DELISTED
                result["reason"] = f"stale_history_{age_days}d"
            else:
                result["status"] = VALID
                result["reason"] = None

        result["name"] = info.get("longName") or info.get("shortName")
        result["currency"] = info.get("currency")
        for fld in ["marketCap", "regularMarketPrice", "trailingPE", "totalDebt"]:
            if fld not in info or info.get(fld) is None:
                result["missing_fields"].append(fld)

        result["eligible_for_screening"] = result["status"] == VALID
    except Exception as exc:
        result["status"] = PROVIDER_UNAVAILABLE if _provider_unavailable_error(exc) else STALE_DELISTED
        result["reason"] = str(exc)
        result["missing_fields"].append("provider_error")
    return result


def run():
    universes = {
        "US": load_universe("universe_us.txt"),
        "India": load_universe("universe_india.txt"),
        "Singapore": load_universe("universe_singapore.txt"),
    }

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "markets": {},
    }

    for market, tickers in universes.items():
        market_report = {"configured": len(tickers), "rows": []}
        for t in tickers:
            res = validate_ticker(t)
            market_report["rows"].append(res)

        valid_rows = [r for r in market_report["rows"] if r["status"] == VALID]
        invalid_rows = [r for r in market_report["rows"] if r["status"] == INVALID]
        stale_rows = [r for r in market_report["rows"] if r["status"] == STALE_DELISTED]
        provider_rows = [r for r in market_report["rows"] if r["status"] == PROVIDER_UNAVAILABLE]
        configured = market_report["configured"] or 1

        report["markets"][market] = {
            "configured": market_report["configured"],
            "valid": len(valid_rows),
            "invalid": len(invalid_rows),
            "stale_delisted": len(stale_rows),
            "provider_unavailable": len(provider_rows),
            "success_rate": round((len(valid_rows) / configured) * 100.0, 2),
            "rows": market_report["rows"],
            "status_breakdown": {
                VALID: len(valid_rows),
                INVALID: len(invalid_rows),
                STALE_DELISTED: len(stale_rows),
                PROVIDER_UNAVAILABLE: len(provider_rows),
            },
            "valid_preview": valid_rows[:20],
            "invalid_preview": invalid_rows[:20],
            "stale_delisted_preview": stale_rows[:20],
            "provider_unavailable_preview": provider_rows[:20],
        }

    aggregate_configured = sum(v["configured"] for v in report["markets"].values())
    aggregate_valid = sum(v["valid"] for v in report["markets"].values())
    report["summary"] = {
        "configured": aggregate_configured,
        "valid": aggregate_valid,
        "invalid": sum(v["invalid"] for v in report["markets"].values()),
        "stale_delisted": sum(v["stale_delisted"] for v in report["markets"].values()),
        "provider_unavailable": sum(v["provider_unavailable"] for v in report["markets"].values()),
        "success_rate": round((aggregate_valid / (aggregate_configured or 1)) * 100.0, 2),
    }

    out_file = DATA_DIR / "universe_validation.json"
    out_file.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
