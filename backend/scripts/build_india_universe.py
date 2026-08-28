"""Build a broad, reproducible India universe for Wave 3.2 discovery.

Usage:
    python backend/scripts/build_india_universe.py

This script downloads the NSE NIFTY Total Market constituent file, appends .NS,
and writes backend/piios_backend/data/universe_india.txt with source provenance.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT_FILE = ROOT / "backend" / "piios_backend" / "data" / "universe_india.txt"

NSE_INDEX_FILES = ["ind_niftytotalmarket_list.csv"]
BASE_URL = "https://archives.nseindia.com/content/indices/"


def _read_symbols_from_url(filename: str) -> list[str]:
    url = BASE_URL + filename
    with urlopen(url, timeout=20) as resp:  # nosec B310 - trusted static URL list
        raw = resp.read().decode("utf-8", errors="replace").splitlines()
    reader = csv.DictReader(raw)
    out: list[str] = []
    for row in reader:
        symbol = (row.get("Symbol") or "").strip().upper()
        if not symbol:
            continue
        out.append(symbol)
    return out


def build() -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for filename in NSE_INDEX_FILES:
        for symbol in _read_symbols_from_url(filename):
            ticker = f"{symbol}.NS"
            if ticker in seen:
                continue
            seen.add(ticker)
            ordered.append(ticker)
    return ordered


def main() -> None:
    tickers = build()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    provenance = [
        "# Universe: NIFTY Total Market constituents",
        f"# Source: {BASE_URL}{NSE_INDEX_FILES[0]}",
        f"# Retrieved: {retrieved_at}",
    ]
    OUT_FILE.write_text("\n".join(provenance + tickers) + "\n")
    print(f"wrote {len(tickers)} tickers to {OUT_FILE}")


if __name__ == "__main__":
    main()
