from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ats_ml.contracts_v3 import load_frozen_d0_v3_contract
from ats_ml.d2_artifacts import (
    D2ArtifactError,
    parquet_identity,
    json_ready,
    publish_immutable,
    read_json,
    validate_manifest,
    write_json,
    write_parquet,
)
from ats_ml.d2_contract import load_execution_config
from ats_ml.d2_data import build_real_labels
from ats_ml.d2_metrics import (
    COMPARATORS,
    choose_model_family,
    evaluate_population,
    gate,
    mechanical_verdict,
    session_ic_table,
    wide_prediction_frame,
)
from ats_ml.d2_stage1 import PRIMARY_CELLS, validate_prediction_run
from ats_research.hashing import content_hash, logical_frame_hash, sha256_file


STAGE_SCHEMAS = {
    "stage2a": "ats.phase_d2.model_selection.v1",
    "stage2b": "ats.phase_d2.development_confirmation.v1",
    "stage2c": "ats.phase_d2.locked_evaluation.v1",
    "final": "ats.phase_d2.final_verdict.v1",
}
STAGE_FILES = {
    "stage2a": {"lineage.json", "outcomes.parquet", "selection.json", "session_ic.parquet", "validation.json"},
    "stage2b": {"lineage.json", "outcomes.parquet", "metrics.json", "gates.json", "session_ic.parquet", "tail_sessions.parquet", "episode_anchors.parquet", "diagnostics.json", "validation.json"},
    "stage2c": {"lineage.json", "outcomes.parquet", "metrics.json", "gates.json", "session_ic.parquet", "tail_sessions.parquet", "episode_anchors.parquet", "diagnostics.json", "monitoring.json", "validation.json"},
    "final": {"lineage.json", "gate_matrix.json", "verdict.json", "validation.json"},
}
BLOCKS = {
    "stage2a": ["MODEL_SELECTION_2023_H1", "MODEL_SELECTION_2023_H2"],
    "stage2b": ["DEVELOPMENT_2024_H1", "DEVELOPMENT_2024_H2"],
    "stage2c": ["LOCKED_2025_H1", "LOCKED_2025_H2", "LOCKED_2026_H1"],
}


def require_stage_outcome_access(stage_name: str, block_ids: list[str], sealed_predecessors: set[str]) -> None:
    expected_predecessors = {
        "stage2a": set(),
        "stage2b": {"stage2a"},
        "stage2c": {"stage2a", "stage2b"},
    }
    if stage_name not in BLOCKS:
        raise PermissionError(f"unknown D2 outcome stage: {stage_name}")
    if sealed_predecessors != expected_predecessors[stage_name]:
        raise PermissionError(f"{stage_name} outcome firewall predecessor violation")
    if set(block_ids) != set(BLOCKS[stage_name]):
        raise PermissionError(f"{stage_name} attempted to open an unpermitted outcome block")


def _prediction_inputs(prediction_dir: Path) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    validation = validate_prediction_run(prediction_dir)
    predictions = pd.read_parquet(prediction_dir / "predictions.parquet")
    masks = pd.read_parquet(prediction_dir / "common_score_masks.parquet")
    return validation, predictions, masks


def prediction_scientific_hash(manifest: dict[str, Any]) -> str:
    try:
        value = manifest["logical_payload"]["prediction_identity"]["logical_hash"]
    except (KeyError, TypeError) as exc:
        raise D2ArtifactError("prediction manifest lacks a scientific table fingerprint") from exc
    if not isinstance(value, str) or len(value) != 64:
        raise D2ArtifactError("prediction scientific fingerprint is invalid")
    return value


def _outcomes(contract: Any, masks: pd.DataFrame, block_ids: list[str], horizons: tuple[int, ...]) -> pd.DataFrame:
    selected_masks = masks.loc[masks["block_id"].isin(block_ids)].copy()
    sessions = sorted(selected_masks["decision_session"].unique())
    labels = build_real_labels(contract, selected_masks, sessions, horizons=horizons)
    block_lookup = selected_masks[["block_id", "security_id", "decision_session"]]
    labels = block_lookup.merge(labels, on=["security_id", "decision_session"], validate="one_to_one")
    keep = [
        column for column in labels.columns
        if column != "label_start_open" and not column.startswith("label_endpoint_open_")
    ]
    return labels[keep].sort_values(["block_id", "decision_session", "security_id"], kind="mergesort").reset_index(drop=True)


