from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from ats_ml.contracts import REPOSITORY_ROOT, resolve_pinned_inputs
from ats_ml.contracts_v3 import D0_V3_CONFIG, load_frozen_d0_v3_contract
from ats_ml.guard import D1ExecutionGuard, FIXTURE_REGISTRY_V3, pinned_real_context, synthetic_fixture_context
from ats_ml.models import LIGHTGBM_PARAMETERS, RIDGE_PARAMETERS
from ats_ml.structural import _resolve_validated_wig, assert_calendar_provenance
from ats_ml.walkforward import (
    LockedSequenceFirewall,
    bind_structural_minimums,
    chronological_bins_for_gate_populations,
    derive_core_score_eligibility,
    derive_walk_forward_plan,
    expected_locked_sequence_bindings,
    synthetic_prequential_proof,
)
from ats_research.hashing import content_hash, sha256_file


STRUCTURAL_OUTPUT_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/structural_runs")
REPOSITORY_RESOLUTION_V3 = REPOSITORY_ROOT / "source/python/configs/phase_d1_structural_resolution_v3.json"
PARENT_RESOLUTION_V2 = REPOSITORY_ROOT / "source/python/configs/phase_d1_structural_resolution.json"
STRUCTURAL_COLUMNS_V3 = (
    "security_id",
    "session_date",
    "split_adjusted_close",
    "split_adjusted_high",
    "official_membership",
    "price_usable_for_features",
    "source_treatment_state",
    "factor_version",
    "missing_state",
    "nontrading_reason",
    "coverage_result",
    "data_basis_version",
)
FORBIDDEN_COLUMNS = (
    "split_adjusted_open",
    "label__open_to_open__20",
    "realized_forward_return",
    "model_score",
    "rank_ic",
    "tail_outcome",
    "economic_result",
)
_SEAL = object()


@dataclass(frozen=True, init=False)
class StructuralBuildV3:
    resolution: dict[str, Any]
    read_audit: dict[str, Any]

    def __init__(self, resolution: dict[str, Any], read_audit: dict[str, Any], *, _token: object):
        if _token is not _SEAL:
            raise ValueError("v3 structural publications must originate from the sealed builder")
        object.__setattr__(self, "resolution", json.loads(json.dumps(resolution)))
        object.__setattr__(self, "read_audit", json.loads(json.dumps(read_audit)))


def _package_versions() -> dict[str, str]:
    names = ("numpy", "pandas", "polars", "pyarrow", "scikit-learn", "lightgbm", "pydantic", "PyYAML", "duckdb", "pytest")
    return {name: importlib.metadata.version(name) for name in names}


def _implementation_fingerprints() -> dict[str, Any]:
    source_root = REPOSITORY_ROOT / "source/python/src/ats_ml"
    files = sorted(source_root.glob("*.py"), key=lambda path: path.name)
    environment = REPOSITORY_ROOT / "RESEARCH/environment/environment.yml"
    return {
        "files": {path.relative_to(REPOSITORY_ROOT).as_posix(): sha256_file(path) for path in files},
        "d0_v3_reference_sha256": sha256_file(D0_V3_CONFIG),
        "unchanged_feature_registry_sha256": sha256_file(REPOSITORY_ROOT / "source/python/configs/phase_d0_feature_registry.json"),
        "fixture_registry_v3_sha256": sha256_file(FIXTURE_REGISTRY_V3),
        "environment_lock": {"path": environment.relative_to(REPOSITORY_ROOT).as_posix(), "sha256": sha256_file(environment)},
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": _package_versions(),
        "ridge_parameters": RIDGE_PARAMETERS,
        "lightgbm_parameters": LIGHTGBM_PARAMETERS,
    }


