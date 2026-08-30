from __future__ import annotations

import numpy as np
import pandas as pd

from market_state import assign_tercile, compute_wig_features, drawdown_episodes, moving_block_indices, stable_frame_hash


def test_wig_feature_formulas_use_exact_lookbacks() -> None:
    dates = pd.bdate_range("2020-01-01", periods=300)
    close = np.exp(np.arange(300) * 0.001)
    frame = pd.DataFrame({"session_date": dates, "close": close})
    result = compute_wig_features(frame)
    row = result.iloc[252]
    assert np.isclose(row["wig_log_return_20"], 0.020)
    assert np.isclose(row["wig_log_return_60"], 0.060)
    assert np.isclose(row["wig_drawdown_252"], 0.0)
    assert np.isclose(row["wig_trend_acceleration_20_60"], 0.0)


def test_drawdown_episode_selection_and_recovery() -> None:
    series = pd.Series([100.0, 110.0, 99.0, 88.0, 111.0, 105.0], index=pd.bdate_range("2020-01-01", periods=6))
    episodes = drawdown_episodes(series)
    assert len(episodes) == 2
    assert episodes.iloc[0]["peak_date"] == series.index[1]
    assert episodes.iloc[0]["trough_date"] == series.index[3]
    assert episodes.iloc[0]["recovery_date"] == series.index[4]
    assert bool(episodes.iloc[0]["recovered"])
    assert not bool(episodes.iloc[1]["recovered"])


def test_terciles_and_bootstrap_are_deterministic() -> None:
    terciles = assign_tercile(pd.Series(np.arange(9.0)))
    assert terciles.tolist() == [1, 1, 1, 2, 2, 2, 3, 3, 3]
    first = moving_block_indices(100, 20, 5, 7)
    second = moving_block_indices(100, 20, 5, 7)
    assert all(np.array_equal(a, b) for a, b in zip(first, second))


def test_logical_hash_accepts_explicit_missing_values() -> None:
    frame = pd.DataFrame({"date": pd.to_datetime(["2020-01-01", "2020-01-02"]), "value": [1.0, np.nan]})
    assert stable_frame_hash(frame, ["date"]) == stable_frame_hash(frame.copy(), ["date"])
