from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ats_ml.d2_stage1 import (
    _actual_fit,
    _score_rows,
    require_common_cell_populations,
    require_stage1_validation,
)
from ats_ml.d2_contract import validate_execution_authorization


def fixture_rows() -> tuple[pd.DataFrame, pd.DataFrame]:
    session = pd.Timestamp("2024-01-02")
    ids = [f"S{index:02d}" for index in range(45)]
    observations = pd.DataFrame({
        "security_id": ids,
        "decision_session": session,
        "model_score_eligible": True,
        "feature": np.arange(45, dtype=float),
    })
    labels = pd.DataFrame({
        "security_id": ids,
        "decision_session": session,
        "label_endpoint_ts_20": pd.Timestamp("2024-01-31 09:00", tz="Europe/Warsaw"),
        "label__open_to_open__20": np.linspace(-0.1, 0.1, 45),
        "label_state_20": "AVAILABLE",
    })
    return observations, labels


def test_actual_fit_uses_only_endpoint_mature_rows_and_enforces_minimums() -> None:
    observations, labels = fixture_rows()
    fit, proof = _actual_fit(
        observations, labels, ["2024-01-02"], "2024-02-01", ("feature",),
        1, 45, "Europe/Warsaw",
    )
    assert len(fit) == 45
    assert proof["endpoint_strictly_before_boundary"] is True
    with pytest.raises(ValueError, match="actual fit minimum"):
        _actual_fit(
            observations, labels, ["2024-01-02"], "2024-01-31", ("feature",),
            1, 45, "Europe/Warsaw",
        )


def test_registered_fit_feature_with_low_finite_coverage_fails_closed() -> None:
    observations, labels = fixture_rows()
    observations.loc[:4, "feature"] = np.nan
    with pytest.raises(ValueError, match="below 90%"):
        _actual_fit(
            observations, labels, ["2024-01-02"], "2024-02-01", ("feature",),
            1, 45, "Europe/Warsaw",
        )


def test_common_score_population_minimum_is_independent_of_labels() -> None:
    observations, _ = fixture_rows()
    score, proof = _score_rows(observations, ["2024-01-02"], ("feature",), 1)
    assert len(score) == 45
    assert proof["qualifying_sessions"] == 1


def test_d2_execution_binds_accepted_contract_inputs_and_structural_run() -> None:
    contract, proof = validate_execution_authorization(require_clean=False)
    assert proof["status"] == "PASS"
    assert contract.config["contract_version"] == "phase-d0-20260901-v3"
    assert proof["execution_config"]["authorization"]["structural_run_id"] == "phase-d1-v3-structural-ed315ee058c7e0e7ce51"


def test_common_population_equality_normalizes_categorical_schema_state() -> None:
    keys = pd.DataFrame({
        "security_id": pd.Categorical(["A", "B"], categories=["A", "B", "UNUSED"]),
        "decision_session": pd.to_datetime(["2024-01-02", "2024-01-02"]),
    })
    left = keys.assign(cell_id="LEFT")
    right = keys.assign(
        security_id=pd.Categorical(["A", "B"], categories=["B", "A"]),
        cell_id="RIGHT",
    )
    proof = require_common_cell_populations(pd.concat([left, right], ignore_index=True), {"LEFT", "RIGHT"})
    assert len(proof) == 64
    with pytest.raises(ValueError, match="populations differ"):
        require_common_cell_populations(
            pd.concat([left, right.iloc[:1]], ignore_index=True), {"LEFT", "RIGHT"}
        )


def test_stage1_validation_requires_no_evaluation_metric() -> None:
    proof = {
        "status": "PASS",
        "all_blocks_present": True,
        "all_cells_present": True,
        "finite_scores_and_thresholds": True,
        "strict_threshold_rule": True,
        "outcome_columns_absent": True,
        "common_population_reconciled": True,
        "ablation_population_identical": True,
        "locked_sequence_complete": True,
        "evaluation_metrics_computed": False,
    }
    require_stage1_validation(proof)
    proof["evaluation_metrics_computed"] = True
    with pytest.raises(ValueError, match="must_be_false"):
        require_stage1_validation(proof)