def _compact_plan(plan: dict[str, Any]) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    for original in plan["blocks"]:
        block = dict(original)
        for key in ("estimator_window_sessions", "evaluation_sessions"):
            values = block.pop(key)
            block[f"{key}_hash"] = content_hash(values)
        inner_blocks = []
        for original_inner in block["inner_score_blocks"]:
            inner = dict(original_inner)
            for key in ("fit_retained_sessions", "score_sessions"):
                values = inner.pop(key)
                inner[f"{key}_hash"] = content_hash(values)
            inner_blocks.append(inner)
        block["inner_score_blocks"] = inner_blocks
        final = dict(block["final_fit"])
        values = final.pop("retained_sessions")
        final["retained_sessions_hash"] = content_hash(values)
        block["final_fit"] = final
        blocks.append(block)
    return {**{key: value for key, value in plan.items() if key != "blocks"}, "blocks": blocks}


def _locked_firewall_fixture(plan: dict[str, Any]) -> dict[str, Any]:
    blocks = {item["block_id"]: item for item in plan["blocks"]}
    expected_bindings = expected_locked_sequence_bindings(plan)
    firewall = LockedSequenceFirewall(expected_bindings)
    records = []
    for block_id in plan["locked_prediction_order"]:
        block = blocks[block_id]
        prediction_hash = content_hash({"synthetic_locked_prediction_fixture": block_id})
        availability_hash = expected_bindings[block_id]["availability_proof_hash"]
        firewall.record_prediction(
            block_id,
            prediction_hash=prediction_hash,
            refit_session=block["refit_session"],
            availability_proof_hash=availability_hash,
        )
        records.append({
            "block_id": block_id,
            "prediction_hash": prediction_hash,
            "refit_session": expected_bindings[block_id]["expected_refit_session"],
            "availability_proof_hash": availability_hash,
        })
    fingerprint = firewall.fingerprint_complete_sequence()
    permit = firewall.evaluation_permit()
    firewall.require_evaluation_permit(permit)
    return {
        "schema_version": "ats.phase_d1.locked_firewall_proof.v3",
        "synthetic_only": True,
        "ordered_blocks": plan["locked_prediction_order"],
        "expected_bindings": expected_bindings,
        "records": records,
        "complete_sequence_fingerprint": fingerprint,
        "evaluation_inaccessible_before_complete_fingerprint": True,
        "outcomes_or_metrics_computed": False,
        "status": "PASS",
    }


