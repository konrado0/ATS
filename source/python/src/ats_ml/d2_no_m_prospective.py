from __future__ import annotations

import math
import os
import shutil
import hashlib
import subprocess
import copy
from dataclasses import replace
import tempfile
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from ats_ml.d2_artifacts import D2ArtifactError, file_inventory, read_json, write_json
from ats_ml.d2_no_m import CONTRACT_PATH, NO_M, COMPARATORS, PREDICTION_ROOT, load_contract
from ats_ml.d2_stage1 import SequentialLabelAdmissionFirewall, _actual_fit, _score_rows
from ats_ml.contracts_v3 import D0_V3_CONFIG, load_frozen_d0_v3_contract
from ats_ml.models import LIGHTGBM_PARAMETERS, RIDGE_PARAMETERS
from ats_ml.labels import label_endpoints
from ats_ml.walkforward import _new_estimator, derive_walk_forward_plan
from ats_research.hashing import content_hash, logical_frame_hash, sha256_file


LEGACY_STREAM_ID = "phase-d2-nm-post-freeze-2026-v2"
STREAM_ID = "phase-d2-nm-post-freeze-2026-v3"
STREAMS_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/prospective_streams")
STREAM_ROOT = STREAMS_ROOT / STREAM_ID
LEGACY_STREAM_ROOT = STREAMS_ROOT / LEGACY_STREAM_ID
SUPERSESSION_ROOT = STREAMS_ROOT / "supersessions"
PROSPECTIVE_CONTRACT_PATH = Path(__file__).resolve().parents[2] / "configs/phase_d2_no_m_prospective_v3.json"
DERIVED_CONTRACT_PATH = PREDICTION_ROOT / "derived_contract.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
EXPECTED_CELLS = (NO_M, *COMPARATORS)
OUTCOME_TOKENS = ("label", "outcome", "return_20", "forward", "target_value")
SCORER_COLUMNS = {
    "information_session", "decision_session", "decision_ts", "cell_id", "security_id",
    "model_score", "threshold", "candidate", "prediction_generation_ts",
    "official_expected_count", "model_exclusion_reason",
}
PUBLISHER_ONLY_COLUMNS = {"prospective_eligible", "monitoring_only", "exclusion_reason"}
INPUT_FILES = (
    "observations.parquet", "training_labels.parquet", "walk_forward_block.json",
    "pit_membership.parquet", "official_calendar.parquet",
)
TRAINING_IMPLEMENTATION_PATHS = (
    "source/python/configs/phase_d0_reference_v3.json",
    "source/python/src/ats_ml/models.py",
    "source/python/src/ats_ml/walkforward.py",
    "source/python/src/ats_ml/d2_stage1.py",
    "source/python/src/ats_ml/d2_no_m_prospective.py",
)


def _now_utc() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def _committed_sha256(relative: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "show", f"HEAD:{relative}"],
        cwd=REPOSITORY_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise D2ArtifactError(f"cannot verify committed operational contract: {relative}")
    return hashlib.sha256(result.stdout).hexdigest()


def _model_definitions() -> dict[str, Any]:
    return {
        "RIDGE": {
            "estimator": "sklearn.linear_model.Ridge",
            "parameters": dict(RIDGE_PARAMETERS),
            "preprocessing": [
                {"step": "SimpleImputer", "strategy": "median", "add_indicator": False, "keep_empty_features": False},
                {"step": "StandardScaler", "with_mean": True, "with_std": True},
            ],
        },
        "LIGHTGBM": {
            "estimator": "lightgbm.LGBMRegressor",
            "parameters": dict(LIGHTGBM_PARAMETERS),
            "preprocessing": [],
            "missing_value_behavior": "native LightGBM handling",
        },
    }


def _implementation_fingerprint() -> dict[str, Any]:
    files = {path: _committed_sha256(path) for path in TRAINING_IMPLEMENTATION_PATHS}
    definition = {"files": files, "model_definitions": _model_definitions()}
    return {**definition, "fingerprint": content_hash(definition)}


