from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

for path in (ROOT, BACKEND):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def fx_rates_base() -> dict[str, Decimal]:
    return {
        "USD/USD": Decimal("1"),
        "INR/USD": Decimal("0.012"),
        "SGD/USD": Decimal("0.74"),
    }
