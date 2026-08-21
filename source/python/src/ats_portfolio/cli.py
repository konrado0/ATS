from __future__ import annotations

import argparse
import json
from pathlib import Path

from ats_portfolio.config import load_config
from ats_portfolio.run import publish_run
from ats_portfolio.validation import reconcile_run, validate_run


def main() -> None:
    parser = argparse.ArgumentParser(prog="ats-portfolio")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", required=True, type=Path)
    run_parser.add_argument("--output-root", type=Path)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--run-dir", required=True, type=Path)
    reconcile_parser = subparsers.add_parser("reconcile")
    reconcile_parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "run":
        path = publish_run(load_config(args.config), args.config, args.output_root)
        result = {"passed": True, "run_dir": path.as_posix(), "run_id": path.name}
    elif args.command == "validate":
        result = validate_run(args.run_dir)
    else:
        result = reconcile_run(args.run_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
