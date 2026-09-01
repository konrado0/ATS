from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "source/python/src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from ats_ml.contracts_v3 import load_frozen_d0_v3_contract  # noqa: E402
from ats_ml.structural_v3 import validate_structural_run_v3  # noqa: E402
from ats_research.hashing import sha256_file  # noqa: E402


MANIFEST = ROOT / "RESEARCH/PHASE_D1_MANIFEST_v3.json"
AUDIT = ROOT / "RESEARCH/PHASE_D1_REQUIREMENT_AUDIT_v3.json"
READINESS = ROOT / "RESEARCH/PHASE_D1_READINESS_v3.md"
RESOLUTION = ROOT / "source/python/configs/phase_d1_structural_resolution_v3.json"
README = ROOT / "README.md"
ROADMAP = ROOT / "RESEARCH/IMPLEMENTATION_ROADMAP.md"
AUTHORIZATION_OVERLAY = ROOT / "RESEARCH/PHASE_D2_AUTHORIZATION_OVERLAY.md"
D0_VALIDATOR = ROOT / "RESEARCH/prototypes/phase_d0/validate_phase_d0_v3.py"
INDEPENDENT_REPRODUCTION = ROOT / "RESEARCH/prototypes/phase_d1/reproduce_phase_d1_v3.py"
PARENT_RUN = Path("D:/Stock/data/ATS/phase_d_ml/structural_runs/phase-d1-structural-b4fb9bbc480c2026e423")
PARENT_RUN_HASHES = {
    "manifest.json": "b9e015a0cdf4dc57b8a1f5dc7d0dbe3abf4e5120a09a609e7a119a6e2f43ba34",
    "permitted_read_audit.json": "7b48361fb082c305374d04dacfc2a50653b3c2616fd7dcf71aae2bd3c652a717",
    "structural_resolution.json": "6801c396932a7200960dfedd72b9454088e8f7875c9af9ef402ef212005a599b",
}


