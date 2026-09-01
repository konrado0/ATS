from __future__ import annotations

import copy
import json

import pandas as pd
import pytest

from ats_ml.contracts_v3 import load_frozen_d0_v3_contract
from ats_ml.guard import D1ExecutionGuard, FIXTURE_REGISTRY_V3, synthetic_fixture_context
from ats_ml.walkforward import (
    LockedSequenceFirewall,
    bind_structural_minimums,
    derive_walk_forward_plan,
    expected_locked_sequence_bindings,
    locked_availability_proof_identity,
    synthetic_prequential_proof,
)
from ats_research.hashing import content_hash


def _contract_calendar() -> tuple[object, pd.DatetimeIndex, dict[str, object]]:
    contract = load_frozen_d0_v3_contract(require_publication=False)
    calendar = pd.bdate_range("2018-12-17", "2026-08-18")
    plan = derive_walk_forward_plan(calendar, contract)
    return contract, calendar, plan


def _blocks(plan: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["block_id"]: item for item in plan["blocks"]}  # type: ignore[index]


def _bound_plan() -> dict[str, object]:
    _, calendar, plan = _contract_calendar()
    eligibility = pd.DataFrame({
        "decision_session": calendar,
        "official_expected_count": 60,
        "core_score_eligible_rows": 60,
    })
    return bind_structural_minimums(plan, eligibility)


def test_january_and_july_refit_boundaries_and_month_aligned_windows() -> None:
    _, _, plan = _contract_calendar()
    blocks = _blocks(plan)
    january = blocks["LOCKED_2025_H1"]
    july = blocks["LOCKED_2025_H2"]
    assert january["refit_session"] == "2025-01-01"
    assert january["window_lower_calendar_boundary"] == "2022-01-01"
    assert january["estimator_window_start"] == "2022-01-03"
    assert january["estimator_window_end"] == "2024-12-31"
    assert july["refit_session"] == "2025-07-01"
    assert july["window_lower_calendar_boundary"] == "2022-07-01"
    assert july["estimator_window_start"] == "2022-07-01"
    assert july["estimator_window_end"] == "2025-06-30"


def test_old_and_warmup_observations_never_enter_estimator_rows() -> None:
    _, calendar, plan = _contract_calendar()
    july = _blocks(plan)["LOCKED_2025_H2"]
    window = pd.to_datetime(july["estimator_window_sessions"])
    assert window.min() == pd.Timestamp("2022-07-01")
    assert not (window < pd.Timestamp(july["window_lower_calendar_boundary"])).any()
    assert len(calendar[calendar < window.min()]) > 0, "feature warm-up history exists but is not a model row"
    for inner in july["inner_score_blocks"]:
        assert pd.to_datetime(inner["fit_retained_sessions"]).min() >= window.min()


def test_endpoint_crossing_row_is_purged_then_matures_for_later_refit() -> None:
    _, _, plan = _contract_calendar()
    blocks = _blocks(plan)
    july = blocks["LOCKED_2025_H2"]
    january = blocks["LOCKED_2026_H1"]
    first_purged = pd.Timestamp(july["final_fit"]["availability"]["first_purged_session"])
    assert first_purged not in pd.to_datetime(july["final_fit"]["retained_sessions"])
    assert first_purged in pd.to_datetime(january["final_fit"]["retained_sessions"])


def test_outer_test_rows_never_enter_own_fit_or_threshold_calibration() -> None:
    _, _, plan = _contract_calendar()
    for block in plan["blocks"]:
        evaluation = set(block["evaluation_sessions"])
        assert evaluation.isdisjoint(block["estimator_window_sessions"])
        assert evaluation.isdisjoint(block["final_fit"]["retained_sessions"])
        for inner in block["inner_score_blocks"]:
            assert evaluation.isdisjoint(inner["fit_retained_sessions"])
            assert evaluation.isdisjoint(inner["score_sessions"])


