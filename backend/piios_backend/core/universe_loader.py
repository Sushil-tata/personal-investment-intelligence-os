from __future__ import annotations

from pathlib import Path


def load_india_universe() -> list[str]:
    path = Path(__file__).resolve().parents[1] / "data" / "universe_india.txt"
    if not path.exists():
        raise FileNotFoundError(f"Missing India universe file: {path}")

    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        ticker = line.strip().upper()
        if ticker and not ticker.startswith("#"):
            out.append(ticker)
    return sorted(set(out))