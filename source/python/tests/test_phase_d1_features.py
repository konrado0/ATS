from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ats_ml.features import (
    FROZEN_EXCLUSION_CODES,
    X_INPUTS,
    attach_information_session_features,
    compute_market_features,
    compute_stock_feature_history,
    compute_x_features,
)
from phase_d1_helpers import d1_contract_guard_context, official_membership, stock_bars


HAND = json.loads((Path(__file__).parent / "fixtures/phase_d1/hand_values.json").read_text(encoding="utf-8"))


def test_all_c_and_p_formulas_on_hand_calculated_geometric_fixture() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2023-01-02", periods=254)
    close = 100.0 * np.power(1.01, np.arange(len(dates)))
    bars = stock_bars(dates, close_paths={"S00": close})
    last20 = bars.index[-21:-1]
    bars.loc[last20, "split_adjusted_volume"] = np.arange(1.0, 21.0)
    history = compute_stock_feature_history(bars, dates, contract, guard, context)
    row = history.loc[history["session_date"].eq(dates[-2])].iloc[0]
    expected = HAND["geometric_stock"]
    for name, value in expected.items():
        if name == "growth":
            continue
        assert row[f"eligible__{name}"], name
        assert np.isclose(row[name], value, rtol=1e-11, atol=1e-12), (name, row[name], value)
    simple_returns = close[-22:-1] / close[-23:-2] - 1.0
    assert np.isclose(row["realized_volatility_20"], np.std(simple_returns[-20:], ddof=1), atol=1e-14)
    envelope_high = (close[-21:-1] * 1.1).max()
    envelope_low = (close[-21:-1] * 0.9).min()
    assert np.isclose(row["stock_close_location_value_20"], (close[-2] - envelope_low) / (envelope_high - envelope_low))


def test_sample_volatility_centered_ratio_path_efficiency_and_flat_conventions() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2024-01-02", periods=61)
    returns = np.array([0.0] * 40 + [value for _ in range(10) for value in (0.01, -0.01)])
    close = 100.0 * np.exp(np.r_[0.0, np.cumsum(returns)])
    bars = stock_bars(dates, close_paths={"S00": close})
    history = compute_stock_feature_history(bars, dates, contract, guard, context)
    row = history.iloc[-1]
    assert np.isclose(row["stock_volatility_ratio_20_60"], HAND["volatility_ratio_20_60"], rtol=1e-12)
    assert np.isclose(row["stock_log_return_20"], 0.0, atol=1e-12)
    assert np.isclose(row["stock_path_efficiency_20"], 0.0, atol=1e-12)
    assert np.isclose(row["stock_positive_return_share_20"], 0.5)
    flat = stock_bars(dates, close_paths={"S00": np.full(len(dates), 100.0)})
    flat_row = compute_stock_feature_history(flat, dates, contract, guard, context).iloc[-1]
    assert flat_row["stock_path_efficiency_20"] == 0.0
    assert flat_row["stock_positive_return_share_20"] == 0.0
    assert pd.isna(flat_row["stock_volatility_ratio_20_60"])


def test_realized_volatility_uses_sample_simple_returns() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2024-01-02", periods=21)
    returns = np.array([0.0] * 19 + [0.2])
    close = 100.0 * np.cumprod(np.r_[1.0, 1.0 + returns])
    row = compute_stock_feature_history(stock_bars(dates, close_paths={"S00": close}), dates, contract, guard, context).iloc[-1]
    assert np.isclose(row["realized_volatility_20"], np.sqrt(0.002), rtol=1e-12)


def test_drawdown_recovery_and_close_location_boundaries() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2024-01-02", periods=60)
    close = np.linspace(4.0, 9.0, 60)
    close[10] = 10.0
    close[-1] = 5.0
    bars = stock_bars(dates, close_paths={"S00": close})
    row = compute_stock_feature_history(bars, dates, contract, guard, context).iloc[-1]
    assert row["stock_drawdown_depth_60"] == -0.5
    assert row["stock_recovery_from_low_60"] == 0.25
    clv_dates = pd.bdate_range("2024-05-01", periods=20)
    clv = stock_bars(clv_dates, close_paths={"S00": np.full(20, 7.0)})
    clv["split_adjusted_high"] = 12.0
    clv["split_adjusted_low"] = 2.0
    clv_row = compute_stock_feature_history(clv, clv_dates, contract, guard, context).iloc[-1]
    assert clv_row["stock_close_location_value_20"] == 0.5
    clv["split_adjusted_high"] = 7.0
    clv["split_adjusted_low"] = 7.0
    flat_row = compute_stock_feature_history(clv, clv_dates, contract, guard, context).iloc[-1]
    assert pd.isna(flat_row["stock_close_location_value_20"])


