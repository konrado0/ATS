from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ats_ml.contracts import REPOSITORY_ROOT
from ats_ml.d2_artifacts import (
    D2ArtifactError,
    frame_identity,
    publish_immutable,
    read_json,
    validate_manifest,
    write_json,
    write_parquet,
)
from ats_ml.d2_contract import validate_execution_authorization
from ats_ml.d2_data import build_real_labels, build_real_observations, load_official_calendar
from ats_ml.d2_stage1 import SequentialLabelAdmissionFirewall, _actual_fit, _score_rows
from ats_ml.models import LIGHTGBM_PARAMETERS, RIDGE_PARAMETERS
from ats_ml.structural_v3 import _compact_plan
from ats_ml.walkforward import _new_estimator, bind_structural_minimums, derive_walk_forward_plan
from ats_research.hashing import content_hash, logical_frame_hash, sha256_file


CONTRACT_PATH = REPOSITORY_ROOT / "source/python/configs/phase_d2_no_m_linear_mechanism.json"
PLAN_PATH = REPOSITORY_ROOT / "RESEARCH/PHASE_D2_NO_M_LINEAR_MECHANISM_PLAN.md"
ACCEPTED_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/prediction_runs/phase-d2-predictions-20260902-v4")
EVALUATION_SOURCE = Path("D:/Stock/data/ATS/phase_d_ml/evaluation_runs/phase-d2-evaluation-20260902-v6")
PREDICTION_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/mechanism_runs")
EVALUATION_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/mechanism_evaluation_runs")
INDEPENDENT_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/mechanism_reproductions")
PRIMARY_RUN_ID = "phase-d2-no-m-linear-mechanism-20260903-v1"
REPRODUCTION_RUN_ID = f"{PRIMARY_RUN_ID}-reproduction"
EVALUATION_RUN_ID = "phase-d2-no-m-linear-mechanism-evaluation-20260903-v1"
INDEPENDENT_RUN_ID = "phase-d2-no-m-linear-mechanism-independent-20260903-v1"
PREDICTION_SCHEMA = "ats.phase_d2_nm_linear_mechanism.prediction_run.v1"
EVALUATION_SCHEMA = "ats.phase_d2_nm_linear_mechanism.evaluation_run.v1"
CELLS = ("C_LINEAR", "C_LIGHTGBM", "RICH_NO_M_LINEAR", "RICH_NO_M_LIGHTGBM")
CONTROLS = ("C_LINEAR", "C_LIGHTGBM", "RICH_NO_M_LIGHTGBM")
BLOCK_MAP = {
    "MODEL_SELECTION_2023_H1": "RETRO_2023_H1",
    "MODEL_SELECTION_2023_H2": "RETRO_2023_H2",
    "DEVELOPMENT_2024_H1": "RETRO_2024_H1",
    "DEVELOPMENT_2024_H2": "RETRO_2024_H2",
    "LOCKED_2025_H1": "RETRO_2025_H1",
    "LOCKED_2025_H2": "RETRO_2025_H2",
    "LOCKED_2026_H1": "RETRO_2026_H1",
}
CONTRASTS = {
    "RIDGE_REPRESENTATION": ("RICH_NO_M_LINEAR", "C_LINEAR"),
    "NONLINEAR_INCREMENT": ("RICH_NO_M_LIGHTGBM", "RICH_NO_M_LINEAR"),
    "RIDGE_VS_C_LINEAR": ("RICH_NO_M_LINEAR", "C_LINEAR"),
    "RIDGE_VS_C_LIGHTGBM": ("RICH_NO_M_LINEAR", "C_LIGHTGBM"),
    "LIGHTGBM_VS_C_LINEAR": ("RICH_NO_M_LIGHTGBM", "C_LINEAR"),
    "LIGHTGBM_VS_C_LIGHTGBM": ("RICH_NO_M_LIGHTGBM", "C_LIGHTGBM"),
}


def load_contract() -> dict[str, Any]:
    contract = read_json(CONTRACT_PATH)
    if contract.get("schema_version") != "ats.phase_d2_nm_linear_mechanism.contract.v1":
        raise D2ArtifactError("unexpected mechanism contract schema")
    if contract.get("contract_id") != PRIMARY_RUN_ID:
        raise D2ArtifactError("unexpected mechanism contract ID")
    return contract


def _verify_files_from_manifest(root: Path) -> dict[str, Any]:
    manifest = read_json(root / "manifest.json")
    for relative, record in manifest.get("files", {}).items():
        path = root / relative
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha256_file(path) != record.get("sha256"):
            raise D2ArtifactError(f"accepted artifact hash mismatch: {path}")
    return manifest


