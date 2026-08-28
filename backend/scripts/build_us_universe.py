"""Build a reproducible large/mid/small-cap US universe.

The published S&P 500, S&P MidCap 400, and S&P SmallCap 600 constituent tables
are retrieved through the MediaWiki API. The page URLs and retrieval vintage
are embedded in the generated universe file.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
OUT_FILE = ROOT / "backend" / "piios_backend" / "data" / "universe_us.txt"
API_URL = "https://en.wikipedia.org/w/api.php"
PAGES = [
    "List_of_S&P_500_companies",
    "List_of_S&P_400_companies",
    "List_of_S&P_600_companies",
]
USER_AGENT = "PIIOS-universe-builder/1.0 (local research use)"


def _read_symbols(page: str) -> list[str]:
    response = requests.get(
        API_URL,
        params={"action": "parse", "page": page, "prop": "text", "format": "json", "origin": "*"},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if "parse" not in payload:
        raise RuntimeError(f"MediaWiki did not return page content for {page}: {payload}")
    soup = BeautifulSoup(payload["parse"]["text"]["*"], "html.parser")
    for table in soup.select("table.wikitable"):
        rows = table.select("tr")
        if not rows:
            continue
        headers = [cell.get_text(" ", strip=True) for cell in rows[0].select("th,td")]
        if not headers or headers[0] not in {"Symbol", "Ticker", "Ticker symbol"}:
            continue
        symbols = []
        for row in rows[1:]:
            cells = row.select("th,td")
            if cells:
                symbol = cells[0].get_text(" ", strip=True).upper().replace(".", "-")
                if symbol:
                    symbols.append(symbol)
        return symbols
    raise RuntimeError(f"No constituent table found for {page}")


def build() -> list[str]:
    return sorted({symbol for page in PAGES for symbol in _read_symbols(page)})


def main() -> None:
    tickers = build()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    provenance = [
        "# Universe: S&P Composite 1500 tiers (S&P 500 + MidCap 400 + SmallCap 600)",
        f"# Source API: {API_URL}",
        "# Source pages: " + ", ".join(f"https://en.wikipedia.org/wiki/{page}" for page in PAGES),
        f"# Retrieved: {retrieved_at}",
    ]
    OUT_FILE.write_text("\n".join(provenance + tickers) + "\n")
    print(f"wrote {len(tickers)} tickers to {OUT_FILE}")


if __name__ == "__main__":
    main()