def test_exact_window_interior_gaps_and_source_switch_rules() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2022-01-03", periods=254)
    close = 100.0 * np.power(1.001, np.arange(len(dates)))
    base = stock_bars(dates, close_paths={"S00": close})
    valid = compute_stock_feature_history(base, dates, contract, guard, context).iloc[-2]
    switched = base.copy()
    switched.loc[100:, "selected_source"] = "fixture-b"
    switched_values = compute_stock_feature_history(switched, dates, contract, guard, context).iloc[-2]
    for name in contract.feature_blocks["C"] + contract.feature_blocks["P"]:
        assert np.isclose(valid[name], switched_values[name], equal_nan=True), name
    gap = base.copy()
    gap.loc[len(gap) - 2 - 100, "split_adjusted_close"] = np.nan
    gap_values = compute_stock_feature_history(gap, dates, contract, guard, context).iloc[-2]
    assert pd.isna(gap_values["momentum_12_1"])
    assert pd.isna(gap_values["proximity_to_max_close_252"])
    recent_gap = base.copy()
    recent_gap.loc[len(recent_gap) - 2 - 20, "split_adjusted_close"] = np.nan
    recent_values = compute_stock_feature_history(recent_gap, dates, contract, guard, context).iloc[-2]
    assert recent_values["eligible__momentum_12_1"]
    assert pd.isna(recent_values["stock_log_return_20"])
    unresolved = base.copy()
    unresolved.loc[len(unresolved) - 2 - 3, "source_treatment_state"] = "event=unresolved"
    unresolved_values = compute_stock_feature_history(unresolved, dates, contract, guard, context).iloc[-2]
    assert pd.isna(unresolved_values["return_5"])
    assert pd.isna(unresolved_values["relative_volume_20"])
    assert unresolved_values["missing_state__return_5"] == "SOURCE_TREATMENT_UNRESOLVED"
    assert unresolved_values["missing_state__relative_volume_20"] == "SOURCE_TREATMENT_UNRESOLVED"
    wrong_factor = base.copy()
    wrong_factor.loc[len(wrong_factor) - 2 - 3, "factor_version"] = "fixture-v0"
    wrong_factor_values = compute_stock_feature_history(wrong_factor, dates, contract, guard, context).iloc[-2]
    assert pd.isna(wrong_factor_values["return_5"])
    assert pd.isna(wrong_factor_values["relative_volume_20"])
    assert wrong_factor_values["missing_state__return_5"] == "INVALID_PRICE_BASIS"
    volume = base.copy()
    volume.loc[len(volume) - 2 - 3, "volume_usable_for_relative_volume"] = False
    volume_values = compute_stock_feature_history(volume, dates, contract, guard, context).iloc[-2]
    assert pd.isna(volume_values["relative_volume_20"])
    assert np.isclose(volume_values["return_5"], valid["return_5"])


@pytest.mark.parametrize("column", ["price_usable_for_features", "source_treatment_state", "factor_version", "volume_usable_for_relative_volume"])
def test_stock_validity_columns_are_mandatory_and_never_default_permissive(column: str) -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2024-01-02", periods=25)
    with pytest.raises(ValueError, match="missing columns"):
        compute_stock_feature_history(stock_bars(dates).drop(columns=column), dates, contract, guard, context)


