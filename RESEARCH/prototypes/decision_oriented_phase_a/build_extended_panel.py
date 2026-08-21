from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SOURCE_ROOT = Path(r"D:\Stock\ATS\source\python\src")
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ats_research.config import load_config
from ats_research.run import execute_run
from ats_research.validation import validate_run_directory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()

    destination = args.destination.resolve()
    allowed = Path(r"D:\Stock\data\ATS\decision_oriented_phase_a\runs").resolve()
    if not destination.is_relative_to(allowed):
        raise ValueError(f"destination must stay beneath {allowed}")
    if destination.exists():
        raise FileExistsError(f"immutable destination already exists: {destination}")

    run_dir = execute_run(load_config(args.config.resolve()), destination_override=destination)
    validation = validate_run_directory(run_dir)
    payload = {
        "run_dir": str(run_dir),
        "manifest_run_id": json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["run_id"],
        "validation": validation,
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if validation.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
