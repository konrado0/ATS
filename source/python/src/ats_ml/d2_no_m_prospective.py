from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ats_ml.d2_artifacts import D2ArtifactError, file_inventory, read_json, write_json
from ats_ml.d2_no_m import CONTRACT_PATH, NO_M, COMPARATORS, PREDICTION_ROOT, load_contract
from ats_ml.d2_stage1 import SequentialLabelAdmissionFirewall, _actual_fit, _score_rows
from ats_ml.walkforward import _new_estimator
from ats_research.hashing import content_hash, logical_frame_hash, sha256_file


STREAM_ID = "phase-d2-nm-post-freeze-2026-v1"
STREAM_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/prospective_streams") / STREAM_ID
OUTCOME_TOKENS = ("label", "outcome", "return_20", "forward", "target_value")
REQUIRED_COLUMNS = {
    "information_session", "decision_session", "decision_ts", "cell_id", "security_id",
    "model_score", "threshold", "candidate", "prediction_generation_ts", "publication_seal_ts",
    "target_start_session", "target_endpoint_session", "label_availability_ts",
    "prospective_eligible", "monitoring_only", "exclusion_reason",
    "official_expected_count", "model_exclusion_reason",
}


def validate_prediction_batch(frame: pd.DataFrame) -> dict[str, Any]:
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise D2ArtifactError(f"prospective prediction batch lacks columns: {sorted(missing)}")
    forbidden = sorted(column for column in frame.columns if any(token in column.lower() for token in OUTCOME_TOKENS) and column != "label_availability_ts")
    if forbidden:
        raise D2ArtifactError(f"outcome-bearing prediction artifact rejected: {forbidden}")
    expected_cells = {NO_M, *COMPARATORS}
    if set(frame["cell_id"].astype(str)) != expected_cells:
        raise D2ArtifactError("prospective batch must contain exactly the frozen three cells")
    keys = ["security_id", "decision_session"]
    populations = {
        cell: group[keys].astype({"security_id": str}).sort_values(keys, kind="mergesort").reset_index(drop=True)
        for cell, group in frame.groupby("cell_id", sort=True)
    }
    first = populations[sorted(populations)[0]]
    if any(not first.equals(populations[cell]) for cell in sorted(populations)[1:]):
        raise D2ArtifactError("prospective cell populations differ")
    if frame.duplicated(["cell_id", *keys]).any():
        raise D2ArtifactError("conflicting duplicate prediction rows")
    decision_ts = pd.to_datetime(frame["decision_ts"], utc=True)
    seal_ts = pd.to_datetime(frame["publication_seal_ts"], utc=True)
    timely = seal_ts.le(decision_ts)
    scored = np.isfinite(pd.to_numeric(frame["model_score"], errors="coerce"))
    if not frame["candidate"].eq(frame["model_score"].gt(frame["threshold"])).all():
        raise D2ArtifactError("strict prospective threshold rule failed")
    if not frame["prospective_eligible"].eq(timely & scored).all():
        raise D2ArtifactError("objective prospective eligibility differs from seal timestamp")
    if not frame["monitoring_only"].eq((~timely) & scored).all():
        raise D2ArtifactError("late prediction is not permanently monitoring-only")
    if frame.loc[(~timely) & scored, "exclusion_reason"].astype(str).ne("SEALED_AFTER_DECISION_TS").any():
        raise D2ArtifactError("late prediction exclusion reason is not explicit")
    if frame["official_expected_count"].ne(60).any() or frame.groupby(["cell_id", "decision_session"])["security_id"].nunique().gt(60).any():
        raise D2ArtifactError("official denominator 60 is not visible")
    unscored = ~scored
    if frame.loc[unscored, "model_exclusion_reason"].astype(str).str.len().eq(0).any():
        raise D2ArtifactError("unscored official rows require a visible exclusion reason")
    if frame.loc[unscored, "exclusion_reason"].astype(str).ne(frame.loc[unscored, "model_exclusion_reason"].astype(str)).any():
        raise D2ArtifactError("unscored official row exclusion reason was not preserved")
    unknown = frame["model_exclusion_reason"].astype(str).str.contains("UNKNOWN_(?:SPLIT|MEMBERSHIP)_STATE", regex=True)
    if (unknown & scored).any():
        raise D2ArtifactError("unknown split or membership state was scored")
    return {
        "status": "PASS", "rows": len(frame), "decision_sessions": int(frame["decision_session"].nunique()),
        "prospective_rows": int((timely & scored).sum()), "monitoring_only_rows": int(((~timely) & scored).sum()),
        "cells": sorted(expected_cells), "outcome_columns_absent": True,
        "official_denominator": 60, "visible_exclusion_rows": int(unscored.sum()),
    }


def _existing_keys(root: Path) -> pd.DataFrame:
    pieces = [pd.read_parquet(path) for path in root.glob("batches/*/predictions.parquet")]
    if not pieces:
        return pd.DataFrame(columns=["cell_id", "security_id", "decision_session", "model_score", "threshold", "candidate"])
    return pd.concat(pieces, ignore_index=True)


