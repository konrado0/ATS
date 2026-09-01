from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from ats_ml.chronology import chronological_quartiles, derive_chronological_folds
from ats_ml.contracts import REPOSITORY_ROOT, FrozenD0Contract, load_frozen_d0_contract, resolve_pinned_inputs
from ats_ml.duplicates import registry_formula_collision_audit, resolve_p_duplicates
from ats_ml.features import attach_information_session_features, compute_stock_feature_history, feature_code_fingerprints
from ats_ml.guard import FIXTURE_REGISTRY, D1ExecutionGuard, Operation, pinned_real_context
from ats_ml.models import LIGHTGBM_PARAMETERS, RIDGE_PARAMETERS
from ats_research.hashing import canonical_json_bytes, content_hash, sha256_file


STRUCTURAL_OUTPUT_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/structural_runs")
REPOSITORY_RESOLUTION = REPOSITORY_ROOT / "source/python/configs/phase_d1_structural_resolution.json"
STRUCTURAL_COLUMNS = (
    "security_id",
    "session_date",
    "split_adjusted_close",
    "split_adjusted_high",
    "split_adjusted_low",
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
)
EXPECTED_FOLDS = {"MODEL_SELECTION_2022", "DEV_2023", "DEV_2024", "LOCKED_2025_2026"}
_STRUCTURAL_SEAL = object()


@dataclass(frozen=True, init=False)
class StructuralBuild:
    resolution: dict[str, Any]
    read_audit: dict[str, Any]

    def __init__(self, resolution: dict[str, Any], read_audit: dict[str, Any], *, _token: object):
        if _token is not _STRUCTURAL_SEAL:
            raise ValueError("structural publications must originate from the fixed D1 builder")
        object.__setattr__(self, "resolution", json.loads(json.dumps(resolution)))
        object.__setattr__(self, "read_audit", json.loads(json.dumps(read_audit)))


def _package_versions() -> dict[str, str]:
    names = ("numpy", "pandas", "polars", "pyarrow", "scikit-learn", "lightgbm", "pydantic", "PyYAML", "duckdb", "pytest")
    return {name: importlib.metadata.version(name) for name in names}


def _implementation_fingerprints(contract: FrozenD0Contract) -> dict[str, Any]:
    source_root = REPOSITORY_ROOT / "source/python/src/ats_ml"
    files = sorted(source_root.glob("*.py"), key=lambda path: path.name)
    hashes = {path.relative_to(REPOSITORY_ROOT).as_posix(): sha256_file(path) for path in files}
    environment = REPOSITORY_ROOT / "RESEARCH/environment/environment.yml"
    return {
        "files": hashes,
        "feature_formula_fingerprints": feature_code_fingerprints(contract),
        "registry_formula_collision_audit": registry_formula_collision_audit(contract),
        "registry_sha256": sha256_file(REPOSITORY_ROOT / "source/python/configs/phase_d0_feature_registry.json"),
        "fixture_registry_sha256": sha256_file(FIXTURE_REGISTRY),
        "environment_lock": {"path": environment.relative_to(REPOSITORY_ROOT).as_posix(), "sha256": sha256_file(environment)},
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": _package_versions(),
        "ridge_parameters": RIDGE_PARAMETERS,
        "lightgbm_parameters": LIGHTGBM_PARAMETERS,
    }


def _ordered_sessions(values: Any, role: str) -> pd.DatetimeIndex:
    sessions = pd.DatetimeIndex(pd.to_datetime(values, errors="coerce")).normalize()
    if sessions.hasnans:
        raise ValueError(f"{role} calendar contains invalid sessions")
    return sessions.sort_values().unique()


