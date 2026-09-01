from __future__ import annotations

import argparse
import json
from pathlib import Path

from ats_ml.structural import build_structural_resolution, publish_structural_resolution, validate_structural_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ats-ml")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("structural-resolve")
    validate = subparsers.add_parser("validate-structural")
    validate.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "structural-resolve":
        build = build_structural_resolution()
        run_dir = publish_structural_resolution(build)
        result = validate_structural_run(run_dir)
        result["run_dir"] = str(run_dir)
    else:
        result = validate_structural_run(args.run_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