def _run_json(command: list[str], role: str, *, cwd: Path) -> dict[str, object]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise ValueError(f"{role} failed: {completed.stderr or completed.stdout}")
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
    if manifest.get("schema_version") != "ats.phase_d1.manifest.v3" or manifest.get("status") != "PASS":
        raise ValueError("unexpected D1 v3 manifest")
    if audit.get("schema_version") != "ats.phase_d1.requirement_audit.v3" or audit.get("status") != "PASS":
        raise ValueError("D1 v3 requirement audit is not PASS")
    classifications = [item["classification"] for item in audit["requirements"]]
    expected_counts = {key: value for key, value in audit["summary_counts"].items() if value}
    if dict(Counter(classifications)) != expected_counts or any(item.get("gating", True) and item["classification"] != "PASS" for item in audit["requirements"]):
        raise ValueError("D1 v3 requirement classifications do not satisfy acceptance")
    if audit.get("phase_d2_authorized") is not False:
        raise ValueError("historical D1 v3 audit authorization state changed")
    overlay_state = audit.get("post_readiness_d2_authorization_overlay", {})
    if overlay_state.get("activation") != "AUTOMATIC_AFTER_COMMIT_AND_POST_COMMIT_PASS" or overlay_state.get("repair_task_executes_d2") is not False:
        raise ValueError("D1 v3 audit lacks the bounded post-readiness authorization overlay")

    contract = load_frozen_d0_v3_contract()
    if contract.config["contract_version"] != "phase-d0-20260901-v3":
        raise ValueError("D1 v3 did not load the frozen D0 v3 contract")
    d0_result = _run_json([sys.executable, str(D0_VALIDATOR)], "D0 v3 validator", cwd=ROOT)

    for name, digest in PARENT_RUN_HASHES.items():
        path = PARENT_RUN / name
        if not path.is_file() or sha256_file(path) != digest:
            raise ValueError(f"accepted D1 v2 immutable run changed: {name}")

    for item in manifest.get("artifacts", []) + manifest.get("code", []):
        path = ROOT / item["path"]
        if not path.is_file() or sha256_file(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError(f"D1 v3 manifest artifact mismatch: {item['path']}")

    resolution = json.loads(RESOLUTION.read_text(encoding="utf-8"))
    structural = manifest["structural_run"]
    if resolution["run_id"] != structural["run_id"] or resolution["logical_hash"] != structural["logical_hash"]:
        raise ValueError("repository v3 structural resolution identity mismatch")
    run_dir = Path(structural["path"])
    direct = validate_structural_run_v3(run_dir)
    cli = _run_json([sys.executable, "-m", "ats_ml", "validate-structural-v3", "--run-dir", str(run_dir)], "v3 structural CLI", cwd=ROOT / "source/python")
    reproduction = _run_json([sys.executable, str(INDEPENDENT_REPRODUCTION)], "independent v3 structural reproduction", cwd=ROOT)
    if direct["files"] != structural["files"] or cli.get("files") != structural["files"]:
        raise ValueError("v3 structural physical hashes differ from manifest")
    if reproduction.get("structural_run_id") != structural["run_id"] or reproduction.get("structural_logical_hash") != structural["logical_hash"]:
        raise ValueError("independent v3 structural reproduction identity differs")
    if sha256_file(RESOLUTION) != structural["files"]["structural_resolution.json"]:
        raise ValueError("repository v3 resolution differs from immutable run")

    walk = resolution["walk_forward_resolution"]
    if walk.get("minimums_status") != "PASS" or walk.get("block_count") != 8:
        raise ValueError("v3 structural minima are not PASS")
    if any(len(block["inner_score_blocks"]) != 3 for block in walk["blocks"]):
        raise ValueError("v3 structural block does not contain exactly three inner score blocks")
    partial = [block for block in walk["blocks"] if not block["complete"]]
    if len(partial) != 1 or partial[0]["block_id"] != "MONITORING_2026_H2_PARTIAL" or partial[0]["decisive"]:
        raise ValueError("partial 2026 H2 can enter a decisive gate")
    mapping = walk["evidence_mapping"]
    if mapping["complete_decisive_years"] != [2024, 2025] or mapping["positive_year_fraction_denominator"] != 2:
        raise ValueError("complete-year mapping changed")
    expected_mappings = {
        "model_family_selection": ["MODEL_SELECTION_2023_H1", "MODEL_SELECTION_2023_H2"],
        "development_confirmation_pooled": ["DEVELOPMENT_2024_H1", "DEVELOPMENT_2024_H2"],
        "development_stability_blocks": ["DEVELOPMENT_2024_H1", "DEVELOPMENT_2024_H2"],
        "locked_evidence_pooled": ["LOCKED_2025_H1", "LOCKED_2025_H2", "LOCKED_2026_H1"],
        "locked_stability_blocks": ["LOCKED_2025_H1", "LOCKED_2025_H2", "LOCKED_2026_H1"],
    }
    rendered_gates = json.dumps({name: contract.config[name] for name in ("comparison", "evaluation", "decision_gate")}, sort_keys=True).lower()
    obsolete = ("model_selection_2022", "dev_2023", "dev_2024", "locked_2025_2026", "locked historical test")
    if any(value in rendered_gates for value in obsolete):
        raise ValueError("composed v3 gates retain an obsolete v2 evidence reference")
    if any(contract.config[name].get("evidence_population_mappings") != expected_mappings for name in ("comparison", "evaluation", "decision_gate")):
        raise ValueError("composed v3 gates do not share the explicit half-year mappings")
    proof = resolution["synthetic_prequential_proof"]
    if proof["cell_count"] != 4 or not proof["all_cells_share_inner_score_ledgers"] or proof["test_labels_can_affect_threshold"]:
        raise ValueError("synthetic prequential proof failed")
    locked = resolution["locked_sequence_firewall_proof"]
    if locked["status"] != "PASS" or locked["outcomes_or_metrics_computed"]:
        raise ValueError("locked sequence firewall failed")
    expected_refits = {
        "LOCKED_2025_H1": "2025-01-02",
        "LOCKED_2025_H2": "2025-07-01",
        "LOCKED_2026_H1": "2026-01-02",
    }
    if list(locked.get("expected_bindings", {})) != list(expected_refits):
        raise ValueError("locked firewall expected-binding order changed")
    for block_id, expected_refit in expected_refits.items():
        binding = locked["expected_bindings"][block_id]
        records = [item for item in locked["records"] if item["block_id"] == block_id]
        if len(records) != 1 or binding["expected_refit_session"] != expected_refit:
            raise ValueError(f"locked refit binding differs: {block_id}")
        if records[0]["refit_session"] != expected_refit or records[0]["availability_proof_hash"] != binding["availability_proof_hash"]:
            raise ValueError(f"locked availability proof differs from its binding: {block_id}")
    read_audit = resolution["read_audit"]
    for key in ("market_state_feature_values_loaded", "realized_label_values_loaded_or_derived", "real_model_fit_prediction_or_score", "feature_label_correlations_or_ic_computed", "tail_outcomes_economics_or_model_family_results_computed"):
        if read_audit[key] is not False:
            raise ValueError(f"forbidden real predictive access recorded: {key}")
    authorization = resolution["authorization"]
    for key in ("real_label_values", "real_model_fit", "real_prediction_or_score", "real_predictive_metrics_or_outcomes", "phase_d2"):
        if authorization[key] is not False:
            raise ValueError(f"forbidden authorization enabled: {key}")

    if not AUTHORIZATION_OVERLAY.is_file():
        raise ValueError("Phase D2 authorization overlay is missing")
    guidance = " ".join((README.read_text(encoding="utf-8") + "\n" + ROADMAP.read_text(encoding="utf-8") + "\n" + AUTHORIZATION_OVERLAY.read_text(encoding="utf-8")).split())
    required_guidance = (
        "automatic Phase D2 authorization overlay",
        "post-commit verification",
        "does not execute Phase D2",
        "trailing 36 calendar months",
        "partial 2026 H2",
        "Accepted D0 v2",
    )
    missing = [marker for marker in required_guidance if marker not in guidance]
    if missing:
        raise ValueError(f"current v3 guidance is incomplete: {missing}")
    if not READINESS.is_file():
        raise ValueError("D1 v3 readiness report is missing")
    verification = manifest["verification"]
    if verification.get("focused_phase_d1") != "80 passed" or verification.get("full_source_python") != "187 passed" or verification.get("pre_phase_d_market_state") != "10 passed":
        raise ValueError("D1 v3 manifest verification record differs from completed runs")
    if verification.get("independent_structural_reproduction") != "PASS_IDENTICAL":
        raise ValueError("D1 v3 independent structural reproduction is absent")

    print(json.dumps({
        "schema_version": "ats.phase_d1.validation.v3",
        "status": "PASS",
        "requirement_count": len(audit["requirements"]),
        "d0_v3_validator": d0_result["status"],
        "structural_cli": cli["status"],
        "independent_reproduction": reproduction["status"],
        "structural_run_id": direct["run_id"],
        "structural_logical_hash": direct["logical_hash"],
        "outer_block_count": walk["block_count"],
        "inner_score_block_count": sum(len(block["inner_score_blocks"]) for block in walk["blocks"]),
        "synthetic_cell_count": proof["cell_count"],
        "realized_labels_loaded_or_derived": False,
        "real_fit_prediction_score_metric_or_outcome": False,
        "phase_d2_executed": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
