from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market_state import ALL_FEATURES, assign_tercile, compute_top60_features, compute_wig_features, drawdown_episodes, moving_block_indices, stable_frame_hash
from run_diagnostic import conditional_diagnostics, feature_coverage_gate, prepare_proximity_sessions


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


def test_wig_volatility_ratio_is_centered() -> None:
    dates = pd.bdate_range("2020-01-01", periods=100)
    returns = 0.001 + 0.01 * np.sin(np.arange(100) / 4.0)
    close = np.exp(np.cumsum(returns))
    result = compute_wig_features(pd.DataFrame({"session_date": dates, "close": close}), volatility_ratio_centered=True)
    log_returns = pd.Series(np.log(close)).diff()
    expected = log_returns.iloc[-20:].std(ddof=1) / log_returns.iloc[-60:].std(ddof=1) - 1.0
    assert np.isclose(result.iloc[-1]["wig_volatility_ratio_20_60"], expected)


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


def _top60_fixture(missing_members: int) -> tuple[pd.DataFrame, pd.DatetimeIndex, pd.DatetimeIndex]:
    calendar = pd.bdate_range("2019-01-01", periods=254)
    rows = []
    for member in range(60):
        slope = -0.002 + member * 0.00008
        phase = member * 0.11
        log_price = 5.0 + slope * np.arange(len(calendar)) + 0.012 * np.sin(np.arange(len(calendar)) / 3.0 + phase)
        for index, date in enumerate(calendar):
            value = float(np.exp(log_price[index]))
            if member < missing_members and index == len(calendar) - 10:
                value = np.nan
            rows.append(
                {
                    "session_date": date,
                    "isin": f"TEST{member:08d}",
                    "official_membership": bool(date == calendar[-2]),
                    "split_adjusted_close": value,
                    "missing_state": "source_missing" if pd.isna(value) else "",
                    "nontrading_reason": "",
                    "coverage_result": "covered" if pd.notna(value) else "missing",
                }
            )
    return pd.DataFrame(rows), pd.DatetimeIndex(calendar), pd.DatetimeIndex([calendar[-1]])


def test_top60_iqr_top5_timing_and_missing_member_denominator() -> None:
    candidate, calendar, decisions = _top60_fixture(missing_members=1)
    features, coverage = compute_top60_features(candidate, calendar, decisions, minimum_usable=45, leadership_positive_name_count=5)
    row = features.iloc[0]
    assert row["information_session"] == calendar[-2]
    assert row["official_denominator"] == 60
    pivot = candidate.pivot(index="session_date", columns="isin", values="split_adjusted_close").reindex(calendar)
    log_prices = np.log(pivot)
    usable20 = pivot.iloc[-22:-1].notna().all(axis=0)
    usable60 = pivot.iloc[-62:-1].notna().all(axis=0)
    ret20 = (log_prices.iloc[-2] - log_prices.iloc[-22]).loc[usable20]
    ret60 = (log_prices.iloc[-2] - log_prices.iloc[-62]).loc[usable60]
    expected_iqr = ret20.quantile(0.75, interpolation="linear") - ret20.quantile(0.25, interpolation="linear")
    positive = ret20[ret20 > 0].sort_values(ascending=False)
    assert len(ret20) == len(ret60) == 59
    assert np.isclose(row["top60_return_dispersion_20"], expected_iqr)
    assert np.isclose(row["top60_positive_leadership_share_20"], positive.head(5).sum() / positive.sum())
    assert np.isclose(row["top60_breadth_positive_60"], (ret60 > 0).mean())
    breadth_proof = coverage.loc[coverage["feature"].eq("top60_breadth_positive_60")].iloc[0]
    assert breadth_proof["usable_count"] == breadth_proof["aggregation_denominator"] == 59
    assert breadth_proof["unavailable_members_in_aggregation"] == 0
    assert breadth_proof["positive_observation_count"] == int((ret60 > 0).sum())


