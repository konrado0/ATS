from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "source/python/src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from ats_ml.contracts import EXPECTED_D0_HASHES, load_frozen_d0_contract  # noqa: E402
from ats_ml.matrices import SEMANTIC_ROW_FIELDS  # noqa: E402
from ats_ml.structural import validate_structural_run  # noqa: E402
from ats_research.hashing import sha256_file  # noqa: E402


MANIFEST = ROOT / "RESEARCH/PHASE_D1_MANIFEST_v2.json"
AUDIT = ROOT / "RESEARCH/PHASE_D1_REQUIREMENT_AUDIT_v2.json"
READINESS = ROOT / "RESEARCH/PHASE_D1_READINESS_v2.md"
RESOLUTION = ROOT / "source/python/configs/phase_d1_structural_resolution.json"
D0_VALIDATOR = ROOT / "RESEARCH/prototypes/phase_d0/validate_phase_d0.py"


def _run_json(command: list[str], role: str) -> dict[str, object]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise ValueError(f"{role} failed with exit code {completed.returncode}: {completed.stderr or completed.stdout}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{role} did not emit one JSON document") from exc
    if result.get("status") != "PASS":
        raise ValueError(f"{role} status is not PASS")
    return result


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "ats.phase_d1.manifest.v2":
        raise ValueError("unexpected Phase D1 manifest schema")
    if audit.get("schema_version") != "ats.phase_d1.requirement_audit.v2" or audit.get("status") != "PASS":
        raise ValueError("Phase D1 requirement audit is not PASS")
    if len(audit.get("carried_forward_pass_ids", [])) != 30 or len(set(audit.get("carried_forward_pass_ids", []))) != 30:
        raise ValueError("v2 audit does not carry forward exactly 30 distinct unaffected PASS requirements")
    gating_failures = [
        item["id"] for item in audit.get("reopened_and_new_requirements", [])
        if item.get("gating", True) and item.get("classification") != "PASS"
    ]
    if gating_failures:
        raise ValueError(f"D1 gating requirements are not PASS: {gating_failures}")
    contract = load_frozen_d0_contract()
    if contract.hashes != EXPECTED_D0_HASHES:
        raise ValueError("accepted D0 byte anchors changed")
    d0_result = _run_json([sys.executable, str(D0_VALIDATOR)], "Phase D0 validator")
    if manifest.get("verification", {}).get("phase_d0_validator") != "PASS":
        raise ValueError("D1 manifest does not report the current D0 validator result")
    if not READINESS.is_file():
        raise ValueError("superseding D1 readiness report is missing")
    for item in manifest.get("artifacts", []):
        path = ROOT / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError(f"D1 artifact mismatch: {item['path']}")
    resolution = json.loads(RESOLUTION.read_text(encoding="utf-8"))
    structural = manifest["structural_run"]
    if resolution["run_id"] != structural["run_id"] or resolution["logical_hash"] != structural["logical_hash"]:
        raise ValueError("repository structural resolution identity mismatch")
    run_dir = Path(structural["path"])
    result = validate_structural_run(run_dir)
    if result["run_id"] != structural["run_id"] or result["files"] != structural["files"]:
        raise ValueError("immutable structural run does not reproduce the manifest")
    cli_result = _run_json(
        [sys.executable, "-m", "ats_ml", "validate-structural", "--run-dir", str(run_dir)],
        "Phase D1 structural CLI",
    )
    if cli_result.get("run_id") != structural["run_id"] or cli_result.get("files") != structural["files"]:
        raise ValueError("structural CLI result differs from the v2 manifest")
    read_audit = resolution["read_audit"]
    forbidden_flags = (
        "forbidden_columns_loaded_or_derived",
        "realized_label_values_loaded_or_derived",
        "feature_label_correlations_or_ic_computed",
        "model_scores_predictions_tail_outcomes_or_economics_computed",
    )
    if any(read_audit.get(name) is not False for name in forbidden_flags):
        raise ValueError("structural read audit records a forbidden predictive operation")
    authorization = resolution["authorization"]
    if any(authorization.get(name) is not False for name in ("real_model_fit", "real_prediction", "real_predictive_execution", "phase_d2")):
        raise ValueError("D1 structural authorization expanded beyond contract")
    calendar = resolution.get("calendar_provenance", {})
    if calendar.get("status") != "PASS":
        raise ValueError("calendar provenance is not PASS")
    if calendar.get("candidate_calendar_hash") != calendar.get("validated_wig_candidate_range_hash"):
        raise ValueError("candidate and validated-WIG calendars are not equal")
    if calendar.get("official_membership_calendar_hash") != calendar.get("market_state_calendar_hash"):
        raise ValueError("membership and market-state calendars are not equal")
    fixture_registry = json.loads((ROOT / "source/python/configs/phase_d1_fixture_registry.json").read_text(encoding="utf-8"))
    if fixture_registry.get("schema_version") != "ats.phase_d1.fixture_registry.v2":
        raise ValueError("semantic-row-bound fixture registry v2 is absent")
    model_entries = [entry for entry in fixture_registry.get("fixtures", {}).values() if entry.get("kind") == "model"]
    if not model_entries or any(len(str(entry.get("semantic_row_sha256", ""))) != 64 for entry in model_entries):
        raise ValueError("a model fixture lacks its semantic-row ledger hash")
    print(json.dumps({
        "schema_version": "ats.phase_d1.validation.v2",
        "status": "PASS",
        "artifact_count": len(manifest["artifacts"]),
        "effective_requirement_count": sum(audit["effective_summary_counts"].values()),
        "semantic_row_fields": list(SEMANTIC_ROW_FIELDS),
        "d0_validator": d0_result["status"],
        "structural_cli": cli_result["status"],
        "structural_run_id": result["run_id"],
        "structural_logical_hash": result["logical_hash"],
        "candidate_wig_calendar_sessions": calendar["candidate_calendar_count"],
        "membership_market_state_sessions": calendar["official_membership_calendar_count"],
        "realized_labels_loaded_or_derived": False,
        "real_fit": False,
        "real_prediction": False,
        "phase_d2_executed": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
