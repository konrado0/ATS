from __future__ import annotations

import json
import os
import argparse
from pathlib import Path


ROOT = Path("D:/Stock/data/ATS/pre_phase_d_market_state/runs")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-run-id", default="pre-phase-d-market-state-20260830-v2")
    parser.add_argument("--reproduction-run-id", default="pre-phase-d-market-state-20260830-v2-reproduction")
    args = parser.parse_args()
    primary_dir = ROOT / args.primary_run_id
    reproduction_dir = ROOT / args.reproduction_run_id
    output = ROOT / f"{args.primary_run_id}-reproduction-audit.json"
    if output.exists():
        raise FileExistsError(f"Immutable audit already exists: {output}")
    primary = load(primary_dir / "manifest.json")
    reproduction = load(reproduction_dir / "manifest.json")
    primary_artifacts = primary["artifacts"]
    reproduction_artifacts = reproduction["artifacts"]
    names_equal = sorted(primary_artifacts) == sorted(reproduction_artifacts)
    comparisons = []
    for name in sorted(set(primary_artifacts) | set(reproduction_artifacts)):
        left = primary_artifacts.get(name, {})
        right = reproduction_artifacts.get(name, {})
        comparisons.append(
            {
                "artifact": name,
                "primary_logical_hash": left.get("logical_hash"),
                "reproduction_logical_hash": right.get("logical_hash"),
                "logical_match": left.get("logical_hash") == right.get("logical_hash") and left.get("logical_hash") is not None,
                "primary_physical_sha256": left.get("sha256"),
                "reproduction_physical_sha256": right.get("sha256"),
                "physical_match": left.get("sha256") == right.get("sha256") and left.get("sha256") is not None,
            }
        )
    logical_payload_match = primary["logical_payload_hash"] == reproduction["logical_payload_hash"]
    all_logical_match = all(row["logical_match"] for row in comparisons)
    all_physical_match = all(row["physical_match"] for row in comparisons)
    status = "PASS" if names_equal and logical_payload_match and all_logical_match and all_physical_match else "FAIL"
    audit = {
        "schema_version": "ats.pre_phase_d_market_state.reproduction_audit.v1",
        "status": status,
        "primary_run": primary_dir.as_posix(),
        "reproduction_run": reproduction_dir.as_posix(),
        "artifact_names_match": names_equal,
        "primary_logical_payload_hash": primary["logical_payload_hash"],
        "reproduction_logical_payload_hash": reproduction["logical_payload_hash"],
        "logical_payload_match": logical_payload_match,
        "all_artifact_logical_hashes_match": all_logical_match,
        "all_artifact_physical_hashes_match": all_physical_match,
        "artifact_comparisons": comparisons,
        "final_safe_to_proceed_phase_d0_d1": "YES" if status == "PASS" else "NO",
    }
    temporary = output.with_suffix(f".tmp.{os.getpid()}")
    temporary.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