def build_structural_resolution_v3() -> StructuralBuildV3:
    contract = load_frozen_d0_v3_contract(require_publication=False)
    paths = resolve_pinned_inputs(contract)
    parquet = pq.ParquetFile(paths["candidate_panel"])
    schema_columns = tuple(parquet.schema_arrow.names)
    if set(STRUCTURAL_COLUMNS_V3) - set(schema_columns):
        raise ValueError("candidate panel lacks v3 structural columns")
    if set(STRUCTURAL_COLUMNS_V3) & set(FORBIDDEN_COLUMNS):
        raise AssertionError("v3 structural projection includes predictive columns")
    panel = pd.read_parquet(paths["candidate_panel"], columns=list(STRUCTURAL_COLUMNS_V3))
    panel["session_date"] = pd.to_datetime(panel["session_date"]).dt.normalize()
    calendar = pd.DatetimeIndex(sorted(panel["session_date"].unique()))
    validated_wig_path, validated_wig_sha256 = _resolve_validated_wig(paths["market_state_manifest"])
    validated_wig = pd.read_parquet(validated_wig_path, columns=["session_date"])
    market_sessions = pd.read_parquet(paths["market_state_feature_artifact"], columns=["decision_session"])
    official_sessions = panel.loc[panel["official_membership"].fillna(False), "session_date"]
    calendar_provenance = assert_calendar_provenance(calendar, validated_wig["session_date"], official_sessions, market_sessions["decision_session"])

    raw_plan = derive_walk_forward_plan(calendar, contract)
    eligibility = derive_core_score_eligibility(panel, calendar, expected_factor_version="ats.gpw.split_adjustment.v1")
    bound_plan = bind_structural_minimums(raw_plan, eligibility)
    concentration_bins = chronological_bins_for_gate_populations(bound_plan)

    parent_resolution = json.loads(PARENT_RESOLUTION_V2.read_text(encoding="utf-8"))
    parent_p = parent_resolution["p_duplicate_resolution"]
    expected_survivors = contract.config["v3_amendment"]["unchanged_parent_contract"]["p_survivors"]
    if parent_p.get("survivors") != expected_survivors or parent_p.get("survivor_count") != 8:
        raise ValueError("accepted D1 v2 P-duplicate result cannot be carried unchanged")

    v3_guard = D1ExecutionGuard(contract, FIXTURE_REGISTRY_V3)
    fixture_context = synthetic_fixture_context(contract, v3_guard, "phase-d1-v3-walkforward")
    prequential = synthetic_prequential_proof(contract, v3_guard, fixture_context)
    locked_firewall = _locked_firewall_fixture(bound_plan)
    implementation = _implementation_fingerprints()
    candidate_manifest = json.loads(paths["candidate_manifest"].read_text(encoding="utf-8"))
    official = panel.loc[panel["official_membership"].fillna(False)]
    per_session = official.groupby("session_date")["security_id"].nunique()
    read_audit = {
        "artifacts_opened": [str(paths["candidate_manifest"]), str(paths["candidate_panel"]), str(paths["market_state_manifest"]), str(paths["market_state_feature_artifact"]), str(validated_wig_path)],
        "candidate_parquet_metadata_rows": parquet.metadata.num_rows,
        "candidate_schema_columns": list(schema_columns),
        "candidate_value_columns_loaded": list(STRUCTURAL_COLUMNS_V3),
        "calendar_key_columns_loaded": {"market_state_feature_artifact": ["decision_session"], "validated_wig": ["session_date"]},
        "forbidden_columns": list(FORBIDDEN_COLUMNS),
        "market_state_feature_values_loaded": False,
        "realized_label_values_loaded_or_derived": False,
        "real_model_fit_prediction_or_score": False,
        "feature_label_correlations_or_ic_computed": False,
        "tail_outcomes_economics_or_model_family_results_computed": False,
        "synthetic_fixture_fit_predict_only": True,
    }
    core: dict[str, Any] = {
        "schema_version": "ats.phase_d1.structural_resolution.v3",
        "d0_contract_version": contract.config["contract_version"],
        "parents": {
            "d0_v2_artifacts": {key: value for key, value in contract.hashes.items() if not key.endswith("_v3.json") and not key.endswith("_v3.md")},
            "d1_v2_checkpoint": "724971466dacfba05ff0fa7e92cd68c4628008c7",
            "d1_v2_structural_run_id": parent_resolution["run_id"],
            "d1_v2_structural_resolution_sha256": sha256_file(PARENT_RESOLUTION_V2),
        },
        "pinned_inputs": {
            "candidate_run_id": contract.pinned_identity["candidate_run_id"],
            "candidate_manifest_sha256": sha256_file(paths["candidate_manifest"]),
            "candidate_panel_sha256": sha256_file(paths["candidate_panel"]),
            "candidate_logical_hash": candidate_manifest["adjusted_logical_hash"],
            "candidate_data_basis_version": candidate_manifest["data_basis_version"],
            "market_state_manifest_sha256": sha256_file(paths["market_state_manifest"]),
            "market_state_feature_artifact_sha256": sha256_file(paths["market_state_feature_artifact"]),
            "validated_wig_sha256": validated_wig_sha256,
        },
        "calendar_provenance": calendar_provenance,
        "walk_forward_resolution": _compact_plan(bound_plan),
        "chronological_concentration_bins": concentration_bins,
        "p_duplicate_resolution": {
            "source": "accepted D1 v2 structural resolution; chronology amendment does not change its already-frozen label-blind population through 2024-12-30",
            "parent_resolution_sha256": sha256_file(PARENT_RESOLUTION_V2),
            "survivor_count": parent_p["survivor_count"],
            "survivors": parent_p["survivors"],
            "decisions": parent_p["decisions"],
            "status": "PRESERVED",
        },
        "synthetic_prequential_proof": prequential,
        "locked_sequence_firewall_proof": locked_firewall,
        "implementation_and_environment": implementation,
        "structural_counts": {
            "candidate_rows": len(panel),
            "calendar_sessions": len(calendar),
            "official_member_rows": len(official),
            "official_session_count_min": int(per_session.min()),
            "official_session_count_max": int(per_session.max()),
            "core_score_eligibility_session_count": len(eligibility),
            "core_score_eligible_rows_total": int(eligibility["core_score_eligible_rows"].sum()),
        },
        "read_audit": read_audit,
        "authorization": {
            "synthetic_fixture_fit_predict": True,
            "real_structural_calendar_endpoint_and_label_blind_eligibility_only": True,
            "real_label_values": False,
            "real_model_fit": False,
            "real_prediction_or_score": False,
            "real_predictive_metrics_or_outcomes": False,
            "phase_d2": False,
        },
        "physical_hashes": {
            "candidate_manifest": sha256_file(paths["candidate_manifest"]),
            "candidate_panel": sha256_file(paths["candidate_panel"]),
            "market_state_manifest": sha256_file(paths["market_state_manifest"]),
            "market_state_feature_artifact": sha256_file(paths["market_state_feature_artifact"]),
            "validated_wig": validated_wig_sha256,
            "parent_d1_v2_resolution": sha256_file(PARENT_RESOLUTION_V2),
            "implementation_files": implementation["files"],
        },
    }
    logical_hash = content_hash(core)
    resolution = {**core, "logical_hash": logical_hash, "run_id": f"phase-d1-v3-structural-{logical_hash[:20]}"}
    standalone_audit = {**read_audit, "run_id": resolution["run_id"], "status": "PASS"}
    return StructuralBuildV3(resolution, standalone_audit, _token=_SEAL)


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n")