def test_feature_boundary_rejects_label_or_prediction_columns_before_copying() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2024-01-02", periods=25)
    with pytest.raises(ValueError, match="predictive columns"):
        compute_stock_feature_history(stock_bars(dates).assign(label__open_to_open__20=0.1), dates, contract, guard, context)
    x_frame = pd.DataFrame({
        "decision_session": pd.Timestamp("2024-02-01"),
        "security_id": [f"S{i:02d}" for i in range(60)],
        "momentum_12_1": np.arange(60, dtype=float),
        "eligible__momentum_12_1": True,
        "label__open_to_open__20": 0.2,
    })
    with pytest.raises(ValueError, match="predictive columns"):
        compute_x_features(x_frame)


def test_stock_boundary_dependency_and_closed_missing_states() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2024-01-02", periods=61)
    bars = stock_bars(dates)
    base = compute_stock_feature_history(bars, dates, contract, guard, context)
    assert not base.iloc[-2]["eligible__stock_log_return_60"]
    assert base.iloc[-1]["eligible__stock_log_return_60"]
    nonpositive = bars.copy()
    nonpositive.loc[nonpositive["session_date"].eq(dates[-3]), "split_adjusted_close"] = 0.0
    row = compute_stock_feature_history(nonpositive, dates, contract, guard, context).iloc[-1]
    assert pd.isna(row["stock_log_return_60"])
    assert row["missing_state__stock_log_return_60"] == "INVALID_PRICE_BASIS"
    high_gap = bars.copy()
    high_gap.loc[high_gap["session_date"].eq(dates[-10]), "split_adjusted_high"] = np.nan
    high_row = compute_stock_feature_history(high_gap, dates, contract, guard, context).iloc[-1]
    assert pd.isna(high_row["stock_close_location_value_20"])
    assert high_row["missing_state__stock_close_location_value_20"] == "INVALID_PRICE_BASIS"
    documented = bars.copy()
    mask = documented["session_date"].eq(dates[-4])
    documented.loc[mask, "price_usable_for_features"] = False
    documented.loc[mask, "missing_state"] = "documented_non_trading"
    documented_row = compute_stock_feature_history(documented, dates, contract, guard, context).iloc[-1]
    assert documented_row["missing_state__return_5"] == "DOCUMENTED_NON_TRADING"
    with pytest.raises(ValueError, match="unique"):
        compute_stock_feature_history(bars, list(dates) + [dates[-1]], contract, guard, context)


@pytest.mark.parametrize("target,source", list(X_INPUTS.items()))
def test_x_average_ties_45_of_60_and_row_identity_invariance(target: str, source: str) -> None:
    rows = pd.DataFrame({
        "decision_session": pd.Timestamp("2025-01-02"),
        "security_id": [f"S{i:02d}" for i in range(60)],
        source: [0.0, 1.0, 1.0, 1.0, *map(float, range(2, 43)), *([np.nan] * 15)],
    })
    rows[f"eligible__{source}"] = rows[source].notna()
    ranked = compute_x_features(rows)
    assert ranked[f"eligible_count__{target}"].eq(45).all()
    assert np.isclose(ranked.loc[0, target], 1 / 45)
    assert ranked.loc[1:3, target].eq(3 / 45).all()
    assert np.isclose(ranked.loc[44, target], 1.0)
    assert ranked.loc[45:, target].isna().all()
    shuffled = rows.sample(frac=1.0, random_state=7).copy()
    shuffled["security_id"] = [f"RENAMED{i:02d}" for i in range(60)]
    reranked = compute_x_features(shuffled).sort_values(source, na_position="last").reset_index(drop=True)
    expected = ranked.sort_values(source, na_position="last").reset_index(drop=True)
    assert np.allclose(expected[target], reranked[target], equal_nan=True)


def test_x_below_45_is_null_and_missing_is_not_low() -> None:
    source = "momentum_12_1"
    frame = pd.DataFrame({"decision_session": pd.Timestamp("2025-01-02"), "security_id": [f"S{i:02d}" for i in range(60)], source: [*range(44), *([np.nan] * 16)]})
    frame[f"eligible__{source}"] = frame[source].notna()
    result = compute_x_features(frame)
    assert result["xrank_momentum_12_1"].isna().all()
    assert result["eligible_count__xrank_momentum_12_1"].eq(44).all()
    with pytest.raises(ValueError, match="exactly 45"):
        compute_x_features(frame, minimum_members=44)


