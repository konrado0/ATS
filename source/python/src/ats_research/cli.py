from __future__ import annotations

import argparse
import json
from pathlib import Path

from ats_research.config import load_config
from ats_research.run import execute_run, reproduce_run
from ats_research.validation import validate_run_directory


def main() -> None:
    parser = argparse.ArgumentParser(prog="ats-research")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="execute the real Phase A pipeline")
    run_parser.add_argument("--config", type=Path, required=True)
    validate_parser = subparsers.add_parser("validate", help="parse and validate a run directory")
    validate_parser.add_argument("--run-dir", type=Path, required=True)
    validate_parser.add_argument("--strict-current-checkout", action="store_true", help="also require current checkout files to match the archived snapshot")
    reproduce_parser = subparsers.add_parser("reproduce", help="rerun from an authoritative run config and compare logical hashes")
    reproduce_parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "run":
        result = {"run_dir": execute_run(load_config(args.config)).as_posix()}
    elif args.command == "validate":
        result = validate_run_directory(args.run_dir, strict_current_checkout=args.strict_current_checkout)
    else:
        result = reproduce_run(args.run_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