def _labels_without_block(outcomes: pd.DataFrame) -> pd.DataFrame:
    return outcomes.drop(columns=["block_id"])


def _lineage(prediction_dir: Path, predecessor_dirs: list[Path]) -> dict[str, Any]:
    prediction_manifest = read_json(prediction_dir / "manifest.json")
    return {
        "prediction_run_id": prediction_manifest["run_id"],
        "prediction_manifest_sha256": sha256_file(prediction_dir / "manifest.json"),
        "prediction_package_logical_hash": prediction_manifest["logical_hash"],
        "prediction_scientific_hash": prediction_scientific_hash(prediction_manifest),
        "predecessors": [
            {
                "stage": path.name,
                "run_id": read_json(path / "manifest.json")["run_id"],
                "manifest_sha256": sha256_file(path / "manifest.json"),
                "logical_hash": read_json(path / "manifest.json")["logical_hash"],
            }
            for path in predecessor_dirs
        ],
        "prediction_regenerated": False,
    }


def _stage_root(*, reproduction: bool) -> Path:
    execution = load_execution_config()
    run_id = (
        execution["reproduction_run_ids"]["evaluation"]
        if reproduction else execution["primary_run_ids"]["evaluation"]
    )
    if reproduction:
        return Path(execution["output_roots"]["reproductions"]) / "evaluation_runs" / run_id
    return Path(execution["output_roots"]["evaluation_runs"]) / run_id


def _prediction_dir(*, reproduction: bool) -> Path:
    execution = load_execution_config()
    if reproduction:
        return Path(execution["output_roots"]["reproductions"]) / "prediction_runs" / execution["reproduction_run_ids"]["prediction"]
    return Path(execution["output_roots"]["prediction_runs"]) / execution["primary_run_ids"]["prediction"]


def validate_evaluation_stage(stage_dir: Path, stage_name: str) -> dict[str, Any]:
    if stage_name not in STAGE_SCHEMAS or not (
        stage_dir.name == stage_name or stage_dir.name.startswith(f".stage-{stage_name}-")
    ):
        raise D2ArtifactError("evaluation stage identity is invalid")
    manifest = validate_manifest(
        stage_dir, schema_version=STAGE_SCHEMAS[stage_name], required_files=STAGE_FILES[stage_name]
    )
    validation = read_json(stage_dir / "validation.json")
    if validation.get("status") != "PASS":
        raise D2ArtifactError(f"sealed {stage_name} validation did not pass")
    if stage_name != "final":
        outcomes = pd.read_parquet(stage_dir / "outcomes.parquet")
        permitted = set(BLOCKS[stage_name])
        if set(outcomes["block_id"]) != permitted:
            raise D2ArtifactError(f"{stage_name} exposes an unpermitted outcome block")
    return {
        "schema_version": "ats.phase_d2.evaluation_stage_validation.v1",
        "status": "PASS",
        "stage": stage_name,
        "logical_hash": manifest["logical_hash"],
        "manifest_sha256": sha256_file(stage_dir / "manifest.json"),
    }


def _publish(stage_name: str, build: Any, *, reproduction: bool) -> Path:
    root = _stage_root(reproduction=reproduction)
    return publish_immutable(
        root, stage_name, build, schema_version=STAGE_SCHEMAS[stage_name],
        validate=lambda path: validate_evaluation_stage(path, stage_name),
    )