def test_every_inner_score_has_strictly_earlier_endpoint_purged_fit() -> None:
    _, _, plan = _contract_calendar()
    for block in plan["blocks"]:
        assert len(block["inner_score_blocks"]) == 3
        assert [inner["fit_history_months"] for inner in block["inner_score_blocks"]] == [18, 24, 30]
        for inner in block["inner_score_blocks"]:
            assert pd.Timestamp(inner["fit_availability"]["last_retained_session"]) < pd.Timestamp(inner["score_start"])
            assert inner["fit_availability"]["purged_sessions"] > 0


def test_final_refit_uses_every_and_only_label_mature_window_session() -> None:
    _, _, plan = _contract_calendar()
    for block in plan["blocks"]:
        final = set(block["final_fit"]["retained_sessions"])
        window = set(block["estimator_window_sessions"])
        assert final <= window
        assert len(final) == block["final_fit"]["availability"]["retained_sessions"]
        assert len(window - final) == block["final_fit"]["availability"]["purged_sessions"]


def test_evidence_and_complete_year_mapping_excludes_partial_2026() -> None:
    _, _, plan = _contract_calendar()
    mapping = plan["evidence_mapping"]
    assert mapping["complete_decisive_years"] == [2024, 2025]
    assert mapping["positive_year_fraction_denominator"] == 2
    partial = _blocks(plan)["MONITORING_2026_H2_PARTIAL"]
    assert partial["complete"] is False
    assert partial["decisive"] is False
    assert partial["evaluation_end"] == "2026-08-18"
    assert partial["evaluation_right_censored_sessions"] > 0


def test_composed_v3_gates_use_only_explicit_half_year_evidence_mappings() -> None:
    contract = load_frozen_d0_v3_contract(require_publication=False)
    gates = {name: contract.config[name] for name in ("comparison", "evaluation", "decision_gate")}
    rendered = json.dumps(gates, sort_keys=True).lower()
    for obsolete in ("model_selection_2022", "dev_2023", "dev_2024", "locked_2025_2026", "locked historical test"):
        assert obsolete not in rendered
    mappings = gates["decision_gate"]["evidence_population_mappings"]
    assert mappings["model_family_selection"] == ["MODEL_SELECTION_2023_H1", "MODEL_SELECTION_2023_H2"]
    assert mappings["development_stability_blocks"] == ["DEVELOPMENT_2024_H1", "DEVELOPMENT_2024_H2"]
    assert mappings["locked_stability_blocks"] == ["LOCKED_2025_H1", "LOCKED_2025_H2", "LOCKED_2026_H1"]
    assert gates["decision_gate"]["frequency_and_abstention"]["required_separately_in_blocks"] == [
        "DEVELOPMENT_2024_H1", "DEVELOPMENT_2024_H2", "LOCKED_2025_H1", "LOCKED_2025_H2", "LOCKED_2026_H1",
    ]


def test_structural_minimum_binding_fails_closed_on_insufficient_rows() -> None:
    _, calendar, plan = _contract_calendar()
    good = pd.DataFrame({"decision_session": calendar, "official_expected_count": 60, "core_score_eligible_rows": 60})
    assert bind_structural_minimums(plan, good)["minimums_status"] == "PASS"
    bad = good.copy()
    bad["core_score_eligible_rows"] = 0
    with pytest.raises(ValueError, match="infeasible"):
        bind_structural_minimums(plan, bad)


def test_synthetic_four_cell_prequential_proof_recreates_models_and_uses_three_blocks() -> None:
    contract = load_frozen_d0_v3_contract(require_publication=False)
    guard = D1ExecutionGuard(contract, FIXTURE_REGISTRY_V3)
    context = synthetic_fixture_context(contract, guard, "phase-d1-v3-walkforward")
    proof = synthetic_prequential_proof(contract, guard, context)
    assert set(proof["cells"]) == {"C_LINEAR", "C_LIGHTGBM", "RICH_LINEAR", "RICH_LIGHTGBM"}
    assert proof["all_cells_share_inner_score_ledgers"]
    assert proof["test_labels_can_affect_threshold"] is False
    for cell in proof["cells"].values():
        assert cell["inner_stage_count"] == 3
        assert cell["pooled_score_block_count"] == 3
        assert cell["preprocessing_and_estimator_recreated"]
        assert cell["final_fit_uses_all_label_mature_window_rows"]
        assert cell["threshold_frozen_before_final_refit"]
        assert cell["outer_labels_used_for_threshold"] is False
        assert all(stage["fit_strictly_earlier_than_score"] for stage in cell["inner_stages"])