def _git_binding(relative: str) -> dict[str, Any]:
    blob = subprocess.run(
        ["git", "show", f"HEAD:{relative}"], cwd=REPOSITORY_ROOT, check=True, capture_output=True
    ).stdout
    blob_id = subprocess.run(
        ["git", "rev-parse", f"HEAD:{relative}"], cwd=REPOSITORY_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    committed_sha = hashlib.sha256(blob).hexdigest()
    worktree_sha = sha256_file(REPOSITORY_ROOT / relative)
    if committed_sha != worktree_sha:
        raise D2ArtifactError(f"worktree differs from committed bytes: {relative}")
    return {"git_blob": blob_id, "committed_sha256": committed_sha, "worktree_sha256": worktree_sha}


def _implementation_binding() -> dict[str, Any]:
    files = (
        "RESEARCH/PHASE_D2_NO_M_LINEAR_MECHANISM_PLAN.md",
        "source/python/configs/phase_d2_no_m_linear_mechanism.json",
        "source/python/src/ats_ml/d2_no_m_linear_mechanism.py",
        "source/python/src/ats_ml/models.py",
        "source/python/src/ats_ml/d2_stage1.py",
        "source/python/src/ats_ml/d2_data.py",
        "source/python/src/ats_ml/walkforward.py",
        "RESEARCH/prototypes/phase_d2_no_m_linear_mechanism/independent_evaluate.py",
    )
    packages = ("numpy", "pandas", "pyarrow", "scikit-learn", "lightgbm", "scipy")
    return {
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, check=True, capture_output=True, text=True).stdout.strip(),
        "git_blobs": {name: _git_binding(name) for name in files},
        "environment_lock_sha256": sha256_file(REPOSITORY_ROOT / "RESEARCH/environment/environment.yml"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in packages},
        "ridge_parameters": RIDGE_PARAMETERS,
        "lightgbm_parameters": LIGHTGBM_PARAMETERS,
    }


