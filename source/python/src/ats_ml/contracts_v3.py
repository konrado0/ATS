from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ats_ml.contracts import (
    REPOSITORY_ROOT,
    ContractError,
    FrozenD0Contract,
    load_frozen_d0_contract,
)
from ats_research.hashing import sha256_file


D0_V3_CONFIG = REPOSITORY_ROOT / "source/python/configs/phase_d0_reference_v3.json"
D0_V3_PLAN = REPOSITORY_ROOT / "RESEARCH/PHASE_D0_EXPERIMENT_PLAN_v3.md"
D0_V3_MANIFEST = REPOSITORY_ROOT / "RESEARCH/PHASE_D0_MANIFEST_v3.json"
EXPECTED_V3_CONTRACT_VERSION = "phase-d0-20260901-v3"
EXPECTED_D1_V2_CHECKPOINT = "724971466dacfba05ff0fa7e92cd68c4628008c7"
OBSOLETE_V2_EVIDENCE_REFERENCES = (
    "MODEL_SELECTION_2022",
    "DEV_2023",
    "DEV_2024",
    "LOCKED_2025_2026",
    "locked historical test",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read Phase D0 v3 JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"Phase D0 v3 JSON root must be an object: {path}")
    return value


def _population_mappings(amendment: dict[str, Any]) -> dict[str, list[str]]:
    mapping = amendment["evidence_mapping"]
    return {
        "model_family_selection": list(mapping["model_family_selection"]),
        "development_confirmation_pooled": list(mapping["development_confirmation_pooled"]),
        "development_stability_blocks": list(mapping["development_stability_blocks"]),
        "locked_evidence_pooled": list(mapping["locked_evidence_pooled"]),
        "locked_stability_blocks": list(mapping["locked_stability_blocks"]),
    }


