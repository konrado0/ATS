from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ats_ml.contracts import REPOSITORY_ROOT, FrozenD0Contract
from ats_ml.d2_artifacts import (
    D2ArtifactError,
    frame_identity,
    publish_immutable,
    read_json,
    validate_manifest,
    write_json,
    write_parquet,
)
from ats_ml.d2_contract import load_execution_config, validate_execution_authorization
from ats_ml.d2_data import build_real_labels, build_real_observations, load_official_calendar
from ats_ml.matrices import cell_feature_allowlists
from ats_ml.models import LIGHTGBM_PARAMETERS, RIDGE_PARAMETERS
from ats_ml.structural_v3 import _compact_plan
from ats_ml.walkforward import (
    LockedSequenceFirewall,
    _new_estimator,
    bind_structural_minimums,
    derive_walk_forward_plan,
    expected_locked_sequence_bindings,
)
from ats_research.hashing import content_hash, logical_frame_hash, sha256_file


PREDICTION_SCHEMA = "ats.phase_d2.prediction_run.v1"
PREDICTION_FILES = {
    "authorization.json",
    "derived_contract.json",
    "observation_audit.json",
    "walk_forward_plan.json",
    "fit_calibration_audit.json",
    "locked_sequence.json",
    "predictions.parquet",
    "common_score_masks.parquet",
    "validation.json",
}
PRIMARY_CELLS = ("C_LINEAR", "C_LIGHTGBM", "RICH_LINEAR", "RICH_LIGHTGBM")
ABLATION_CELL = "RICH_NO_M_LIGHTGBM"


def _decision_ts(session: object, timezone: str) -> pd.Timestamp:
    return pd.Timestamp(session).normalize().tz_localize(timezone) + pd.Timedelta(hours=8, minutes=45)