def test_x_all_45_eligible_values_tied_have_average_rank_23_of_45() -> None:
    source = "momentum_12_1"
    frame = pd.DataFrame({
        "decision_session": pd.Timestamp("2025-01-02"),
        "security_id": [f"S{i:02d}" for i in range(60)],
        source: [*([7.0] * 45), *([np.nan] * 15)],
    })
    frame[f"eligible__{source}"] = frame[source].notna()
    result = compute_x_features(frame)
    assert result.loc[:44, "xrank_momentum_12_1"].eq(23 / 45).all()


def test_preceding_session_attachment_ignores_decision_session_prices() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2023-01-02", periods=255)
    bars = stock_bars(dates, securities=60)
    history = compute_stock_feature_history(bars, dates, contract, guard, context)
    membership = official_membership(bars, [dates[-1]])
    attached = attach_information_session_features(membership, history, dates, contract.feature_blocks["C"])
    before = attached.set_index("security_id")[list(contract.feature_blocks["C"])]
    changed = bars.copy()
    changed.loc[changed["session_date"].eq(dates[-1]), ["split_adjusted_close", "split_adjusted_high", "split_adjusted_low"]] *= 1000
    changed_history = compute_stock_feature_history(changed, dates, contract, guard, context)
    after = attach_information_session_features(membership, changed_history, dates, contract.feature_blocks["C"]).set_index("security_id")[list(contract.feature_blocks["C"])]
    assert np.allclose(before, after, equal_nan=True)


def test_all_twelve_m_features_and_corrected_wig_definitions() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2023-01-02", periods=300)
    bars = stock_bars(dates, securities=60)
    wig = pd.DataFrame({"session_date": dates, "close": np.exp(0.01 * np.arange(len(dates)))})
    result = compute_market_features(wig, bars, dates, [dates[-1]], guard, context).iloc[0]
    for name in contract.feature_blocks["M"]:
        assert name in result.index
    assert np.isclose(result["wig_log_return_20"], 0.2)
    assert np.isclose(result["wig_log_return_60"], 0.6)
    assert np.isclose(result["wig_trend_acceleration_20_60"], 0.0, atol=1e-14)
    assert np.isclose(result["wig_drawdown_252"], 0.0)
    assert np.isclose(result["wig_downside_semivolatility_20"], 0.0)
    with pytest.raises(ValueError, match="exactly 45"):
        compute_market_features(wig, bars, dates, [dates[-1]], guard, context, minimum_members=44)


def test_wig_trend_drawdown_downside_and_centered_volatility_hand_values() -> None:
    _, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2023-01-02", periods=263)
    bars = stock_bars(dates, securities=60)
    info = len(dates) - 2
    wig_close = np.full(len(dates), 100.0)
    wig_close[100] = 125.0
    wig_close[info] = 100.0
    wig = pd.DataFrame({"session_date": dates, "close": wig_close})
    row = compute_market_features(wig, bars, dates, [dates[-1]], guard, context).iloc[0]
    assert np.isclose(row["wig_drawdown_252"], -0.2)
    trend_close = np.full(len(dates), 100.0)
    trend_close[info] = 200.0
    trend = compute_market_features(pd.DataFrame({"session_date": dates, "close": trend_close}), bars, dates, [dates[-1]], guard, context).iloc[0]
    assert np.isclose(trend["wig_trend_200"], 199 / 201)
    daily = np.zeros(len(dates) - 1)
    pattern = np.array([0.0] * 40 + [value for _ in range(10) for value in (0.01, -0.01)])
    daily[info - 60:info] = pattern
    vol_close = np.exp(np.r_[0.0, np.cumsum(daily)])
    vol = compute_market_features(pd.DataFrame({"session_date": dates, "close": vol_close}), bars, dates, [dates[-1]], guard, context).iloc[0]
    assert np.isclose(vol["wig_downside_semivolatility_20"], 0.01 * np.sqrt(126), rtol=1e-12)
    assert np.isclose(vol["wig_volatility_ratio_20_60"], HAND["volatility_ratio_20_60"], rtol=1e-12)


