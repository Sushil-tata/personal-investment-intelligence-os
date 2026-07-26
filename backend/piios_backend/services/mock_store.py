import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from piios_backend.schemas.domain import JournalEntry, PortfolioSnapshot, Recommendation, TacticalSignal


class MockStore:
    def __init__(self) -> None:
        self.root = Path(__file__).resolve().parents[2] / "data" / "mock"
        self.root.mkdir(parents=True, exist_ok=True)

    def _load_json(self, name: str):
        path = self.root / name
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _dump_json(self, name: str, payload) -> None:
        (self.root / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_holdings(self):
        return self._load_json("holdings.json")

    def get_watchlist(self):
        return self._load_json("watchlist.json")

    def get_recommendations(self) -> list[Recommendation]:
        return [Recommendation.model_validate(x) for x in self._load_json("recommendations.json")]

    def get_journal(self) -> list[JournalEntry]:
        return [JournalEntry.model_validate(x) for x in self._load_json("journal_entries.json")]

    def get_signals(self) -> list[TacticalSignal]:
        return [TacticalSignal.model_validate(x) for x in self._load_json("tactical_signals.json")]

    def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        holdings = self.get_holdings()
        total = sum(float(item["value"]) for item in holdings)
        return PortfolioSnapshot(
            as_of=datetime.now(timezone.utc).isoformat(),
            total_value=total,
            holdings=holdings,
        )

    def export_csv(self, rows: list[dict]) -> str:
        if not rows:
            return ""
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()

    def import_csv(self, content: str) -> list[dict]:
        return list(csv.DictReader(io.StringIO(content)))
