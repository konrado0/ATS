from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "source/python/configs/phase_d0_reference.json"
REGISTRY_PATH = ROOT / "source/python/configs/phase_d0_feature_registry.json"
PLAN_PATH = ROOT / "RESEARCH/PHASE_D0_EXPERIMENT_PLAN.md"
AUDIT_PATH = ROOT / "RESEARCH/PHASE_D0_REQUIREMENT_AUDIT.json"
MANIFEST_PATH = ROOT / "RESEARCH/PHASE_D0_MANIFEST.json"
CHARTER_PATH = ROOT / "RESEARCH/PHASE_D_POOLED_ML_RESEARCH_CHARTER.md"
ROADMAP_PATH = ROOT / "RESEARCH/IMPLEMENTATION_ROADMAP.md"

REQUIRED_FEATURE_FIELDS = {
    "canonical_name",
    "block",
    "formula",
    "raw_dependencies",
    "lookback_sessions",
    "minimum_valid_observations",
    "decision_time_lag_sessions",
    "missing_value_behavior",
    "expected_range",
    "economic_interpretation",
    "code_owner_or_source",
    "fold_local_transformation_required",
    "uses_market_wide_state",
}
EXPECTED_M = [
    "wig_log_return_20",
    "wig_log_return_60",
    "wig_trend_200",
    "wig_trend_acceleration_20_60",
    "wig_drawdown_252",
    "wig_downside_semivolatility_20",
    "wig_volatility_ratio_20_60",
    "top60_breadth_positive_60",
    "top60_breadth_change_10",
    "top60_return_dispersion_20",
    "top60_average_pairwise_correlation_60",
    "top60_positive_leadership_share_20",
]
EXPECTED_CELLS = {
    ("C_LINEAR", "C", "RIDGE"),
    ("C_LIGHTGBM", "C", "LIGHTGBM"),
    ("RICH_LINEAR", "C+P+X+M", "RIDGE"),
    ("RICH_LIGHTGBM", "C+P+X+M", "LIGHTGBM"),
}
ALLOWED_AUDIT_STATUSES = {"PASS", "FAIL", "NOT PROVEN", "DEFERRED BY CONTRACT"}
REQUIRED_DERIVATION_FIELDS = {
    "name",
    "permitted_inputs",
    "formula",
    "rounding",
    "lower_bound",
    "upper_bound",
    "fallback",
    "artifact",
    "freeze_before_predictive_execution",
    "freeze_before_first_real_model_fit_or_prediction",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append({"check": name, "status": "PASS" if condition else "FAIL", "detail": detail})

    required_paths = [CONFIG_PATH, REGISTRY_PATH, PLAN_PATH, AUDIT_PATH, MANIFEST_PATH, CHARTER_PATH, ROADMAP_PATH]
    check("required_files_exist", all(path.is_file() for path in required_paths), ", ".join(str(path) for path in required_paths))
    if not all(path.is_file() for path in required_paths):
        print(json.dumps({"schema_version": "ats.phase_d0.validation.v1", "status": "FAIL", "checks": checks}, indent=2))
        return 1

    config = load_json(CONFIG_PATH)
    registry = load_json(REGISTRY_PATH)
    audit = load_json(AUDIT_PATH)
    manifest = load_json(MANIFEST_PATH)
    features = registry["features"]

    check("config_schema", config.get("schema_version") == "ats.phase_d0.reference.v1", str(config.get("schema_version")))
    check("registry_schema", registry.get("schema_version") == "ats.phase_d0.feature_registry.v1", str(registry.get("schema_version")))
    check("audit_schema", audit.get("schema_version") == "ats.phase_d0.requirement_audit.v1", str(audit.get("schema_version")))
    check("manifest_schema", manifest.get("schema_version") == "ats.phase_d0.manifest.v1", str(manifest.get("schema_version")))
    expected_contract_version = "phase-d0-20260831-v2"
    contract_versions = {
        "config": config.get("contract_version"),
        "registry": registry.get("contract_version"),
        "audit": audit.get("contract_version"),
        "manifest": manifest.get("contract_version"),
    }
    check("contract_version_v2_consistent", set(contract_versions.values()) == {expected_contract_version}, repr(contract_versions))
    amendment = manifest.get("amendment", {})
    parent_commit = "e3c9f7cecd47fb07e37edb246af0848d16944a9a"
    amendment_ok = (
        amendment.get("parent_contract_version") == "phase-d0-20260831-v1"
        and amendment.get("parent_commit") == parent_commit
        and manifest["repository_state"]["starting_git_head"] == parent_commit
        and amendment.get("predictive_result_inspection") is False
        and amendment.get("phase_d1_started") is False
        and len(amendment.get("parent_artifact_sha256", {})) >= 6
    )
    check("v2_amendment_parent_and_boundary", amendment_ok, repr(amendment))

    names = [item["canonical_name"] for item in features]
    formulas = [item["formula"] for item in features]
    blocks = Counter(item["block"] for item in features)
    duplicate_names = sorted(name for name, count in Counter(names).items() if count != 1)
    duplicate_formulas = sorted(formula for formula, count in Counter(formulas).items() if count != 1)
    check("feature_names_unique", not duplicate_names, repr(duplicate_names))
    check("feature_formulas_unique", not duplicate_formulas, repr(duplicate_formulas))
    check("feature_required_fields", all(REQUIRED_FEATURE_FIELDS <= set(item) for item in features), f"features={len(features)}")
    check("feature_blocks_exact", set(blocks) == {"C", "P", "X", "M"}, repr(dict(blocks)))
    caps = config["feature_caps"]
    caps_ok = all(blocks[key] <= caps[key] for key in ["C", "P", "X", "M"]) and len(features) <= caps["total"]
    check("feature_caps", caps_ok, f"counts={dict(blocks)} total={len(features)} caps={caps}")

    registry_by_block = {
        block: [item["canonical_name"] for item in features if item["block"] == block]
        for block in ["C", "P", "X", "M"]
    }
    check("config_registry_block_agreement", registry_by_block == config["feature_blocks"], repr(registry_by_block))
    check("market_state_block_complete", registry_by_block["M"] == EXPECTED_M, repr(registry_by_block["M"]))
    check("C_has_no_market_state", all(not item["uses_market_wide_state"] for item in features if item["block"] == "C"), "all C uses_market_wide_state=false")
    check("M_is_market_state", all(item["uses_market_wide_state"] for item in features if item["block"] == "M"), "all M uses_market_wide_state=true")
    check("ablation_disjoint", not (set(registry_by_block["C"] + registry_by_block["P"] + registry_by_block["X"]) & set(registry_by_block["M"])), "C+P+X and M names do not overlap")

    allowlist = set(names)
    prohibited = {value.lower() for value in config["identity_blindness"]["prohibited_inputs"]}
    check("identity_fields_excluded", not ({name.lower() for name in allowlist} & prohibited), repr(sorted({name.lower() for name in allowlist} & prohibited)))
    check("identity_tests_defined", len(config["identity_blindness"]["positive_tests"]) >= 4 and len(config["identity_blindness"]["negative_tests"]) >= 5, "positive and negative tests present")

    cells = {(item["cell_id"], item["features"], item["model"]) for item in config["comparison"]["cells"]}
    check("four_primary_cells_exact", cells == EXPECTED_CELLS, repr(sorted(cells)))
    check("primary_label_exact", config["target_contract"]["primary"] == "label__open_to_open__20", config["target_contract"]["primary"])
    check("market_ablation_fixed", config["comparison"]["market_state_ablation"] == {
        "model": "LIGHTGBM",
        "without_market_state": "C+P+X",
        "with_market_state": "C+P+X+M",
        "role": "secondary attribution diagnostic only",
        "feature_overlap_between_added_block_and_base": False,
        "cannot_rescue_primary_gate": True,
    }, repr(config["comparison"]["market_state_ablation"]))

    folds = config["chronology"]["folds"]
    chronology_ok = True
    for fold in folds:
        values = [date.fromisoformat(fold[key]) for key in ["fit_start", "fit_end", "calibration_start", "calibration_end", "validation_start", "validation_end"]]
        chronology_ok = chronology_ok and values[0] <= values[1] < values[2] <= values[3] < values[4] <= values[5]
    expected_fold_ids = ["MODEL_SELECTION_2022", "DEV_2023", "DEV_2024", "LOCKED_2025_2026"]
    chronology_ok = chronology_ok and config["chronology"]["random_split"] is False and len(folds) == 4
    chronology_ok = chronology_ok and [fold["fold_id"] for fold in folds] == expected_fold_ids
    chronology_ok = chronology_ok and "selection only" in folds[0]["role"]
    chronology_ok = chronology_ok and all("confirmation" in fold["role"] for fold in folds[1:3])
    check("chronological_folds_unambiguous", chronology_ok, repr(folds))
    check("purge_is_endpoint_derived", "label endpoint timestamp" in config["chronology"]["purge_rule"] and "not subtract a hard-coded" in config["chronology"]["purge_rule"], config["chronology"]["purge_rule"])

    check("first_fit_minimum_feasible", config["observation_contract"]["structural_minimums"]["fit_decision_sessions"] == 230, repr(config["observation_contract"]["structural_minimums"]))
    score_eligibility_text = " ".join(config["observation_contract"]["model_score_base_eligibility"]).lower()
    check("score_mask_is_label_free", "label" not in score_eligibility_text and "future-label availability" in config["comparison"]["common_primary_score_mask"], score_eligibility_text)
    check("score_and_outcome_masks_separate", "common_primary_score_mask" in config["comparison"] and "common_primary_outcome_mask" in config["comparison"] and "label" in config["comparison"]["common_primary_outcome_mask"].lower(), repr(config["comparison"]))
    check("estimands_match_squared_loss", config["models"]["RIDGE"]["objective"] == "squared_error regression" and config["models"]["LIGHTGBM"]["parameters"]["objective"] == "regression_l2", repr(config["models"]))
    selection_text = " ".join(config["comparison"][key] for key in ["reference_selection", "challenger_selection", "selection_period_role", "locked_test_selection_freeze"])
    check("selection_is_separate_from_confirmation", "MODEL_SELECTION_2022" in selection_text and "excluded" in selection_text and "before opening DEV_2023" in selection_text, selection_text)
    rank_protection = config["comparison"]["decisive_rank_ic_protection"]
    check("comparison_claim_requires_both_conventional_cells", all(name in rank_protection for name in ["C_LINEAR", "C_LIGHTGBM"]) and "every mandatory" in rank_protection.lower(), rank_protection)

    derivations = config["structural_derivations"]
    derivation_fields_ok = all(REQUIRED_DERIVATION_FIELDS <= set(item) for item in derivations)
    derivation_freeze_ok = all(item["freeze_before_predictive_execution"] is True and item["freeze_before_first_real_model_fit_or_prediction"] is True for item in derivations)
    forbidden_text = " ".join(config["forbidden_derivation_inputs"]).lower()
    permitted_text = " ".join(" ".join(item["permitted_inputs"]) for item in derivations).lower()
    forbidden_tokens = ["realized forward return", "feature-label association", "rank ic", "tail outcome", "economic performance"]
    check("derivation_rules_complete", derivation_fields_ok and derivation_freeze_ok, f"count={len(derivations)}")
    check("derivations_are_label_blind", not any(token in permitted_text for token in forbidden_tokens) and all(token in forbidden_text for token in forbidden_tokens), permitted_text)

    authorization = config["authorization"]
    check("no_predictive_authorization", all(authorization[key] is False for key in ["phase_d1_fixture_and_structural_implementation", "phase_d1_label_inaccessible_structural_feature_execution", "real_feature_execution", "real_model_fit", "real_prediction", "locked_historical_test_access", "phase_d2"]), repr(authorization))
    open_policy = config["chronology"]["locked_test_open_policy"]
    check("d1_structural_resolution_precedes_first_fit", "registered predictor values through 2024-12-30" in open_policy and "before any D2 model fit or prediction" in open_policy and open_policy.index("phase_d1_structural_resolution.json") < open_policy.index("MODEL_SELECTION_2022"), open_policy)
    check("opportunity_is_not_portfolio", config["opportunity_contract"]["not_trade_construction"] is True and config["opportunity_contract"]["quota"] is None, repr(config["opportunity_contract"]))
    matching = config["opportunity_contract"]["frequency_matching"]
    matching_text = json.dumps(matching, sort_keys=True).lower()
    matching_ok = (
        matching["comparators"] == ["C_LINEAR", "C_LIGHTGBM"]
        and "(k - n_above) / n_equal" in matching["row_weights"]
        and "weight sum equals k exactly" in matching["weighted_statistics"]
        and "combine equal outcome values by summed weight" in matching["weighted_distribution_convention"]
        and "security_id" in matching["identity_neutrality"]
        and "no identity or row-order tie break" in matching["boundary_score"]
        and "security_id ascending" not in matching_text
    )
    check("frequency_matching_is_identity_neutral", matching_ok, repr(matching))
    check("gate_is_conjunctive", config["decision_gate"]["all_dimensions_required"] is True and "cannot" in config["decision_gate"]["failure_rule"], config["decision_gate"]["failure_rule"])
    gate = config["decision_gate"]
    tail = gate["tail_outcome_separation"]
    stability = gate["chronological_stability"]
    check("tail_gate_has_both_conventional_and_ci_controls", tail["rich_minus_each_frequency_matched_conventional_mean_return_min"] == 0.005 and tail["rich_minus_each_conventional_95pct_lower_bound_min_exclusive"] == 0.0 and tail["severe_rate_difference_95pct_upper_bound_max"] == 0.02, repr(tail))
    rank = gate["incremental_rank_information"]
    both_c = ["C_LINEAR", "C_LIGHTGBM"]
    rank_gate_ok = (
        rank["comparators_required_separately"] == both_c
        and rank["development_confirmation_mean_delta_ic_min_against_each_conventional"] == 0.01
        and rank["locked_test_mean_delta_ic_min_against_each_conventional"] == 0.01
        and rank["development_confirmation_paired_95pct_lower_bound_min_exclusive_against_each_conventional"] == 0.0
        and rank["locked_test_paired_95pct_lower_bound_min_exclusive_against_each_conventional"] == 0.0
        and stability["comparators_required_separately"] == both_c
        and stability["confirmation_fold_count"] == 2
        and stability["positive_confirmation_fold_delta_ic_min_count_against_each_conventional"] == 2
        and stability["positive_eligible_year_fraction_min_against_each_conventional"] == 0.75
    )
    check("decisive_rank_gates_use_both_conventional_cells", rank_gate_ok, f"rank={rank!r} stability={stability!r}")
    contributor_rule = config["evaluation"]["metric_definitions"]["top_security_contributors"].lower()
    identity_ties_ok = "security_id ascending" not in json.dumps(config["opportunity_contract"], sort_keys=True).lower() and "include every security at or above" in contributor_rule and "never broken by identity" in contributor_rule
    check("identity_neutral_decisive_ties", identity_ties_ok, contributor_rule)

    statuses = [item["status"] for item in audit["requirements"]]
    check("audit_status_vocabulary", set(statuses) <= ALLOWED_AUDIT_STATUSES, repr(sorted(set(statuses))))
    check("audit_has_no_in_scope_fail", "FAIL" not in statuses, repr(Counter(statuses)))

    no_latest_payload = json.dumps(config, sort_keys=True).lower() + json.dumps(manifest, sort_keys=True).lower()
    check("no_mutable_latest_pointer", "/latest" not in no_latest_payload and "\\latest" not in no_latest_payload and '"latest"' not in no_latest_payload, "config and manifest contain no mutable latest path")

    manifest_entries = manifest["inputs"] + manifest["artifacts"] + manifest["code"]
    manifest_ok = True
    manifest_errors: list[str] = []
    for entry in manifest_entries:
        path = resolve_path(entry["path"])
        if not path.is_file():
            manifest_ok = False
            manifest_errors.append(f"missing:{path}")
            continue
        actual_hash = sha256(path)
        actual_bytes = path.stat().st_size
        if actual_hash != entry["sha256"] or actual_bytes != entry["bytes"]:
            manifest_ok = False
            manifest_errors.append(f"mismatch:{path}:{actual_hash}:{actual_bytes}")
    check("manifest_hashes_and_sizes", manifest_ok, repr(manifest_errors))

    plan = PLAN_PATH.read_text(encoding="utf-8")
    charter = CHARTER_PATH.read_text(encoding="utf-8")
    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")
    plan_markers = [
        "30 model predictors",
        "locked historical test",
        "does not create `ats_ml`",
        "at least 230 decision sessions",
        'objective="regression_l2"',
        "`MODEL_SELECTION_2022` only",
        "at least 75% of calendar years",
        "applied separately to selected-rich-minus-`C_LINEAR` and selected-rich-minus-`C_LIGHTGBM`",
        "every boundary-tied row receives the same fractional weight",
        "before any D2 model fit or prediction",
    ]
    docs_ok = all(marker in plan for marker in plan_markers) and "four disjoint blocks" in charter and "registered predictor" in charter and "through 2024-12-30" in charter and "Phase D0 experiment plan" in roadmap and "registered predictor values through 2024-12-30" in roadmap
    check("plan_charter_roadmap_consistency_markers", docs_ok, "required D0 markers present")

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    print(json.dumps({"schema_version": "ats.phase_d0.validation.v1", "status": status, "checks": checks}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