def initialize_stream(*, registered_ts: str, reason: str) -> Path:
    if STREAM_ROOT.exists():
        raise D2ArtifactError(f"append-only prospective stream already exists: {STREAM_ROOT}")
    STREAM_ROOT.mkdir(parents=True)
    registration = {
        "schema_version": "ats.phase_d2_nm.prospective_registration.v1",
        "stream_id": STREAM_ID,
        "contract_id": load_contract()["contract_id"],
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "registered_ts": pd.Timestamp(registered_ts).isoformat(),
        "status": "ACTIVE_NO_ELIGIBLE_POST_FREEZE_SESSION",
        "reason": reason,
        "accepted_35_sessions": "HISTORICAL_CANARY_ONLY",
        "missed_predictions_are_never_backfilled": True,
        "notification_or_scheduler": None,
    }
    registration["logical_hash"] = content_hash(registration)
    write_json(STREAM_ROOT / "registration.json", registration)
    write_json(STREAM_ROOT / "manifest.json", {
        "schema_version": "ats.phase_d2_nm.prospective_stream.v1", "stream_id": STREAM_ID,
        "files": file_inventory(STREAM_ROOT), "mutable_latest_pointer": False,
    })
    return STREAM_ROOT


def append_prediction_batch(input_path: Path, *, batch_id: str) -> Path:
    if not STREAM_ROOT.is_dir() or not (STREAM_ROOT / "registration.json").is_file():
        raise D2ArtifactError("prospective stream is not registered")
    if not batch_id or "latest" in batch_id.lower() or "current" in batch_id.lower():
        raise D2ArtifactError("immutable batch ID is required")
    frame = pd.read_parquet(input_path)
    validation = validate_prediction_batch(frame)
    existing = _existing_keys(STREAM_ROOT)
    key_cols = ["cell_id", "security_id", "decision_session"]
    overlap = frame.merge(existing[key_cols], on=key_cols, how="inner") if len(existing) else pd.DataFrame()
    if len(overlap):
        raise D2ArtifactError("conflicting duplicate prospective prediction rejected")
    destination = STREAM_ROOT / "batches" / batch_id
    if destination.exists():
        raise D2ArtifactError("append-only prediction batch already exists")
    destination.mkdir(parents=True)
    frame.sort_values(["decision_session", "cell_id", "security_id"], kind="mergesort").to_parquet(
        destination / "predictions.parquet", index=False, compression="zstd", use_dictionary=False
    )
    write_json(destination / "validation.json", validation)
    write_json(destination / "manifest.json", {
        "schema_version": "ats.phase_d2_nm.prospective_batch.v1", "batch_id": batch_id,
        "input_sha256": sha256_file(input_path), "files": file_inventory(destination),
    })
    return destination


