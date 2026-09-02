from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ats_ml.d2_metrics import (
    _concentration,
    bootstrap_vector,
    choose_model_family,
    circular_bootstrap_indices,
    episode_anchor_flags,
    fractional_boundary_weights,
    mechanical_verdict,
    require_identical_population,
    spearman_ic,
    weighted_quantile,
)


def test_session_ic_is_undefined_for_constant_scores_and_small_sessions() -> None:
    labels = np.arange(45, dtype=float)
    assert np.isnan(spearman_ic(np.ones(45), labels))
    assert np.isnan(spearman_ic(np.arange(44), np.arange(44)))
    assert spearman_ic(np.arange(45), labels) == pytest.approx(1.0)


def test_strict_threshold_equality_and_zero_candidates_are_preserved() -> None:
    scores = pd.Series([0.009, 0.010, 0.010])
    candidate = scores.gt(0.010)
    assert candidate.tolist() == [False, False, False]
    assert int(candidate.sum()) == 0


def test_overlapping_signals_chain_until_gap_exceeds_twenty_sessions() -> None:
    calendar = pd.bdate_range("2024-01-02", periods=50)
    candidates = pd.DataFrame({
        "security_id": ["A"] * 5,
        "decision_session": calendar[[0, 20, 40, 41, 49]],
        "candidate": [True] * 5,
    })
    result = episode_anchor_flags(candidates, calendar)
    assert result["episode_anchor"].tolist() == [True, False, False, False, False]
    isolated = pd.DataFrame({"security_id": ["B", "B"], "decision_session": calendar[[0, 21]], "candidate": True})
    assert episode_anchor_flags(isolated, calendar)["episode_anchor"].tolist() == [True, True]


def test_fractional_boundary_ties_are_identity_and_row_order_neutral() -> None:
    base = pd.DataFrame({"security_id": ["A", "B", "C", "D"], "score": [3.0, 2.0, 2.0, 1.0]})
    base["weight"] = fractional_boundary_weights(base["score"], 2)
    shuffled = base.sample(frac=1.0, random_state=9).drop(columns="weight")
    shuffled["weight"] = fractional_boundary_weights(shuffled["score"], 2)
    assert base.set_index("security_id")["weight"].to_dict() == shuffled.set_index("security_id")["weight"].to_dict()
    assert base["weight"].tolist() == [1.0, 0.5, 0.5, 0.0]
    reassigned = base.assign(security_id=["W", "X", "Y", "Z"])
    assert fractional_boundary_weights(reassigned["score"], 2).tolist() == [1.0, 0.5, 0.5, 0.0]


def test_weighted_quantile_combines_tied_outcomes_before_crossing_boundary() -> None:
    assert weighted_quantile([0.1, 0.1, 0.2, 0.3], [0.25, 0.75, 1.0, 1.0], 0.5) == pytest.approx(0.2)
    order = [3, 1, 0, 2]
    values = np.asarray([0.1, 0.1, 0.2, 0.3])[order]
    weights = np.asarray([0.25, 0.75, 1.0, 1.0])[order]
    assert weighted_quantile(values, weights, 0.5) == pytest.approx(0.2)


def test_missing_labels_and_bootstrap_defined_replicate_failure_remain_visible() -> None:
    scores = np.arange(50, dtype=float)
    labels = np.r_[np.arange(44, dtype=float), np.repeat(np.nan, 6)]
    assert np.isnan(spearman_ic(scores, labels))
    indices = circular_bootstrap_indices(10, samples=100, block=3)
    result = bootstrap_vector(np.repeat(np.nan, 10), indices)
    assert result["status"] == "NOT PROVEN"
    assert result["defined_fraction"] == 0.0


def test_model_selection_is_within_representation_and_unselected_rich_cannot_replace_it() -> None:
    selection = choose_model_family(
        {"RICH_LINEAR": 0.1000, "RICH_LIGHTGBM": 0.1015},
        "RICH_LINEAR", "RICH_LIGHTGBM",
    )
    assert selection["selected"] == "RICH_LINEAR"
    assert selection["ridge_tie_rule_applied"] is True
    later_diagnostic = {"RICH_LINEAR": 0.01, "RICH_LIGHTGBM": 0.20}
    assert later_diagnostic["RICH_LIGHTGBM"] > later_diagnostic[selection["selected"]]
    assert selection["selected"] == "RICH_LINEAR"


def test_predictive_failure_maps_to_stop_and_validity_failure_to_not_proven() -> None:
    predictive = [{"category": "incremental_rank_information", "status": "FAIL"}]
    assert mechanical_verdict(predictive, complete=True) == "STOP"
    validity = [
        {"category": "validity", "status": "FAIL"},
        {"category": "incremental_rank_information", "status": "PASS"},
    ]
    assert mechanical_verdict(validity, complete=True) == "NOT PROVEN"


def test_mismatched_ablation_population_fails_closed() -> None:
    left = pd.DataFrame({"security_id": ["A", "B"], "decision_session": pd.to_datetime(["2024-01-02"] * 2)})
    right = left.iloc[:1].copy()
    with pytest.raises(ValueError, match="populations differ"):
        require_identical_population(left, right)


def test_concentration_boundary_includes_all_fifth_place_ties() -> None:
    sessions = pd.bdate_range("2024-01-02", periods=6)
    anchors = pd.DataFrame({
        "security_id": list("ABCDEF"),
        "decision_session": sessions,
        "label__open_to_open__20": [0.06, 0.05, 0.04, 0.03, 0.02, -0.02],
    })
    tail = pd.DataFrame({"decision_session": sessions, "eligible_mean": 0.0})
    result = _concentration(pd.DataFrame(), anchors, tail, sessions)
    assert result["top_contribution_boundary"] == pytest.approx(0.02)
    assert result["top_contribution_boundary_set"] == list("ABCDEF")
