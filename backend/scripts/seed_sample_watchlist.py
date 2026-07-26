import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "mock"


def main() -> None:
    payload = [
        {"watchlist_id": "w1", "ticker": "NVDA", "note": "AI compute moat", "bucket": "Strategic Alpha"}
    ]
    (ROOT / "watchlist.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
