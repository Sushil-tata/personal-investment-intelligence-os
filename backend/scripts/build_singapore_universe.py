"""Build the published SGX stock-screener universe."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT_FILE = ROOT / "backend" / "piios_backend" / "data" / "universe_singapore.txt"
SOURCE_URL = "https://api.sgx.com/stockscreener/v2.0/all"
SOURCE_PAGE = "https://investors.sgx.com/stock-screener"
FIELDS = "exchange,exchangeCountryCode,companyName,stockCode,marketCapitalization,salesTTM,priceToEarningsRatio,dividendYield,fourWeekPricePercentChange,thirteenWeekPricePercentChange,twentySixWeekPricePercentChange,fiftyTwoWeekPricePercentChange,netProfitMargin,returnOnAvgCommonEquity,priceToCashFlowPerShareRatio,totalDebtToTotalEquityRatio,salesPercentageChange,sector,priceToBookRatio,priceCurrCode"
VALID_CODE = re.compile(r"^[A-Z0-9]+$")


def build() -> list[str]:
    response = requests.get(
        SOURCE_URL,
        params={"params": FIELDS},
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://investors.sgx.com/"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError(f"SGX did not return stock rows: {payload}")
    codes = {
        str(row.get("stockCode") or "").strip().upper()
        for row in rows
        if isinstance(row, dict)
    }
    return sorted(f"{code}.SI" for code in codes if VALID_CODE.fullmatch(code))


def main() -> None:
    tickers = build()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    provenance = [
        "# Universe: all records returned by the official SGX stock screener",
        f"# Source page: {SOURCE_PAGE}",
        f"# Source API: {SOURCE_URL}",
        f"# Retrieved: {retrieved_at}",
    ]
    OUT_FILE.write_text("\n".join(provenance + tickers) + "\n")
    print(f"wrote {len(tickers)} tickers to {OUT_FILE}")


if __name__ == "__main__":
    main()