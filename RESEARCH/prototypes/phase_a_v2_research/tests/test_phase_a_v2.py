from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "run_phase_a_v2.py"
SPEC = importlib.util.spec_from_file_location("phase_a_v2_runner", MODULE_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def test_frozen_feature_endpoints_and_proximity_definitions() -> None:
    dates = pd.date_range("2020-01-01", periods=260, freq="B")
    close = pd.DataFrame({"A": np.arange(1.0, 261.0)}, index=dates)
    high = close + 10.0
    volume = pd.DataFrame({"A": np.arange(101.0, 361.0)}, index=dates)
    features = runner.build_features(close, high, volume)
    assert features["momentum_12_1"].iloc[252, 0] == close.iloc[231, 0] / close.iloc[0, 0] - 1
    assert features["return_5"].iloc[252, 0] == close.iloc[252, 0] / close.iloc[247, 0] - 1
    assert features["proximity_to_max_high_252"].iloc[251, 0] == close.iloc[251, 0] / high.iloc[:252, 0].max()
    assert features["proximity_to_max_close_252"].iloc[251, 0] == 1.0
    assert not np.isclose(
        features["proximity_to_max_high_252"].iloc[251, 0],
        features["proximity_to_max_close_252"].iloc[251, 0],
    )


def test_strict_windows_fail_closed_on_internal_missing_values() -> None:
    dates = pd.date_range("2020-01-01", periods=260, freq="B")
    close = pd.DataFrame({"A": np.linspace(10, 20, 260)}, index=dates)
    high = close + 1
    volume = pd.DataFrame({"A": 100.0}, index=dates)
    close.iloc[250, 0] = np.nan
    volume.iloc[250, 0] = np.nan
    features = runner.build_features(close, high, volume)
    assert pd.isna(features["realized_volatility_20"].iloc[259, 0])
    assert pd.isna(features["relative_volume_20"].iloc[259, 0])
    assert pd.isna(features["proximity_to_max_close_252"].iloc[259, 0])


def test_decision_features_use_prior_session_and_labels_use_exact_anchors() -> None:
    dates = pd.date_range("2020-01-01", periods=280, freq="B")
    close = pd.DataFrame({"A": np.arange(1.0, 281.0)}, index=dates)
    open_ = close + 0.5
    high = close + 1.0
    volume = pd.DataFrame({"A": 100.0}, index=dates)
    usable = close.notna()
    membership = pd.DataFrame({"session_date": [dates[260]], "security_id": ["A"], "isin": ["TEST"]})
    panel = runner.attach_decision_values(
        membership,
        close,
        open_,
        runner.build_features(close, high, volume),
        usable,
        pd.Series(0.0, index=dates),
        "test",
    )
    assert panel.loc[0, "feature_session_date"] == dates[259]
    expected_feature = close.iloc[238, 0] / close.iloc[7, 0] - 1
    assert panel.loc[0, "momentum_12_1"] == expected_feature
    assert panel.loc[0, "label__close_to_close__3"] == close.iloc[263, 0] / close.iloc[260, 0] - 1
    assert panel.loc[0, "label__open_to_open__3"] == open_.iloc[263, 0] / open_.iloc[260, 0] - 1


def test_paired_rank_samples_are_identity_intersections() -> None:
    frame = pd.DataFrame(
        {
            "session_date": pd.to_datetime(["2026-01-02"] * 4),
            "security_id": list("ABCD"),
            "feature": [1.0, 2.0, 3.0, 4.0],
            "eligible": [True, True, False, True],
            "label": [0.4, 0.3, 0.2, np.nan],
        }
    )
    joint = frame.eligible & frame.label.notna()
    pct, quantile = runner.rank_and_quantile(frame, "feature", joint)
    assert pct.notna().sum() == 2
    assert set(frame.loc[pct.notna(), "security_id"]) == {"A", "B"}
    assert set(quantile.dropna().astype(int)) == {3, 5}
