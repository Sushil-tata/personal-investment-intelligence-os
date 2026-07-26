from datetime import datetime, timezone
from pathlib import Path

import yaml

from piios_backend.core.config import settings
from piios_backend.schemas.enums import Bucket, RecommendationStatus
from piios_backend.schemas.journal import JournalEntry
from piios_backend.schemas.portfolio import DriftItem, Holding, PortfolioDriftResponse, PortfolioSnapshot, WatchlistIdea
from piios_backend.schemas.recommendation import Recommendation, TacticalSignal
from piios_backend.schemas.thesis import InvestmentThesis, ThesisCreateRequest


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deep_get(data: dict, key: str) -> dict:
    value = data.get(key, {})
    return value if isinstance(value, dict) else {}


class InMemoryStore:
    def __init__(self) -> None:
        self.holdings: list[Holding] = [
            Holding(
                holding_id="h1",
                ticker="VTI",
                name="Vanguard Total Stock Market ETF",
                quantity=15,
                market_value=4200,
                bucket=Bucket.EDUCATION,
                geography="US",
                currency="USD",
                asset_class="ETF",
                sector="Broad Market",
                theme="Global Core",
            ),
            Holding(
                holding_id="h2",
                ticker="NPS",
                name="National Pension System",
                quantity=1,
                market_value=15000,
                bucket=Bucket.RETIREMENT,
                geography="India",
                currency="INR",
                asset_class="Retirement Fund",
                sector="Diversified",
                theme="Retirement Core",
            )
        ]
        self.watchlist: list[WatchlistIdea] = [
            WatchlistIdea(watchlist_id="w1", ticker="NVDA", note="AI infra leader", bucket=Bucket.STRATEGIC_ALPHA)
        ]
        self.recommendations: list[Recommendation] = [
            Recommendation(
                recommendation_id="r1",
                ticker="NVDA",
                thesis_id="t1",
                bucket=Bucket.STRATEGIC_ALPHA,
                portfolio_bucket=Bucket.STRATEGIC_ALPHA,
                bull_case="Strong pricing power and ecosystem lock-in.",
                bear_case="Multiple compression if growth normalizes.",
                why_now="Earnings momentum and demand visibility remain robust.",
                why_not_now="Valuation can overshoot fair value in risk-off periods.",
                thesis_invalidation_trigger="Two consecutive quarters of sharp margin erosion.",
                position_size_suggestion="2-3% initial position in Strategic Alpha bucket.",
                time_horizon="2-5 years",
                confidence_score=76,
                portfolio_fit_score=74,
                data_freshness_timestamp=now_iso(),
                source_documents=["rd1"],
                source_links=["https://example.com/research/nvda"],
                rationale="Blended fundamental and trend score exceeds threshold.",
                data_source="mock",
                model_version=settings.model_version,
                status=RecommendationStatus.APPROVED,
                created_at=now_iso(),
                updated_at=now_iso(),
                approved_by="system_seed",
                advisory_only=True,
            )
        ]
        self.signals: list[TacticalSignal] = [
            TacticalSignal(
                signal_id="s1",
                ticker="AVGO",
                status="Watch",
                entry_zone="1600-1640",
                invalidation="Daily close below 1540",
                target="1740",
                bucket=Bucket.TACTICAL_OPPORTUNITIES,
                advisory_only=True,
            )
        ]
        self.journal: list[JournalEntry] = [
            JournalEntry(
                entry_id="j1",
                ticker="AVGO",
                notes="Waited for setup confirmation",
                outcome="open",
                bucket=Bucket.TACTICAL_OPPORTUNITIES,
                created_at=now_iso(),
            )
        ]
        self.snapshots: list[PortfolioSnapshot] = [
            PortfolioSnapshot(snapshot_id="p1", owner="NRI Investor", total_value=900000.0, holdings=self.holdings)
        ]
        self.theses: list[InvestmentThesis] = [
            InvestmentThesis(
                thesis_id="t1",
                ticker="NVDA",
                asset_name="NVIDIA",
                theme="AI Infrastructure",
                bucket=Bucket.STRATEGIC_ALPHA,
                thesis="Core AI compute enabler with durable demand tailwinds.",
                bull_case="Scale advantage and software ecosystem support premium pricing.",
                bear_case="Valuation and cyclical semiconductor demand shocks.",
                why_now="Visibility on demand and product cycle remains favorable.",
                why_not_now="Positioning is crowded and can mean-revert quickly.",
                invalidation_trigger="Multi-quarter margin contraction and loss of data-center momentum.",
                valuation_notes="Premium multiple requires growth delivery.",
                expected_holding_period="2-5 years",
                source_documents=["rd1"],
                confidence_score=76,
                status=RecommendationStatus.RESEARCHED,
                created_at=now_iso(),
                updated_at=now_iso(),
            )
        ]
        config_root = Path(__file__).resolve().parents[2] / "config" / "scoring"
        self.target_allocation = yaml.safe_load((config_root / "target_allocation.yaml").read_text(encoding="utf-8"))
        self.drift_thresholds = yaml.safe_load((config_root / "drift_thresholds.yaml").read_text(encoding="utf-8"))

    def visible_recommendations(self) -> list[Recommendation]:
        return [item for item in self.recommendations if item.status == RecommendationStatus.APPROVED]

    def recommendation_queue(self) -> list[Recommendation]:
        return self.recommendations

    def update_recommendation_status(self, recommendation_id: str, status: RecommendationStatus, approved_by: str | None) -> Recommendation | None:
        for item in self.recommendations:
            if item.recommendation_id == recommendation_id:
                item.status = status
                item.updated_at = now_iso()
                if approved_by:
                    item.approved_by = approved_by
                return item
        return None

    def list_theses(self) -> list[InvestmentThesis]:
        return self.theses

    def get_thesis(self, thesis_id: str) -> InvestmentThesis | None:
        for thesis in self.theses:
            if thesis.thesis_id == thesis_id:
                return thesis
        return None

    def create_thesis(self, request: ThesisCreateRequest) -> InvestmentThesis:
        thesis = InvestmentThesis(
            thesis_id=f"t{len(self.theses)+1}",
            status=RecommendationStatus.DRAFT,
            created_at=now_iso(),
            updated_at=now_iso(),
            **request.model_dump(),
        )
        self.theses.append(thesis)
        return thesis

    def update_thesis_status(self, thesis_id: str, status: RecommendationStatus) -> InvestmentThesis | None:
        thesis = self.get_thesis(thesis_id)
        if thesis:
            thesis.status = status
            thesis.updated_at = now_iso()
        return thesis

    def calculate_drift(self) -> PortfolioDriftResponse:
        total_value = sum(item.market_value for item in self.holdings) or 1
        thresholds = self.drift_thresholds.get("thresholds", {})

        def severity_for(drift_pct: float) -> str:
            abs_val = abs(drift_pct)
            if abs_val >= thresholds.get("high", 15):
                return "HIGH"
            if abs_val >= thresholds.get("medium", 8):
                return "MEDIUM"
            return "LOW"

        dimensions = {
            "bucket": lambda h: h.bucket.value if h.bucket else "Unknown",
            "geography": lambda h: h.geography,
            "currency": lambda h: h.currency,
            "asset_class": lambda h: h.asset_class,
            "sector": lambda h: h.sector,
            "theme": lambda h: h.theme,
        }

        items: list[DriftItem] = []
        targets = self.target_allocation.get("targets", {})
        for dimension, key_fn in dimensions.items():
            actual_map: dict[str, float] = {}
            for holding in self.holdings:
                key = key_fn(holding)
                actual_map[key] = actual_map.get(key, 0.0) + holding.market_value

            actual_pct = {k: (v / total_value) * 100 for k, v in actual_map.items()}
            target_map = _deep_get(targets, dimension)
            for key, target_percentage in target_map.items():
                actual_percentage = actual_pct.get(key, 0.0)
                drift_pct = actual_percentage - float(target_percentage)
                drift_amount = (drift_pct / 100.0) * total_value
                sev = severity_for(drift_pct)
                action = "Rebalance toward target" if sev != "LOW" else "Monitor"
                items.append(
                    DriftItem(
                        dimension=dimension,
                        key=key,
                        target_percentage=float(target_percentage),
                        actual_percentage=round(actual_percentage, 2),
                        drift_amount=round(drift_amount, 2),
                        drift_percentage=round(drift_pct, 2),
                        severity=sev,
                        recommended_action=action,
                        advisory_only=True,
                    )
                )
        return PortfolioDriftResponse(generated_at=now_iso(), items=items)


store = InMemoryStore()