def test_top60_iqr_top_five_and_57_of_60_denominators() -> None:
    _, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2024-01-02", periods=80)
    info_index = len(dates) - 2
    paths: dict[str, np.ndarray] = {}
    for number in range(60):
        values = np.full(len(dates), 100.0)
        if number < 57:
            segment = np.linspace(0.0, number / 100.0, 21)
            values[info_index - 20:info_index + 1] = 100.0 * np.exp(segment)
        paths[f"S{number:02d}"] = values
    bars = stock_bars(dates, securities=60, close_paths=paths)
    for number in range(57, 60):
        mask = bars["security_id"].eq(f"S{number:02d}") & bars["session_date"].eq(dates[info_index - 10])
        bars.loc[mask, "price_usable_for_features"] = False
    wig = pd.DataFrame({"session_date": dates, "close": 1000.0 * np.exp(0.001 * np.arange(len(dates)))})
    row = compute_market_features(wig, bars, dates, [dates[-1]], guard, context).iloc[0]
    assert row["eligible_count__top60_return_dispersion_20"] == 57
    assert np.isclose(row["top60_return_dispersion_20"], HAND["top60"]["dispersion_57_of_60"])
    assert np.isclose(row["top60_positive_leadership_share_20"], HAND["top60"]["leadership_57_of_60"])


def test_top60_complete_vector_pairwise_correlation_uses_46_of_60() -> None:
    _, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2024-01-02", periods=63)
    decision = dates[-1]
    x = np.linspace(-0.02, 0.02, 60)
    paths: dict[str, np.ndarray] = {}
    for number in range(60):
        daily = x if number < 45 else (-x if number == 45 else np.zeros(60))
        returns = np.zeros(len(dates) - 1)
        returns[-60:] = daily
        paths[f"S{number:02d}"] = 100.0 * np.exp(np.r_[0.0, np.cumsum(returns)])
    bars = stock_bars(dates, securities=60, close_paths=paths)
    wig = pd.DataFrame({"session_date": dates, "close": 1000.0 * np.exp(0.001 * np.arange(len(dates)))})
    row = compute_market_features(wig, bars, dates, [decision], guard, context).iloc[0]
    assert row["eligible_count__top60_average_pairwise_correlation_60"] == 46
    assert np.isclose(row["top60_average_pairwise_correlation_60"], HAND["top60"]["pairwise_correlation_45_plus_one_inverse"], rtol=1e-12)
    assert set(json.loads(row["exclusion_reason_counts__top60_average_pairwise_correlation_60"])) <= FROZEN_EXCLUSION_CODES


def test_top60_breadth_and_calendar_lag10_change_keep_both_denominators() -> None:
    _, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2023-01-02", periods=90)
    decision_pos = len(dates) - 1
    info_pos = decision_pos - 1
    prior_info_pos = info_pos - 10
    returns_by_security: dict[str, np.ndarray] = {}
    for number in range(60):
        daily = np.zeros(len(dates) - 1)
        if number < 9:
            daily[:] = 0.001
        elif number < 30:
            daily[prior_info_pos:info_pos] = 0.01
        elif 50 <= number < 57:
            daily[info_pos - 60:info_pos] = -0.001
        returns_by_security[f"S{number:02d}"] = 100.0 * np.exp(np.r_[0.0, np.cumsum(daily)])
    bars = stock_bars(dates, securities=60, close_paths=returns_by_security)
    prior_start = dates[prior_info_pos - 60]
    for number in range(45, 60):
        bars.loc[bars["security_id"].eq(f"S{number:02d}") & bars["session_date"].eq(prior_start), "price_usable_for_features"] = False
    for number in range(57, 60):
        bars.loc[bars["security_id"].eq(f"S{number:02d}") & bars["session_date"].eq(dates[info_pos - 3]), "price_usable_for_features"] = False
    wig = pd.DataFrame({"session_date": dates, "close": 1000.0 * np.exp(0.001 * np.arange(len(dates)))})
    row = compute_market_features(wig, bars, dates, [dates[-1]], guard, context).iloc[0]
    assert row["eligible_count__top60_breadth_positive_60"] == 57
    assert np.isclose(row["top60_breadth_positive_60"], HAND["top60"]["breadth_30_of_57"])
    assert row["eligible_count__top60_breadth_change_10"] == 45
    assert row["eligible_count_current__top60_breadth_change_10"] == 57
    assert row["eligible_count_lag10__top60_breadth_change_10"] == 45
    assert np.isclose(row["top60_breadth_change_10"], HAND["top60"]["breadth_change"])


