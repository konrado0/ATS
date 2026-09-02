from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ats_ml.d2_stage1 import _actual_fit, _score_rows
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