def score_pinned_package(package_dir: Path, *, output_path: Path) -> Path:
    """Fit/score only the frozen three cells from an explicit immutable input package."""
    generation_ts = pd.Timestamp.now(tz="UTC")
    config = read_json(package_dir / "input_config.json")
    if config.get("schema_version") != "ats.phase_d2_nm.prospective_input.v1":
        raise D2ArtifactError("unexpected prospective input schema")
    files = config.get("files", {})
    for name in ("observations.parquet", "training_labels.parquet", "walk_forward_block.json"):
        path = package_dir / name
        if not path.is_file() or sha256_file(path) != files.get(name, {}).get("sha256"):
            raise D2ArtifactError(f"pinned prospective input mismatch: {name}")
    observations = pd.read_parquet(package_dir / "observations.parquet")
    labels = pd.read_parquet(package_dir / "training_labels.parquet")
    block = read_json(package_dir / "walk_forward_block.json")
    if block.get("refit_session") != config.get("refit_session"):
        raise D2ArtifactError("prospective refit binding mismatch")
    decision_sessions = [str(value) for value in config.get("decision_sessions", [])]
    if not decision_sessions or set(decision_sessions) - set(block.get("evaluation_sessions", [])):
        raise D2ArtifactError("requested sessions are absent from the pinned walk-forward block")
    admitted, admission = SequentialLabelAdmissionFirewall({"blocks": [block]}).admit(block)
    if set(pd.to_datetime(labels["decision_session"]).dt.strftime("%Y-%m-%d")) - set(admitted):
        raise D2ArtifactError("training-label input exceeds the block-scoped admission set")
    refit_ts = pd.Timestamp(block["refit_session"]).tz_localize("Europe/Warsaw") + pd.Timedelta(hours=8, minutes=45)
    endpoints = pd.to_datetime(labels["label_endpoint_ts_20"], utc=True)
    if not endpoints.lt(refit_ts.tz_convert("UTC")).all():
        raise D2ArtifactError("training-label package reaches or exceeds the refit timestamp")
    accepted = read_json(PREDICTION_ROOT / "derived_contract.json")
    cells = {cell: accepted["cells"][cell] for cell in (NO_M, *COMPARATORS)}
    outputs: list[pd.DataFrame] = []
    audits: list[dict[str, Any]] = []
    outer_all = observations.loc[observations["decision_session"].isin(pd.to_datetime(decision_sessions))].copy()
    if outer_all.groupby("decision_session")["security_id"].nunique().ne(60).any():
        raise D2ArtifactError("prospective input does not preserve the official denominator 60")
    for cell_id, cell in cells.items():
        features = tuple(cell["feature_names"])
        inner_values: list[np.ndarray] = []
        inner_audits: list[dict[str, Any]] = []
        for inner in block["inner_score_blocks"]:
            fit, fit_proof = _actual_fit(
                observations, labels, inner["fit_retained_sessions"], inner["fit_boundary_session"], features,
                int(inner["minimum_qualifying_sessions"]), int(inner["minimum_model_rows"]), "Europe/Warsaw",
            )
            score, score_proof = _score_rows(observations, inner["score_sessions"], features, int(inner["score_minimum_qualifying_sessions"]))
            estimator = _new_estimator(str(cell["model"])); estimator.fit(fit[list(features)], fit["label__open_to_open__20"])
            values = np.asarray(estimator.predict(score[list(features)]), float)
            inner_values.append(values)
            inner_audits.append({"fit": fit_proof, "score": score_proof, "score_hash": logical_frame_hash(pd.DataFrame({"score": values}))})
        pooled = np.concatenate(inner_values)
        threshold = max(0.01, float(np.quantile(pooled, 0.90, method="linear")))
        final, final_proof = _actual_fit(
            observations, labels, block["final_fit"]["retained_sessions"], block["final_fit"]["boundary_session"], features,
            int(block["final_fit"]["minimum_qualifying_sessions"]), int(block["final_fit"]["minimum_model_rows"]), "Europe/Warsaw",
        )
        score, score_proof = _score_rows(observations, decision_sessions, features, 0)
        estimator = _new_estimator(str(cell["model"])); estimator.fit(final[list(features)], final["label__open_to_open__20"])
        score_values = np.asarray(estimator.predict(score[list(features)]), float)
        value_map = {(str(row.security_id), pd.Timestamp(row.decision_session)): value for row, value in zip(score.itertuples(), score_values)}
        output = outer_all[["security_id", "decision_session", "information_session", "decision_ts", "official_expected_count", "model_exclusion_reason"]].copy()
        output["cell_id"] = cell_id
        output["model_score"] = [value_map.get((str(row.security_id), pd.Timestamp(row.decision_session)), math.nan) for row in output.itertuples()]
        output["threshold"] = threshold
        output["candidate"] = output["model_score"].gt(threshold)
        outputs.append(output)
        audits.append({"cell_id": cell_id, "features": list(features), "inner": inner_audits, "final_fit": final_proof, "outer_score": score_proof, "threshold": threshold})
    frame = pd.concat(outputs, ignore_index=True)
    targets = {str(row["decision_session"]): row for row in config.get("targets", [])}
    frame["prediction_generation_ts"] = generation_ts
    frame["publication_seal_ts"] = pd.Timestamp.now(tz="UTC")
    for name in ("target_start_session", "target_endpoint_session", "label_availability_ts"):
        frame[name] = frame["decision_session"].dt.strftime("%Y-%m-%d").map(lambda key: targets[key][name])
    timely = pd.to_datetime(frame["publication_seal_ts"], utc=True).le(pd.to_datetime(frame["decision_ts"], utc=True))
    scored = np.isfinite(frame["model_score"])
    frame["prospective_eligible"] = timely & scored
    frame["monitoring_only"] = (~timely) & scored
    frame["exclusion_reason"] = np.where(~scored, frame["model_exclusion_reason"], np.where(~timely, "SEALED_AFTER_DECISION_TS", ""))
    validate_prediction_batch(frame)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise D2ArtifactError("prediction-only output is append-only")
    frame.to_parquet(output_path, index=False, compression="zstd", use_dictionary=False)
    write_json(output_path.with_suffix(".audit.json"), {"label_admission": admission, "fit_audit": audits, "input_config_sha256": sha256_file(package_dir / "input_config.json")})
    return output_path


def record_missed_session(*, decision_session: str, reason: str) -> Path:
    session = pd.Timestamp(decision_session).strftime("%Y-%m-%d")
    destination = STREAM_ROOT / "missed" / f"{session}.json"
    if destination.exists():
        raise D2ArtifactError("missed-session record is append-only")
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_json(destination, {
        "schema_version": "ats.phase_d2_nm.missed_session.v1", "decision_session": session,
        "status": "MISSED_PERMANENTLY_INELIGIBLE", "reason": reason, "backfill_permitted": False,
    })
    return destination
