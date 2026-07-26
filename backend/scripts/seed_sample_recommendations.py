import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "mock"


def main() -> None:
    payload = [
        {
            "recommendation_id": "r1",
            "ticker": "NVDA",
            "bucket": "Strategic Alpha",
            "bull_case": "Strong demand",
            "bear_case": "Compression risk",
            "why_now": "Momentum",
            "why_not_now": "Valuation",
            "thesis_invalidation_trigger": "Margin drop",
            "position_size_suggestion": "2%",
            "time_horizon": "2-5 years",
            "confidence_score": 76,
            "data_freshness_timestamp": "2026-06-03T00:00:00Z",
            "source_links": ["https://example.com"],
            "rationale": "Scoring pass",
            "data_source": "mock",
            "model_version": "piios-model-0.1.0",
            "advisory_only": true
        }
    ]
    (ROOT / "recommendations.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
