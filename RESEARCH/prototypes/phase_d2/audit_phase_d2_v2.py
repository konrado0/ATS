from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from evaluate_phase_d2 import (
    COMPARATORS,
    anchors_for_all,
    evaluate as evaluate_core,
    population_metrics,
    read_json,
    select,
    session_ics,
    validate_seal,
    wide,
)


BLOCKS = {
    "stage2a": ["MODEL_SELECTION_2023_H1", "MODEL_SELECTION_2023_H2"],
    "stage2b": ["DEVELOPMENT_2024_H1", "DEVELOPMENT_2024_H2"],
    "stage2c": ["LOCKED_2025_H1", "LOCKED_2025_H2", "LOCKED_2026_H1"],
}
PRIMARY_CELLS = {"C_LINEAR", "C_LIGHTGBM", "RICH_LINEAR", "RICH_LIGHTGBM", "RICH_NO_M_LIGHTGBM"}


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(float(value)) else float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def population_equal_by_cell(predictions: pd.DataFrame, blocks: list[str]) -> bool:
    keys = ["block_id", "security_id", "decision_session"]
    selected = predictions.loc[predictions["block_id"].isin(blocks)]
    groups = {
        str(cell): group[keys].sort_values(keys, kind="mergesort").reset_index(drop=True)
        for cell, group in selected.groupby("cell_id", sort=True)
    }
    if set(groups) != PRIMARY_CELLS:
        return False
    first = groups[sorted(groups)[0]]
    return all(first.equals(groups[cell]) for cell in sorted(groups)[1:])


def actual_minimums_pass(fit_records: list[dict[str, Any]], plan: dict[str, Any]) -> bool:
    blocks = {block["block_id"]: block for block in plan["blocks"]}
    records = [record for record in fit_records if record.get("cell_id")]
    if len(records) != len(blocks) * 5:
        return False
    for record in records:
        block = blocks[record["block_id"]]
        final = record["final_fit"]
        expected_final = block["final_fit"]
        if (
            final["rows"] < expected_final["minimum_model_rows"]
            or final["qualifying_sessions"] < expected_final["minimum_qualifying_sessions"]
            or record["outer_score"]["rows"]
            < (block["evaluation_minimum_rows"] if block["complete"] else 0)
            or record["outer_score"]["qualifying_sessions"]
            < (block["evaluation_minimum_qualifying_sessions"] if block["complete"] else 0)
        ):
            return False
        inner_plan = {item["score_block_number"]: item for item in block["inner_score_blocks"]}
        for inner in record["inner"]:
            expected = inner_plan[inner["score_block_number"]]
            if (
                inner["fit"]["rows"] < expected["minimum_model_rows"]
                or inner["fit"]["qualifying_sessions"] < expected["minimum_qualifying_sessions"]
                or inner["score"]["qualifying_sessions"]
                < expected["score_minimum_qualifying_sessions"]
            ):
                return False
    return True


def session_concentration(evaluation_root: Path, stage: str) -> dict[str, Any]:
    anchors = pd.read_parquet(
        evaluation_root / stage / "episode_anchors.parquet",
        columns=["block_id", "decision_session"],
    )
    total = len(anchors)
    if total == 0:
        return {
            "status": "NOT PROVEN",
            "episode_count": 0,
            "largest_session_episode_share": None,
            "top5_session_episode_share": None,
            "session_episode_hhi": None,
            "largest_block_episode_share": None,
            "block_episode_hhi": None,
        }
    session_counts = anchors.groupby("decision_session", sort=True).size().astype(float)
    session_shares = session_counts / total
    block_counts = anchors.groupby("block_id", sort=True).size().astype(float)
    block_shares = block_counts / total
    return {
        "status": "PASS",
        "episode_count": total,
        "nonzero_sessions": len(session_counts),
        "largest_session_episode_count": int(session_counts.max()),
        "largest_session_episode_share": float(session_shares.max()),
        "top5_session_episode_share": float(session_shares.nlargest(5).sum()),
        "session_episode_hhi": float(session_shares.pow(2).sum()),
        "largest_session_boundary": [
            pd.Timestamp(value).date().isoformat()
            for value in session_counts.loc[session_counts.eq(session_counts.max())].index
        ],
        "block_episode_counts": {str(key): int(value) for key, value in block_counts.items()},
        "block_episode_shares": {str(key): float(value) for key, value in block_shares.items()},
        "largest_block_episode_share": float(block_shares.max()),
        "block_episode_hhi": float(block_shares.pow(2).sum()),
    }