def test_locked_metrics_are_inaccessible_until_ordered_sequence_is_fingerprinted() -> None:
    plan = _bound_plan()
    bindings = expected_locked_sequence_bindings(plan)
    firewall = LockedSequenceFirewall(bindings)
    with pytest.raises(PermissionError, match="inaccessible"):
        firewall.evaluation_permit()
    with pytest.raises(PermissionError, match="order"):
        firewall.record_prediction(
            "LOCKED_2025_H2",
            prediction_hash="a" * 64,
            refit_session=bindings["LOCKED_2025_H2"]["expected_refit_session"],
            availability_proof_hash=bindings["LOCKED_2025_H2"]["availability_proof_hash"],
        )
    first = "LOCKED_2025_H1"
    with pytest.raises(PermissionError, match="refit-date"):
        firewall.record_prediction(
            first,
            prediction_hash=content_hash(first),
            refit_session="2025-01-31",
            availability_proof_hash=bindings[first]["availability_proof_hash"],
        )
    with pytest.raises(PermissionError, match="availability-proof"):
        firewall.record_prediction(
            first,
            prediction_hash=content_hash(first),
            refit_session=bindings[first]["expected_refit_session"],
            availability_proof_hash="b" * 64,
        )
    tampered = copy.deepcopy(_blocks(plan)[first])
    tampered["final_fit"]["retained_sessions"][0] = "1999-01-01"
    with pytest.raises(PermissionError, match="availability-proof"):
        firewall.record_prediction(
            first,
            prediction_hash=content_hash(first),
            refit_session=bindings[first]["expected_refit_session"],
            availability_proof_hash=locked_availability_proof_identity(tampered),
        )
    for block in ("LOCKED_2025_H1", "LOCKED_2025_H2"):
        firewall.record_prediction(
            block,
            prediction_hash=content_hash(block),
            refit_session=bindings[block]["expected_refit_session"],
            availability_proof_hash=bindings[block]["availability_proof_hash"],
        )
    with pytest.raises(PermissionError, match="all three"):
        firewall.fingerprint_complete_sequence()
    final = "LOCKED_2026_H1"
    firewall.record_prediction(
        final,
        prediction_hash=content_hash(final),
        refit_session=bindings[final]["expected_refit_session"],
        availability_proof_hash=bindings[final]["availability_proof_hash"],
    )
    fingerprint = firewall.fingerprint_complete_sequence()
    permit = firewall.evaluation_permit()
    firewall.require_evaluation_permit(permit)
    assert permit.sequence_fingerprint == fingerprint


def test_locked_firewall_rejects_unvalidated_binding_sets() -> None:
    bindings = expected_locked_sequence_bindings(_bound_plan())
    with pytest.raises(ValueError, match="exact frozen block order"):
        LockedSequenceFirewall({key: value for key, value in bindings.items() if key != "LOCKED_2026_H1"})
    reversed_bindings = dict(reversed(list(bindings.items())))
    with pytest.raises(ValueError, match="exact frozen block order"):
        LockedSequenceFirewall(reversed_bindings)


def test_calendar_mismatch_and_missing_required_blocks_fail_closed() -> None:
    contract, calendar, _ = _contract_calendar()
    with pytest.raises(ValueError, match="strictly ordered"):
        derive_walk_forward_plan(calendar.insert(2, calendar[1]), contract)
    with pytest.raises(ValueError, match="no official evaluation sessions"):
        derive_walk_forward_plan(calendar[calendar < pd.Timestamp("2026-07-01")], contract)