def _atomic_directory(destination: Path, build: Callable[[Path], None]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise D2ArtifactError(f"append-only destination already exists: {destination}")
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        build(stage)
        os.replace(stage, destination)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise D2ArtifactError(f"append-only file already exists: {path}")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(fd)
    temp_path = Path(temporary)
    try:
        write_json(temp_path, value)
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _verified_contract_binding() -> dict[str, Any]:
    operational = read_json(PROSPECTIVE_CONTRACT_PATH)
    scientific = load_contract()
    derived = read_json(DERIVED_CONTRACT_PATH)
    expected = {
        cell: {"feature_names": derived["cells"][cell]["feature_names"], "model": derived["cells"][cell]["model"]}
        for cell in EXPECTED_CELLS
    }
    if operational.get("scientific_contract_id") != scientific.get("contract_id"):
        raise D2ArtifactError("corrupt prospective scientific-contract binding")
    if operational.get("cells") != expected:
        raise D2ArtifactError("prospective feature allowlist or model definition differs from accepted D2")
    if operational.get("training_procedure", {}).get("model_definitions") != _model_definitions():
        raise D2ArtifactError("prospective estimator parameters or preprocessing differ from committed implementation")
    declared = operational.get("bindings", {})
    actual = {
        "scientific_contract_sha256": sha256_file(CONTRACT_PATH),
        "accepted_derived_contract_sha256": sha256_file(DERIVED_CONTRACT_PATH),
        "phase_d0_v3_contract_sha256": _committed_sha256("source/python/configs/phase_d0_reference_v3.json"),
    }
    if declared != actual:
        raise D2ArtifactError("corrupt prospective contract hash binding")
    return {
        "operational_contract_sha256": _committed_sha256("source/python/configs/phase_d2_no_m_prospective_v3.json"),
        **actual,
        "cells": expected,
        "training_procedure": operational["training_procedure"],
    }


def _load_input_package(package_dir: Path) -> tuple[dict[str, Any], dict[str, pd.DataFrame | dict[str, Any]]]:
    config_path = package_dir / "input_config.json"
    config = read_json(config_path)
    if config.get("schema_version") != "ats.phase_d2_nm.prospective_input.v3":
        raise D2ArtifactError("unexpected prospective input schema")
    files = config.get("files", {})
    loaded: dict[str, pd.DataFrame | dict[str, Any]] = {}
    for name in INPUT_FILES:
        path = package_dir / name
        record = files.get(name, {})
        if not path.is_file() or record.get("sha256") != sha256_file(path):
            raise D2ArtifactError(f"pinned prospective input mismatch: {name}")
        loaded[name] = read_json(path) if path.suffix == ".json" else pd.read_parquet(path)
    return config, loaded


def _calendar_and_targets(config: dict[str, Any], loaded: dict[str, pd.DataFrame | dict[str, Any]]) -> tuple[pd.DatetimeIndex, dict[pd.Timestamp, dict[str, Any]]]:
    calendar_frame = loaded["official_calendar.parquet"]
    assert isinstance(calendar_frame, pd.DataFrame)
    if set(calendar_frame.columns) != {"session_date"}:
        raise D2ArtifactError("official calendar artifact must contain only session_date")
    calendar = pd.DatetimeIndex(pd.to_datetime(calendar_frame["session_date"])).normalize()
    if calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise D2ArtifactError("pinned official calendar is duplicate or unordered")
    positions = {value: index for index, value in enumerate(calendar)}
    targets: dict[pd.Timestamp, dict[str, Any]] = {}
    for row in config.get("targets", []):
        decision = pd.Timestamp(row["decision_session"]).normalize()
        index = positions.get(decision)
        if index is None or index == 0 or index + 20 >= len(calendar):
            raise D2ArtifactError("target decision session lacks the frozen calendar context")
        endpoint = calendar[index + 20]
        expected = {
            "information_session": calendar[index - 1], "decision_session": decision,
            "decision_ts": decision.tz_localize("Europe/Warsaw") + pd.Timedelta(hours=8, minutes=45),
            "target_start_session": decision, "target_endpoint_session": endpoint,
            "label_availability_ts": endpoint.tz_localize("Europe/Warsaw") + pd.Timedelta(hours=9),
        }
        for field, value in expected.items():
            supplied = pd.Timestamp(row[field])
            if field.endswith("_ts"):
                if supplied.tzinfo is None or supplied.tz_convert("UTC") != value.tz_convert("UTC"):
                    raise D2ArtifactError(f"invalid frozen target timing: {field}")
            elif supplied.normalize().tz_localize(None) != value.normalize().tz_localize(None):
                raise D2ArtifactError(f"invalid frozen target timing: {field}")
        targets[decision] = expected
    declared = {pd.Timestamp(value).normalize() for value in config.get("decision_sessions", [])}
    if not declared or set(targets) != declared:
        raise D2ArtifactError("target bindings differ from requested decision sessions")
    return calendar, targets


def _derive_expected_walk_forward_block(
    config: dict[str, Any],
    loaded: dict[str, pd.DataFrame | dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    calendar, targets = _calendar_and_targets(config, loaded)
    decisions = sorted(targets)
    halves = {(value.year, 1 if value.month <= 6 else 2) for value in decisions}
    if len(halves) != 1:
        raise D2ArtifactError("one prospective package cannot cross a January/July refit boundary")
    year, half = next(iter(halves))
    specification = {
        "block_id": f"PROSPECTIVE_{year}_H{half}",
        "calendar_half": f"{year}H{half}",
        "role": "prospective_monitoring",
        "complete": False,
        "observation_end": decisions[-1].strftime("%Y-%m-%d"),
    }
    frozen = load_frozen_d0_v3_contract()
    composed = copy.deepcopy(frozen.config)
    composed["v3_amendment"]["evidence_blocks"] = [specification]
    derived = derive_walk_forward_plan(calendar, replace(frozen, config=composed))
    expected = derived["blocks"][0]
    if config.get("refit_session") != expected["refit_session"]:
        raise D2ArtifactError("prospective refit binding differs from the first January/July official session")
    if not set(config["decision_sessions"]).issubset(set(expected["evaluation_sessions"])):
        raise D2ArtifactError("requested sessions are outside the derived following half-year score block")
    endpoints = label_endpoints(calendar, calendar, timezone="Europe/Warsaw").set_index("decision_session")

    def exact_purge(candidates: list[str], retained: list[str], boundary: str) -> bool:
        candidate_dates = pd.DatetimeIndex(pd.to_datetime(candidates)).normalize()
        boundary_ts = pd.Timestamp(boundary).tz_localize("Europe/Warsaw") + pd.Timedelta(hours=8, minutes=45)
        expected_retained = endpoints.loc[candidate_dates, "label_endpoint_ts"]
        expected_retained = list(candidate_dates[expected_retained.notna() & expected_retained.lt(boundary_ts)])
        return [pd.Timestamp(value) for value in retained] == expected_retained

    inner_purge = []
    for item in expected["inner_score_blocks"]:
        candidates = calendar[
            (calendar >= pd.Timestamp(item["fit_start"]))
            & (calendar <= pd.Timestamp(item["fit_end_candidate"]))
        ]
        inner_purge.append(exact_purge(
            [value.strftime("%Y-%m-%d") for value in candidates],
            item["fit_retained_sessions"],
            item["fit_boundary_session"],
        ))
    proof = {
        "schema_version": "ats.phase_d2_nm.walk_forward_proof.v3",
        "block_id": expected["block_id"],
        "block_logical_hash": content_hash(expected),
        "refit_session": expected["refit_session"],
        "estimator_window_calendar_months": 36,
        "estimator_window_start": expected["estimator_window_start"],
        "estimator_window_end": expected["estimator_window_end"],
        "inner_calibration_block_count": len(expected["inner_score_blocks"]),
        "inner_fit_history_months": [item["fit_history_months"] for item in expected["inner_score_blocks"]],
        "inner_score_block_months": 6,
        "endpoint_purge_strict_before_each_boundary": all(inner_purge) and exact_purge(
            expected["estimator_window_sessions"],
            expected["final_fit"]["retained_sessions"],
            expected["final_fit"]["boundary_session"],
        ),
    }
    if proof["inner_calibration_block_count"] != 3 or proof["inner_fit_history_months"] != [18, 24, 30]:
        raise D2ArtifactError("derived calibration structure differs from the frozen three-block contract")
    if proof["endpoint_purge_strict_before_each_boundary"] is not True:
        raise D2ArtifactError("derived endpoint purge is not strictly before its boundary")
    proof["proof_hash"] = content_hash(proof)
    return expected, proof


def _derive_and_verify_walk_forward_block(
    config: dict[str, Any],
    loaded: dict[str, pd.DataFrame | dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected, proof = _derive_expected_walk_forward_block(config, loaded)
    supplied = loaded["walk_forward_block.json"]
    assert isinstance(supplied, dict)
    if supplied != expected:
        raise D2ArtifactError("submitted walk-forward block differs from the frozen canonical derivation")
    return expected, proof


def _validate_population_and_timing(observations: pd.DataFrame, membership: pd.DataFrame, targets: dict[pd.Timestamp, dict[str, Any]]) -> None:
    required = {"security_id", "decision_session", "official_membership"}
    if required - set(membership.columns):
        raise D2ArtifactError("pinned PIT membership artifact lacks required columns")
    official = membership.loc[membership["official_membership"].fillna(False)].copy()
    official["decision_session"] = pd.to_datetime(official["decision_session"]).dt.normalize()
    official["security_id"] = official["security_id"].astype(str)
    if official.duplicated(["decision_session", "security_id"]).any():
        raise D2ArtifactError("duplicate identities in pinned PIT membership")
    if official.groupby("decision_session").size().ne(60).any():
        raise D2ArtifactError("pinned PIT membership must contain exactly 60 unique identities per session")
    obs = observations.copy()
    obs["decision_session"] = pd.to_datetime(obs["decision_session"]).dt.normalize()
    obs["information_session"] = pd.to_datetime(obs["information_session"]).dt.normalize()
    obs["security_id"] = obs["security_id"].astype(str)
    if not set(targets).issubset(set(obs["decision_session"].unique())):
        raise D2ArtifactError("observation sessions differ from the pinned request")
    if obs.duplicated(["decision_session", "security_id"]).any():
        raise D2ArtifactError("duplicate identities in prospective observations")
    prospective = obs.loc[obs["decision_session"].isin(targets)]
    for session, group in prospective.groupby("decision_session", sort=True):
        expected = targets[pd.Timestamp(session)]
        member_ids = set(official.loc[official["decision_session"].eq(session), "security_id"])
        if len(group) != 60 or group["security_id"].nunique() != 60 or set(group["security_id"]) != member_ids:
            raise D2ArtifactError("prospective identities do not exactly match pinned PIT TOP60 membership")
        if not group["information_session"].eq(expected["information_session"]).all():
            raise D2ArtifactError("information_session is not the preceding official session")
        if not pd.to_datetime(group["decision_ts"], utc=True).eq(expected["decision_ts"].tz_convert("UTC")).all():
            raise D2ArtifactError("decision_ts is not exactly 08:45 Europe/Warsaw")
        if "official_expected_count" not in group or not group["official_expected_count"].eq(60).all():
            raise D2ArtifactError("official denominator 60 is not visible")


def validate_scorer_predictions(frame: pd.DataFrame, observations: pd.DataFrame, membership: pd.DataFrame, targets: dict[pd.Timestamp, dict[str, Any]]) -> dict[str, Any]:
    missing = SCORER_COLUMNS - set(frame.columns)
    if missing:
        raise D2ArtifactError(f"scorer prediction package lacks columns: {sorted(missing)}")
    forbidden = sorted(
        column for column in frame.columns
        if any(token in column.lower() for token in OUTCOME_TOKENS)
        or column.lower().startswith("publication_")
        or column.lower() in PUBLISHER_ONLY_COLUMNS
    )
    if forbidden:
        raise D2ArtifactError(f"outcome or publisher-authority column rejected: {forbidden}")
    if set(frame["cell_id"].astype(str)) != set(EXPECTED_CELLS):
        raise D2ArtifactError("prospective batch must contain exactly the frozen three cells")
    if frame.duplicated(["cell_id", "security_id", "decision_session"]).any():
        raise D2ArtifactError("duplicate prediction identity")
    _validate_population_and_timing(observations, membership, targets)
    base = observations[["security_id", "decision_session"]].copy()
    base["security_id"] = base["security_id"].astype(str)
    base["decision_session"] = pd.to_datetime(base["decision_session"]).dt.normalize()
    base = base.sort_values(["decision_session", "security_id"]).reset_index(drop=True)
    for cell, group in frame.groupby("cell_id", sort=True):
        keys = group[["security_id", "decision_session"]].copy()
        keys["security_id"] = keys["security_id"].astype(str)
        keys["decision_session"] = pd.to_datetime(keys["decision_session"]).dt.normalize()
        if not keys.sort_values(["decision_session", "security_id"]).reset_index(drop=True).equals(base):
            raise D2ArtifactError(f"{cell} population differs from the exact TOP60 observation population")
    if not frame["candidate"].eq(pd.to_numeric(frame["model_score"], errors="coerce").gt(frame["threshold"])).all():
        raise D2ArtifactError("strict prospective threshold rule failed")
    scored = np.isfinite(pd.to_numeric(frame["model_score"], errors="coerce"))
    if frame.loc[~scored, "model_exclusion_reason"].astype(str).str.len().eq(0).any():
        raise D2ArtifactError("unscored official rows require a visible exclusion reason")
    unknown = frame["model_exclusion_reason"].astype(str).str.contains("UNKNOWN_(?:SPLIT|MEMBERSHIP)_STATE", regex=True)
    if (unknown & scored).any():
        raise D2ArtifactError("unknown split or membership state was scored")
    return {"status": "PASS", "rows": len(frame), "decision_sessions": len(targets), "cells": list(EXPECTED_CELLS), "official_rows_per_cell_session": 60, "outcome_columns_absent": True, "publisher_columns_absent": True}


def _verify_score_package(score_package: Path) -> tuple[pd.DataFrame, dict[str, Any], dict[pd.Timestamp, dict[str, Any]], dict[str, Any]]:
    prediction_path = score_package / "predictions.parquet"
    audit_path = score_package / "scorer_audit.json"
    manifest_path = score_package / "manifest.json"
    if not prediction_path.is_file() or not audit_path.is_file() or not manifest_path.is_file():
        raise D2ArtifactError("complete scorer-generated audit sidecar and manifest are required")
    audit, manifest = read_json(audit_path), read_json(manifest_path)
    if audit.get("schema_version") != "ats.phase_d2_nm.scorer_audit.v3":
        raise D2ArtifactError("invalid scorer audit schema")
    for name in ("predictions.parquet", "scorer_audit.json"):
        record, path = manifest.get("files", {}).get(name, {}), score_package / name
        if record.get("bytes") != path.stat().st_size or record.get("sha256") != sha256_file(path):
            raise D2ArtifactError(f"scorer package manifest mismatch: {name}")
    binding = _verified_contract_binding()
    if audit.get("contract_binding") != binding:
        raise D2ArtifactError("corrupt scorer contract binding")
    if audit.get("cells") != binding["cells"]:
        raise D2ArtifactError("scorer audit feature allowlists or models changed")
    package_dir = Path(audit.get("input_package", ""))
    config, loaded = _load_input_package(package_dir)
    if audit.get("input_config_sha256") != sha256_file(package_dir / "input_config.json"):
        raise D2ArtifactError("scorer audit input-config hash changed")
    expected_inputs = {name: config["files"][name]["sha256"] for name in INPUT_FILES}
    if audit.get("pinned_input_hashes") != expected_inputs:
        raise D2ArtifactError("scorer audit pinned-input hashes changed")
    _calendar, targets = _calendar_and_targets(config, loaded)
    _block, walk_forward_proof = _derive_and_verify_walk_forward_block(config, loaded)
    if audit.get("walk_forward_proof") != walk_forward_proof:
        raise D2ArtifactError("scorer audit is not bound to the canonically derived walk-forward block")
    implementation = _implementation_fingerprint()
    if audit.get("implementation_fingerprint") != implementation:
        raise D2ArtifactError("scorer audit implementation, estimator parameters, or preprocessing fingerprint changed")
    observations, membership = loaded["observations.parquet"], loaded["pit_membership.parquet"]
    assert isinstance(observations, pd.DataFrame) and isinstance(membership, pd.DataFrame)
    frame = pd.read_parquet(prediction_path)
    validation = validate_scorer_predictions(frame, observations, membership, targets)
    if audit.get("prediction_sha256") != sha256_file(prediction_path):
        raise D2ArtifactError("scorer audit prediction hash changed")
    return frame, validation, targets, audit


def initialize_repaired_stream(*, reason: str, now_provider: Callable[[], pd.Timestamp] = _now_utc) -> Path:
    binding = _verified_contract_binding()
    if not (LEGACY_STREAM_ROOT / "registration.json").is_file():
        raise D2ArtifactError("legacy empty registration is missing")
    if list(LEGACY_STREAM_ROOT.glob("batches/*/predictions.parquet")):
        raise D2ArtifactError("legacy stream is not empty and cannot be superseded by this repair")
    legacy_hash = sha256_file(LEGACY_STREAM_ROOT / "registration.json")
    completed = pd.Timestamp(now_provider()).tz_convert("UTC")
    marker = {"schema_version": "ats.phase_d2_nm.stream_supersession.v1", "stream_id": LEGACY_STREAM_ID, "status": "NON_OPERATIONAL_SUPERSEDED_EMPTY_REGISTRATION", "prediction_rows": 0, "registration_sha256": legacy_hash, "superseded_by": STREAM_ID, "publisher_completed_ts": completed.isoformat(), "reason": reason}
    marker["logical_hash"] = content_hash(marker)
    _atomic_json(SUPERSESSION_ROOT / f"{LEGACY_STREAM_ID}.json", marker)

    def build(stage: Path) -> None:
        registration = {"schema_version": "ats.phase_d2_nm.prospective_registration.v3", "stream_id": STREAM_ID, "status": "ACTIVE_EMPTY_AWAITING_ELIGIBLE_SESSION", "publisher_completed_ts": completed.isoformat(), "contract_binding": binding, "implementation_fingerprint": _implementation_fingerprint(), "supersedes": LEGACY_STREAM_ID, "legacy_registration_sha256": legacy_hash, "missed_predictions_are_never_backfilled": True, "late_publications_are_permanently_monitoring_only": True, "reason": reason}
        registration["logical_hash"] = content_hash(registration)
        write_json(stage / "registration.json", registration)
        write_json(stage / "manifest.json", {"schema_version": "ats.phase_d2_nm.prospective_stream.v3", "stream_id": STREAM_ID, "files": file_inventory(stage), "mutable_latest_pointer": False})
    _atomic_directory(STREAM_ROOT, build)
    return STREAM_ROOT


def append_prediction_batch(score_package: Path, *, batch_id: str, now_provider: Callable[[], pd.Timestamp] = _now_utc) -> Path:
    if not (STREAM_ROOT / "registration.json").is_file():
        raise D2ArtifactError("repaired prospective stream is not registered")
    if not batch_id or any(token in batch_id.lower() for token in ("latest", "current")):
        raise D2ArtifactError("immutable batch ID is required")
    frame, validation, targets, audit = _verify_score_package(score_package)
    keys = ["cell_id", "security_id", "decision_session"]
    existing = [pd.read_parquet(path, columns=keys) for path in STREAM_ROOT.glob("batches/*/predictions.parquet")]
    if existing and len(frame.merge(pd.concat(existing), on=keys, how="inner")):
        raise D2ArtifactError("conflicting duplicate prospective prediction rejected")
    destination, receipt_path = STREAM_ROOT / "batches" / batch_id, STREAM_ROOT / "receipts" / f"{batch_id}.json"
    started = pd.Timestamp(now_provider()).tz_convert("UTC")

    def build(stage: Path) -> None:
        output = frame.copy()
        sessions = pd.to_datetime(output["decision_session"]).dt.normalize()
        for field in ("target_start_session", "target_endpoint_session", "label_availability_ts"):
            output[field] = [targets[value][field] for value in sessions]
        output.sort_values(["decision_session", "cell_id", "security_id"], kind="mergesort").to_parquet(stage / "predictions.parquet", index=False, compression="zstd", use_dictionary=False)
        write_json(stage / "validation.json", validation)
        write_json(stage / "source_scorer_audit.json", audit)
        write_json(stage / "manifest.json", {"schema_version": "ats.phase_d2_nm.prospective_batch.v3", "batch_id": batch_id, "source_score_package_manifest_sha256": sha256_file(score_package / "manifest.json"), "files": file_inventory(stage)})
    _atomic_directory(destination, build)
    completed = pd.Timestamp(now_provider()).tz_convert("UTC")
    if completed < started:
        raise D2ArtifactError("publisher clock moved backward")
    session_records = []
    for decision, target in sorted(targets.items()):
        decision_ts = target["decision_ts"].tz_convert("UTC")
        timely = completed <= decision_ts
        session_records.append({"decision_session": decision.strftime("%Y-%m-%d"), "decision_ts": decision_ts.isoformat(), "publication_completed_ts": completed.isoformat(), "prospective_eligible": bool(timely), "monitoring_only": bool(not timely), "exclusion_reason": "" if timely else "PUBLISHED_AFTER_DECISION_TS"})
    receipt = {"schema_version": "ats.phase_d2_nm.publication_receipt.v3", "stream_id": STREAM_ID, "batch_id": batch_id, "publication_started_ts": started.isoformat(), "publication_completed_ts": completed.isoformat(), "batch_manifest_sha256": sha256_file(destination / "manifest.json"), "eligibility_authority": "publisher_post_atomic_finalization_clock", "sessions": session_records}
    receipt["logical_hash"] = content_hash(receipt)
    _atomic_json(receipt_path, receipt)
    return destination


def score_pinned_package(package_dir: Path, *, output_dir: Path) -> Path:
    """Fit and score the frozen cells; emit an audited score package without publication claims."""
    generation_ts, binding = _now_utc(), _verified_contract_binding()
    config, loaded = _load_input_package(package_dir)
    observations, labels, block, membership = loaded["observations.parquet"], loaded["training_labels.parquet"], loaded["walk_forward_block.json"], loaded["pit_membership.parquet"]
    assert isinstance(observations, pd.DataFrame) and isinstance(labels, pd.DataFrame) and isinstance(block, dict) and isinstance(membership, pd.DataFrame)
    _calendar, targets = _calendar_and_targets(config, loaded)
    _validate_population_and_timing(observations, membership, targets)
    expected_block, walk_forward_proof = _derive_and_verify_walk_forward_block(config, loaded)
    block = expected_block
    decision_sessions = [str(value) for value in config.get("decision_sessions", [])]
    if set(decision_sessions) - set(block.get("evaluation_sessions", [])):
        raise D2ArtifactError("requested sessions are absent from the pinned walk-forward block")
    admitted, admission = SequentialLabelAdmissionFirewall({"blocks": [block]}).admit(block)
    if set(pd.to_datetime(labels["decision_session"]).dt.strftime("%Y-%m-%d")) - set(admitted):
        raise D2ArtifactError("training-label input exceeds the block-scoped admission set")
    refit_ts = pd.Timestamp(block["refit_session"]).tz_localize("Europe/Warsaw") + pd.Timedelta(hours=8, minutes=45)
    if not pd.to_datetime(labels["label_endpoint_ts_20"], utc=True).lt(refit_ts.tz_convert("UTC")).all():
        raise D2ArtifactError("training-label package reaches or exceeds the refit timestamp")
    outputs, audits = [], []
    outer_all = observations.loc[observations["decision_session"].isin(pd.to_datetime(decision_sessions))].copy()
    for cell_id, cell in binding["cells"].items():
        features, inner_values, inner_audits = tuple(cell["feature_names"]), [], []
        for inner in block["inner_score_blocks"]:
            fit, fit_proof = _actual_fit(observations, labels, inner["fit_retained_sessions"], inner["fit_boundary_session"], features, int(inner["minimum_qualifying_sessions"]), int(inner["minimum_model_rows"]), "Europe/Warsaw")
            score, score_proof = _score_rows(observations, inner["score_sessions"], features, int(inner["score_minimum_qualifying_sessions"]))
            estimator = _new_estimator(str(cell["model"])); estimator.fit(fit[list(features)], fit["label__open_to_open__20"])
            values = np.asarray(estimator.predict(score[list(features)]), float); inner_values.append(values)
            inner_audits.append({"fit": fit_proof, "score": score_proof, "score_hash": logical_frame_hash(pd.DataFrame({"score": values}))})
        threshold = max(0.01, float(np.quantile(np.concatenate(inner_values), 0.90, method="linear")))
        final, final_proof = _actual_fit(observations, labels, block["final_fit"]["retained_sessions"], block["final_fit"]["boundary_session"], features, int(block["final_fit"]["minimum_qualifying_sessions"]), int(block["final_fit"]["minimum_model_rows"]), "Europe/Warsaw")
        score, score_proof = _score_rows(observations, decision_sessions, features, 0)
        estimator = _new_estimator(str(cell["model"])); estimator.fit(final[list(features)], final["label__open_to_open__20"])
        values = np.asarray(estimator.predict(score[list(features)]), float)
        value_map = {(str(row.security_id), pd.Timestamp(row.decision_session)): value for row, value in zip(score.itertuples(), values)}
        output = outer_all[["security_id", "decision_session", "information_session", "decision_ts", "official_expected_count", "model_exclusion_reason"]].copy()
        output["cell_id"], output["model_score"] = cell_id, [value_map.get((str(row.security_id), pd.Timestamp(row.decision_session)), math.nan) for row in output.itertuples()]
        output["threshold"], output["candidate"], output["prediction_generation_ts"] = threshold, output["model_score"].gt(threshold), generation_ts
        outputs.append(output)
        audits.append({"cell_id": cell_id, "features": list(features), "model": cell["model"], "inner": inner_audits, "final_fit": final_proof, "outer_score": score_proof, "threshold": threshold})
    frame = pd.concat(outputs, ignore_index=True)
    validation = validate_scorer_predictions(frame, observations, membership, targets)

    def build(stage: Path) -> None:
        frame.to_parquet(stage / "predictions.parquet", index=False, compression="zstd", use_dictionary=False)
        audit = {"schema_version": "ats.phase_d2_nm.scorer_audit.v3", "input_package": str(package_dir.resolve()), "input_config_sha256": sha256_file(package_dir / "input_config.json"), "pinned_input_hashes": {name: config["files"][name]["sha256"] for name in INPUT_FILES}, "contract_binding": binding, "cells": binding["cells"], "walk_forward_proof": walk_forward_proof, "implementation_fingerprint": _implementation_fingerprint(), "label_admission": admission, "fit_audit": audits, "validation": validation, "prediction_sha256": sha256_file(stage / "predictions.parquet")}
        write_json(stage / "scorer_audit.json", audit)
        write_json(stage / "manifest.json", {"schema_version": "ats.phase_d2_nm.score_package.v3", "files": file_inventory(stage)})
    _atomic_directory(output_dir, build)
    return output_dir


def record_missed_session(*, decision_session: str, reason: str, now_provider: Callable[[], pd.Timestamp] = _now_utc) -> Path:
    session, destination = pd.Timestamp(decision_session).strftime("%Y-%m-%d"), STREAM_ROOT / "missed" / f"{pd.Timestamp(decision_session).strftime('%Y-%m-%d')}.json"
    _atomic_json(destination, {"schema_version": "ats.phase_d2_nm.missed_session.v3", "decision_session": session, "publisher_recorded_ts": pd.Timestamp(now_provider()).tz_convert("UTC").isoformat(), "status": "MISSED_PERMANENTLY_INELIGIBLE", "reason": reason, "backfill_permitted": False})
    return destination
