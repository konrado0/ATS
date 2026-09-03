from __future__ import annotations

import argparse
import json
from pathlib import Path

from ats_research.hashing import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.root / "RESEARCH/PHASE_D2_NO_M_MANIFEST.json").read_text(encoding="utf-8"))
    failures = []
    for record in manifest["repository_artifacts"]:
        path = args.root / record["path"]
        if not path.is_file() or path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
            failures.append(record["path"])
    status = "PASS" if not failures else "FAIL"
    print(json.dumps({"status": status, "checked": len(manifest["repository_artifacts"]), "failures": failures}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
