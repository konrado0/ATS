from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ats_ml.guard import AuthorizationError, Operation, pinned_real_context
from ats_ml.matrices import (
    MatrixContractError,
    ModelMatrix,
    build_four_cell_matrices,
    cell_feature_allowlists,
    load_authorized_model_fixture,
)
from ats_ml.models import LIGHTGBM_PARAMETERS, RIDGE_PARAMETERS, LightGBMAdapter, ModelScores, RidgeAdapter
from ats_ml.opportunity import CalibrationThreshold, calibration_threshold, fractional_boundary_weights, qualifies, weighted_mean, weighted_rate
from phase_d1_helpers import d1_contract_guard_context


def _synthetic_matrix(rows: int, features: tuple[str, ...], seed: int = 4) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=(rows, len(features)))
    return pd.DataFrame(values, columns=features), values


def test_four_frozen_cells_share_mask_rows_and_exact_allowlists() -> None:
    contract, guard, context = d1_contract_guard_context()
    rng = np.random.default_rng(5)
    rows = 120
    observations = pd.DataFrame({
        "decision_session": np.repeat(pd.bdate_range("2024-01-02", periods=2), 60),
        "security_id": [f"S{i:02d}" for _ in range(2) for i in range(60)],
        "model_score_eligible": [True] * 117 + [False] * 3,
    })
    for name in contract.registry_order:
        observations[name] = rng.normal(size=rows)
    matrices = build_four_cell_matrices(observations, contract, context, guard)
    expected = cell_feature_allowlists(contract)
    assert set(matrices) == {"C_LINEAR", "C_LIGHTGBM", "RICH_LINEAR", "RICH_LIGHTGBM"}
    assert {len(value.frame) for value in matrices.values()} == {117}
    assert {value.provenance_hash for value in matrices.values()}.__len__() == 1
    assert {key: value.feature_names for key, value in matrices.items()} == expected


def test_four_cell_numeric_matrices_ignore_identity_reassignment_and_row_order() -> None:
    contract, guard, context = d1_contract_guard_context()
    rows = 120
    rng = np.random.default_rng(52)
    observations = pd.DataFrame({
        "decision_session": np.repeat(pd.bdate_range("2024-01-02", periods=2), 60),
        "security_id": [f"S{i:02d}" for _ in range(2) for i in range(60)],
        "model_score_eligible": True,
        "ticker": [f"T{i:02d}" for _ in range(2) for i in range(60)],
        "selected_source": "fixture-a",
    })
    for name in contract.registry_order:
        observations[name] = rng.normal(size=rows)
    first = build_four_cell_matrices(observations, contract, context, guard)
    renamed = observations.sample(frac=1.0, random_state=8).reset_index(drop=True)
    renamed["security_id"] = [f"RENAMED{i:03d}" for i in range(rows)]
    renamed["ticker"] = "CHANGED"
    renamed["selected_source"] = "fixture-b"
    second = build_four_cell_matrices(renamed, contract, context, guard)
    for cell_id in first:
        assert first[cell_id].provenance_hash == second[cell_id].provenance_hash
        assert np.array_equal(first[cell_id].frame, second[cell_id].frame)


def test_ridge_exact_fold_local_preprocessing_and_determinism() -> None:
    contract, guard, _ = d1_contract_guard_context()
    names = contract.feature_blocks["C"]
    matrix, target = load_authorized_model_fixture("phase-d1-fixture-linear-train", names, contract, guard)
    assert target is not None
    frame = matrix.frame
    first = RidgeAdapter(guard).fit(matrix, target)
    second = RidgeAdapter(guard).fit(matrix, target)
    assert np.array_equal(first.predict(matrix).values, second.predict(matrix).values)
    assert np.corrcoef(first.predict(matrix).values, target.values)[0, 1] > 0.99
    imputer = first.estimator.named_steps["imputer"]
    scaler = first.estimator.named_steps["scaler"]
    assert imputer.add_indicator is False
    assert np.isclose(imputer.statistics_[0], np.nanmedian(frame.iloc[:, 0]))
    transformed = imputer.transform(frame)
    assert np.allclose(scaler.mean_, transformed.mean(axis=0))
    assert first.estimator.named_steps["ridge"].get_params()["solver"] == RIDGE_PARAMETERS["solver"]
    evaluation_matrix, evaluation_target = load_authorized_model_fixture("phase-d1-fixture-linear-eval", names, contract, guard)
    assert evaluation_target is None
    before = imputer.statistics_.copy(), scaler.mean_.copy(), scaler.scale_.copy()
    first.predict(evaluation_matrix)
    after = imputer.statistics_, scaler.mean_, scaler.scale_
    assert all(np.array_equal(left, right) for left, right in zip(before, after, strict=True))


