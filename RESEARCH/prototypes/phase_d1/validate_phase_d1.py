from __future__ import annotations

import io
import json
import subprocess
import sys
import tarfile
import tempfile
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
README = ROOT / "README.md"
ROADMAP = ROOT / "RESEARCH/IMPLEMENTATION_ROADMAP.md"
RESOLUTION = ROOT / "source/python/configs/phase_d1_structural_resolution.json"
HISTORICAL_D0_COMMIT = "cbddb4ff13f4452aa37f427f0f3c09a3f3da1ae4"
D0_VALIDATOR_RELATIVE = Path("RESEARCH/prototypes/phase_d0/validate_phase_d0.py")


def _run_json(command: list[str], role: str, *, cwd: Path = ROOT) -> dict[str, object]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise ValueError(f"{role} failed with exit code {completed.returncode}: {completed.stderr or completed.stdout}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{role} did not emit one JSON document") from exc
    if result.get("status") != "PASS":
        raise ValueError(f"{role} status is not PASS")
    return result


def _run_historical_d0_validator(commit: str) -> dict[str, object]:
    archived = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "archive", "--format=tar", commit],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if archived.returncode != 0:
        detail = archived.stderr.decode(errors="replace") or archived.stdout.decode(errors="replace")
        raise ValueError(f"could not archive accepted Phase D0 tree {commit}: {detail}")
    with tempfile.TemporaryDirectory(prefix="ats-d0-replay-") as temporary_directory:
        snapshot = Path(temporary_directory)
        snapshot_root = snapshot.resolve()
        with tarfile.open(fileobj=io.BytesIO(archived.stdout), mode="r:") as archive:
            for member in archive.getmembers():
                target = (snapshot / member.name).resolve()
                if target != snapshot_root and snapshot_root not in target.parents:
                    raise ValueError(f"unsafe path in accepted Phase D0 archive: {member.name}")
                if member.issym() or member.islnk():
                    raise ValueError(f"unsupported link in accepted Phase D0 archive: {member.name}")
            archive.extractall(snapshot, filter="data")
        validator = snapshot / D0_VALIDATOR_RELATIVE
        return _run_json(
            [sys.executable, str(validator)],
            f"historical Phase D0 validator at {commit}",
            cwd=snapshot,
        )


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
    historical_d0 = manifest.get("historical_d0_validation", {})
    if historical_d0.get("commit") != HISTORICAL_D0_COMMIT:
        raise ValueError("D1 manifest does not pin the accepted historical D0 commit")
    if historical_d0.get("validator") != D0_VALIDATOR_RELATIVE.as_posix():
        raise ValueError("D1 manifest does not pin the historical D0 validator path")
    if historical_d0.get("status") != "PASS" or historical_d0.get("current_tree_validator_applicable") is not False:
        raise ValueError("D1 manifest does not separate historical D0 validation from current guidance")
    d0_result = _run_historical_d0_validator(HISTORICAL_D0_COMMIT)
    verification = manifest.get("verification", {})
    if verification.get("historical_phase_d0_validator") != "PASS":
        raise ValueError("D1 manifest does not report the historical D0 replay result")
    if verification.get("current_tree_historical_d0_validator") != "NOT_APPLICABLE":
        raise ValueError("D1 manifest incorrectly treats the historical D0 validator as a current-tree gate")
    guidance = manifest.get("current_project_guidance", {})
    if guidance.get("phase_d1_state") != "complete — PASS" or guidance.get("phase_d2_authorized") is not False:
        raise ValueError("D1 manifest does not state the current D1/D2 authorization boundary")
    for path in (README, ROADMAP):
        relative = path.relative_to(ROOT).as_posix()
        if guidance.get(relative) != sha256_file(path):
            raise ValueError(f"current guidance hash mismatch: {relative}")
    readme_text = README.read_text(encoding="utf-8")
    roadmap_text = ROADMAP.read_text(encoding="utf-8")
    required_guidance = (
        "Phase D1 is complete",
        "Phase D2 may inspect real model performance only after separate owner authorization",
        "PHASE_D1_READINESS_v2.md",
        "Phase D2 remains unauthorized",
        "Session-level predictive evaluation, paired comparisons, uncertainty",
        "remain Phase D2 work",
    )
    combined_guidance = " ".join(f"{readme_text}\n{roadmap_text}".split())
    missing_guidance = [marker for marker in required_guidance if marker not in combined_guidance]
    prohibited_guidance = (
        "The next gate is **owner review of Phase D0**",
        "| Phase D1 | Not authorized |",
        "D0 is ready for renewed owner review; it does not authorize D1",
    )
    stale_guidance = [marker for marker in prohibited_guidance if marker in combined_guidance]
    if missing_guidance or stale_guidance:
        raise ValueError(f"current guidance boundary is inconsistent: missing={missing_guidance}, stale={stale_guidance}")
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
        "historical_d0_commit": HISTORICAL_D0_COMMIT,
        "historical_d0_validator": d0_result["status"],
        "current_project_guidance": "PASS",
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
