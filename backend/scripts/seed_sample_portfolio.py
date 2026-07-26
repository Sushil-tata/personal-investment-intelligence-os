import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "mock"


def main() -> None:
    payload = [
        {
            "snapshot_id": "p1",
            "owner": "NRI Investor",
            "total_value": 900000,
            "holdings": [
                {
                    "holding_id": "h1",
                    "ticker": "VTI",
                    "name": "Vanguard Total Stock Market ETF",
                    "quantity": 15,
                    "market_value": 4200,
                    "bucket": "Education"
                }
            ]
        }
    ]
    (ROOT / "portfolio_snapshots.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