def _compose_comparison_v3(parent: dict[str, Any], amendment: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(parent)
    populations = _population_mappings(amendment)
    selection = populations["model_family_selection"]
    result.pop("same_folds", None)
    result["same_refit_blocks"] = True
    result["evidence_population_mappings"] = populations
    result["reference_selection"] = (
        f"Using only the equal-session-weighted pooled blocks {selection}, choose the conventional cell with higher "
        "mean rank IC; if the absolute difference is <=0.002 choose C_LINEAR. This selected reference is the named "
        "reporting reference only and does not exempt the other fixed conventional cell from any decisive gate."
    )
    result["challenger_selection"] = (
        f"Using only the equal-session-weighted pooled blocks {selection}, choose the rich cell with higher mean rank "
        "IC; if the absolute difference is <=0.002 choose RICH_LINEAR."
    )
    result["selection_period_role"] = (
        f"The blocks {selection} select model families only and are excluded from development-confirmation and locked "
        "evidence thresholds and confidence intervals."
    )
    result["decisive_rank_ic_protection"] = (
        f"Every mandatory incremental rank-IC, block-stability and leave-security-out rank gate for the {selection}-"
        "selected rich challenger must pass separately against C_LINEAR and C_LIGHTGBM."
    )
    result["strongest_conventional_tail_protection"] = (
        "Every mandatory rich tail and severe-outcome comparison in the explicit development and locked half-year "
        "mappings must pass separately against same-session frequency-matched C_LINEAR and C_LIGHTGBM."
    )
    result.pop("locked_test_selection_freeze", None)
    result["locked_sequence_selection_freeze"] = (
        f"Record the selected reference and challenger after {selection} and before opening any block in "
        f"{populations['development_confirmation_pooled']} or {populations['locked_evidence_pooled']}. Nonselected "
        "cells remain reported but cannot replace the frozen pair."
    )
    return result


def _compose_evaluation_v3(parent: dict[str, Any], amendment: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(parent)
    populations = _population_mappings(amendment)
    result["evidence_population_mappings"] = populations
    result["required_metrics"] = [
        "half_year_block_and_complete_year_stability" if value == "fold_and_year_stability" else value
        for value in result["required_metrics"]
    ]
    definitions = result["metric_definitions"]
    definitions["rich_minus_each_conventional_rank_ic"] = (
        f"For the challenger selected only on {populations['model_family_selection']}, subtract the named C_LINEAR or "
        "C_LIGHTGBM session IC on identical common outcome rows; aggregate with equal session weight and apply every "
        "decisive pooled and half-year-block gate separately to both named contrasts."
    )
    definitions["eligible_year"] = (
        f"Calendar year with at least 120 outcome-evaluable scored decision sessions; selection blocks "
        f"{populations['model_family_selection']} are excluded. Complete decisive years are "
        f"{amendment['evidence_mapping']['complete_decisive_years']}."
    )
    return result


def _rename_key(mapping: dict[str, Any], old: str, new: str) -> None:
    mapping[new] = mapping.pop(old)


def _compose_decision_gate_v3(parent: dict[str, Any], amendment: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(parent)
    populations = _population_mappings(amendment)
    pooled = {
        "development_confirmation_pooled": populations["development_confirmation_pooled"],
        "locked_evidence_pooled": populations["locked_evidence_pooled"],
    }
    result["evidence_population_mappings"] = populations
    result["validity"].pop("outcome_evaluability_required_in", None)
    result["validity"]["outcome_evaluability_required_population_mappings"] = pooled

    incremental = result["incremental_rank_information"]
    incremental["challenger"] = f"rich cell selected only on {populations['model_family_selection']}"
    _rename_key(incremental, "locked_test_mean_delta_ic_min_against_each_conventional", "locked_evidence_mean_delta_ic_min_against_each_conventional")
    _rename_key(incremental, "locked_test_paired_95pct_lower_bound_min_exclusive_against_each_conventional", "locked_evidence_paired_95pct_lower_bound_min_exclusive_against_each_conventional")
    incremental.pop("selection_period_excluded", None)
    incremental["selection_blocks_excluded"] = populations["model_family_selection"]
    incremental["required_population_mappings"] = pooled

    tail = result["tail_outcome_separation"]
    tail.pop("required_in", None)
    tail["required_population_mappings"] = pooled

    stability = result["chronological_stability"]
    _rename_key(stability, "positive_confirmation_fold_delta_ic_min_count_against_each_conventional", "positive_development_block_delta_ic_min_count_against_each_conventional")
    _rename_key(stability, "confirmation_fold_count", "development_block_count")
    _rename_key(stability, "each_confirmation_fold_delta_ic_min_against_each_conventional", "each_development_block_delta_ic_min_against_each_conventional")
    _rename_key(stability, "leave_one_confirmation_fold_out_delta_ic_min_against_each_conventional", "leave_one_development_block_out_delta_ic_min_against_each_conventional")
    _rename_key(stability, "locked_chronological_half_delta_ic_floor_against_each_conventional", "each_locked_block_delta_ic_floor_against_each_conventional")
    _rename_key(stability, "locked_chronological_half_rich_minus_each_conventional_tail_floor", "each_locked_block_rich_minus_each_conventional_tail_floor")
    stability["development_blocks"] = populations["development_stability_blocks"]
    stability["locked_blocks"] = populations["locked_stability_blocks"]
    stability["complete_decisive_years"] = list(amendment["evidence_mapping"]["complete_decisive_years"])

    opportunity = result["opportunity_evidence"]
    _rename_key(opportunity, "locked_effective_security_episodes_min", "locked_evidence_effective_security_episodes_min")
    _rename_key(opportunity, "distinct_opportunity_sessions_locked_min", "distinct_opportunity_sessions_locked_evidence_min")
    opportunity.pop("required_populations", None)
    opportunity["required_population_mappings"] = pooled

    frequency = result["frequency_and_abstention"]
    frequency.pop("required_separately_in", None)
    frequency["required_separately_in_blocks"] = populations["development_stability_blocks"] + populations["locked_stability_blocks"]

    concentration = result["concentration"]
    concentration.pop("required_separately_in", None)
    concentration["required_population_mappings"] = pooled
    result["partial_monitoring_excluded_from_every_decisive_gate"] = amendment["evidence_mapping"]["partial_monitoring_excluded_from_every_decisive_gate"]
    return result


def _assert_no_obsolete_v2_gate_references(config: dict[str, Any]) -> None:
    rendered = json.dumps(
        {name: config[name] for name in ("comparison", "evaluation", "decision_gate")},
        sort_keys=True,
    )
    stale = [value for value in OBSOLETE_V2_EVIDENCE_REFERENCES if value.lower() in rendered.lower()]
    if stale:
        raise ContractError(f"Phase D0 v3 composed gates retain obsolete v2 evidence references: {stale}")


def load_frozen_d0_v3_contract(*, require_publication: bool = True) -> FrozenD0Contract:
    """Load v3 as a narrow amendment over immutable D0 v2 scientific anchors."""

    parent = load_frozen_d0_contract()
    amendment = _read_json(D0_V3_CONFIG)
    if amendment.get("schema_version") != "ats.phase_d0.reference.v3":
        raise ContractError("unexpected Phase D0 v3 reference schema")
    if amendment.get("contract_version") != EXPECTED_V3_CONTRACT_VERSION:
        raise ContractError("unexpected Phase D0 v3 contract version")
    parents = amendment.get("parents", {})
    if parents.get("phase_d0_contract_version") != parent.config["contract_version"]:
        raise ContractError("Phase D0 v3 does not bind the accepted D0 v2 parent")
    if parents.get("phase_d1_checkpoint") != EXPECTED_D1_V2_CHECKPOINT:
        raise ContractError("Phase D0 v3 does not bind the accepted D1 v2 checkpoint")
    if amendment.get("final_design_amendment_before_d2") is not True:
        raise ContractError("Phase D0 v3 is not declared final before D2")
    authorization = amendment.get("authorization", {})
    forbidden = ("real_label_values", "real_model_fit", "real_prediction_or_score", "real_predictive_metrics_or_outcomes", "phase_d2")
    if any(authorization.get(name) is not False for name in forbidden):
        raise ContractError("Phase D0 v3 expands authorization into predictive execution")

    config = copy.deepcopy(parent.config)
    config["schema_version"] = "ats.phase_d0.reference.composed.v3"
    config["contract_version"] = EXPECTED_V3_CONTRACT_VERSION
    config["v3_amendment"] = amendment
    config["chronology"] = {
        "split_unit": "whole decision_session",
        "random_split": False,
        "outer_walk_forward": amendment["outer_walk_forward"],
        "inner_prequential_calibration": amendment["inner_prequential_calibration"],
        "evidence_blocks": amendment["evidence_blocks"],
        "evidence_mapping": amendment["evidence_mapping"],
        "locked_sequential_generation": amendment["locked_sequential_generation"],
    }
    config["observation_contract"]["structural_minimums_v3"] = amendment["minimums"]
    config["authorization"] = amendment["authorization"]
    config["opportunity_contract"]["calibration_population"] = amendment["inner_prequential_calibration"]["pooling"]
    config["opportunity_contract"]["threshold"] = amendment["unchanged_parent_contract"]["opportunity_threshold_formula"]
    config["comparison"] = _compose_comparison_v3(parent.config["comparison"], amendment)
    config["evaluation"] = _compose_evaluation_v3(parent.config["evaluation"], amendment)
    config["decision_gate"] = _compose_decision_gate_v3(parent.config["decision_gate"], amendment)
    _assert_no_obsolete_v2_gate_references(config)

    hashes = dict(parent.hashes)
    hashes["source/python/configs/phase_d0_reference_v3.json"] = sha256_file(D0_V3_CONFIG)
    if require_publication:
        for path in (D0_V3_PLAN, D0_V3_MANIFEST):
            if not path.is_file():
                raise ContractError(f"Phase D0 v3 publication is incomplete: {path}")
        hashes["RESEARCH/PHASE_D0_EXPERIMENT_PLAN_v3.md"] = sha256_file(D0_V3_PLAN)
        hashes["RESEARCH/PHASE_D0_MANIFEST_v3.json"] = sha256_file(D0_V3_MANIFEST)
        manifest = _read_json(D0_V3_MANIFEST)
    else:
        manifest = {"contract_version": EXPECTED_V3_CONTRACT_VERSION, "status": "DRAFT"}
    return FrozenD0Contract(config=config, registry=parent.registry, manifest=manifest, hashes=hashes)