def test_lightgbm_native_nan_fixed_parameters_and_nonlinear_plumbing() -> None:
    contract, guard, _ = d1_contract_guard_context()
    names = contract.feature_blocks["C"]
    matrix, target = load_authorized_model_fixture("phase-d1-fixture-nonlinear-train", names, contract, guard)
    assert target is not None
    first = LightGBMAdapter(guard).fit(matrix, target)
    second = LightGBMAdapter(guard).fit(matrix, target)
    assert np.array_equal(first.predict(matrix).values, second.predict(matrix).values)
    params = first.estimator.get_params()
    for name, value in LIGHTGBM_PARAMETERS.items():
        assert params[name] == value
    predictions = first.predict(matrix).values
    assert np.std(predictions) > 0.0
    assert np.mean((predictions - target.values) ** 2) < np.var(target.values)


def test_no_signal_constant_target_and_all_missing_feature_failure() -> None:
    contract, guard, _ = d1_contract_guard_context()
    names = contract.feature_blocks["C"]
    matrix, target = load_authorized_model_fixture("phase-d1-fixture-no-signal-train", names, contract, guard)
    assert target is not None
    for adapter in (RidgeAdapter(guard), LightGBMAdapter(guard)):
        adapter.fit(matrix, target)
        assert np.allclose(adapter.predict(matrix).values, 0.0, atol=1e-12)
    broken_matrix, broken_target = load_authorized_model_fixture("phase-d1-fixture-all-missing-train", names, contract, guard)
    assert broken_target is not None
    with pytest.raises(MatrixContractError, match="no finite value"):
        RidgeAdapter(guard).fit(broken_matrix, broken_target)
    with pytest.raises(MatrixContractError, match="no finite value"):
        LightGBMAdapter(guard).fit(broken_matrix, broken_target)


def test_real_fit_predict_rejected_even_with_fixture_like_metadata() -> None:
    contract, guard, _ = d1_contract_guard_context()
    names = contract.feature_blocks["C"]
    real = pinned_real_context(contract)
    with pytest.raises(AuthorizationError):
        guard.require(Operation.FIT, real)
    frame, _ = _synthetic_matrix(10, names)
    with pytest.raises(MatrixContractError, match="sealed"):
        RidgeAdapter(guard).fit(frame, np.zeros(len(frame)))  # type: ignore[arg-type]


def test_arbitrary_or_four_cell_matrix_cannot_reach_model_adapter() -> None:
    contract, guard, context = d1_contract_guard_context()
    names = contract.feature_blocks["C"]
    frame, _ = _synthetic_matrix(10, names)
    with pytest.raises(MatrixContractError, match="factory"):
        ModelMatrix(frame, context, names, "forged", data_hash="0" * 64, fixture_id="phase-d1-fixture-linear-train", suite_id="linear", fixture_registry_sha256=guard.fixture_registry_sha256, _token=object())
    observations = pd.DataFrame({
        "decision_session": np.repeat(pd.Timestamp("2024-01-02"), 60),
        "security_id": [f"S{i:02d}" for i in range(60)],
        "model_score_eligible": True,
    })
    rng = np.random.default_rng(77)
    for name in contract.registry_order:
        observations[name] = rng.normal(size=60)
    unapproved = build_four_cell_matrices(observations, contract, context, guard)["C_LINEAR"]
    _, target = load_authorized_model_fixture("phase-d1-fixture-linear-train", names, contract, guard)
    assert target is not None
    with pytest.raises(MatrixContractError, match="fixture registry"):
        RidgeAdapter(guard).fit(unapproved, target)
    authorized, authorized_target = load_authorized_model_fixture("phase-d1-fixture-linear-train", names, contract, guard)
    assert authorized_target is not None
    leaked_copy = authorized.frame
    leaked_copy.iloc[:, 0] = np.arange(len(leaked_copy), dtype=float)  # encoded identity under a registered name
    assert not np.array_equal(leaked_copy, authorized.frame, equal_nan=True)
    original_scores = RidgeAdapter(guard).fit(authorized, authorized_target).predict(authorized).values
    repeated_scores = RidgeAdapter(guard).fit(authorized, authorized_target).predict(authorized).values
    assert np.array_equal(original_scores, repeated_scores)


