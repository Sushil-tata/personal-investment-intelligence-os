from __future__ import annotations

import argparse

from piios_backend.pit_fundamentals.exact_proof import StageA20BExactPitProofRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage A2.0B exact PIT availability-date proof")
    parser.add_argument("--output-root", type=str, default="backend/runtime/stage_a2_exact_pit_proof")
    args = parser.parse_args()

    summary = StageA20BExactPitProofRunner(output_root=args.output_root).run()
    print("Stage A2.0B exact PIT proof complete")
    print(f"historical_classification={summary['historical_classification']}")
    print(f"scalability_classification={summary['scalability_classification']}")
    print(f"summary={args.output_root}/exact_pit_summary.json")


if __name__ == "__main__":
    main()