def test_wig_internal_gap_and_top60_below_45_fail_closed_with_proof() -> None:
    _, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2024-01-02", periods=80)
    bars = stock_bars(dates, securities=60)
    info = dates[-2]
    wig = pd.DataFrame({"session_date": dates, "close": 1000.0 * np.exp(0.001 * np.arange(len(dates)))})
    wig.loc[wig["session_date"].eq(dates[-10]), "close"] = np.nan
    for number in range(16):
        mask = bars["security_id"].eq(f"S{number:02d}") & bars["session_date"].eq(dates[-5])
        bars.loc[mask, "price_usable_for_features"] = False
        bars.loc[mask, "missing_state"] = "documented_non_trading"
    row = compute_market_features(wig, bars, dates, [dates[-1]], guard, context).iloc[0]
    assert pd.isna(row["wig_log_return_20"])
    assert row["eligible_count__top60_return_dispersion_20"] == 44
    assert pd.isna(row["top60_return_dispersion_20"])
    assert row["excluded_count__top60_return_dispersion_20"] == 16
    assert "DOCUMENTED_NON_TRADING" in row["exclusion_reason_counts__top60_return_dispersion_20"]
    reason_columns = [name for name in row.index if name.startswith("exclusion_reason_counts__")]
    for column in reason_columns:
        value = row[column]
        if pd.notna(value) and value:
            parsed = json.loads(value)
            if set(parsed) == {"current", "lag10"}:
                continue
            assert set(parsed) <= FROZEN_EXCLUSION_CODES
    states = {row[column] for column in row.index if column.startswith("aggregation_state__") and row[column]}
    assert states <= FROZEN_EXCLUSION_CODES


def test_top60_zero_positive_leadership_has_visible_closed_aggregate_state() -> None:
    _, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2024-01-02", periods=80)
    paths = {f"S{number:02d}": 100.0 * np.exp(-0.001 * np.arange(len(dates))) for number in range(60)}
    bars = stock_bars(dates, securities=60, close_paths=paths)
    wig = pd.DataFrame({"session_date": dates, "close": 1000.0 * np.exp(0.001 * np.arange(len(dates)))})
    row = compute_market_features(wig, bars, dates, [dates[-1]], guard, context).iloc[0]
    assert row["eligible_count__top60_positive_leadership_share_20"] == 60
    assert row["excluded_count__top60_positive_leadership_share_20"] == 0
    assert pd.isna(row["top60_positive_leadership_share_20"])
    assert row["aggregation_state__top60_positive_leadership_share_20"] == "MARKET_FEATURE_UNAVAILABLE"


def test_x_uses_decision_members_and_top60_uses_preceding_members() -> None:
    contract, guard, context = d1_contract_guard_context()
    dates = pd.bdate_range("2024-01-02", periods=270)
    bars = stock_bars(dates, securities=61)
    bars.loc[bars["security_id"].eq("S60"), "official_membership"] = False
    decision = dates[-1]
    bars.loc[bars["session_date"].eq(decision) & bars["security_id"].eq("S00"), "official_membership"] = False
    bars.loc[bars["session_date"].eq(decision) & bars["security_id"].eq("S60"), "official_membership"] = True
    history = compute_stock_feature_history(bars, dates, contract, guard, context)
    decision_membership = official_membership(bars, [decision])
    attached = attach_information_session_features(decision_membership, history, dates, contract.feature_blocks["C"])
    assert set(attached["security_id"]) == {f"S{i:02d}" for i in range(1, 61)}
    wig = pd.DataFrame({"session_date": dates, "close": 1000.0 * np.exp(0.001 * np.arange(len(dates)))})
    market = compute_market_features(wig, bars, dates, [decision], guard, context)
    assert market.iloc[0]["information_session"] == dates[-2]
    assert market.iloc[0]["eligible_count__top60_breadth_positive_60"] == 60