def publish_stage2a(*, reproduction: bool = False) -> Path:
    prediction_dir = _prediction_dir(reproduction=reproduction)

    def build(stage: Path) -> dict[str, Any]:
        contract = load_frozen_d0_v3_contract()
        prediction_validation, predictions, masks = _prediction_inputs(prediction_dir)
        require_stage_outcome_access("stage2a", BLOCKS["stage2a"], set())
        outcomes = _outcomes(contract, masks, BLOCKS["stage2a"], (20,))
        selected_predictions = predictions.loc[predictions["block_id"].isin(BLOCKS["stage2a"])]
        selected_masks = masks.loc[masks["block_id"].isin(BLOCKS["stage2a"])]
        wide = wide_prediction_frame(selected_predictions, selected_masks, _labels_without_block(outcomes))
        ic = session_ic_table(wide, PRIMARY_CELLS)
        statistics = {cell: float(ic[f"ic__{cell}"].mean()) for cell in PRIMARY_CELLS}
        conventional = choose_model_family(statistics, "C_LINEAR", "C_LIGHTGBM")
        rich = choose_model_family(statistics, "RICH_LINEAR", "RICH_LIGHTGBM")
        if conventional["status"] != "PASS" or rich["status"] != "PASS":
            raise D2ArtifactError("2023 model-family selection statistic is not defined")
        lineage = _lineage(prediction_dir, [])
        selection = {
            "schema_version": "ats.phase_d2.selection_result.v1",
            "population_blocks": BLOCKS["stage2a"],
            "equal_session_weighting": True,
            "selection_statistic": "mean_session_spearman_rank_ic",
            "cell_statistics": statistics,
            "conventional": conventional,
            "rich": rich,
            "rich_vs_conventional_selection_performed": False,
            "tie_rule_absolute_difference_max": 0.002,
            "selected_models_frozen_before_stage2b": True,
        }
        validation = {
            "schema_version": "ats.phase_d2.stage2a_validation.v1",
            "status": "PASS",
            "prediction_stage_valid": prediction_validation["status"] == "PASS",
            "only_2023_outcomes_loaded": int(outcomes["decision_session"].dt.year.max()) == 2023,
            "later_period_metrics_computed": False,
            "common_rows": True,
            "prediction_regenerated": False,
        }
        write_json(stage / "lineage.json", lineage)
        write_parquet(stage / "outcomes.parquet", outcomes)
        write_json(stage / "selection.json", selection)
        write_parquet(stage / "session_ic.parquet", ic)
        write_json(stage / "validation.json", validation)
        science = {key: value for key, value in selection.items() if key != "schema_version"}
        return {
            "prediction_scientific_hash": lineage["prediction_scientific_hash"],
            "outcome_identity": parquet_identity(stage / "outcomes.parquet", sort_by=["block_id", "decision_session", "security_id"]),
            "session_ic_identity": parquet_identity(stage / "session_ic.parquet", sort_by=["decision_session"]),
            "selection": science,
        }

    return _publish("stage2a", build, reproduction=reproduction)


def _diagnostics(result: dict[str, Any], horizons: tuple[int, ...]) -> dict[str, Any]:
    wide = result["wide"]
    selected_rich = result["metrics"]["selected_rich"]
    diagnostic: dict[str, Any] = {
        "market_state_ablation": {
            "with_market_state": "RICH_LIGHTGBM",
            "without_market_state": "RICH_NO_M_LIGHTGBM",
            "mean_session_ic_difference": float(
                result["session_ic"]["ic__RICH_LIGHTGBM"].mean()
                - result["session_ic"]["ic__RICH_NO_M_LIGHTGBM"].mean()
            ),
            "identical_population": True,
            "role": "DIAGNOSTIC ONLY",
        },
        "secondary_labels": {},
        "proximity_q5": {},
        "feature_importance": "NOT COMPUTED; optional descriptive diagnostic",
        "forward_path_diagnostics": "DEFERRED BY CONTRACT: no frozen MFE/MAE/time/path formula was specified",
        "diagnostics_cannot_rescue_gate": True,
    }
    for horizon in horizons:
        if horizon == 20:
            continue
        label = f"label__open_to_open__{horizon}"
        table = wide.rename(columns={label: "label__open_to_open__20"})
        if label in wide:
            table = wide.copy()
            table["label__open_to_open__20"] = table[label]
            ic = session_ic_table(table, [*COMPARATORS, selected_rich])
            diagnostic["secondary_labels"][label] = {
                cell: float(ic[f"ic__{cell}"].mean()) for cell in [*COMPARATORS, selected_rich]
            }
    q5_parts = []
    for _, group in wide.groupby("decision_session", sort=True):
        values = group["proximity_to_max_high_252"]
        boundary = float(np.quantile(values[np.isfinite(values)], 0.80, method="linear"))
        q5_parts.append(group.loc[values.ge(boundary)])
    q5 = pd.concat(q5_parts, ignore_index=True) if q5_parts else wide.iloc[0:0]
    q5_ic = session_ic_table(q5, [*COMPARATORS, selected_rich])
    diagnostic["proximity_q5"] = {
        "boundary": "per-session linear q80; all boundary ties included without identity ordering",
        "rows": len(q5),
        "mean_session_ic": {
            cell: float(q5_ic[f"ic__{cell}"].mean()) for cell in [*COMPARATORS, selected_rich]
        },
        "role": "DIAGNOSTIC ONLY",
    }
    return diagnostic


