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

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "backend" / "piios_backend" / "data"
TICKER_ALLOWED = re.compile(r"^[A-Z0-9.&-]+$")
MAX_STALE_DAYS = 14
HISTORY_PERIOD = "3mo"
MAX_WORKERS = 2
RESUME_BATCH_SIZE = 100

MARKET_CONFIG = {
    "US": {
        "currency": "USD",
        "liquidity_threshold": 10_000_000.0,
        "cap_tiers": [(10_000_000_000.0, "LARGE"), (2_000_000_000.0, "MID"), (300_000_000.0, "SMALL")],
    },
    "India": {
        "currency": "INR",
        "liquidity_threshold": 25_000_000.0,
        "cap_tiers": [(500_000_000_000.0, "LARGE"), (160_000_000_000.0, "MID"), (50_000_000_000.0, "SMALL")],
    },
    "Singapore": {
        "currency": "SGD",
        "liquidity_threshold": 1_200_000.0,
        "cap_tiers": [(10_000_000_000.0, "LARGE"), (2_000_000_000.0, "MID"), (300_000_000.0, "SMALL")],
    },
}

VALID = "VALID"
INVALID = "INVALID"
STALE_DELISTED = "STALE_DELISTED"
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"


def load_universe(filename: str) -> list[str]:
    p = DATA_DIR / filename
    if not p.exists():
        return []
    lines = [
        line.strip()
        for line in p.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return lines


def market_cap_tier(market: str, market_cap: object) -> str | None:
    config = MARKET_CONFIG.get(market)
    if config is None or not isinstance(market_cap, (int, float)) or market_cap <= 0:
        return None
    for threshold, tier in config["cap_tiers"]:
        if market_cap >= threshold:
            return tier
    return "MICRO"


def median_daily_traded_value(history) -> float | None:
    if history is None or history.empty or "Volume" not in history:
        return None
    price_column = "Adj Close" if "Adj Close" in history else "Close"
    if price_column not in history:
        return None
    values = (history[price_column] * history["Volume"]).dropna()
    values = values[values >= 0]
    if values.empty:
        return None
    return float(median(float(value) for value in values))


def _sanitize_ticker(raw: str) -> str | None:
    ticker = str(raw).strip().upper()
    if not ticker:
        return None
    if " " in ticker or "(" in ticker or ")" in ticker:
        return None
    if not TICKER_ALLOWED.match(ticker):
        return None
    return ticker


def validate_ticker(raw_ticker: str, market: str) -> dict:
    ticker = _sanitize_ticker(raw_ticker)
    config = MARKET_CONFIG[market]
    result = {
        "ticker": raw_ticker,
        "normalized_ticker": ticker,
        "provider": "yfinance",
        "status": INVALID,
        "reason": "invalid_symbol_format",
        "as_of": None,
        "name": None,
        "currency": None,
        "quote_type": None,
        "market_cap": None,
        "market_cap_currency": None,
        "cap_tier_currency": config["currency"],
        "cap_tier": None,
        "liquidity_window": HISTORY_PERIOD,
        "median_daily_traded_value": None,
        "liquidity_threshold": config["liquidity_threshold"],
        "liquidity_status": "DATA_PENDING",
        "eligibility_status": "NOT_VALIDATED",
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
        hist = tk.history(period=HISTORY_PERIOD, interval="1d", auto_adjust=False, timeout=10)

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
        result["market_cap_currency"] = info.get("currency")
        result["quote_type"] = info.get("quoteType")
        market_cap = info.get("marketCap")
        result["market_cap"] = float(market_cap) if isinstance(market_cap, (int, float)) else None
        if result["market_cap_currency"] == config["currency"]:
            result["cap_tier"] = market_cap_tier(market, market_cap)
        elif market_cap is not None:
            result["missing_fields"].append("marketCapCurrencyConversion")
        traded_value = median_daily_traded_value(hist)
        result["median_daily_traded_value"] = traded_value
        if traded_value is not None:
            result["liquidity_status"] = (
                "PASS" if traded_value >= config["liquidity_threshold"] else "FAIL"
            )
        for fld in ["marketCap", "regularMarketPrice", "trailingPE", "totalDebt"]:
            if fld not in info or info.get(fld) is None:
                result["missing_fields"].append(fld)

        if result["status"] == VALID:
            pending = []
            if result["cap_tier"] is None:
                pending.append(
                    "MARKET_CAP_CURRENCY"
                    if market_cap is not None and result["market_cap_currency"] != config["currency"]
                    else "MARKET_CAP"
                )
            if traded_value is None:
                pending.append("LIQUIDITY")
            if pending:
                result["eligibility_status"] = "DATA_PENDING_" + "_AND_".join(pending)
            elif result["liquidity_status"] == "FAIL":
                result["eligibility_status"] = "INELIGIBLE_LIQUIDITY"
            else:
                result["eligibility_status"] = "ELIGIBLE"
                result["eligible_for_screening"] = True
        else:
            result["eligibility_status"] = "INELIGIBLE_LISTING_STATUS"
    except Exception as exc:
        result["status"] = PROVIDER_UNAVAILABLE
        result["reason"] = str(exc)
        result["missing_fields"].append("provider_error")
        result["eligibility_status"] = "DATA_PENDING_PROVIDER"
    return result


def _settled_row(row: dict) -> bool:
    status = row.get("status")
    reason = str(row.get("reason") or "")
    return status in {VALID, INVALID} or (
        status == STALE_DELISTED
        and (reason == "empty_history" or reason.startswith("stale_history_"))
    )


def run(
    *,
    resume: bool = False,
    workers: int = MAX_WORKERS,
    batch_size: int | None = None,
):
    universes = {
        "US": load_universe("universe_us.txt"),
        "India": load_universe("universe_india.txt"),
        "Singapore": load_universe("universe_singapore.txt"),
    }

    out_file = DATA_DIR / "universe_validation.json"
    previous_report = {}
    if resume and out_file.exists():
        try:
            previous_report = json.loads(out_file.read_text())
        except (OSError, json.JSONDecodeError):
            previous_report = {}

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "resumed_from_generated_at": previous_report.get("generated_at") if resume else None,
        "markets": {},
    }

    for market, tickers in universes.items():
        previous_rows: dict[str, dict] = {}
        for row in previous_report.get("markets", {}).get(market, {}).get("rows", []):
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "")
            if ticker:
                previous_rows[ticker] = row
        rows_by_ticker: dict[str, dict] = {
            ticker: previous_rows[ticker] for ticker in tickers if ticker in previous_rows
        }
        pending_tickers = [
            ticker
            for ticker in tickers
            if ticker not in previous_rows or not _settled_row(previous_rows[ticker])
        ]
        selected_tickers = pending_tickers[:batch_size] if batch_size is not None else pending_tickers
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {executor.submit(validate_ticker, ticker, market): ticker for ticker in selected_tickers}
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    rows_by_ticker[ticker] = future.result()
                except Exception as exc:
                    rows_by_ticker[ticker] = {
                        "ticker": ticker,
                        "status": PROVIDER_UNAVAILABLE,
                        "reason": str(exc),
                        "eligibility_status": "DATA_PENDING_PROVIDER",
                        "eligible_for_screening": False,
                    }
        for ticker in tickers:
            if ticker not in rows_by_ticker:
                rows_by_ticker[ticker] = {
                    "ticker": ticker,
                    "status": PROVIDER_UNAVAILABLE,
                    "reason": "not_attempted_resume_batch_limit",
                    "eligibility_status": "DATA_PENDING_PROVIDER",
                    "eligible_for_screening": False,
                    "missing_fields": ["provider_data"],
                }
        market_report = {"configured": len(tickers), "rows": [rows_by_ticker[ticker] for ticker in tickers]}

        valid_rows = [r for r in market_report["rows"] if r["status"] == VALID]
        invalid_rows = [r for r in market_report["rows"] if r["status"] == INVALID]
        stale_rows = [r for r in market_report["rows"] if r["status"] == STALE_DELISTED]
        provider_rows = [r for r in market_report["rows"] if r["status"] == PROVIDER_UNAVAILABLE]
        eligible_rows = [r for r in market_report["rows"] if r.get("eligible_for_screening") is True]
        cap_rows = [r for r in market_report["rows"] if r.get("cap_tier") is not None]
        liquidity_rows = [r for r in market_report["rows"] if r.get("median_daily_traded_value") is not None]
        configured = market_report["configured"] or 1

        report["markets"][market] = {
            "configured": market_report["configured"],
            "valid": len(valid_rows),
            "invalid": len(invalid_rows),
            "stale_delisted": len(stale_rows),
            "provider_unavailable": len(provider_rows),
            "success_rate": round((len(valid_rows) / configured) * 100.0, 2),
            "market_cap_coverage_rate": round((len(cap_rows) / configured) * 100.0, 2),
            "liquidity_coverage_rate": round((len(liquidity_rows) / configured) * 100.0, 2),
            "eligible": len(eligible_rows),
            "eligibility_rate": round((len(eligible_rows) / configured) * 100.0, 2),
            "resume_progress": {
                "pending_before_run": len(pending_tickers),
                "attempted_this_run": len(selected_tickers),
                "pending_after_run": sum(1 for row in market_report["rows"] if not _settled_row(row)),
            },
            "cap_tier_breakdown": {
                tier: sum(1 for row in cap_rows if row["cap_tier"] == tier)
                for tier in ["LARGE", "MID", "SMALL", "MICRO"]
            },
            "eligibility_breakdown": {
                status: sum(1 for row in market_report["rows"] if row.get("eligibility_status") == status)
                for status in sorted({str(row.get("eligibility_status")) for row in market_report["rows"]})
            },
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

    temporary_file = out_file.with_suffix(".json.tmp")
    temporary_file.write_text(json.dumps(report, indent=2))
    temporary_file.replace(out_file)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="Reuse prior VALID and STALE_DELISTED rows; retry all others.")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=RESUME_BATCH_SIZE,
        help="Maximum unresolved tickers to retry per market in a resume pass.",
    )
    args = parser.parse_args()
    run(
        resume=args.resume,
        workers=args.workers,
        batch_size=args.batch_size if args.resume else None,
    )
