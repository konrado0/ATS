from __future__ import annotations

import json
import copy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ats_ml.duplicates import registry_formula_collision_audit, resolve_p_duplicates
from ats_ml.features import compute_market_features, compute_stock_feature_history
from ats_ml.features import FROZEN_EXCLUSION_CODES
from ats_ml.guard import AuthorizationError, ExecutionClass, pinned_real_context
from ats_ml.observations import ObservationContractError, build_observation_matrix
from ats_ml.structural import assert_calendar_provenance, validate_structural_run
from ats_research.hashing import content_hash, sha256_file
from phase_d1_helpers import d1_contract_guard_context, official_membership, stock_bars


def test_observation_matrix_preserves_57_of_60_and_label_free_score_mask() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2023-01-02", periods=270)
    bars = stock_bars(dates, securities=60)
    information = dates[-2]
    for number in range(57, 60):
        bars.loc[bars["security_id"].eq(f"S{number:02d}") & bars["session_date"].eq(information), "price_usable_for_features"] = False
        bars.loc[bars["security_id"].eq(f"S{number:02d}") & bars["session_date"].eq(information), "missing_state"] = "documented_non_trading"
    history = compute_stock_feature_history(bars, dates, contract, guard, context)
    membership = official_membership(bars, [dates[-1]])
    wig = pd.DataFrame({"session_date": dates, "close": 1000.0 * np.exp(0.001 * np.arange(len(dates)))})
    market = compute_market_features(wig, bars, dates, [dates[-1]], guard, context)
    observations = build_observation_matrix(membership, history, market, dates, contract)
    assert len(observations) == 60
    assert observations["official_expected_count"].eq(60).all()
    assert observations["model_eligible_count"].eq(57).all()
    assert observations["scored_count"].eq(57).all()
    assert observations["excluded_count"].eq(3).all()
    assert observations["feature_eligible_count__top60_return_dispersion_20"].eq(57).all()
    assert observations["official_expected_count__top60_return_dispersion_20"].eq(60).all()
    assert observations["excluded_count__top60_return_dispersion_20"].eq(3).all()
    assert observations["outcome_evaluable_count"].isna().all()
    assert "3" in observations["exclusion_reason_counts"].iloc[0]
    assert set(json.loads(observations["exclusion_reason_counts"].iloc[0])) <= FROZEN_EXCLUSION_CODES


def test_observation_denominator_59_61_or_duplicate_identity_fails_closed() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2023-01-02", periods=270)
    bars = stock_bars(dates, securities=60)
    history = compute_stock_feature_history(bars, dates, contract, guard, context)
    wig = pd.DataFrame({"session_date": dates, "close": 1000.0 * np.exp(0.001 * np.arange(len(dates)))})
    market = compute_market_features(wig, bars, dates, [dates[-1]], guard, context)
    membership = official_membership(bars, [dates[-1]])
    with pytest.raises((ValueError, ObservationContractError), match="60"):
        build_observation_matrix(membership.iloc[:-1], history, market, dates, contract)
    duplicate_59 = pd.concat([membership.iloc[:-1], membership.iloc[[0]]], ignore_index=True)
    with pytest.raises((ValueError, ObservationContractError), match="60|duplicate"):
        build_observation_matrix(duplicate_59, history, market, dates, contract)
    duplicate_61 = pd.concat([membership, membership.iloc[[0]]], ignore_index=True)
    with pytest.raises((ValueError, ObservationContractError), match="duplicate"):
        build_observation_matrix(duplicate_61, history, market, dates, contract)


def test_p_duplicate_rule_is_label_blind_deterministic_and_prefers_shorter_lookback() -> None:
    contract, _, _ = d1_contract_guard_context()
    sessions = pd.bdate_range("2023-01-02", periods=200)
    rows = 60 * len(sessions)
    rng = np.random.default_rng(21)
    frame = pd.DataFrame({"decision_session": np.repeat(sessions, 60)})
    for name in contract.feature_blocks["P"]:
        frame[name] = rng.normal(size=rows)
    frame["stock_log_return_60"] = frame["stock_log_return_20"]
    result = resolve_p_duplicates(frame, contract)
    assert result["survivor_count"] == 7
    assert "stock_log_return_20" in result["survivors"]
    assert "stock_log_return_60" not in result["survivors"]
    assert all("label" not in key.lower() for key in result)
    reordered = resolve_p_duplicates(frame.sample(frac=1.0, random_state=2), contract)
    assert reordered["survivors"] == result["survivors"]
    first_metrics = {(item["left"], item["right"]): item for item in result["pair_metrics"]}
    assert first_metrics[("stock_log_return_20", "stock_log_return_60")]["exact_duplicate"]


def _duplicate_boundary_frame(contract: object, seed: int = 91) -> pd.DataFrame:
    sessions = pd.bdate_range("2023-01-02", periods=200)
    rows = len(sessions) * 60
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame({"decision_session": np.repeat(sessions, 60)})
    for name in contract.feature_blocks["P"]:  # type: ignore[attr-defined]
        frame[name] = rng.normal(size=rows)
    return frame