def test_unfitted_manual_state_and_estimator_replacement_cannot_mint_scores() -> None:
    contract, guard, _ = d1_contract_guard_context()
    names = contract.feature_blocks["C"]
    train, target = load_authorized_model_fixture("phase-d1-fixture-linear-train", names, contract, guard)
    evaluation, _ = load_authorized_model_fixture("phase-d1-fixture-linear-eval", names, contract, guard)
    assert target is not None

    class DummyEstimator:
        def predict(self, frame: pd.DataFrame) -> np.ndarray:
            return np.full(len(frame), 0.42)

    unfitted = RidgeAdapter(guard)
    unfitted.estimator = DummyEstimator()
    with pytest.raises(MatrixContractError, match="sealed authorized fit state"):
        unfitted.predict(evaluation)
    fitted = RidgeAdapter(guard).fit(train, target)
    fitted.estimator = DummyEstimator()
    with pytest.raises(MatrixContractError, match="replaced or mutated"):
        fitted.predict(evaluation)
    with pytest.raises(MatrixContractError, match="fitted authorized"):
        ModelScores(np.full(len(evaluation.frame), 0.42), evaluation, "RidgeAdapter", "forged", _token=object())


def test_calibration_threshold_is_strict_label_free_and_zero_candidate_valid() -> None:
    contract, guard, _ = d1_contract_guard_context()
    names = contract.feature_blocks["C"]
    train, target = load_authorized_model_fixture("phase-d1-fixture-linear-train", names, contract, guard)
    evaluation, _ = load_authorized_model_fixture("phase-d1-fixture-linear-eval", names, contract, guard)
    assert target is not None
    model = RidgeAdapter(guard).fit(train, target)
    scores = model.predict(evaluation)
    threshold = calibration_threshold(scores, guard)
    assert threshold.value >= 0.01
    assert not qualifies(scores, threshold, guard).any(), "strict equality must produce a valid zero-candidate population"
    with pytest.raises(ValueError, match="provenance-bearing"):
        calibration_threshold(np.array([0.1, 0.2]), guard)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="frozen D1 rule"):
        CalibrationThreshold(0.0, "linear", "forged", _token=object())


@pytest.mark.parametrize(
    "scores,k,expected",
    [
        ([4.0, 3.0, 2.0, 1.0], 2, [1.0, 1.0, 0.0, 0.0]),
        ([4.0, 3.0, 3.0, 1.0], 2, [1.0, 0.5, 0.5, 0.0]),
        ([5.0, 4.0, 3.0, 3.0, 3.0, 1.0], 4, [1.0, 1.0, 2 / 3, 2 / 3, 2 / 3, 0.0]),
        ([2.0, 2.0, 2.0, 2.0], 3, [0.75, 0.75, 0.75, 0.75]),
        ([2.0, 1.0], 0, [0.0, 0.0]),
        ([2.0, 1.0], 3, [1.0, 1.0]),
    ],
)
def test_fractional_boundary_tie_hand_fixtures(scores: list[float], k: int, expected: list[float]) -> None:
    weights = fractional_boundary_weights(scores, k)
    assert np.allclose(weights, expected)
    assert np.isclose(weights.sum(), min(k, len(scores)))


def test_fractional_boundary_weights_and_weighted_statistics_are_identity_order_neutral() -> None:
    frame = pd.DataFrame({"security_id": list("ABCDE"), "score": [0.4, 0.2, 0.2, 0.2, 0.1], "outcome": [1.0, 0.0, 1.0, 0.0, -1.0]})
    first = fractional_boundary_weights(frame["score"], 2)
    mean = weighted_mean(frame["outcome"], first)
    rate = weighted_rate(frame["outcome"].gt(0), first)
    shuffled = frame.sample(frac=1.0, random_state=17).reset_index(drop=True)
    shuffled["security_id"] = ["X", "Y", "Z", "Q", "R"]
    second = fractional_boundary_weights(shuffled["score"], 2)
    assert np.isclose(weighted_mean(shuffled["outcome"], second), mean)
    assert np.isclose(weighted_rate(shuffled["outcome"].gt(0), second), rate)
