from __future__ import annotations

import argparse

from piios_backend.pit_fundamentals.audit import StageA20PitDataProofRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PIIOS Stage A2.0 PIT fundamentals data proof")
    parser.add_argument("--output-root", type=str, default="backend/runtime/stage_a2_pit_proof")
    args = parser.parse_args()

    summary = StageA20PitDataProofRunner(output_root=args.output_root).run()
    print("Stage A2.0 PIT data proof complete")
    print(f"primary_classification={summary['primary_classification']}")
    print(f"scalability_classification={summary['scalability_classification']}")
    print(f"summary={args.output_root}/pit_data_proof_summary.json")


if __name__ == "__main__":
    main()