def _cell_definitions(derived: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    c = derived["cells"]["C_LINEAR"]
    rich = derived["cells"]["RICH_NO_M_LIGHTGBM"]
    if len(rich["feature_names"]) != 18 or rich.get("features") != "C+P+X":
        raise D2ArtifactError("accepted C+P+X allowlist is not the frozen 18-feature list")
    return {
        "C_LINEAR": {"features": tuple(c["feature_names"]), "model": "RIDGE"},
        "C_LIGHTGBM": {"features": tuple(c["feature_names"]), "model": "LIGHTGBM"},
        "RICH_NO_M_LINEAR": {"features": tuple(rich["feature_names"]), "model": "RIDGE"},
        "RICH_NO_M_LIGHTGBM": {"features": tuple(rich["feature_names"]), "model": "LIGHTGBM"},
    }


def _score_hash(frame: pd.DataFrame) -> str:
    return logical_frame_hash(
        frame[["security_id", "decision_session", "model_score"]],
        ["decision_session", "security_id"],
    )


def _expected_control_hashes(accepted: pd.DataFrame) -> dict[str, dict[str, str]]:
    return {
        block: {
            cell: _score_hash(accepted.loc[accepted["block_id"].eq(block) & accepted["cell_id"].eq(cell)])
            for cell in CONTROLS
        }
        for block in BLOCK_MAP
    }


def _coefficient_record(estimator: Any, features: tuple[str, ...]) -> dict[str, Any] | None:
    if not hasattr(estimator, "named_steps"):
        return None
    ridge = estimator.named_steps["ridge"]
    values = np.asarray(ridge.coef_, dtype=float)
    return {
        "intercept": float(ridge.intercept_),
        "standardized_coefficients": {name: float(value) for name, value in zip(features, values, strict=True)},
    }


def _build_prediction(stage: Path) -> dict[str, Any]:
    task = load_contract()
    contract, authorization = validate_execution_authorization(require_clean=True)
    accepted_manifest = _verify_files_from_manifest(ACCEPTED_ROOT)
    if accepted_manifest.get("run_id") != task["accepted_inputs"]["prediction_run_id"]:
        raise D2ArtifactError("accepted prediction run ID mismatch")
    accepted_identity = accepted_manifest.get("logical_payload", {}).get("prediction_identity", {})
    if accepted_identity.get("logical_hash") != task["accepted_inputs"]["prediction_table_logical_hash"]:
        raise D2ArtifactError("accepted prediction logical hash mismatch")
    followup = Path("D:/Stock/data/ATS/phase_d_ml/followup_runs") / task["accepted_inputs"]["d2_nm_followup_run_id"]
    followup_manifest = _verify_files_from_manifest(followup)
    accepted = pd.read_parquet(ACCEPTED_ROOT / "predictions.parquet")
    expected_hashes = _expected_control_hashes(accepted)
    derived = read_json(ACCEPTED_ROOT / "derived_contract.json")
    cells = _cell_definitions(derived)
    observations, observation_audit = build_real_observations(contract)
    calendar = load_official_calendar(contract)
    eligibility = observations.groupby("decision_session", sort=True).agg(
        official_expected_count=("security_id", "nunique"),
        core_score_eligible_rows=("model_score_eligible", "sum"),
    ).reset_index()
    plan = bind_structural_minimums(derive_walk_forward_plan(calendar, contract), eligibility)
    structural = read_json(REPOSITORY_ROOT / "source/python/configs/phase_d1_structural_resolution_v3.json")
    if _compact_plan(plan) != structural["walk_forward_resolution"]:
        raise D2ArtifactError("walk-forward structure differs from accepted D1")
    selected_blocks = [block for block in plan["blocks"] if block["block_id"] in BLOCK_MAP]
    timezone = contract.config["observation_contract"]["market_timezone"]
    label_firewall = SequentialLabelAdmissionFirewall({**plan, "blocks": selected_blocks})
    predictions: list[pd.DataFrame] = []
    fit_records: list[dict[str, Any]] = []
    admission_records: list[dict[str, Any]] = []
    control_records: list[dict[str, Any]] = []
    common_population_hashes: dict[str, str] = {}
    for block in selected_blocks:
        block_id = block["block_id"]
        training_sessions, admission = label_firewall.admit(block)
        labels = build_real_labels(contract, observations, training_sessions, horizons=(20,))
        boundary = pd.Timestamp(block["refit_session"]).tz_localize(timezone) + pd.Timedelta(hours=8, minutes=45)
        endpoints = labels["label_endpoint_ts_20"].dropna()
        if not endpoints.lt(boundary).all():
            raise D2ArtifactError(f"label admission exceeds refit boundary: {block_id}")
        admission.update({
            "loaded_label_rows": len(labels),
            "loaded_endpoint_count": int(len(endpoints)),
            "all_loaded_endpoints_strictly_before_refit": True,
            "semantic_row_hash": logical_frame_hash(labels[["security_id", "decision_session"]], ["decision_session", "security_id"]),
        })
        admission_records.append(admission)
        block_parts: list[pd.DataFrame] = []
        for cell_id, definition in cells.items():
            features = definition["features"]
            inner_scores: list[np.ndarray] = []
            inner_audit: list[dict[str, Any]] = []
            for inner in block["inner_score_blocks"]:
                fit, fit_proof = _actual_fit(
                    observations, labels, inner["fit_retained_sessions"], inner["fit_boundary_session"],
                    features, int(inner["minimum_qualifying_sessions"]), int(inner["minimum_model_rows"]), timezone,
                )
                if not np.isfinite(fit[list(features)].to_numpy(float)).any(axis=0).all():
                    raise D2ArtifactError(f"registered feature has no finite training value: {block_id}/{cell_id}")
                score, score_proof = _score_rows(
                    observations, inner["score_sessions"], features, int(inner["score_minimum_qualifying_sessions"])
                )
                estimator = _new_estimator(definition["model"])
                estimator.fit(fit[list(features)], fit["label__open_to_open__20"].to_numpy())
                values = np.asarray(estimator.predict(score[list(features)]), dtype=float)
                inner_scores.append(values)
                inner_audit.append({
                    "score_block_number": inner["score_block_number"], "fit": fit_proof, "score": score_proof,
                    "score_hash": logical_frame_hash(pd.DataFrame({"score": values})), "estimator_recreated": True,
                })
            final, final_proof = _actual_fit(
                observations, labels, block["final_fit"]["retained_sessions"], block["final_fit"]["boundary_session"],
                features, int(block["final_fit"]["minimum_qualifying_sessions"]),
                int(block["final_fit"]["minimum_model_rows"]), timezone,
            )
            if not np.isfinite(final[list(features)].to_numpy(float)).any(axis=0).all():
                raise D2ArtifactError(f"registered final-fit feature has no finite value: {block_id}/{cell_id}")
            outer, outer_proof = _score_rows(
                observations, block["evaluation_sessions"], features, int(block["evaluation_minimum_qualifying_sessions"])
            )
            estimator = _new_estimator(definition["model"])
            estimator.fit(final[list(features)], final["label__open_to_open__20"].to_numpy())
            values = np.asarray(estimator.predict(outer[list(features)]), dtype=float)
            if not np.isfinite(values).all():
                raise D2ArtifactError(f"nonfinite score: {block_id}/{cell_id}")
            result = outer[["security_id", "decision_session"]].copy()
            result.insert(0, "block_id", block_id)
            result["cell_id"] = cell_id
            result["model_family"] = definition["model"]
            result["refit_session"] = pd.Timestamp(block["refit_session"])
            result["model_score"] = values
            block_parts.append(result)
            fit_records.append({
                "block_id": block_id, "cell_id": cell_id, "model_family": definition["model"],
                "feature_names": list(features),
                "model_parameters": RIDGE_PARAMETERS if definition["model"] == "RIDGE" else LIGHTGBM_PARAMETERS,
                "preprocessing": "median_no_indicator_then_standardize" if definition["model"] == "RIDGE" else "native_missing_values",
                "inner": inner_audit, "pooled_inner_score_hash": logical_frame_hash(pd.DataFrame({"score": np.concatenate(inner_scores)})),
                "final_fit": final_proof, "outer_score": outer_proof, "outer_outcomes_accessed": False,
                "final_fit_coefficients": _coefficient_record(estimator, features),
            })
        block_frame = pd.concat(block_parts, ignore_index=True)
        ledgers = {
            logical_frame_hash(group[["security_id", "decision_session"]], ["decision_session", "security_id"])
            for _, group in block_frame.groupby("cell_id")
        }
        if len(ledgers) != 1:
            raise D2ArtifactError(f"cell populations differ: {block_id}")
        common_population_hashes[block_id] = next(iter(ledgers))
        for cell_id in CONTROLS:
            generated = block_frame.loc[block_frame["cell_id"].eq(cell_id)].sort_values(["decision_session", "security_id"], kind="mergesort")
            accepted_cell = accepted.loc[accepted["block_id"].eq(block_id) & accepted["cell_id"].eq(cell_id)].sort_values(["decision_session", "security_id"], kind="mergesort")
            actual_hash, expected_hash = _score_hash(generated), expected_hashes[block_id][cell_id]
            exact_values = np.array_equal(generated["model_score"].to_numpy(), accepted_cell["model_score"].to_numpy())
            record = {"block_id": block_id, "cell_id": cell_id, "expected_score_hash": expected_hash, "actual_score_hash": actual_hash, "exact_values_equal": bool(exact_values), "status": "PASS" if actual_hash == expected_hash and exact_values else "FAIL"}
            control_records.append(record)
            if record["status"] != "PASS":
                raise D2ArtifactError(f"accepted control reproduction mismatch: {block_id}/{cell_id}")
        predictions.append(block_frame)
    label_firewall.require_complete()
    frame = pd.concat(predictions, ignore_index=True).sort_values(
        ["block_id", "cell_id", "decision_session", "security_id"], kind="mergesort"
    ).reset_index(drop=True)
    forbidden = [column for column in frame if any(token in column.lower() for token in task["stage1"]["forbidden_prediction_fields_containing"])]
    if forbidden:
        raise D2ArtifactError(f"prediction package contains forbidden fields: {forbidden}")
    implementation = _implementation_binding()
    rich_features = list(cells["RICH_NO_M_LINEAR"]["features"])
    feature_missingness: dict[str, dict[str, float]] = {}
    for block in selected_blocks:
        population = BLOCK_MAP[block["block_id"]]
        rows = observations.loc[observations["decision_session"].isin(pd.to_datetime(block["evaluation_sessions"]))]
        feature_missingness[population] = {
            feature: float((~np.isfinite(pd.to_numeric(rows[feature], errors="coerce"))).mean())
            for feature in rich_features
        }
    write_json(stage / "contract_binding.json", {
        "contract_id": task["contract_id"], "contract_sha256": sha256_file(CONTRACT_PATH), "plan_sha256": sha256_file(PLAN_PATH),
        "accepted_prediction_manifest_sha256": sha256_file(ACCEPTED_ROOT / "manifest.json"),
        "accepted_followup_manifest_sha256": sha256_file(followup / "manifest.json"),
        "accepted_followup_logical_hash": followup_manifest["logical_hash"],
        "feature_registry_sha256": task["accepted_inputs"]["feature_registry_sha256"],
        "feature_allowlists": {cell: list(value["features"]) for cell, value in cells.items()},
        "models": {cell: value["model"] for cell, value in cells.items()},
    })
    write_json(stage / "authorization.json", authorization)
    write_json(stage / "implementation.json", implementation)
    write_json(stage / "observation_audit.json", observation_audit)
    write_json(stage / "walk_forward_plan.json", {**{key: value for key, value in plan.items() if key != "blocks"}, "blocks": selected_blocks})
    write_json(stage / "label_admission_audit.json", {"mode": "outer_block_sequential", "records": admission_records, "complete": True})
    write_json(stage / "fit_score_audit.json", {"records": fit_records, "common_population_hashes": common_population_hashes})
    write_json(stage / "control_reproduction.json", {"status": "PASS", "source": str(ACCEPTED_ROOT), "records": control_records})
    write_json(stage / "feature_missingness.json", {"rates_by_population": feature_missingness, "nongating": True})
    write_parquet(stage / "predictions.parquet", frame)
    validation = {
        "status": "PASS", "prediction_only": True, "cells": list(CELLS), "blocks": list(BLOCK_MAP),
        "all_scores_finite": bool(np.isfinite(frame["model_score"]).all()), "identical_semantic_rows": True,
        "official_denominator": 60, "control_reproduction": "PASS", "block_scoped_label_admission": True,
        "outer_outcomes_accessed": False, "forbidden_prediction_fields": forbidden,
    }
    write_json(stage / "validation.json", validation)
    return {
        "prediction_identity": frame_identity(frame, sort_by=["block_id", "cell_id", "decision_session", "security_id"]),
        "prediction_sha256": sha256_file(stage / "predictions.parquet"),
        "control_reproduction_hash": content_hash(control_records),
        "common_population_hashes": common_population_hashes,
        "contract_sha256": sha256_file(CONTRACT_PATH), "implementation": implementation,
        "outcomes_in_publication": False, "metrics_in_publication": False,
    }


def validate_prediction_run(run_dir: Path) -> dict[str, Any]:
    required = {"contract_binding.json", "authorization.json", "implementation.json", "observation_audit.json", "walk_forward_plan.json", "label_admission_audit.json", "fit_score_audit.json", "control_reproduction.json", "feature_missingness.json", "predictions.parquet", "validation.json"}
    manifest = validate_manifest(run_dir, schema_version=PREDICTION_SCHEMA, required_files=required)
    frame = pd.read_parquet(run_dir / "predictions.parquet")
    validation = read_json(run_dir / "validation.json")
    forbidden_tokens = load_contract()["stage1"]["forbidden_prediction_fields_containing"]
    forbidden = [column for column in frame if any(token in column.lower() for token in forbidden_tokens)]
    if validation.get("status") != "PASS" or forbidden or set(frame["cell_id"]) != set(CELLS) or set(frame["block_id"]) != set(BLOCK_MAP):
        raise D2ArtifactError("sealed mechanism prediction validation failed")
    if read_json(run_dir / "control_reproduction.json").get("status") != "PASS":
        raise D2ArtifactError("sealed control reproduction did not pass")
    actual = frame_identity(frame, sort_by=["block_id", "cell_id", "decision_session", "security_id"])
    if actual != manifest["logical_payload"]["prediction_identity"]:
        raise D2ArtifactError("prediction logical identity mismatch")
    return {"status": "PASS", "logical_hash": manifest["logical_hash"], "prediction_sha256": sha256_file(run_dir / "predictions.parquet"), "rows": len(frame)}


def publish_prediction_run(*, reproduction: bool = False) -> Path:
    run_id = REPRODUCTION_RUN_ID if reproduction else PRIMARY_RUN_ID
    return publish_immutable(PREDICTION_ROOT, run_id, _build_prediction, schema_version=PREDICTION_SCHEMA, validate=validate_prediction_run)


def _outcomes() -> pd.DataFrame:
    pieces = []
    for stage in ("stage2a", "stage2b", "stage2c"):
        _verify_files_from_manifest(EVALUATION_SOURCE / stage)
        pieces.append(pd.read_parquet(EVALUATION_SOURCE / stage / "outcomes.parquet"))
    return pd.concat(pieces, ignore_index=True).drop_duplicates(["block_id", "security_id", "decision_session"])


def _spearman(scores: Iterable[float], outcomes: Iterable[float]) -> float:
    frame = pd.DataFrame({"score": scores, "outcome": outcomes}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 45 or frame["score"].nunique() < 2 or frame["outcome"].nunique() < 2:
        return math.nan
    return float(frame["score"].rank(method="average").corr(frame["outcome"].rank(method="average")))


def _wide(predictions: pd.DataFrame) -> pd.DataFrame:
    keys = ["block_id", "security_id", "decision_session"]
    score = predictions.pivot(index=keys, columns="cell_id", values="model_score").add_prefix("score__").reset_index()
    labels = _outcomes()[keys + ["label__open_to_open__20"]]
    wide = score.merge(labels, on=keys, how="left", validate="one_to_one")
    wide["population"] = wide["block_id"].map(BLOCK_MAP)
    if wide["population"].isna().any() or wide[[f"score__{cell}" for cell in CELLS]].isna().any().any():
        raise D2ArtifactError("evaluation population or common score matrix is incomplete")
    return wide.sort_values(["decision_session", "security_id"], kind="mergesort").reset_index(drop=True)


def _session_metrics(wide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (population, session), group in wide.groupby(["population", "decision_session"], sort=True):
        row: dict[str, Any] = {"population": population, "decision_session": session, "semantic_rows": len(group), "outcome_rows": int(np.isfinite(group["label__open_to_open__20"]).sum())}
        for cell in CELLS:
            row[f"ic__{cell}"] = _spearman(group[f"score__{cell}"], group["label__open_to_open__20"])
        for name, (candidate, comparator) in CONTRASTS.items():
            row[f"delta__{name}"] = row[f"ic__{candidate}"] - row[f"ic__{comparator}"]
        rows.append(row)
    return pd.DataFrame(rows).sort_values("decision_session", kind="mergesort").reset_index(drop=True)


def _bootstrap_indices(n: int) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(20260831))
    starts = rng.integers(0, n, size=(5000, math.ceil(n / 20)))
    return ((starts[:, :, None] + np.arange(20)) % n).reshape(5000, -1)[:, :n]


def _interval(values: np.ndarray, indices: np.ndarray) -> dict[str, Any]:
    estimates = np.nanmean(values[indices], axis=1)
    defined = np.isfinite(estimates)
    fraction = float(defined.mean())
    if fraction < 0.99:
        return {"status": "NOT PROVEN", "defined_fraction": fraction, "lower": None, "upper": None}
    return {"status": "PASS", "defined_fraction": fraction, "lower": float(np.quantile(estimates[defined], 0.025, method="linear")), "upper": float(np.quantile(estimates[defined], 0.975, method="linear"))}


def _leave_security(wide: pd.DataFrame, sessions: pd.DataFrame) -> dict[str, Any]:
    baseline = {name: float(sessions[f"delta__{name}"].mean()) for name in CONTRASTS}
    sums = {name: float(sessions[f"delta__{name}"].sum()) for name in CONTRASTS}
    counts = {name: int(sessions[f"delta__{name}"].notna().sum()) for name in CONTRASTS}
    by_session = sessions.set_index("decision_session")
    securities = sorted(wide["security_id"].astype(str).unique())
    reduced = {security: dict(sums) for security in securities}
    reduced_counts = {security: dict(counts) for security in securities}
    for session, group in wide.groupby("decision_session", sort=True):
        ids = group["security_id"].astype(str).to_numpy()
        outcome = group["label__open_to_open__20"].to_numpy(float)
        scores = {cell: group[f"score__{cell}"].to_numpy(float) for cell in CELLS}
        for position, security in enumerate(ids):
            keep = np.arange(len(group)) != position
            cell_ic = {cell: _spearman(values[keep], outcome[keep]) for cell, values in scores.items()}
            for name, (candidate, comparator) in CONTRASTS.items():
                original = float(by_session.at[session, f"delta__{name}"])
                if np.isfinite(original):
                    reduced[security][name] -= original
                    reduced_counts[security][name] -= 1
                value = cell_ic[candidate] - cell_ic[comparator]
                if np.isfinite(value):
                    reduced[security][name] += value
                    reduced_counts[security][name] += 1
    output: dict[str, Any] = {}
    for name in CONTRASTS:
        leave = {security: reduced[security][name] / reduced_counts[security][name] for security in securities if reduced_counts[security][name]}
        decreases = {security: baseline[name] - value for security, value in leave.items()}
        maximum = max(decreases.values())
        boundary = sorted(security for security, value in decreases.items() if value == maximum)
        positive = {security: max(value, 0.0) for security, value in decreases.items()}
        total = sum(positive.values())
        output[name] = {
            "baseline_mean_delta": baseline[name], "largest_contributor_boundary_set": boundary,
            "leave_boundary_security_out": {security: leave[security] for security in boundary},
            "largest_positive_contribution_share": max(positive.values()) / total if total > 0 else None,
            "all_leave_security_out": leave,
        }
    return output


def calculate_decision_core(prediction_run: Path) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    validate_prediction_run(prediction_run)
    predictions = pd.read_parquet(prediction_run / "predictions.parquet")
    wide = _wide(predictions)
    sessions = _session_metrics(wide)
    indices = _bootstrap_indices(len(sessions))
    influence = _leave_security(wide, sessions)
    results: dict[str, Any] = {}
    gate_results: dict[str, bool] = {}
    for name, (candidate, comparator) in CONTRASTS.items():
        values = sessions[f"delta__{name}"]
        half_year = {population: float(sessions.loc[sessions["population"].eq(population), f"delta__{name}"].mean()) for population in BLOCK_MAP.values()}
        positive_by_half = sessions.assign(positive=values.clip(lower=0.0)).groupby("population")["positive"].sum()
        positive_total = float(positive_by_half.sum())
        half_share = float(positive_by_half.max() / positive_total) if positive_total > 0 else None
        leave_half = {population: float(sessions.loc[sessions["population"].ne(population), f"delta__{name}"].mean()) for population in BLOCK_MAP.values()}
        security = influence[name]
        checks = {
            "pooled_mean_gt_0_005": float(values.mean()) > 0.005,
            "positive_half_years_at_least_5": sum(value > 0 for value in half_year.values()) >= 5,
            "median_half_year_positive": float(np.median(list(half_year.values()))) > 0,
            "all_leave_half_year_out_positive": all(value > 0 for value in leave_half.values()),
            "all_tied_largest_security_out_positive": all(value > 0 for value in security["leave_boundary_security_out"].values()),
            "security_positive_share_below_0_50": security["largest_positive_contribution_share"] is not None and security["largest_positive_contribution_share"] < 0.50,
            "half_year_positive_share_below_0_50": half_share is not None and half_share < 0.50,
        }
        gate_results[name] = all(checks.values())
        results[name] = {
            "candidate": candidate, "comparator": comparator, "pooled_mean_delta": float(values.mean()),
            "pooled_median_delta": float(values.median()), "half_year_mean_deltas": half_year,
            "median_half_year_mean_delta": float(np.median(list(half_year.values()))),
            "positive_half_year_count": sum(value > 0 for value in half_year.values()),
            "positive_session_count": int(values.gt(0).sum()), "positive_session_fraction": float(values.gt(0).sum() / values.notna().sum()),
            "moving_block_95_interval": _interval(values.to_numpy(float), indices), "leave_one_half_year_out": leave_half,
            "leave_largest_contributing_security_out": security["leave_boundary_security_out"],
            "largest_contributing_security_boundary_set": security["largest_contributor_boundary_set"],
            "largest_positive_contribution_share_by_security": security["largest_positive_contribution_share"],
            "largest_positive_contribution_share_by_half_year": half_share, "broad_increment_checks": checks,
            "broad_increment": "PASS" if gate_results[name] else "FAIL",
        }
    ridge_both = gate_results["RIDGE_VS_C_LINEAR"] and gate_results["RIDGE_VS_C_LIGHTGBM"]
    nonlinear = gate_results["NONLINEAR_INCREMENT"]
    lightgbm_conventional = all(
        results[name]["pooled_mean_delta"] > 0 and results[name]["positive_half_year_count"] >= 4
        for name in ("LIGHTGBM_VS_C_LINEAR", "LIGHTGBM_VS_C_LIGHTGBM")
    )
    if ridge_both and not nonlinear:
        verdict = "REPRESENTATION ROBUST — RIDGE SUFFICIENT"
    elif ridge_both and nonlinear:
        verdict = "REPRESENTATION ROBUST — NONLINEARITY ADDS"
    elif not ridge_both and nonlinear and lightgbm_conventional:
        verdict = "NONLINEARITY-DEPENDENT — WEAK"
    else:
        verdict = "NOT ROBUST"
    core = {"contrasts": results, "scientific_verdict_if_all_integrity_checks_pass": verdict}
    diagnostics = _diagnostics(wide, predictions, prediction_run)
    return core, sessions, diagnostics


def _diagnostics(wide: pd.DataFrame, predictions: pd.DataFrame, prediction_run: Path) -> dict[str, Any]:
    score_correlations = {}
    for population, group in wide.groupby("population", sort=True):
        per_session = [
            _spearman(part[f"score__RICH_NO_M_LINEAR"], part[f"score__RICH_NO_M_LIGHTGBM"])
            for _, part in group.groupby("decision_session", sort=True)
        ]
        score_correlations[population] = float(np.nanmean(per_session))
    dispersion = {
        f"{block}/{cell}": {"mean": float(group["model_score"].mean()), "std": float(group["model_score"].std()), "p05": float(group["model_score"].quantile(0.05)), "p95": float(group["model_score"].quantile(0.95))}
        for (block, cell), group in predictions.groupby(["block_id", "cell_id"], sort=True)
    }
    turnover = {}
    for (block, cell), group in predictions.groupby(["block_id", "cell_id"], sort=True):
        matrix = group.pivot(index="decision_session", columns="security_id", values="model_score").sort_index()
        adjacent = [float(matrix.iloc[index - 1].rank(method="average").corr(matrix.iloc[index].rank(method="average"))) for index in range(1, len(matrix))]
        turnover[f"{block}/{cell}"] = {"mean_adjacent_rank_correlation": float(np.nanmean(adjacent)), "mean_rank_turnover": float(1.0 - np.nanmean(adjacent))}
    coefficient_records = [row for row in read_json(prediction_run / "fit_score_audit.json")["records"] if row.get("cell_id") == "RICH_NO_M_LINEAR"]
    coefficients = {
        row["block_id"]: row["final_fit_coefficients"] for row in coefficient_records
    }
    levels = _session_metrics(wide.loc[wide["population"].eq("RETRO_2023_H1")])
    decomposition = {cell: float(levels[f"ic__{cell}"].mean()) for cell in CELLS}
    decomposition["ridge_representation_delta"] = decomposition["RICH_NO_M_LINEAR"] - decomposition["C_LINEAR"]
    decomposition["lightgbm_representation_delta"] = decomposition["RICH_NO_M_LIGHTGBM"] - decomposition["C_LIGHTGBM"]
    decomposition["nonlinear_increment"] = decomposition["RICH_NO_M_LIGHTGBM"] - decomposition["RICH_NO_M_LINEAR"]
    return {
        "cpx_mean_session_score_spearman_by_half_year": score_correlations,
        "prediction_dispersion": dispersion,
        "rank_turnover": turnover,
        "ridge_coefficients_by_refit": coefficients,
        "feature_missingness": read_json(prediction_run / "feature_missingness.json"),
        "RETRO_2023_H1_mean_ic_decomposition": decomposition,
    }


def publish_evaluation() -> Path:
    primary, reproduction = PREDICTION_ROOT / PRIMARY_RUN_ID, PREDICTION_ROOT / REPRODUCTION_RUN_ID
    primary_validation, reproduction_validation = validate_prediction_run(primary), validate_prediction_run(reproduction)
    byte_identical = sha256_file(primary / "predictions.parquet") == sha256_file(reproduction / "predictions.parquet")
    independent_dir = INDEPENDENT_ROOT / INDEPENDENT_RUN_ID
    independent_manifest = _verify_files_from_manifest(independent_dir)
    independent = read_json(independent_dir / "results.json")

    def build(stage: Path) -> dict[str, Any]:
        core, sessions, diagnostics = calculate_decision_core(primary)
        primary_core_hash = content_hash(core)
        independent_match = independent.get("decision_core_hash") == primary_core_hash
        integrity = {
            "primary_prediction_validation": primary_validation["status"],
            "reproduction_prediction_validation": reproduction_validation["status"],
            "byte_identical_prediction_table": byte_identical,
            "control_reproduction": read_json(primary / "control_reproduction.json")["status"],
            "independent_evaluation_match": independent_match,
            "independent_manifest_sha256": sha256_file(independent_dir / "manifest.json"),
        }
        all_pass = all(value is True or value == "PASS" for key, value in integrity.items() if key != "independent_manifest_sha256")
        verdict = core["scientific_verdict_if_all_integrity_checks_pass"] if all_pass else "NOT PROVEN"
        verdict_record = {"verdict": verdict, "integrity_status": "PASS" if all_pass else "NOT PROVEN", "evidence_level": load_contract()["evidence_level"], "original_D2_STOP_unchanged": True, "prospective_stream_unchanged": True, "follow_on_automatically_authorized": False}
        write_parquet(stage / "per_session.parquet", sessions)
        write_json(stage / "contrasts.json", core["contrasts"])
        write_json(stage / "diagnostics.json", diagnostics)
        write_json(stage / "integrity.json", integrity)
        write_json(stage / "verdict.json", verdict_record)
        write_json(stage / "provenance.json", {"contract_sha256": sha256_file(CONTRACT_PATH), "primary_prediction_manifest_sha256": sha256_file(primary / "manifest.json"), "reproduction_prediction_manifest_sha256": sha256_file(reproduction / "manifest.json"), "accepted_evaluation_stage_manifests": {name: sha256_file(EVALUATION_SOURCE / name / "manifest.json") for name in ("stage2a", "stage2b", "stage2c")}, "independent_logical_hash": independent_manifest["logical_hash"], "decision_core_hash": primary_core_hash})
        return {"decision_core_hash": primary_core_hash, "per_session": frame_identity(sessions, sort_by=["decision_session"]), "verdict": verdict_record, "integrity": integrity, "diagnostics_hash": content_hash(diagnostics)}

    def validate(run_dir: Path) -> dict[str, Any]:
        required = {"per_session.parquet", "contrasts.json", "diagnostics.json", "integrity.json", "verdict.json", "provenance.json"}
        manifest = validate_manifest(run_dir, schema_version=EVALUATION_SCHEMA, required_files=required)
        verdict = read_json(run_dir / "verdict.json")
        if verdict.get("verdict") not in load_contract()["verdict_order"]:
            raise D2ArtifactError("invalid mechanism verdict")
        return {"status": "PASS", "logical_hash": manifest["logical_hash"], "verdict": verdict["verdict"]}

    return publish_immutable(EVALUATION_ROOT, EVALUATION_RUN_ID, build, schema_version=EVALUATION_SCHEMA, validate=validate)
