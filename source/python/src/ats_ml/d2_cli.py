from __future__ import annotations

import argparse
import json
from pathlib import Path

from ats_ml.d2_stage1 import publish_prediction_run, validate_prediction_run
from ats_ml.d2_stages import (
    publish_final,
    publish_stage2a,
    publish_stage2b,
    publish_stage2c,
    validate_evaluation_stage,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ats-ml-d2")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("stage1", "stage2a", "stage2b", "stage2c", "finalize"):
        command = commands.add_parser(name)
        command.add_argument("--reproduction", action="store_true")
    validate_prediction = commands.add_parser("validate-stage1")
    validate_prediction.add_argument("--run-dir", type=Path, required=True)
    validate_stage = commands.add_parser("validate-stage")
    validate_stage.add_argument("--stage-dir", type=Path, required=True)
    validate_stage.add_argument("--stage", choices=("stage2a", "stage2b", "stage2c", "final"), required=True)
    args = parser.parse_args(argv)
    if args.command == "stage1":
        run_dir = publish_prediction_run(reproduction=args.reproduction)
        result = validate_prediction_run(run_dir)
    elif args.command == "stage2a":
        run_dir = publish_stage2a(reproduction=args.reproduction)
        result = validate_evaluation_stage(run_dir, "stage2a")
    elif args.command == "stage2b":
        run_dir = publish_stage2b(reproduction=args.reproduction)
        result = validate_evaluation_stage(run_dir, "stage2b")
    elif args.command == "stage2c":
        run_dir = publish_stage2c(reproduction=args.reproduction)
        result = validate_evaluation_stage(run_dir, "stage2c")
    elif args.command == "finalize":
        run_dir = publish_final(reproduction=args.reproduction, peer_reproduction=not args.reproduction)
        result = validate_evaluation_stage(run_dir, "final")
    elif args.command == "validate-stage1":
        run_dir = args.run_dir
        result = validate_prediction_run(run_dir)
    else:
        run_dir = args.stage_dir
        result = validate_evaluation_stage(run_dir, args.stage)
    result["run_dir"] = str(run_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

