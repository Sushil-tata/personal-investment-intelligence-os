from __future__ import annotations

import argparse
from datetime import date

from piios_backend.backtesting.runner import StageA1BacktestRunner, StageA1Config


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PIIOS Stage A1 PIT backtest")
    parser.add_argument("--start-date", type=_parse_date, default=date(2016, 1, 1))
    parser.add_argument("--end-date", type=_parse_date, default=date.today())
    parser.add_argument("--output-root", type=str, default="backend/runtime/stage_a1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--replay-from-artifacts", action="store_true", help="Rebuild summary from existing factor/rank/forward CSV artifacts")
    args = parser.parse_args()

    config = StageA1Config(
        start_date=args.start_date,
        end_date=args.end_date,
        output_root=args.output_root,
        seed=args.seed,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    runner = StageA1BacktestRunner(config)
    if args.replay_from_artifacts:
        payload = runner.replay_from_artifacts(artifact_root=args.output_root)
    else:
        payload = runner.run()

    print("Stage A1 complete")
    print(f"signal_state={payload['signal_state']}")
    print(f"naive_comparison={payload['signal_checks'].get('piios_vs_naive_statement')}")
    print(f"summary={args.output_root}/stage_a1_summary.json")


if __name__ == "__main__":
    main()