def test_p_duplicate_affine_near_negative_rank_and_preference_boundaries() -> None:
    contract, _, _ = d1_contract_guard_context()
    frame = _duplicate_boundary_frame(contract)
    x = frame["stock_log_return_20"].to_numpy()
    frame["stock_log_return_60"] = 2.0 * x + 3.0
    near = frame["stock_path_efficiency_20"].to_numpy()
    frame["stock_positive_return_share_20"] = near + 0.01 * near**3
    inverse = frame["stock_drawdown_depth_60"].to_numpy()
    frame["stock_recovery_from_low_60"] = -inverse - 0.001 * inverse**3
    result = resolve_p_duplicates(frame, contract)
    metrics = {(item["left"], item["right"]): item for item in result["pair_metrics"]}
    affine = metrics[("stock_log_return_20", "stock_log_return_60")]
    assert affine["algebraic_duplicate"] and not affine["exact_duplicate"]
    near_metric = metrics[("stock_path_efficiency_20", "stock_positive_return_share_20")]
    assert near_metric["near_duplicate"] and not near_metric["algebraic_duplicate"]
    inverse_metric = metrics[("stock_drawdown_depth_60", "stock_recovery_from_low_60")]
    assert inverse_metric["pooled_spearman"] < -0.995
    assert inverse_metric["median_session_percentile_distance"] > 0.01
    assert not inverse_metric["near_duplicate"] and not inverse_metric["algebraic_duplicate"]
    assert "stock_log_return_20" in result["survivors"] and "stock_log_return_60" not in result["survivors"]
    assert "stock_path_efficiency_20" in result["survivors"] and "stock_positive_return_share_20" not in result["survivors"]


def test_p_duplicate_connected_component_uses_frozen_preference_order() -> None:
    contract, _, _ = d1_contract_guard_context()
    frame = _duplicate_boundary_frame(contract, seed=92)
    base = frame["stock_path_efficiency_20"].to_numpy()
    frame["stock_positive_return_share_20"] = base + 0.01 * base**3
    frame["stock_close_location_value_20"] = base + 0.02 * base**3
    result = resolve_p_duplicates(frame, contract)
    assert "stock_close_location_value_20" in result["survivors"]
    assert "stock_path_efficiency_20" not in result["survivors"]
    assert "stock_positive_return_share_20" not in result["survivors"]
    assert result["survivor_count"] == 6


def test_registry_wide_normalized_formula_collision_audit_fails_outside_p() -> None:
    contract, _, _ = d1_contract_guard_context()
    audit = registry_formula_collision_audit(contract)
    assert audit == {
        "registered_feature_count": 30,
        "normalized_formula_count": 30,
        "normalized_formula_collisions": [],
        "outside_p_collision_count": 0,
        "status": "PASS",
    }
    changed_registry = copy.deepcopy(contract.registry)
    changed_registry["features"][-1]["formula"] = changed_registry["features"][0]["formula"]
    forged = replace(contract, registry=changed_registry)
    with pytest.raises(ValueError, match="outside permitted P"):
        registry_formula_collision_audit(forged)


def test_real_structural_context_cannot_compute_non_p_features() -> None:
    contract, guard, _ = d1_contract_guard_context()
    real = pinned_real_context(contract)
    dates = pd.bdate_range("2024-01-02", periods=5)
    bars = stock_bars(dates)
    with pytest.raises((AuthorizationError, ValueError)):
        compute_stock_feature_history(bars, dates, contract, guard, real, blocks=("C", "P"))


def test_calendar_provenance_requires_exact_wig_and_market_state_equality() -> None:
    candidate = pd.bdate_range("2024-01-02", periods=5)
    wig = candidate.insert(0, pd.Timestamp("2023-12-29")).append(pd.DatetimeIndex([pd.Timestamp("2024-01-09")]))
    official = candidate[1:]
    proof = assert_calendar_provenance(candidate, wig, official, official)
    assert proof["status"] == "PASS"
    assert proof["candidate_calendar_count"] == 5
    assert proof["candidate_calendar_hash"] == proof["validated_wig_candidate_range_hash"]
    assert proof["official_membership_calendar_hash"] == proof["market_state_calendar_hash"]

    with pytest.raises(ValueError, match="validated WIG"):
        assert_calendar_provenance(candidate, wig.delete(3), official, official)
    with pytest.raises(ValueError, match="market-state"):
        assert_calendar_provenance(candidate, wig, official, official[:-1])


def test_structural_run_validator_rejects_schema_free_self_consistent_artifact(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    core = {"schema_version": "ats.phase_d1.structural_resolution.v1", "value": 1}
    logical = content_hash(core)
    resolution = {**core, "logical_hash": logical, "run_id": f"phase-d1-structural-{logical[:20]}"}
    resolution_path = run / "structural_resolution.json"
    audit_path = run / "permitted_read_audit.json"
    resolution_path.write_text(json.dumps(resolution, sort_keys=True), encoding="utf-8")
    audit_path.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    manifest = {
        "schema_version": "ats.phase_d1.structural_run_manifest.v1",
        "run_id": resolution["run_id"],
        "logical_hash": logical,
        "files": {"structural_resolution.json": sha256_file(resolution_path), "permitted_read_audit.json": sha256_file(audit_path)},
    }
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_structural_run(run)