def assert_calendar_provenance(
    candidate_sessions: Any,
    validated_wig_sessions: Any,
    official_membership_sessions: Any,
    market_state_sessions: Any,
) -> dict[str, Any]:
    candidate = _ordered_sessions(candidate_sessions, "candidate")
    wig_all = _ordered_sessions(validated_wig_sessions, "validated WIG")
    official = _ordered_sessions(official_membership_sessions, "official membership")
    market = _ordered_sessions(market_state_sessions, "market-state")
    if len(candidate) == 0 or len(official) == 0:
        raise ValueError("calendar provenance requires nonempty candidate and official calendars")
    wig = wig_all[(wig_all >= candidate[0]) & (wig_all <= candidate[-1])]
    if not candidate.equals(wig):
        candidate_only = candidate.difference(wig)
        wig_only = wig.difference(candidate)
        raise ValueError(
            "candidate calendar differs from validated WIG over the candidate range; "
            f"candidate_only={list(candidate_only[:5])}, wig_only={list(wig_only[:5])}"
        )
    if not official.equals(market):
        official_only = official.difference(market)
        market_only = market.difference(official)
        raise ValueError(
            "official membership calendar differs from accepted market-state sessions; "
            f"official_only={list(official_only[:5])}, market_only={list(market_only[:5])}"
        )

    def calendar_hash(sessions: pd.DatetimeIndex) -> str:
        return content_hash([value.strftime("%Y-%m-%d") for value in sessions])

    return {
        "status": "PASS",
        "candidate_vs_validated_wig_equal": True,
        "official_membership_vs_market_state_equal": True,
        "candidate_calendar_count": len(candidate),
        "validated_wig_candidate_range_count": len(wig),
        "official_membership_calendar_count": len(official),
        "market_state_calendar_count": len(market),
        "candidate_calendar_start": candidate[0].strftime("%Y-%m-%d"),
        "candidate_calendar_end": candidate[-1].strftime("%Y-%m-%d"),
        "candidate_calendar_hash": calendar_hash(candidate),
        "validated_wig_candidate_range_hash": calendar_hash(wig),
        "official_membership_calendar_hash": calendar_hash(official),
        "market_state_calendar_hash": calendar_hash(market),
    }


