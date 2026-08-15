from __future__ import annotations

import argparse
import json
from pathlib import Path

from piios_backend.competition.runner import run_competition
from piios_backend.services.recommendation_mvp import assert_live_market_data_mode


MARKET_DATA_MODE = "live"


def main() -> None:
    assert_live_market_data_mode(MARKET_DATA_MODE, caller="run_stage_c_competition")
    parser = argparse.ArgumentParser(description="Run Stage C prospective competition framework")
    parser.add_argument(
        "--prospective-db",
        type=str,
        default="backend/runtime/prospective_ledger_proof/prospective_ledger.db",
        help="Path to prospective ledger sqlite DB",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="backend/runtime/stage_c_competition",
        help="Output directory for Stage C runtime artifacts",
    )
    parser.add_argument("--monthly-contribution", type=float, default=5000.0)
    args = parser.parse_args()

    result = run_competition(
        prospective_db_path=Path(args.prospective_db),
        output_root=Path(args.output_root),
        monthly_contribution=args.monthly_contribution,
    )

    print("Stage C competition run complete")
    print(f"start_month={result.start_month}")
    print(f"end_month={result.end_month}")
    print(f"contestants={len(result.leaderboard)}")
    summary_path = Path(args.output_root) / "competition_summary.json"
    current_rank_1 = result.leaderboard[0].strategy_id if result.leaderboard else "NONE"
    investment_conclusion = "UNKNOWN"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        current_rank_1 = str(summary.get("current_rank_1") or current_rank_1)
        investment_conclusion = str(summary.get("investment_conclusion") or investment_conclusion)
    print(f"current_rank_1={current_rank_1}")
    print(f"investment_conclusion={investment_conclusion}")


if __name__ == "__main__":
    main()