def _actual_fit(
    observations: pd.DataFrame,
    labels: pd.DataFrame,
    sessions: list[str],
    boundary_session: str,
    features: tuple[str, ...],
    minimum_sessions: int,
    minimum_rows: int,
    timezone: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    selected = observations.loc[
        observations["decision_session"].isin(pd.to_datetime(sessions))
        & observations["model_score_eligible"],
        ["security_id", "decision_session", *features],
    ].merge(
        labels[
            [
                "security_id", "decision_session", "label_endpoint_ts_20",
                "label__open_to_open__20", "label_state_20",
            ]
        ],
        on=["security_id", "decision_session"],
        how="left",
        validate="one_to_one",
    )
    boundary = _decision_ts(boundary_session, timezone)
    mature = (
        selected["label__open_to_open__20"].notna()
        & np.isfinite(selected["label__open_to_open__20"])
        & selected["label_endpoint_ts_20"].notna()
        & selected["label_endpoint_ts_20"].lt(boundary)
    )
    fit = selected.loc[mature].sort_values(["decision_session", "security_id"], kind="mergesort")
    counts = fit.groupby("decision_session").size()
    qualifying_sessions = int(counts.ge(45).sum())
    if qualifying_sessions < minimum_sessions or len(fit) < minimum_rows:
        raise D2ArtifactError(
            f"actual fit minimum failed at {boundary_session}: "
            f"sessions={qualifying_sessions}/{minimum_sessions}, rows={len(fit)}/{minimum_rows}"
        )
    validity = {
        name: float(np.isfinite(pd.to_numeric(fit[name], errors="coerce")).mean()) for name in features
    }
    failed = {name: value for name, value in validity.items() if value < 0.90}
    if failed:
        raise D2ArtifactError(f"fit predictor validity is below 90% at {boundary_session}: {failed}")
    audit = {
        "boundary_session": boundary_session,
        "rows": len(fit),
        "qualifying_sessions": qualifying_sessions,
        "semantic_row_hash": logical_frame_hash(
            fit[["security_id", "decision_session"]], ["decision_session", "security_id"]
        ),
        "target_hash": logical_frame_hash(
            fit[["security_id", "decision_session", "label__open_to_open__20"]],
            ["decision_session", "security_id"],
        ),
        "feature_valid_fraction": validity,
        "endpoint_strictly_before_boundary": bool(fit["label_endpoint_ts_20"].lt(boundary).all()),
    }
    return fit, audit


def _score_rows(
    observations: pd.DataFrame, sessions: list[str], features: tuple[str, ...], minimum_sessions: int
) -> tuple[pd.DataFrame, dict[str, Any]]:
    score = observations.loc[
        observations["decision_session"].isin(pd.to_datetime(sessions))
        & observations["model_score_eligible"],
        ["security_id", "decision_session", *features],
    ].sort_values(["decision_session", "security_id"], kind="mergesort")
    qualifying = int(score.groupby("decision_session").size().ge(45).sum())
    if qualifying < minimum_sessions:
        raise D2ArtifactError(
            f"actual score minimum failed: sessions={qualifying}/{minimum_sessions}"
        )
    return score, {
        "rows": len(score),
        "qualifying_sessions": qualifying,
        "semantic_row_hash": logical_frame_hash(
            score[["security_id", "decision_session"]], ["decision_session", "security_id"]
        ),
    }


def _cell_definitions(contract: FrozenD0Contract, p_survivors: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    allowlists = cell_feature_allowlists(contract, p_survivors)
    cells = {item["cell_id"]: dict(item) for item in contract.config["comparison"]["cells"]}
    for cell_id in PRIMARY_CELLS:
        cells[cell_id]["feature_names"] = allowlists[cell_id]
    cells[ABLATION_CELL] = {
        "cell_id": ABLATION_CELL,
        "features": "C+P+X",
        "model": "LIGHTGBM",
        "feature_names": tuple(
            [*contract.feature_blocks["C"], *p_survivors, *contract.feature_blocks["X"]]
        ),
        "diagnostic_only": True,
    }
    return cells


def build_prediction_run(stage: Path) -> dict[str, Any]:
    contract, authorization = validate_execution_authorization(require_clean=True)
    execution = load_execution_config()
    structural = json.loads(
        (REPOSITORY_ROOT / "source/python/configs/phase_d1_structural_resolution_v3.json").read_text(encoding="utf-8")
    )
    observations, observation_audit = build_real_observations(contract)
    calendar = load_official_calendar(contract)
    eligibility = observations.groupby("decision_session", sort=True).agg(
        official_expected_count=("security_id", "nunique"),
        core_score_eligible_rows=("model_score_eligible", "sum"),
    ).reset_index()
    plan = bind_structural_minimums(derive_walk_forward_plan(calendar, contract), eligibility)
    if _compact_plan(plan) != structural["walk_forward_resolution"]:
        raise D2ArtifactError("real Stage 1 walk-forward structure differs from the accepted D1 binding")
    p_survivors = tuple(structural["p_duplicate_resolution"]["survivors"])
    cells = _cell_definitions(contract, p_survivors)
    training_sessions = sorted({
        session
        for block in plan["blocks"]
        for collection in [
            block["final_fit"]["retained_sessions"],
            *[inner["fit_retained_sessions"] for inner in block["inner_score_blocks"]],
        ]
        for session in collection
    })
    labels = build_real_labels(contract, observations, training_sessions, horizons=(20,))
    timezone = contract.config["observation_contract"]["market_timezone"]
    predictions: list[pd.DataFrame] = []
    masks: list[pd.DataFrame] = []
    fit_audit: list[dict[str, Any]] = []
    expected_locked = expected_locked_sequence_bindings(plan)
    if expected_locked != structural["locked_sequence_firewall_proof"]["expected_bindings"]:
        raise D2ArtifactError("Stage 1 locked availability bindings differ from accepted D1")
    firewall = LockedSequenceFirewall(expected_locked)
    locked_records: list[dict[str, Any]] = []

    for block in plan["blocks"]:
        block_id = block["block_id"]
        outer_sessions = block["evaluation_sessions"]
        block_mask = observations.loc[
            observations["decision_session"].isin(pd.to_datetime(outer_sessions)),
            [
                "security_id", "decision_session", "information_session", "decision_ts",
                "official_expected_count", "model_score_eligible", "scored_count",
                "excluded_count", "exclusion_reason_counts", "model_exclusion_reason",
                "proximity_to_max_high_252",
            ],
        ].copy()
        block_mask.insert(0, "block_id", block_id)
        masks.append(block_mask)
        block_predictions: list[pd.DataFrame] = []
        for cell_id, cell in cells.items():
            features = tuple(cell["feature_names"])
            inner_score_values: list[np.ndarray] = []
            inner_audits: list[dict[str, Any]] = []
            for inner in block["inner_score_blocks"]:
                fit, fit_proof = _actual_fit(
                    observations, labels, inner["fit_retained_sessions"],
                    inner["fit_boundary_session"], features,
                    int(inner["minimum_qualifying_sessions"]), int(inner["minimum_model_rows"]), timezone,
                )
                score, score_proof = _score_rows(
                    observations, inner["score_sessions"], features,
                    int(inner["score_minimum_qualifying_sessions"]),
                )
                estimator = _new_estimator(str(cell["model"]))
                estimator.fit(fit.loc[:, list(features)], fit["label__open_to_open__20"].to_numpy())
                values = np.asarray(estimator.predict(score.loc[:, list(features)]), dtype=float)
                if len(values) == 0 or not np.isfinite(values).all():
                    raise D2ArtifactError(f"nonfinite inner scores for {block_id}/{cell_id}")
                inner_score_values.append(values)
                inner_audits.append({
                    "score_block_number": inner["score_block_number"],
                    "fit": fit_proof,
                    "score": score_proof,
                    "score_values_hash": logical_frame_hash(pd.DataFrame({"score": values})),
                    "estimator_recreated": True,
                })
            pooled = np.concatenate(inner_score_values)
            threshold = max(0.01, float(np.quantile(pooled, 0.90, method="linear")))
            if not np.isfinite(threshold):
                raise D2ArtifactError(f"nonfinite threshold for {block_id}/{cell_id}")
            final, final_proof = _actual_fit(
                observations, labels, block["final_fit"]["retained_sessions"],
                block["final_fit"]["boundary_session"], features,
                int(block["final_fit"]["minimum_qualifying_sessions"]),
                int(block["final_fit"]["minimum_model_rows"]), timezone,
            )
            outer, outer_proof = _score_rows(
                observations, outer_sessions, features,
                0 if not block["complete"] else int(block["evaluation_minimum_qualifying_sessions"]),
            )
            if block["complete"] and len(outer) < int(block["evaluation_minimum_rows"]):
                raise D2ArtifactError(f"actual outer row minimum failed for {block_id}")
            estimator = _new_estimator(str(cell["model"]))
            estimator.fit(final.loc[:, list(features)], final["label__open_to_open__20"].to_numpy())
            scores = np.asarray(estimator.predict(outer.loc[:, list(features)]), dtype=float)
            if not np.isfinite(scores).all():
                raise D2ArtifactError(f"nonfinite outer scores for {block_id}/{cell_id}")
            result = outer[["security_id", "decision_session"]].copy()
            result.insert(0, "block_id", block_id)
            result["cell_id"] = cell_id
            result["model_family"] = cell["model"]
            result["refit_session"] = pd.Timestamp(block["refit_session"])
            result["model_score"] = scores
            result["threshold"] = threshold
            result["candidate"] = result["model_score"].gt(result["threshold"])
            block_predictions.append(result)
            fit_audit.append({
                "block_id": block_id,
                "cell_id": cell_id,
                "model_family": cell["model"],
                "diagnostic_only": bool(cell.get("diagnostic_only", False)),
                "feature_names": list(features),
                "model_parameters": RIDGE_PARAMETERS if cell["model"] == "RIDGE" else LIGHTGBM_PARAMETERS,
                "inner": inner_audits,
                "pooled_inner_score_count": len(pooled),
                "pooled_inner_score_hash": logical_frame_hash(pd.DataFrame({"score": pooled})),
                "threshold": threshold,
                "threshold_provenance_hash": content_hash({
                    "score_hashes": [item["score_values_hash"] for item in inner_audits],
                    "floor": 0.01, "quantile": 0.90, "method": "linear",
                }),
                "threshold_frozen_before_final_refit": True,
                "final_fit": final_proof,
                "outer_score": outer_proof,
                "outer_outcomes_accessed": False,
            })
        block_frame = pd.concat(block_predictions, ignore_index=True)
        expected_hashes = {
            logical_frame_hash(
                group[["security_id", "decision_session"]], ["decision_session", "security_id"]
            ) for _, group in block_frame.groupby("cell_id", sort=True)
        }
        if len(expected_hashes) != 1:
            raise D2ArtifactError(f"cell score populations differ in {block_id}")
        predictions.append(block_frame)
        if block_id in expected_locked:
            prediction_hash = logical_frame_hash(
                block_frame.sort_values(["cell_id", "decision_session", "security_id"], kind="mergesort"),
                ["cell_id", "decision_session", "security_id"],
            )
            binding = expected_locked[block_id]
            firewall.record_prediction(
                block_id,
                prediction_hash=prediction_hash,
                refit_session=block["refit_session"],
                availability_proof_hash=binding["availability_proof_hash"],
            )
            locked_records.append({
                "block_id": block_id,
                "prediction_hash": prediction_hash,
                "refit_session": block["refit_session"],
                "availability_proof_hash": binding["availability_proof_hash"],
            })

    prediction_frame = pd.concat(predictions, ignore_index=True).sort_values(
        ["block_id", "cell_id", "decision_session", "security_id"], kind="mergesort"
    ).reset_index(drop=True)
    mask_frame = pd.concat(masks, ignore_index=True).sort_values(
        ["block_id", "decision_session", "security_id"], kind="mergesort"
    ).reset_index(drop=True)
    locked_fingerprint = firewall.fingerprint_complete_sequence()
    permit = firewall.evaluation_permit()
    firewall.require_evaluation_permit(permit)
    locked_sequence = {
        "schema_version": "ats.phase_d2.locked_sequence.v1",
        "ordered_blocks": plan["locked_prediction_order"],
        "expected_bindings": expected_locked,
        "records": locked_records,
        "complete_sequence_fingerprint": locked_fingerprint,
        "evaluation_permit_minted": True,
    }
    derived_contract = {
        "schema_version": "ats.phase_d2.derived_contract.v1",
        "contract_version": contract.config["contract_version"],
        "feature_registry_order": list(contract.registry_order),
        "p_survivors": list(p_survivors),
        "cells": {
            key: {**{k: v for k, v in value.items() if k != "feature_names"}, "feature_names": list(value["feature_names"])}
            for key, value in cells.items()
        },
        "comparison": contract.config["comparison"],
        "evaluation": contract.config["evaluation"],
        "decision_gate": contract.config["decision_gate"],
        "opportunity_contract": contract.config["opportunity_contract"],
        "target_contract": contract.config["target_contract"],
        "execution_config": execution,
        "scientific_choices_derived_only": True,
    }
    write_json(stage / "authorization.json", authorization)
    write_json(stage / "derived_contract.json", derived_contract)
    write_json(stage / "observation_audit.json", observation_audit)
    write_json(stage / "walk_forward_plan.json", plan)
    write_json(stage / "fit_calibration_audit.json", {
        "schema_version": "ats.phase_d2.fit_calibration_audit.v1",
        "records": fit_audit,
        "evaluation_metrics_computed": False,
        "evaluation_outcomes_attached": False,
    })
    write_json(stage / "locked_sequence.json", locked_sequence)
    write_parquet(stage / "predictions.parquet", prediction_frame)
    write_parquet(stage / "common_score_masks.parquet", mask_frame)
    validation = {
        "schema_version": "ats.phase_d2.prediction_validation.v1",
        "status": "PASS",
        "all_blocks_present": set(prediction_frame["block_id"]) == {item["block_id"] for item in plan["blocks"]},
        "all_cells_present": set(prediction_frame["cell_id"]) == set(cells),
        "finite_scores_and_thresholds": bool(
            np.isfinite(prediction_frame["model_score"]).all()
            and np.isfinite(prediction_frame["threshold"]).all()
        ),
        "strict_threshold_rule": bool(
            prediction_frame["candidate"].eq(
                prediction_frame["model_score"].gt(prediction_frame["threshold"])
            ).all()
        ),
        "outcome_columns_absent": not any(
            str(column).startswith("label__") or "outcome" in str(column).lower()
            for column in prediction_frame.columns
        ),
        "common_population_reconciled": True,
        "ablation_population_identical": True,
        "locked_sequence_complete": True,
        "evaluation_metrics_computed": False,
    }
    if not all(value is True for key, value in validation.items() if key not in {"schema_version", "status"}):
        raise D2ArtifactError(f"Stage 1 validation failed: {validation}")
    write_json(stage / "validation.json", validation)
    return {
        "prediction_identity": frame_identity(
            prediction_frame, sort_by=["block_id", "cell_id", "decision_session", "security_id"]
        ),
        "common_score_mask_identity": frame_identity(
            mask_frame, sort_by=["block_id", "decision_session", "security_id"]
        ),
        "observation_feature_matrix_hash": observation_audit["feature_matrix_hash"],
        "locked_sequence_fingerprint": locked_fingerprint,
        "code_commit": authorization["implementation"]["code_commit"],
        "outcomes_in_publication": False,
        "metrics_in_publication": False,
    }


def validate_prediction_run(run_dir: Path) -> dict[str, Any]:
    manifest = validate_manifest(run_dir, schema_version=PREDICTION_SCHEMA, required_files=PREDICTION_FILES)
    validation = read_json(run_dir / "validation.json")
    if validation.get("status") != "PASS":
        raise D2ArtifactError("Stage 1 sealed validation did not pass")
    predictions = pd.read_parquet(run_dir / "predictions.parquet")
    masks = pd.read_parquet(run_dir / "common_score_masks.parquet")
    forbidden = [column for column in predictions if str(column).startswith("label__") or "outcome" in str(column).lower()]
    if forbidden:
        raise D2ArtifactError(f"prediction publication exposes outcomes: {forbidden}")
    if not predictions["candidate"].eq(predictions["model_score"].gt(predictions["threshold"])).all():
        raise D2ArtifactError("sealed candidate flags do not use strict threshold comparison")
    cells = set(predictions["cell_id"])
    if cells != {*PRIMARY_CELLS, ABLATION_CELL}:
        raise D2ArtifactError("sealed Stage 1 cells differ from the frozen execution")
    if masks.groupby(["block_id", "decision_session"]).size().ne(60).any():
        raise D2ArtifactError("sealed common mask does not preserve denominator 60")
    logical = manifest["logical_payload"]
    actual_identity = frame_identity(
        predictions, sort_by=["block_id", "cell_id", "decision_session", "security_id"]
    )
    if actual_identity != logical.get("prediction_identity"):
        raise D2ArtifactError("sealed prediction logical identity differs")
    return {
        "schema_version": "ats.phase_d2.prediction_run_validation.v1",
        "status": "PASS",
        "run_id": manifest["run_id"],
        "logical_hash": manifest["logical_hash"],
        "prediction_logical_hash": actual_identity["logical_hash"],
        "locked_sequence_fingerprint": logical["locked_sequence_fingerprint"],
    }


def publish_prediction_run(*, reproduction: bool = False) -> Path:
    execution = load_execution_config()
    run_id = (
        execution["reproduction_run_ids"]["prediction"]
        if reproduction else execution["primary_run_ids"]["prediction"]
    )
    root = Path(execution["output_roots"]["prediction_runs"])
    if reproduction:
        root = Path(execution["output_roots"]["reproductions"]) / "prediction_runs"
    return publish_immutable(
        root, run_id, build_prediction_run,
        schema_version=PREDICTION_SCHEMA, validate=validate_prediction_run,
    )