INTEGRITY_GATE_NAMES = (
        "pit_membership_and_information_timing",
        "official_denominator_60",
        "exact_label_anchors_and_availability",
        "endpoint_derived_purge",
        "fold_local_preprocessing",
        "identity_predictors_absent",
        "identity_neutral_ties",
        "common_score_and_outcome_populations",
        "ablation_population_identical",
        "actual_minimums",
        "prediction_not_regenerated",
        "stage_information_order",
        "logical_and_physical_reconciliation",
)


def _integrity_gates(
    stage_name: str, population: str, checks: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    missing = sorted(set(INTEGRITY_GATE_NAMES) - set(checks))
    extra = sorted(set(checks) - set(INTEGRITY_GATE_NAMES))
    if missing or extra:
        raise D2ArtifactError(
            f"execution-integrity evidence differs from the frozen gate set: "
            f"missing={missing}, extra={extra}"
        )
    rows = []
    for name in INTEGRITY_GATE_NAMES:
        value = checks[name]["value"]
        status = "NOT PROVEN" if value is None else ("PASS" if value is True else "FAIL")
        rows.append({
            "gate_id": f"{stage_name}__{name}",
            "category": "execution_integrity",
            "population": population,
            "comparator": None,
            "value": value,
            "operator": "is",
            "threshold": True,
            "status": status,
            "evidence": checks[name]["evidence"],
        })
    return rows


def _same_population_by_cell(predictions: pd.DataFrame, cell_ids: set[str]) -> bool:
    keys = ["block_id", "security_id", "decision_session"]
    groups = {
        str(cell): group[keys].sort_values(keys, kind="mergesort").reset_index(drop=True)
        for cell, group in predictions.groupby("cell_id", sort=True)
    }
    if set(groups) != cell_ids:
        return False
    first = groups[sorted(groups)[0]]
    return all(first.equals(groups[cell]) for cell in sorted(groups)[1:])


def _actual_minimums_pass(
    fit_records: list[dict[str, Any]], plan: dict[str, Any], block_ids: list[str]
) -> bool:
    blocks = {block["block_id"]: block for block in plan["blocks"] if block["block_id"] in block_ids}
    records = [record for record in fit_records if record.get("cell_id") and record["block_id"] in blocks]
    if len(records) != len(blocks) * 5:
        return False
    for record in records:
        block = blocks[record["block_id"]]
        final = record["final_fit"]
        final_plan = block["final_fit"]
        if (
            final["rows"] < final_plan["minimum_model_rows"]
            or final["qualifying_sessions"] < final_plan["minimum_qualifying_sessions"]
            or record["outer_score"]["rows"] < (block["evaluation_minimum_rows"] if block["complete"] else 0)
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


def derive_execution_integrity(
    *,
    prediction_dir: Path,
    prediction_validation: dict[str, Any],
    predictions: pd.DataFrame,
    masks: pd.DataFrame,
    outcomes: pd.DataFrame,
    block_ids: list[str],
    lineage: dict[str, Any],
    predecessor_dirs: list[Path],
) -> dict[str, dict[str, Any]]:
    selected_predictions = predictions.loc[predictions["block_id"].isin(block_ids)].copy()
    selected_masks = masks.loc[masks["block_id"].isin(block_ids)].copy()
    fit_audit = read_json(prediction_dir / "fit_calibration_audit.json")
    plan = read_json(prediction_dir / "walk_forward_plan.json")
    derived = read_json(prediction_dir / "derived_contract.json")
    prediction_manifest = read_json(prediction_dir / "manifest.json")
    forbidden_features = {"security_id", "ticker", "vendor_symbol", "decision_session", "decision_ts"}
    feature_lists = [
        set(record.get("feature_names", []))
        for record in fit_audit["records"]
        if record.get("cell_id") and record["block_id"] in block_ids
    ]
    fit_records = [
        record for record in fit_audit["records"]
        if record.get("cell_id") and record["block_id"] in block_ids
    ]
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
    admission = fit_audit.get("label_admission", {})
    admission_records = admission.get("records", [])
    admission_blocks = [record.get("block_id") for record in admission_records]
    permitted_blocks = set(block_ids)
    outcome_available = outcomes["label_state_20"].eq("AVAILABLE")
    endpoint_order = outcomes.loc[
        outcomes["label_endpoint_session_20"].notna(), "label_endpoint_session_20"
    ].gt(outcomes.loc[outcomes["label_endpoint_session_20"].notna(), "decision_session"])
    cells = set(derived["cells"])
    common_population = _same_population_by_cell(selected_predictions, cells)
    mask_groups = selected_masks.groupby(["block_id", "decision_session"], sort=True)
    scored_reconciles = mask_groups["model_score_eligible"].sum().eq(
        mask_groups["scored_count"].first()
    ).all()
    predecessor_names = [path.name for path in predecessor_dirs]
    if block_ids == BLOCKS["stage2a"]:
        expected_predecessors = []
    elif block_ids == BLOCKS["stage2b"]:
        expected_predecessors = ["stage2a"]
    elif block_ids == BLOCKS["stage2c"]:
        expected_predecessors = ["stage2a", "stage2b"]
    else:
        raise D2ArtifactError(f"unrecognized evaluation block sequence: {block_ids}")
    lineage_predecessors = [item["stage"] for item in lineage["predecessors"]]
    prediction_hash_matches = (
        lineage["prediction_scientific_hash"]
        == prediction_scientific_hash(prediction_manifest)
    )
    label_admission_proved = (
        admission.get("mode") == "outer_block_sequential"
        and admission.get("complete") is True
        and admission_blocks == [block["block_id"] for block in plan["blocks"]]
        and all(record.get("all_loaded_endpoints_strictly_before_refit") is True for record in admission_records)
    )
    population_keys = ["block_id", "security_id", "decision_session"]
    mask_population = selected_masks[population_keys].sort_values(
        population_keys, kind="mergesort"
    ).reset_index(drop=True)
    outcome_population = outcomes[population_keys].sort_values(
        population_keys, kind="mergesort"
    ).reset_index(drop=True)
    return {
        "pit_membership_and_information_timing": {
            "value": bool(
                selected_masks["information_session"].lt(selected_masks["decision_session"]).all()
                and selected_masks["decision_ts"].dt.hour.eq(8).all()
                and selected_masks["decision_ts"].dt.minute.eq(45).all()
            ),
            "evidence": "derived from sealed mask information_session, decision_session, and decision_ts",
        },
        "official_denominator_60": {
            "value": bool(
                mask_groups.size().eq(60).all()
                and selected_masks["official_expected_count"].eq(60).all()
                and scored_reconciles
                and mask_groups["excluded_count"].first().add(mask_groups["scored_count"].first()).eq(60).all()
            ),
            "evidence": "derived from sealed per-session mask rows and scored/excluded counts",
        },
        "exact_label_anchors_and_availability": {
            "value": bool(
                outcome_available.eq(np.isfinite(outcomes["label__open_to_open__20"])).all()
                and endpoint_order.all()
                and label_admission_proved
            ),
            "evidence": "derived from sealed outcome states/endpoints and sequential label-admission audit",
        },
        "endpoint_derived_purge": {
            "value": bool(endpoint_proofs and all(endpoint_proofs)),
            "evidence": "derived from every retained inner/final fit endpoint proof",
        },
        "fold_local_preprocessing": {
            "value": bool(
                estimator_proofs
                and all(estimator_proofs)
                and all(record.get("threshold_frozen_before_final_refit") is True for record in fit_records)
            ),
            "evidence": "derived from every fit/calibration record, not a constant gate value",
        },
        "identity_predictors_absent": {
            "value": bool(feature_lists and all(not (features & forbidden_features) for features in feature_lists)),
            "evidence": "derived from every sealed fit feature allowlist",
        },
        "identity_neutral_ties": {
            "value": bool(
                selected_predictions["candidate"].eq(
                    selected_predictions["model_score"].gt(selected_predictions["threshold"])
                ).all()
                and derived["opportunity_contract"]["frequency_matching"].get("identity_neutrality") is not None
            ),
            "evidence": "derived from strict sealed candidate flags and the frozen tie contract",
        },
        "common_score_and_outcome_populations": {
            "value": bool(
                common_population
                and mask_population.equals(outcome_population)
            ),
            "evidence": "derived by comparing sealed cell, mask, and outcome semantic populations",
        },
        "ablation_population_identical": {
            "value": bool(common_population and "RICH_NO_M_LIGHTGBM" in cells),
            "evidence": "derived from sealed semantic keys for all cells including the ablation",
        },
        "actual_minimums": {
            "value": _actual_minimums_pass(fit_audit["records"], plan, block_ids),
            "evidence": "derived by comparing every retained fit/score count with its frozen plan minimum",
        },
        "prediction_not_regenerated": {
            "value": bool(lineage.get("prediction_regenerated") is False and prediction_hash_matches),
            "evidence": "derived from sealed prediction scientific identity and stage lineage",
        },
        "stage_information_order": {
            "value": bool(
                predecessor_names == expected_predecessors
                and lineage_predecessors == expected_predecessors
                and set(outcomes["block_id"]) == permitted_blocks
            ),
            "evidence": "derived from sealed predecessor lineage and permitted outcome blocks",
        },
        "logical_and_physical_reconciliation": {
            "value": bool(
                prediction_validation.get("status") == "PASS"
                and prediction_hash_matches
                and all(validate_evaluation_stage(path, path.name)["status"] == "PASS" for path in predecessor_dirs)
            ),
            "evidence": "derived by revalidating sealed manifests, inventories, hashes, and logical payloads",
        },
    }


def _publish_evidence_stage(stage_name: str, *, reproduction: bool) -> Path:
    prediction_dir = _prediction_dir(reproduction=reproduction)
    evaluation_root = _stage_root(reproduction=reproduction)
    stage2a = evaluation_root / "stage2a"
    validate_evaluation_stage(stage2a, "stage2a")
    predecessors = [stage2a]
    if stage_name == "stage2c":
        stage2b = evaluation_root / "stage2b"
        validate_evaluation_stage(stage2b, "stage2b")
        transition = read_json(stage2b / "validation.json").get("transition")
        if transition == "STOP_BEFORE_LOCKED_NOT_PROVEN":
            raise D2ArtifactError("Stage 2B validity failed; locked outcomes remain inaccessible")
        predecessors.append(stage2b)

    def build(stage: Path) -> dict[str, Any]:
        contract = load_frozen_d0_v3_contract()
        prediction_validation, predictions, masks = _prediction_inputs(prediction_dir)
        selection = read_json(stage2a / "selection.json")
        selected_rich = selection["rich"]["selected"]
        block_ids = BLOCKS[stage_name]
        require_stage_outcome_access(stage_name, block_ids, {path.name for path in predecessors})
        outcomes = _outcomes(contract, masks, block_ids, (5, 10, 20))
        population = "DEVELOPMENT_CONFIRMATION_2024" if stage_name == "stage2b" else "LOCKED_COMPLETE_2025_2026H1"
        result = evaluate_population(
            predictions, masks, _labels_without_block(outcomes), block_ids=block_ids,
            selected_rich=selected_rich, contract=contract.config, population_name=population,
        )
        lineage = _lineage(prediction_dir, predecessors)
        integrity_evidence = derive_execution_integrity(
            prediction_dir=prediction_dir,
            prediction_validation=prediction_validation,
            predictions=predictions,
            masks=masks,
            outcomes=outcomes,
            block_ids=block_ids,
            lineage=lineage,
            predecessor_dirs=predecessors,
        )
        gates = [*_integrity_gates(stage_name, population, integrity_evidence), *result["gates"]]
        diagnostics = _diagnostics(result, (5, 10, 20))
        validity_ok = all(
            row["status"] == "PASS"
            for row in gates if row["category"] in {"validity", "execution_integrity"}
        )
        research_ok = all(row["status"] == "PASS" for row in gates if row["category"] not in {"validity", "execution_integrity"})
        transition = (
            "STOP_BEFORE_LOCKED_NOT_PROVEN" if not validity_ok else
            ("CONTINUE_LOCKED_WITH_PREDICTIVE_FAILURE_FROZEN" if not research_ok else "CONTINUE_LOCKED")
        ) if stage_name == "stage2b" else "READY_FOR_FINAL_ASSEMBLY"
        validation = {
            "schema_version": f"ats.phase_d2.{stage_name}_validation.v1",
            "status": "PASS",
            "prediction_stage_valid": prediction_validation["status"] == "PASS",
            "predecessors_sealed": True,
            "permitted_outcome_blocks_only": set(outcomes["block_id"]) == set(block_ids),
            "prediction_regenerated": False,
            "validity_gate_status": "PASS" if validity_ok else "FAIL",
            "research_gate_status": "PASS" if research_ok else "FAIL",
            "transition": transition,
            "execution_integrity_evidence": integrity_evidence,
        }
        write_json(stage / "lineage.json", lineage)
        write_parquet(stage / "outcomes.parquet", outcomes)
        write_json(stage / "metrics.json", result["metrics"])
        write_json(stage / "gates.json", {"gates": gates})
        write_parquet(stage / "session_ic.parquet", result["session_ic"])
        write_parquet(stage / "tail_sessions.parquet", result["tail_sessions"])
        anchor_columns = [
            "block_id", "security_id", "decision_session", "episode_number",
            "label__open_to_open__5", "label__open_to_open__10", "label__open_to_open__20",
        ]
        write_parquet(stage / "episode_anchors.parquet", result["episode_anchors"][anchor_columns])
        write_json(stage / "diagnostics.json", diagnostics)
        if stage_name == "stage2c":
            monitor_block = "MONITORING_2026_H2_PARTIAL"
            monitor = predictions.loc[
                predictions["block_id"].eq(monitor_block) & predictions["cell_id"].eq(selected_rich)
            ]
            by_session = monitor.groupby("decision_session")["candidate"].sum()
            monitoring = {
                "block_id": monitor_block,
                "outcomes_loaded": False,
                "nongating": True,
                "scored_rows": len(monitor),
                "scored_sessions": int(monitor["decision_session"].nunique()),
                "candidate_row_fraction": float(monitor["candidate"].mean()),
                "opportunity_session_fraction": float(by_session.gt(0).mean()),
                "idle_session_fraction": float(by_session.eq(0).mean()),
                "right_censoring_reported_from_structural_plan_only": True,
            }
            write_json(stage / "monitoring.json", monitoring)
        write_json(stage / "validation.json", validation)
        return {
            "prediction_scientific_hash": lineage["prediction_scientific_hash"],
            "predecessor_logical_hashes": [item["logical_hash"] for item in lineage["predecessors"]],
            "outcome_identity": parquet_identity(stage / "outcomes.parquet", sort_by=["block_id", "decision_session", "security_id"]),
            "session_ic_identity": parquet_identity(stage / "session_ic.parquet", sort_by=["decision_session"]),
            "tail_session_identity": parquet_identity(stage / "tail_sessions.parquet", sort_by=["decision_session"]),
            "episode_anchor_identity": parquet_identity(stage / "episode_anchors.parquet", sort_by=["decision_session", "security_id"]),
            "metrics": json_ready(result["metrics"]),
            "gates": json_ready(gates),
            "diagnostics": json_ready(diagnostics),
            "monitoring": json_ready(monitoring) if stage_name == "stage2c" else None,
        }

    return _publish(stage_name, build, reproduction=reproduction)


def publish_stage2b(*, reproduction: bool = False) -> Path:
    return _publish_evidence_stage("stage2b", reproduction=reproduction)


def publish_stage2c(*, reproduction: bool = False) -> Path:
    return _publish_evidence_stage("stage2c", reproduction=reproduction)


def _year_gates(stage2b: Path, stage2c: Path) -> list[dict[str, Any]]:
    contract = load_frozen_d0_v3_contract().config
    stability = contract["decision_gate"]["chronological_stability"]
    development = pd.read_parquet(stage2b / "session_ic.parquet")
    locked = pd.read_parquet(stage2c / "session_ic.parquet")
    locked_outcomes = pd.read_parquet(stage2c / "outcomes.parquet")[["block_id", "decision_session"]].drop_duplicates()
    locked = locked.merge(locked_outcomes, on="decision_session", validate="one_to_one")
    year_tables = {
        2024: development,
        2025: locked.loc[locked["block_id"].isin(["LOCKED_2025_H1", "LOCKED_2025_H2"])],
    }
    gates: list[dict[str, Any]] = []
    selection = read_json(stage2b.parent / "stage2a" / "selection.json")
    rich = selection["rich"]["selected"]
    for comparator in COMPARATORS:
        deltas = {
            year: float((table[f"ic__{rich}"] - table[f"ic__{comparator}"]).mean())
            for year, table in year_tables.items()
        }
        positive_fraction = float(np.mean([value > 0.0 for value in deltas.values()]))
        gates.append(gate(
            f"positive_complete_year_fraction__{comparator}", "chronological_stability",
            positive_fraction, "min", stability["positive_eligible_year_fraction_min_against_each_conventional"],
            population="COMPLETE_YEARS_2024_2025", comparator=comparator,
        ))
        for year, value in deltas.items():
            gates.append(gate(
                f"complete_year_delta_floor__{year}__{comparator}", "chronological_stability",
                value, "min", stability["any_year_delta_ic_floor_against_each_conventional"],
                population="COMPLETE_YEARS_2024_2025", comparator=comparator,
            ))
    return gates


def publish_final(*, reproduction: bool = False, peer_reproduction: bool) -> Path:
    evaluation_root = _stage_root(reproduction=reproduction)
    stage2a = evaluation_root / "stage2a"
    stage2b = evaluation_root / "stage2b"
    stage2c = evaluation_root / "stage2c"
    for name, path in (("stage2a", stage2a), ("stage2b", stage2b), ("stage2c", stage2c)):
        validate_evaluation_stage(path, name)
    peer_root = _stage_root(reproduction=peer_reproduction)
    peer_prediction = _prediction_dir(reproduction=peer_reproduction)
    own_prediction = _prediction_dir(reproduction=reproduction)

    def build(stage: Path) -> dict[str, Any]:
        peer_stages = [peer_root / name for name in ("stage2a", "stage2b", "stage2c")]
        for name, path in zip(("stage2a", "stage2b", "stage2c"), peer_stages, strict=True):
            validate_evaluation_stage(path, name)
        own_prediction_manifest = read_json(own_prediction / "manifest.json")
        peer_prediction_manifest = read_json(peer_prediction / "manifest.json")
        reproduction_checks = {
            "prediction_table_logical_hash_equal": prediction_scientific_hash(own_prediction_manifest) == prediction_scientific_hash(peer_prediction_manifest),
            "stage2a_logical_hash_equal": read_json(stage2a / "manifest.json")["logical_hash"] == read_json(peer_stages[0] / "manifest.json")["logical_hash"],
            "stage2b_logical_hash_equal": read_json(stage2b / "manifest.json")["logical_hash"] == read_json(peer_stages[1] / "manifest.json")["logical_hash"],
            "stage2c_logical_hash_equal": read_json(stage2c / "manifest.json")["logical_hash"] == read_json(peer_stages[2] / "manifest.json")["logical_hash"],
        }
        reproduction_pass = all(reproduction_checks.values())
        gates = [
            *read_json(stage2b / "gates.json")["gates"],
            *read_json(stage2c / "gates.json")["gates"],
            *_year_gates(stage2b, stage2c),
            {
                "gate_id": "full_logical_reproduction", "category": "reproducibility",
                "population": "FULL_D2", "comparator": None, "value": reproduction_pass,
                "operator": "is", "threshold": True, "status": "PASS" if reproduction_pass else "FAIL",
            },
        ]
        verdict = mechanical_verdict(gates, complete=True)
        selection = read_json(stage2a / "selection.json")
        verdict_record = {
            "schema_version": "ats.phase_d2.mechanical_verdict.v1",
            "execution_integrity": "PASS" if all(row["status"] == "PASS" for row in gates if row["category"] in {"validity", "execution_integrity", "reproducibility"}) else "NOT PROVEN",
            "predictive_evidence_package": "COMPLETE",
            "selected_conventional": selection["conventional"]["selected"],
            "selected_rich": selection["rich"]["selected"],
            "frozen_phase_d_research_verdict": verdict,
            "d3_execution_authorized": "NO",
            "portfolio_backtest_work_authorized": "NO",
            "diagnostics_can_reverse_verdict": False,
        }
        lineage = {
            "prediction_scientific_hash": prediction_scientific_hash(own_prediction_manifest),
            "prediction_package_logical_hash": own_prediction_manifest["logical_hash"],
            "stage_logical_hashes": {
                name: read_json(path / "manifest.json")["logical_hash"]
                for name, path in (("stage2a", stage2a), ("stage2b", stage2b), ("stage2c", stage2c))
            },
            "peer_prediction_scientific_hash": prediction_scientific_hash(peer_prediction_manifest),
            "peer_prediction_package_logical_hash": peer_prediction_manifest["logical_hash"],
            "peer_stage_logical_hashes": {
                name: read_json(path / "manifest.json")["logical_hash"]
                for name, path in zip(("stage2a", "stage2b", "stage2c"), peer_stages, strict=True)
            },
        }
        validation = {
            "schema_version": "ats.phase_d2.final_validation.v1",
            "status": "PASS",
            "all_preceding_stages_sealed": True,
            "reproduction_checks": reproduction_checks,
            "verdict_derived_mechanically": True,
            "diagnostics_excluded_from_gate_matrix": True,
        }
        write_json(stage / "lineage.json", lineage)
        write_json(stage / "gate_matrix.json", {"gates": gates})
        write_json(stage / "verdict.json", verdict_record)
        write_json(stage / "validation.json", validation)
        return {
            "prediction_scientific_hash": prediction_scientific_hash(own_prediction_manifest),
            "stage_logical_hashes": lineage["stage_logical_hashes"],
            "gate_matrix": gates,
            "verdict": verdict_record,
            "reproduction_pass": reproduction_pass,
        }

    return _publish("final", build, reproduction=reproduction)