def derive_integrity(
    prediction_dir: Path, evaluation_root: Path, seals: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    predictions = pd.read_parquet(prediction_dir / "predictions.parquet")
    masks = pd.read_parquet(prediction_dir / "common_score_masks.parquet")
    fit_audit = read_json(prediction_dir / "fit_calibration_audit.json")
    plan = read_json(prediction_dir / "walk_forward_plan.json")
    derived = read_json(prediction_dir / "derived_contract.json")
    fit_records = [record for record in fit_audit["records"] if record.get("cell_id")]
    forbidden = {"security_id", "ticker", "vendor_symbol", "decision_session", "decision_ts"}
    endpoint_proofs = [
        proof["endpoint_strictly_before_boundary"]
        for record in fit_records
        for proof in [record["final_fit"], *[inner["fit"] for inner in record["inner"]]]
    ]
    estimator_proofs = [
        inner["estimator_recreated"]
        for record in fit_records
        for inner in record["inner"]
    ]
    all_outcomes = []
    for stage in ("stage2a", "stage2b", "stage2c"):
        frame = pd.read_parquet(evaluation_root / stage / "outcomes.parquet")
        frame["source_stage"] = stage
        all_outcomes.append(frame)
    outcomes = pd.concat(all_outcomes, ignore_index=True)
    available = outcomes["label_state_20"].eq("AVAILABLE")
    endpoint_rows = outcomes["label_endpoint_session_20"].notna()
    endpoint_order = outcomes.loc[endpoint_rows, "label_endpoint_session_20"].gt(
        outcomes.loc[endpoint_rows, "decision_session"]
    ).all()
    mask_groups = masks.groupby(["block_id", "decision_session"], sort=True)
    population_checks = [population_equal_by_cell(predictions, BLOCKS[stage]) for stage in ("stage2a", "stage2b", "stage2c")]
    outcome_population_checks = []
    for stage in ("stage2a", "stage2b", "stage2c"):
        outcome = outcomes.loc[outcomes["source_stage"].eq(stage)]
        mask = masks.loc[masks["block_id"].isin(BLOCKS[stage])]
        left = mask[["block_id", "security_id", "decision_session"]].sort_values(
            ["block_id", "decision_session", "security_id"], kind="mergesort"
        ).reset_index(drop=True)
        right = outcome[["block_id", "security_id", "decision_session"]].sort_values(
            ["block_id", "decision_session", "security_id"], kind="mergesort"
        ).reset_index(drop=True)
        outcome_population_checks.append(left.equals(right))
    stage2a_lineage = read_json(evaluation_root / "stage2a" / "lineage.json")
    stage2b_lineage = read_json(evaluation_root / "stage2b" / "lineage.json")
    stage2c_lineage = read_json(evaluation_root / "stage2c" / "lineage.json")
    final_lineage = read_json(evaluation_root / "final" / "lineage.json")
    prediction_scientific_hash = seals["prediction"]["logical_payload"]["prediction_identity"]["logical_hash"]
    lineage_hashes = [stage2a_lineage, stage2b_lineage, stage2c_lineage]
    all_lineage_prediction_match = all(
        lineage["prediction_scientific_hash"] == prediction_scientific_hash
        and lineage["prediction_regenerated"] is False
        for lineage in lineage_hashes
    )
    predecessor_order = (
        stage2a_lineage["predecessors"] == []
        and [item["stage"] for item in stage2b_lineage["predecessors"]] == ["stage2a"]
        and [item["stage"] for item in stage2c_lineage["predecessors"]] == ["stage2a", "stage2b"]
        and final_lineage["stage_logical_hashes"]
        == {stage: seals[stage]["logical_hash"] for stage in ("stage2a", "stage2b", "stage2c")}
    )
    admission = fit_audit.get("label_admission")
    sequential_status = "PASS" if (
        admission
        and admission.get("mode") == "outer_block_sequential"
        and admission.get("complete") is True
        and [item.get("block_id") for item in admission.get("records", [])]
        == [block["block_id"] for block in plan["blocks"]]
        and all(item.get("all_loaded_endpoints_strictly_before_refit") is True for item in admission.get("records", []))
    ) else "NOT PROVEN"
    rows = [
        ("pit_membership_and_information_timing", bool(
            masks["information_session"].lt(masks["decision_session"]).all()
            and masks["decision_ts"].dt.hour.eq(8).all()
            and masks["decision_ts"].dt.minute.eq(45).all()
        ), "sealed mask timestamps"),
        ("official_denominator_60", bool(
            mask_groups.size().eq(60).all()
            and masks["official_expected_count"].eq(60).all()
            and mask_groups["model_score_eligible"].sum().eq(mask_groups["scored_count"].first()).all()
            and mask_groups["scored_count"].first().add(mask_groups["excluded_count"].first()).eq(60).all()
        ), "sealed mask rows and scored/excluded counts"),
        ("exact_label_anchors_and_availability", bool(
            available.eq(np.isfinite(outcomes["label__open_to_open__20"])).all() and endpoint_order
        ), "sealed outcome states, endpoints, and values"),
        ("endpoint_derived_purge", bool(endpoint_proofs and all(endpoint_proofs)), "all retained fit endpoint proofs"),
        ("fold_local_preprocessing", bool(
            estimator_proofs and all(estimator_proofs)
            and all(record.get("threshold_frozen_before_final_refit") is True for record in fit_records)
        ), "all fit/calibration records"),
        ("identity_predictors_absent", bool(
            fit_records and all(not (set(record["feature_names"]) & forbidden) for record in fit_records)
        ), "all sealed fit feature allowlists"),
        ("identity_neutral_ties", bool(
            predictions["candidate"].eq(predictions["model_score"].gt(predictions["threshold"])).all()
            and derived["opportunity_contract"]["frequency_matching"].get("identity_neutrality")
        ), "strict candidates and frozen frequency-match tie contract"),
        ("common_score_and_outcome_populations", bool(all(population_checks) and all(outcome_population_checks)), "sealed cell/mask/outcome semantic keys"),
        ("ablation_population_identical", bool(all(population_checks) and "RICH_NO_M_LIGHTGBM" in set(predictions["cell_id"])), "sealed ablation semantic keys"),
        ("actual_minimums", actual_minimums_pass(fit_audit["records"], plan), "retained counts versus frozen minima"),
        ("prediction_not_regenerated", bool(all_lineage_prediction_match), "prediction fingerprints and stage lineage"),
        ("stage_information_order", bool(predecessor_order), "predecessor logical-hash chain and outcome stages"),
        ("logical_and_physical_reconciliation", True, "independent seal inventory, byte, and logical validation"),
    ]
    checks = [
        {"check_id": name, "status": "PASS" if value is True else "FAIL", "value": value, "evidence": evidence}
        for name, value, evidence in rows
    ]
    checks.append({
        "check_id": "sequential_locked_label_admission",
        "status": sequential_status,
        "value": True if sequential_status == "PASS" else None,
        "evidence": (
            "sealed outer-block sequential admission records"
            if sequential_status == "PASS"
            else "accepted v4 fit audit has no sequential admission record; its code loaded the union before block generation"
        ),
    })
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "NOT FULLY PROVEN"
    return {"status": status, "checks": checks}


def independent_negative_anchors(
    prediction_dir: Path, evaluation_root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    predictions = pd.read_parquet(prediction_dir / "predictions.parquet")
    masks = pd.read_parquet(prediction_dir / "common_score_masks.parquet")
    selection_outcomes = pd.read_parquet(evaluation_root / "stage2a" / "outcomes.parquet")
    selection_frame = wide(predictions, selection_outcomes, BLOCKS["stage2a"])
    selection_ic = session_ics(selection_frame, ["C_LINEAR", "C_LIGHTGBM", "RICH_LINEAR", "RICH_LIGHTGBM"])
    selection_statistics = {
        cell: float(selection_ic[cell].mean())
        for cell in ("C_LINEAR", "C_LIGHTGBM", "RICH_LINEAR", "RICH_LIGHTGBM")
    }
    selected_conventional = select(selection_statistics, "C_LINEAR", "C_LIGHTGBM")
    selected_rich = select(selection_statistics, "RICH_LINEAR", "RICH_LIGHTGBM")
    calendar = pd.DatetimeIndex(sorted(masks["decision_session"].unique()))
    anchors = anchors_for_all(predictions, selected_rich, calendar)
    values = {}
    for stage in ("stage2b", "stage2c"):
        outcomes = pd.read_parquet(evaluation_root / stage / "outcomes.parquet")
        values[stage] = population_metrics(predictions, outcomes, BLOCKS[stage], selected_rich, anchors)
    derived = read_json(prediction_dir / "derived_contract.json")
    frozen = derived["decision_gate"]["incremental_rank_information"]
    thresholds = {
        "stage2b": frozen["development_confirmation_mean_delta_ic_min_against_each_conventional"],
        "stage2c": frozen["locked_evidence_mean_delta_ic_min_against_each_conventional"],
    }
    failing = []
    for stage in ("stage2b", "stage2c"):
        for comparator in COMPARATORS:
            value = values[stage]["mean_delta_ic"][comparator]
            if value < thresholds[stage]:
                failing.append({
                    "stage": stage,
                    "comparator": comparator,
                    "value": value,
                    "threshold": thresholds[stage],
                    "classification": "FAIL",
                })
    summary = {
        "selection_statistics": selection_statistics,
        "selected_conventional": selected_conventional,
        "selected_rich": selected_rich,
        "mean_delta_ic": {
            stage: values[stage]["mean_delta_ic"] for stage in ("stage2b", "stage2c")
        },
        "frozen_mean_delta_thresholds": thresholds,
        "independently_recomputed_failures": failing,
        "scientific_stop_verified": bool(failing),
    }
    return summary, values


def build_audit(prediction_dir: Path, evaluation_root: Path) -> dict[str, Any]:
    seals = {"prediction": validate_seal(prediction_dir)}
    for stage in ("stage2a", "stage2b", "stage2c", "final"):
        seals[stage] = validate_seal(evaluation_root / stage)
    core = evaluate_core(prediction_dir, evaluation_root)
    negative, _ = independent_negative_anchors(prediction_dir, evaluation_root)
    concentration = {
        "stage2b": session_concentration(evaluation_root, "stage2b"),
        "stage2c": session_concentration(evaluation_root, "stage2c"),
    }
    integrity = derive_integrity(prediction_dir, evaluation_root, seals)
    accepted_verdict = read_json(evaluation_root / "final" / "verdict.json")
    coverage = {
        "independently_recomputed": [
            "2023 within-representation model selection",
            "population denominators",
            "mean session IC and paired mean delta IC",
            "candidate and idle frequencies",
            "episode anchors",
            "rich-minus-eligible and frequency-matched mean tail separation",
            "severe-outcome rate differences",
            "security and chronological-quartile concentration",
            "new session and half-year block concentration",
        ],
        "reclassified_from_primary_gate_values": "all stored gate rows",
        "not_independently_recomputed": [
            "bootstrap intervals and defined-replicate fractions",
            "leave-top-contributor calculations",
            "complete-year gate inputs",
            "every remaining gate input not listed as independently recomputed",
        ],
        "claim": "bounded independent core audit; not a full independent recomputation of every gate input",
    }
    scientific_payload = json_ready({
        "schema_version": "ats.phase_d2.audit_science.v2",
        "prediction_scientific_hash": seals["prediction"]["logical_payload"]["prediction_identity"]["logical_hash"],
        "stage_logical_hashes": {stage: seals[stage]["logical_hash"] for stage in ("stage2a", "stage2b", "stage2c", "final")},
        "negative_result": negative,
        "session_and_period_concentration": concentration,
        "execution_integrity_status": integrity["status"],
        "execution_integrity_check_statuses": {
            item["check_id"]: item["status"] for item in integrity["checks"]
        },
        "independent_coverage": coverage,
        "accepted_mechanical_verdict": accepted_verdict["frozen_phase_d_research_verdict"],
        "d3_execution_authorized": "NO",
        "portfolio_backtest_work_authorized": "NO",
    })
    if not negative["scientific_stop_verified"] or accepted_verdict["frozen_phase_d_research_verdict"] != "STOP":
        audit_status = "NOT PROVEN"
    else:
        audit_status = "PASS WITH EXECUTION-INTEGRITY QUALIFICATION"
    return {
        "schema_version": "ats.phase_d2.audit.v2",
        "audit_status": audit_status,
        "scientific_stop_status": "STOP — VERIFIED" if negative["scientific_stop_verified"] else "NOT PROVEN",
        "execution_integrity": integrity,
        "independent_core_evaluator": {
            "status": core["status"],
            "logical_hash": core["logical_hash"],
            "gate_classification_from_stored_values_match": core["gate_classification_match"],
            "coverage": coverage,
        },
        "scientific_payload": scientific_payload,
        "scientific_logical_hash": canonical_hash(scientific_payload),
        "operational_inputs": {
            "prediction_dir": str(prediction_dir),
            "evaluation_root": str(evaluation_root),
            "manifest_sha256": {
                "prediction": digest(prediction_dir / "manifest.json"),
                **{stage: digest(evaluation_root / stage / "manifest.json") for stage in ("stage2a", "stage2b", "stage2c", "final")},
            },
        },
        "accepted_artifacts_modified": False,
        "prediction_regenerated": False,
        "scientific_choice_changed": False,
    }


def publish(audit: dict[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise FileExistsError(f"audit publication already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = output_dir.parent / f".stage-{output_dir.name}-{uuid.uuid4().hex}"
    stage.mkdir()
    try:
        evidence = stage / "audit.json"
        evidence.write_text(
            json.dumps(audit, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "schema_version": "ats.phase_d2.audit_manifest.v2",
            "run_id": output_dir.name,
            "scientific_logical_hash": audit["scientific_logical_hash"],
            "package_logical_hash": canonical_hash(audit),
            "files": {
                "audit.json": {
                    "bytes": evidence.stat().st_size,
                    "sha256": digest(evidence),
                }
            },
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(stage, output_dir)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prediction-dir", type=Path, required=True)
    parser.add_argument("--evaluation-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    audit = build_audit(args.prediction_dir, args.evaluation_root)
    publish(audit, args.output_dir)
    print(json.dumps({
        "audit_status": audit["audit_status"],
        "scientific_stop_status": audit["scientific_stop_status"],
        "execution_integrity": audit["execution_integrity"]["status"],
        "scientific_logical_hash": audit["scientific_logical_hash"],
        "output_dir": str(args.output_dir),
    }, indent=2, sort_keys=True))
    return 0 if audit["scientific_stop_status"] == "STOP — VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
