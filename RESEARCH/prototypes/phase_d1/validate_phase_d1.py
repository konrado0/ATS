from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "source/python/src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from ats_ml.contracts import EXPECTED_D0_HASHES, load_frozen_d0_contract  # noqa: E402
from ats_ml.structural import validate_structural_run  # noqa: E402
from ats_research.hashing import sha256_file  # noqa: E402


MANIFEST = ROOT / "RESEARCH/PHASE_D1_MANIFEST.json"
AUDIT = ROOT / "RESEARCH/PHASE_D1_REQUIREMENT_AUDIT.json"
RESOLUTION = ROOT / "source/python/configs/phase_d1_structural_resolution.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "ats.phase_d1.manifest.v1":
        raise ValueError("unexpected Phase D1 manifest schema")
    if audit.get("schema_version") != "ats.phase_d1.requirement_audit.v1" or audit.get("status") != "PASS":
        raise ValueError("Phase D1 requirement audit is not PASS")
    gating_failures = [
        item["id"] for item in audit.get("requirements", [])
        if item.get("gating", True) and item.get("classification") != "PASS"
    ]
    if gating_failures:
        raise ValueError(f"D1 gating requirements are not PASS: {gating_failures}")
    contract = load_frozen_d0_contract()
    if contract.hashes != EXPECTED_D0_HASHES:
        raise ValueError("accepted D0 byte anchors changed")
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
    print(json.dumps({
        "schema_version": "ats.phase_d1.validation.v1",
        "status": "PASS",
        "artifact_count": len(manifest["artifacts"]),
        "requirement_count": len(audit["requirements"]),
        "structural_run_id": result["run_id"],
        "structural_logical_hash": result["logical_hash"],
        "realized_labels_loaded_or_derived": False,
        "real_fit": False,
        "real_prediction": False,
        "phase_d2_executed": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
