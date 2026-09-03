from __future__ import annotations

import argparse
import json
from pathlib import Path

from ats_ml.d2_no_m import publish, validate_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen Phase D2-NM retrospective adjudication")
    parser.add_argument("--validate", type=Path)
    args = parser.parse_args()
    run_dir = args.validate if args.validate else publish()
    result = validate_run(run_dir)
    result["run_dir"] = str(run_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