def publish_structural_resolution_v3(build: StructuralBuildV3) -> Path:
    if not isinstance(build, StructuralBuildV3):
        raise ValueError("v3 structural publication accepts only a sealed builder result")
    _validate_payload(build.resolution, build.read_audit)
    STRUCTURAL_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    destination = STRUCTURAL_OUTPUT_ROOT / build.resolution["run_id"]
    stage = STRUCTURAL_OUTPUT_ROOT / f".stage-{build.resolution['run_id']}-{uuid.uuid4().hex}"
    stage.mkdir()
    try:
        _write_json(stage / "structural_resolution.json", build.resolution)
        _write_json(stage / "permitted_read_audit.json", build.read_audit)
        manifest = {
            "schema_version": "ats.phase_d1.structural_run_manifest.v3",
            "run_id": build.resolution["run_id"],
            "logical_hash": build.resolution["logical_hash"],
            "files": {
                "structural_resolution.json": sha256_file(stage / "structural_resolution.json"),
                "permitted_read_audit.json": sha256_file(stage / "permitted_read_audit.json"),
            },
            "mutable_latest_pointer": False,
            "real_fit_prediction_metrics_or_outcomes_authorized": False,
        }
        _write_json(stage / "manifest.json", manifest)
        validate_structural_run_v3(stage)
        if destination.exists():
            existing = validate_structural_run_v3(destination)
            if existing["files"] != manifest["files"]:
                raise ValueError("immutable v3 structural run collision")
            shutil.rmtree(stage)
        else:
            os.replace(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    _write_json(REPOSITORY_RESOLUTION_V3, build.resolution)
    return destination


def _validate_payload(resolution: dict[str, Any], read_audit: dict[str, Any]) -> None:
    required = {
        "schema_version", "d0_contract_version", "parents", "pinned_inputs", "calendar_provenance",
        "walk_forward_resolution", "chronological_concentration_bins", "p_duplicate_resolution",
        "synthetic_prequential_proof", "locked_sequence_firewall_proof", "implementation_and_environment",
        "structural_counts", "read_audit", "authorization", "physical_hashes", "logical_hash", "run_id",
    }
    if set(resolution) != required or resolution.get("schema_version") != "ats.phase_d1.structural_resolution.v3":
        raise ValueError("v3 structural resolution schema mismatch")
    contract = load_frozen_d0_v3_contract(require_publication=False)
    if resolution["d0_contract_version"] != contract.config["contract_version"]:
        raise ValueError("v3 structural resolution contract mismatch")
    if resolution["parents"]["d1_v2_checkpoint"] != "724971466dacfba05ff0fa7e92cd68c4628008c7":
        raise ValueError("v3 structural resolution parent checkpoint mismatch")
    if resolution["parents"]["d1_v2_structural_resolution_sha256"] != sha256_file(PARENT_RESOLUTION_V2):
        raise ValueError("accepted D1 v2 structural resolution changed")
    audit = resolution["read_audit"]
    false_flags = (
        "market_state_feature_values_loaded", "realized_label_values_loaded_or_derived",
        "real_model_fit_prediction_or_score", "feature_label_correlations_or_ic_computed",
        "tail_outcomes_economics_or_model_family_results_computed",
    )
    if any(audit.get(key) is not False for key in false_flags):
        raise ValueError("v3 structural read audit records forbidden predictive access")
    if tuple(audit.get("candidate_value_columns_loaded", ())) != STRUCTURAL_COLUMNS_V3:
        raise ValueError("v3 structural read projection differs from allowlist")
    if set(audit["candidate_value_columns_loaded"]) & set(FORBIDDEN_COLUMNS):
        raise ValueError("v3 structural read projection includes forbidden fields")
    if read_audit != {**audit, "run_id": resolution["run_id"], "status": "PASS"}:
        raise ValueError("v3 standalone read audit mismatch")
    if resolution["calendar_provenance"].get("status") != "PASS":
        raise ValueError("v3 calendar provenance is not PASS")
    walk = resolution["walk_forward_resolution"]
    if walk.get("schema_version") != "ats.phase_d1.walk_forward_plan.v3" or walk.get("minimums_status") != "PASS" or walk.get("block_count") != 8:
        raise ValueError("v3 walk-forward resolution is incomplete")
    if any(len(block.get("inner_score_blocks", ())) != 3 for block in walk["blocks"]):
        raise ValueError("every v3 outer block requires exactly three inner score blocks")
    if any(inner.get("fit_minimum_status") != "PASS" or inner.get("score_minimum_status") != "PASS" for block in walk["blocks"] for inner in block["inner_score_blocks"]):
        raise ValueError("v3 inner structural minimum failed")
    if any(block["final_fit"].get("minimum_status") != "PASS" for block in walk["blocks"]):
        raise ValueError("v3 final-fit structural minimum failed")
    partial = [block for block in walk["blocks"] if not block["complete"]]
    if len(partial) != 1 or partial[0]["block_id"] != "MONITORING_2026_H2_PARTIAL" or partial[0]["decisive"]:
        raise ValueError("partial monitoring block can enter a decisive gate")
    proof = resolution["synthetic_prequential_proof"]
    if proof.get("cell_count") != 4 or proof.get("all_cells_share_inner_score_ledgers") is not True or proof.get("test_labels_can_affect_threshold") is not False:
        raise ValueError("v3 synthetic prequential proof failed")
    if any(cell.get("inner_stage_count") != 3 or cell.get("preprocessing_and_estimator_recreated") is not True or cell.get("pooled_score_block_count") != 3 for cell in proof["cells"].values()):
        raise ValueError("v3 synthetic cell proof failed")
    locked = resolution["locked_sequence_firewall_proof"]
    if locked.get("status") != "PASS" or locked.get("outcomes_or_metrics_computed") is not False:
        raise ValueError("v3 locked-sequence firewall proof failed")
    expected_refits = {
        "LOCKED_2025_H1": "2025-01-02",
        "LOCKED_2025_H2": "2025-07-01",
        "LOCKED_2026_H1": "2026-01-02",
    }
    bindings = locked.get("expected_bindings")
    records = locked.get("records")
    if not isinstance(bindings, dict) or tuple(bindings) != tuple(expected_refits):
        raise ValueError("v3 locked firewall lacks the exact expected binding order")
    if not isinstance(records, list) or [item.get("block_id") for item in records] != list(expected_refits):
        raise ValueError("v3 locked firewall records differ from the exact prediction order")
    for record in records:
        block_id = record["block_id"]
        binding = bindings[block_id]
        if binding.get("expected_refit_session") != expected_refits[block_id]:
            raise ValueError(f"v3 locked refit date is not pinned: {block_id}")
        if record.get("refit_session") != binding.get("expected_refit_session"):
            raise ValueError(f"v3 locked record refit date differs from its binding: {block_id}")
        if record.get("availability_proof_hash") != binding.get("availability_proof_hash"):
            raise ValueError(f"v3 locked record availability identity differs from its binding: {block_id}")
    if locked.get("complete_sequence_fingerprint") != content_hash(records):
        raise ValueError("v3 locked complete-sequence fingerprint differs from bound records")
    authorization = resolution["authorization"]
    for key in ("real_label_values", "real_model_fit", "real_prediction_or_score", "real_predictive_metrics_or_outcomes", "phase_d2"):
        if authorization.get(key) is not False:
            raise ValueError("v3 structural authorization expanded into D2")
    counts = resolution["structural_counts"]
    if counts.get("official_session_count_min") != 60 or counts.get("official_session_count_max") != 60:
        raise ValueError("v3 structural denominator is not exactly 60")
    implementation = resolution["implementation_and_environment"]
    if implementation.get("ridge_parameters") != RIDGE_PARAMETERS or implementation.get("lightgbm_parameters") != LIGHTGBM_PARAMETERS:
        raise ValueError("v3 model parameters changed")
    physical = resolution["physical_hashes"]
    if physical.get("implementation_files") != implementation.get("files") or physical.get("parent_d1_v2_resolution") != sha256_file(PARENT_RESOLUTION_V2):
        raise ValueError("v3 physical hashes do not reconcile")
    stable = {key: value for key, value in resolution.items() if key not in {"logical_hash", "run_id"}}
    logical = content_hash(stable)
    if resolution["logical_hash"] != logical or resolution["run_id"] != f"phase-d1-v3-structural-{logical[:20]}":
        raise ValueError("v3 structural logical identity mismatch")


def validate_structural_run_v3(run_dir: Path) -> dict[str, Any]:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    required = {"schema_version", "run_id", "logical_hash", "files", "mutable_latest_pointer", "real_fit_prediction_metrics_or_outcomes_authorized"}
    if set(manifest) != required or manifest.get("schema_version") != "ats.phase_d1.structural_run_manifest.v3":
        raise ValueError("v3 structural manifest schema mismatch")
    if manifest["mutable_latest_pointer"] is not False or manifest["real_fit_prediction_metrics_or_outcomes_authorized"] is not False:
        raise ValueError("v3 structural manifest authorization mismatch")
    if run_dir.name != manifest["run_id"] and not run_dir.name.startswith(".stage-"):
        raise ValueError("v3 structural run directory identity mismatch")
    if set(manifest["files"]) != {"structural_resolution.json", "permitted_read_audit.json"}:
        raise ValueError("v3 structural manifest file allowlist mismatch")
    actual = {path.name for path in run_dir.iterdir() if path.is_file()}
    if actual != {"manifest.json", *manifest["files"]}:
        raise ValueError("v3 structural run artifact set mismatch")
    for name, digest in manifest["files"].items():
        if sha256_file(run_dir / name) != digest:
            raise ValueError(f"v3 structural run hash mismatch: {name}")
    resolution = json.loads((run_dir / "structural_resolution.json").read_text(encoding="utf-8"))
    read_audit = json.loads((run_dir / "permitted_read_audit.json").read_text(encoding="utf-8"))
    _validate_payload(resolution, read_audit)
    if resolution["run_id"] != manifest["run_id"] or resolution["logical_hash"] != manifest["logical_hash"]:
        raise ValueError("v3 structural run logical identity mismatch")
    return {"status": "PASS", "run_id": manifest["run_id"], "logical_hash": manifest["logical_hash"], "files": manifest["files"]}
