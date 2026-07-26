import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "mock"


def main() -> None:
    payload = [
        {"ticker": "NVDA", "price": 1250.0, "timestamp": "2026-06-03T00:00:00Z"}
    ]
    (ROOT / "market_prices.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