def _resolve_validated_wig(market_state_manifest_path: Path) -> tuple[Path, str]:
    manifest = json.loads(market_state_manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    artifacts = manifest.get("artifacts", {})
    file_entry = files.get("tables/validated_wig.parquet")
    artifact_entry = artifacts.get("validated_wig.parquet")
    if not isinstance(file_entry, dict) or not isinstance(artifact_entry, dict):
        raise ValueError("market-state manifest does not pin validated_wig.parquet")
    digest = str(file_entry.get("sha256", ""))
    if digest != artifact_entry.get("sha256"):
        raise ValueError("market-state manifest validated-WIG hashes disagree")
    path = market_state_manifest_path.parent / "tables/validated_wig.parquet"
    if not path.is_file() or sha256_file(path) != digest:
        raise ValueError("validated WIG calendar artifact does not match the pinned market-state manifest")
    return path, digest


def build_structural_resolution() -> StructuralBuild:
    contract = load_frozen_d0_contract()
    paths = resolve_pinned_inputs(contract)
    guard = D1ExecutionGuard(contract)
    context = pinned_real_context(contract)
    guard.require(Operation.READ_SCHEMA, context)
    parquet = pq.ParquetFile(paths["candidate_panel"])
    schema_columns = tuple(parquet.schema_arrow.names)
    if set(STRUCTURAL_COLUMNS) - set(schema_columns):
        raise ValueError("candidate panel lacks D1 structural columns")
    if set(STRUCTURAL_COLUMNS) & set(FORBIDDEN_COLUMNS):
        raise AssertionError("structural projection includes a forbidden predictive column")
    panel = pd.read_parquet(paths["candidate_panel"], columns=list(STRUCTURAL_COLUMNS))
    panel["session_date"] = pd.to_datetime(panel["session_date"]).dt.normalize()
    if any(column in panel for column in FORBIDDEN_COLUMNS):
        raise AssertionError("forbidden predictive data entered structural memory")
    calendar = pd.DatetimeIndex(sorted(panel["session_date"].unique()))
    validated_wig_path, validated_wig_sha256 = _resolve_validated_wig(paths["market_state_manifest"])
    validated_wig = pd.read_parquet(validated_wig_path, columns=["session_date"])
    market_state_sessions = pd.read_parquet(paths["market_state_feature_artifact"], columns=["decision_session"])
    official_calendar = panel.loc[panel["official_membership"].fillna(False), "session_date"]
    calendar_provenance = assert_calendar_provenance(
        calendar,
        validated_wig["session_date"],
        official_calendar,
        market_state_sessions["decision_session"],
    )
    eval_start = pd.Timestamp(contract.config["observation_contract"]["evaluation_start"])
    cutoff = pd.Timestamp("2024-12-30")
    p_panel = panel.loc[panel["session_date"].le(cutoff)].copy()
    p_calendar = calendar[calendar <= cutoff]
    p_history = compute_stock_feature_history(p_panel, p_calendar, contract, guard, context, blocks=("P",))
    membership = panel.loc[
        panel["official_membership"].fillna(False) & panel["session_date"].between(eval_start, cutoff),
        ["security_id", "session_date", "official_membership", "missing_state", "nontrading_reason", "coverage_result"],
    ].copy()
    p_observations = attach_information_session_features(membership, p_history, calendar, contract.feature_blocks["P"])
    p_resolution = resolve_p_duplicates(p_observations, contract)
    fold_sessions, boundary_objects = derive_chronological_folds(calendar, contract, guard, context)
    boundaries = {fold: [asdict(item) for item in values] for fold, values in boundary_objects.items()}
    guard.require(Operation.RESOLVE_CONCENTRATION_BINS, context)
    bins: dict[str, list[dict[str, object]]] = {}
    for fold_id, group in fold_sessions.loc[(fold_sessions["partition"] == "evaluation") & fold_sessions["retained"]].groupby("fold_id", sort=True):
        bins[fold_id] = chronological_quartiles(group["decision_session"])
    guard.require(Operation.RESOLVE_FINGERPRINTS, context)
    implementation = _implementation_fingerprints(contract)
    candidate_manifest = json.loads(paths["candidate_manifest"].read_text(encoding="utf-8"))
    official = panel.loc[panel["official_membership"].fillna(False)]
    per_session = official.groupby("session_date")["security_id"].nunique()
    core: dict[str, Any] = {
        "schema_version": "ats.phase_d1.structural_resolution.v2",
        "d0_contract_version": contract.config["contract_version"],
        "d0_artifacts": contract.hashes,
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
        "read_audit": {
            "artifacts_opened": [
                str(paths["candidate_manifest"]),
                str(paths["candidate_panel"]),
                str(paths["market_state_manifest"]),
                str(paths["market_state_feature_artifact"]),
                str(validated_wig_path),
            ],
            "candidate_parquet_metadata_rows": parquet.metadata.num_rows,
            "candidate_schema_columns": list(schema_columns),
            "candidate_value_columns_loaded": list(STRUCTURAL_COLUMNS),
            "market_state_feature_values_loaded": False,
            "calendar_key_columns_loaded": {
                "market_state_feature_artifact": ["decision_session"],
                "validated_wig": ["session_date"],
            },
            "forbidden_columns": list(FORBIDDEN_COLUMNS),
            "forbidden_columns_loaded_or_derived": False,
            "realized_label_values_loaded_or_derived": False,
            "feature_label_correlations_or_ic_computed": False,
            "model_scores_predictions_tail_outcomes_or_economics_computed": False,
        },
        "purge_boundaries": boundaries,
        "calendar_provenance": calendar_provenance,
        "p_duplicate_resolution": p_resolution,
        "chronological_concentration_bins": bins,
        "implementation_and_environment": implementation,
        "structural_counts": {
            "candidate_rows": len(panel),
            "calendar_sessions": len(calendar),
            "official_member_rows": len(official),
            "official_session_count_min": int(per_session.min()),
            "official_session_count_max": int(per_session.max()),
            "p_population_rows": len(p_observations),
            "p_population_sessions": int(p_observations["decision_session"].nunique()),
            "p_feature_valid_counts": {name: int(p_observations[name].notna().sum()) for name in contract.feature_blocks["P"]},
        },
        "authorization": {
            "synthetic_fixture_fit_predict": True,
            "real_structural_values": "only the four frozen D1 resolutions",
            "real_model_fit": False,
            "real_prediction": False,
            "real_predictive_execution": False,
            "phase_d2": False,
        },
        "physical_hashes": {
            "candidate_manifest": sha256_file(paths["candidate_manifest"]),
            "candidate_panel": sha256_file(paths["candidate_panel"]),
            "market_state_manifest": sha256_file(paths["market_state_manifest"]),
            "market_state_feature_artifact": sha256_file(paths["market_state_feature_artifact"]),
            "validated_wig": validated_wig_sha256,
            "implementation_files": implementation["files"],
        },
    }
    logical_hash = content_hash(core)
    resolution = {**core, "logical_hash": logical_hash, "run_id": f"phase-d1-structural-{logical_hash[:20]}"}
    read_audit = resolution["read_audit"] | {"run_id": resolution["run_id"], "status": "PASS"}
    return StructuralBuild(resolution, read_audit, _token=_STRUCTURAL_SEAL)


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n")


def publish_structural_resolution(build: StructuralBuild) -> Path:
    if not isinstance(build, StructuralBuild):
        raise ValueError("structural publication accepts only a sealed builder result")
    resolution = build.resolution
    read_audit = build.read_audit
    _validate_structural_payload(resolution, read_audit)
    STRUCTURAL_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    destination = STRUCTURAL_OUTPUT_ROOT / resolution["run_id"]
    stage = STRUCTURAL_OUTPUT_ROOT / f".stage-{resolution['run_id']}-{uuid.uuid4().hex}"
    stage.mkdir()
    try:
        _write_json(stage / "structural_resolution.json", resolution)
        _write_json(stage / "permitted_read_audit.json", read_audit)
        manifest = {
            "schema_version": "ats.phase_d1.structural_run_manifest.v2",
            "run_id": resolution["run_id"],
            "logical_hash": resolution["logical_hash"],
            "files": {
                "structural_resolution.json": sha256_file(stage / "structural_resolution.json"),
                "permitted_read_audit.json": sha256_file(stage / "permitted_read_audit.json"),
            },
            "mutable_latest_pointer": False,
            "real_fit_or_prediction_authorized": False,
        }
        _write_json(stage / "manifest.json", manifest)
        validate_structural_run(stage)
        if destination.exists():
            existing = validate_structural_run(destination)
            if existing["files"] != manifest["files"]:
                raise ValueError("immutable structural run collision")
            shutil.rmtree(stage)
        else:
            os.replace(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    published = json.loads((destination / "structural_resolution.json").read_text(encoding="utf-8"))
    _write_json(REPOSITORY_RESOLUTION, published)
    return destination


def _validate_structural_payload(resolution: dict[str, Any], read_audit: dict[str, Any]) -> None:
    contract = load_frozen_d0_contract()
    paths = resolve_pinned_inputs(contract)
    required = {
        "schema_version", "d0_contract_version", "d0_artifacts", "pinned_inputs", "read_audit",
        "purge_boundaries", "calendar_provenance", "p_duplicate_resolution", "chronological_concentration_bins",
        "implementation_and_environment", "structural_counts", "authorization", "physical_hashes",
        "logical_hash", "run_id",
    }
    if set(resolution) != required:
        raise ValueError(f"structural resolution schema mismatch: {sorted(set(resolution) ^ required)}")
    if resolution["schema_version"] != "ats.phase_d1.structural_resolution.v2":
        raise ValueError("unexpected structural resolution schema")
    if resolution["d0_contract_version"] != contract.config["contract_version"] or resolution["d0_artifacts"] != contract.hashes:
        raise ValueError("structural resolution does not bind accepted D0 bytes")
    pinned = resolution["pinned_inputs"]
    validated_wig_path, validated_wig_sha256 = _resolve_validated_wig(paths["market_state_manifest"])
    expected_pinned = {
        "candidate_run_id": contract.pinned_identity["candidate_run_id"],
        "candidate_manifest_sha256": contract.pinned_identity["candidate_manifest_sha256"],
        "candidate_panel_sha256": contract.pinned_identity["candidate_panel_sha256"],
        "candidate_logical_hash": contract.pinned_identity["candidate_logical_hash"],
        "candidate_data_basis_version": contract.pinned_identity["candidate_data_basis_version"],
        "market_state_manifest_sha256": contract.config["input"]["market_state_manifest_sha256"],
        "market_state_feature_artifact_sha256": contract.config["input"]["market_state_feature_artifact_sha256"],
        "validated_wig_sha256": validated_wig_sha256,
    }
    if pinned != expected_pinned:
        raise ValueError("structural resolution pinned-input identity mismatch")
    audit = resolution["read_audit"]
    false_claims = (
        "market_state_feature_values_loaded", "forbidden_columns_loaded_or_derived",
        "realized_label_values_loaded_or_derived", "feature_label_correlations_or_ic_computed",
        "model_scores_predictions_tail_outcomes_or_economics_computed",
    )
    if any(audit.get(key) is not False for key in false_claims):
        raise ValueError("structural read audit contains a forbidden operation")
    if tuple(audit.get("candidate_value_columns_loaded", ())) != STRUCTURAL_COLUMNS:
        raise ValueError("structural read projection differs from the frozen allowlist")
    if set(audit.get("candidate_value_columns_loaded", ())) & set(FORBIDDEN_COLUMNS):
        raise ValueError("structural read projection includes predictive columns")
    if tuple(audit.get("forbidden_columns", ())) != FORBIDDEN_COLUMNS:
        raise ValueError("structural forbidden-column declaration mismatch")
    if audit.get("calendar_key_columns_loaded") != {
        "market_state_feature_artifact": ["decision_session"],
        "validated_wig": ["session_date"],
    }:
        raise ValueError("structural calendar-key read projection differs from the frozen assertion")
    expected_opened = {str(path) for path in paths.values()} | {str(validated_wig_path)}
    if set(audit.get("artifacts_opened", ())) != expected_opened:
        raise ValueError("structural read-audit artifact set mismatch")
    if read_audit != audit | {"run_id": resolution["run_id"], "status": "PASS"}:
        raise ValueError("standalone permitted-read audit differs from the resolution")
    if set(resolution["purge_boundaries"]) != EXPECTED_FOLDS or set(resolution["chronological_concentration_bins"]) != EXPECTED_FOLDS:
        raise ValueError("structural fold set mismatch")
    if any(len(value) != 4 for value in resolution["chronological_concentration_bins"].values()):
        raise ValueError("each evaluation fold must have four chronological concentration bins")
    calendar_provenance = resolution["calendar_provenance"]
    if calendar_provenance.get("status") != "PASS":
        raise ValueError("structural calendar provenance is not PASS")
    if calendar_provenance.get("candidate_vs_validated_wig_equal") is not True or calendar_provenance.get("official_membership_vs_market_state_equal") is not True:
        raise ValueError("structural calendar provenance equality is not proven")
    if calendar_provenance.get("candidate_calendar_hash") != calendar_provenance.get("validated_wig_candidate_range_hash"):
        raise ValueError("candidate and validated-WIG calendar hashes differ")
    if calendar_provenance.get("official_membership_calendar_hash") != calendar_provenance.get("market_state_calendar_hash"):
        raise ValueError("official membership and market-state calendar hashes differ")
    p_resolution = resolution["p_duplicate_resolution"]
    if int(p_resolution.get("survivor_count", 0)) < 5 or len(p_resolution.get("survivors", ())) != p_resolution.get("survivor_count"):
        raise ValueError("structural P duplicate resolution violates the frozen minimum")
    p_names = set(contract.feature_blocks["P"])
    if not set(p_resolution.get("survivors", ())).issubset(p_names) or set(p_resolution.get("coverage", {})) != p_names:
        raise ValueError("structural P resolution feature set differs from the frozen block")
    if len(p_resolution.get("pair_metrics", ())) != len(p_names) * (len(p_names) - 1) // 2:
        raise ValueError("structural P resolution does not contain every pair")
    if p_resolution.get("population_cutoff") != "2024-12-30":
        raise ValueError("structural P duplicate population cutoff changed")
    authorization = resolution["authorization"]
    if authorization != {
        "synthetic_fixture_fit_predict": True,
        "real_structural_values": "only the four frozen D1 resolutions",
        "real_model_fit": False,
        "real_prediction": False,
        "real_predictive_execution": False,
        "phase_d2": False,
    }:
        raise ValueError("structural authorization state mismatch")
    implementation = resolution["implementation_and_environment"]
    for key in ("files", "feature_formula_fingerprints", "registry_formula_collision_audit", "environment_lock", "packages", "ridge_parameters", "lightgbm_parameters", "fixture_registry_sha256"):
        if key not in implementation:
            raise ValueError(f"structural implementation fingerprint missing: {key}")
    if implementation["ridge_parameters"] != RIDGE_PARAMETERS or implementation["lightgbm_parameters"] != LIGHTGBM_PARAMETERS:
        raise ValueError("structural model parameter fingerprints changed")
    if implementation["registry_sha256"] != contract.hashes["source/python/configs/phase_d0_feature_registry.json"]:
        raise ValueError("structural feature-registry fingerprint mismatch")
    if implementation["fixture_registry_sha256"] != sha256_file(FIXTURE_REGISTRY):
        raise ValueError("structural fixture-registry fingerprint mismatch")
    if implementation["registry_formula_collision_audit"] != registry_formula_collision_audit(contract):
        raise ValueError("structural registry-wide formula-collision audit mismatch")
    physical = resolution["physical_hashes"]
    if physical != {
        "candidate_manifest": pinned["candidate_manifest_sha256"],
        "candidate_panel": pinned["candidate_panel_sha256"],
        "market_state_manifest": pinned["market_state_manifest_sha256"],
        "market_state_feature_artifact": pinned["market_state_feature_artifact_sha256"],
        "validated_wig": pinned["validated_wig_sha256"],
        "implementation_files": implementation["files"],
    }:
        raise ValueError("structural physical hashes do not reconcile")
    counts = resolution["structural_counts"]
    if counts.get("official_session_count_min") != 60 or counts.get("official_session_count_max") != 60:
        raise ValueError("structural official denominator is not exactly 60")
    if set(counts.get("p_feature_valid_counts", {})) != p_names or any(int(counts[key]) <= 0 for key in ("candidate_rows", "calendar_sessions", "official_member_rows", "p_population_rows", "p_population_sessions")):
        raise ValueError("structural count evidence is incomplete")
    if int(calendar_provenance.get("candidate_calendar_count", 0)) != int(counts["calendar_sessions"]):
        raise ValueError("calendar provenance count does not reconcile to structural counts")
    stable = {key: value for key, value in resolution.items() if key not in {"logical_hash", "run_id"}}
    logical = content_hash(stable)
    if resolution["logical_hash"] != logical or resolution["run_id"] != f"phase-d1-structural-{logical[:20]}":
        raise ValueError("structural logical identity mismatch")


def validate_structural_run(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if set(manifest) != {"schema_version", "run_id", "logical_hash", "files", "mutable_latest_pointer", "real_fit_or_prediction_authorized"}:
        raise ValueError("structural manifest schema mismatch")
    if manifest["schema_version"] != "ats.phase_d1.structural_run_manifest.v2" or manifest["mutable_latest_pointer"] is not False or manifest["real_fit_or_prediction_authorized"] is not False:
        raise ValueError("structural manifest authorization or schema mismatch")
    if run_dir.name != manifest["run_id"] and not run_dir.name.startswith(".stage-"):
        raise ValueError("structural run directory identity mismatch")
    if set(manifest["files"]) != {"structural_resolution.json", "permitted_read_audit.json"}:
        raise ValueError("structural manifest file allowlist mismatch")
    expected = {"manifest.json", *manifest["files"]}
    actual = {path.name for path in run_dir.iterdir() if path.is_file()}
    if actual != expected:
        raise ValueError(f"structural run artifact set mismatch: expected={sorted(expected)}, actual={sorted(actual)}")
    for name, digest in manifest["files"].items():
        if sha256_file(run_dir / name) != digest:
            raise ValueError(f"structural run hash mismatch: {name}")
    resolution = json.loads((run_dir / "structural_resolution.json").read_text(encoding="utf-8"))
    read_audit = json.loads((run_dir / "permitted_read_audit.json").read_text(encoding="utf-8"))
    _validate_structural_payload(resolution, read_audit)
    if resolution["logical_hash"] != manifest["logical_hash"] or resolution["run_id"] != manifest["run_id"]:
        raise ValueError("structural run logical identity mismatch")
    return {"status": "PASS", "run_id": manifest["run_id"], "logical_hash": manifest["logical_hash"], "files": manifest["files"]}