def test_top60_correlation_uses_exact_history_and_excludes_missing_member() -> None:
    candidate, calendar, decisions = _top60_fixture(missing_members=1)
    features, coverage = compute_top60_features(
        candidate,
        calendar,
        decisions,
        minimum_usable=45,
        leadership_positive_name_count=5,
    )
    pivot = candidate.pivot(index="session_date", columns="isin", values="split_adjusted_close").reindex(calendar)
    exact_returns = np.log(pivot).diff().iloc[-61:-1]
    usable = exact_returns.columns[exact_returns.notna().all(axis=0)]
    correlation = np.corrcoef(exact_returns[usable].to_numpy(dtype=float), rowvar=False)
    upper_triangle = correlation[np.triu_indices_from(correlation, k=1)]
    expected = float(upper_triangle.mean())

    row = features.iloc[0]
    proof = coverage.loc[coverage["feature"].eq("top60_average_pairwise_correlation_60")].iloc[0]
    assert len(usable) == 59
    assert np.isclose(row["top60_average_pairwise_correlation_60"], expected)
    assert proof["usable_count"] == proof["aggregation_denominator"] == 59
    assert proof["excluded_count"] == 1
    assert proof["unavailable_members_in_aggregation"] == 0
    assert bool(proof["feature_valid"])


def test_top60_fails_closed_below_45_and_rejects_wrong_official_denominator() -> None:
    candidate, calendar, decisions = _top60_fixture(missing_members=16)
    features, coverage = compute_top60_features(candidate, calendar, decisions, minimum_usable=45, leadership_positive_name_count=5)
    assert pd.isna(features.iloc[0]["top60_return_dispersion_20"])
    assert not bool(coverage.loc[coverage["feature"].eq("top60_return_dispersion_20"), "feature_valid"].iloc[0])
    assert pd.isna(features.iloc[0]["top60_average_pairwise_correlation_60"])
    assert not bool(coverage.loc[coverage["feature"].eq("top60_average_pairwise_correlation_60"), "feature_valid"].iloc[0])
    wrong = candidate.loc[~candidate["isin"].eq("TEST00000059")].copy()
    with pytest.raises(ValueError, match="Official denominator is 59"):
        compute_top60_features(wrong, calendar, decisions, minimum_usable=45, leadership_positive_name_count=5)


def test_unavailable_as_negative_gate_is_calculated_from_proof_fields() -> None:
    date = pd.Timestamp("2025-01-02")
    state = pd.DataFrame({"decision_session": [date], "information_session": [date - pd.Timedelta(days=1)], "timing_valid": [True]})
    for index, feature in enumerate(ALL_FEATURES):
        state[feature] = float(index + 1)
    coverage_rows = []
    for feature in [name for name in ALL_FEATURES if name.startswith("top60_") and name != "top60_share_within_5pct_high_252"]:
        coverage_rows.append(
            {
                "decision_session": date,
                "feature": feature,
                "official_denominator": 60,
                "usable_count": 59,
                "aggregation_denominator": 59,
                "lag10_aggregation_denominator": 59 if feature == "top60_breadth_change_10" else np.nan,
                "unavailable_members_in_aggregation": 1 if feature == "top60_breadth_positive_60" else 0,
            }
        )
    gate = feature_coverage_gate(
        {"controlling_start": "2025-01-02", "controlling_end": "2025-01-02", "minimum_valid_session_fraction": 0.9, "minimum_usable_members": 45, "duplicate_tolerance": 1e-12},
        state,
        pd.DataFrame(coverage_rows),
    )
    breadth = gate.loc[gate["feature"].eq("top60_breadth_positive_60")].iloc[0]
    assert breadth["unavailable_as_negative_violations"] == 1
    assert breadth["status"] == "NOT PROVEN"


def test_right_censored_session_does_not_enter_outcome_terciles() -> None:
    dates = pd.to_datetime(["2025-01-02", "2025-01-03"])
    adapted_rows = []
    for date_index, date in enumerate(dates):
        for member in range(60):
            adapted_rows.append(
                {
                    "session_date": date,
                    "security_id": f"security-{member}",
                    "official_expected": 60,
                    "eligible__proximity_to_max_high_252": True,
                    "proximity_to_max_high_252": float(member),
                    "label__open_to_open__20": float(member) / 1000.0 if date_index == 0 else np.nan,
                }
            )
    state = pd.DataFrame({"decision_session": dates, "information_session": dates - pd.Timedelta(days=1)})
    for feature in ALL_FEATURES:
        state[feature] = [0.0, 1.0]
    sessions, rows = prepare_proximity_sessions(
        {"controlling_start": "2025-01-02", "controlling_end": "2025-01-03"},
        pd.DataFrame(adapted_rows),
        state,
    )
    assert sessions["outcome_population"].tolist() == [True, False]
    _, _, _, assignments = conditional_diagnostics(sessions, rows)
    assert assignments["session_date"].nunique() == 1
    assert assignments["session_date"].iloc[0] == dates[0]
