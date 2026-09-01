from __future__ import annotations

import hashlib
import inspect
import json
import math
from collections.abc import Iterable

import numpy as np
import pandas as pd

from ats_ml.contracts import FrozenD0Contract
from ats_ml.guard import D1ExecutionGuard, ExecutionClass, ExecutionContext, Operation


STOCK_BLOCKS = ("C", "P")
X_INPUTS = {
    "xrank_momentum_12_1": "momentum_12_1",
    "xrank_proximity_to_max_high_252": "proximity_to_max_high_252",
    "xrank_realized_volatility_20": "realized_volatility_20",
    "xrank_relative_volume_20": "relative_volume_20",
}
FROZEN_EXCLUSION_CODES = {
    "PRELISTING", "DOCUMENTED_NON_TRADING", "UNRESOLVED_IDENTITY", "MISSING_PRICE",
    "INVALID_PRICE_BASIS", "SOURCE_TREATMENT_UNRESOLVED", "INSUFFICIENT_EXACT_LOOKBACK",
    "MISSING_VOLUME", "VOLUME_NOT_COMPARABLE", "LABEL_START_MISSING", "LABEL_ENDPOINT_MISSING",
    "LABEL_RIGHT_CENSORED", "MARKET_FEATURE_UNAVAILABLE", "CROSS_SECTION_BELOW_45",
    "PREDICTOR_COVERAGE_BELOW_MINIMUM", "MODEL_INPUT_ALL_MISSING",
}


class FeatureContractError(ValueError):
    pass


def _reject_predictive_columns(frame: pd.DataFrame, role: str) -> None:
    forbidden_tokens = ("label" + "__", "forward" + "_return", "model_score", "prediction", "rank_ic", "tail_outcome")
    forbidden = [column for column in frame.columns if any(token in str(column).lower() for token in forbidden_tokens)]
    if forbidden:
        raise FeatureContractError(f"{role} contains predictive columns: {forbidden}")


def _calendar(calendar: Iterable[object]) -> pd.DatetimeIndex:
    result = pd.DatetimeIndex(pd.to_datetime(list(calendar))).normalize().sort_values()
    if len(result) == 0 or result.has_duplicates:
        raise FeatureContractError("official calendar must be nonempty and unique")
    return result


def _finite_positive(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.notna() & np.isfinite(values) & values.gt(0.0)


def _rolling_all(mask: pd.Series, window: int) -> pd.Series:
    return mask.astype("int8").rolling(window, min_periods=window).sum().eq(window)


_MISSING_REASON_PRIORITY = (
    "SOURCE_TREATMENT_UNRESOLVED",
    "INVALID_PRICE_BASIS",
    "PRELISTING",
    "DOCUMENTED_NON_TRADING",
    "MISSING_VOLUME",
    "VOLUME_NOT_COMPARABLE",
    "MISSING_PRICE",
)


def _window_failure_state(reason: pd.Series, window: int, *, shift: int = 0) -> pd.Series:
    source = reason.shift(shift) if shift else reason
    result = pd.Series("", index=reason.index, dtype="object")
    for code in _MISSING_REASON_PRIORITY:
        present = source.eq(code).rolling(window, min_periods=window).sum().gt(0.0)
        result = result.mask(result.eq("") & present, code)
    return result


def _compute_one_security(group: pd.DataFrame, calendar: pd.DatetimeIndex, expected_factor_version: str, blocks: tuple[str, ...] = STOCK_BLOCKS) -> pd.DataFrame:
    source = group.copy()
    source["session_date"] = pd.to_datetime(source["session_date"]).dt.normalize()
    if source.duplicated("session_date").any():
        raise FeatureContractError("duplicate security/session bars")
    source = source.set_index("session_date").reindex(calendar)
    source.index.name = "session_date"
    has_bar = source["security_id"].notna()
    price_flag = source["price_usable_for_features"].fillna(False).astype(bool)
    treatment = source["source_treatment_state"].fillna("").astype(str)
    treatment_ok = ~treatment.str.lower().str.contains("unknown|unresolved", regex=True)
    factor_ok = source["factor_version"].eq(expected_factor_version)
    price_flag &= treatment_ok & factor_ok
    close = pd.to_numeric(source.get("split_adjusted_close"), errors="coerce")
    high = pd.to_numeric(source.get("split_adjusted_high"), errors="coerce")
    low = pd.to_numeric(source.get("split_adjusted_low"), errors="coerce")
    volume = pd.to_numeric(source.get("split_adjusted_volume", pd.Series(np.nan, index=source.index)), errors="coerce")
    close_ok = price_flag & _finite_positive(close)
    high_ok = price_flag & _finite_positive(high) & high.ge(close)
    low_ok = price_flag & _finite_positive(low) & low.le(close)
    volume_flag = (
        source["volume_usable_for_relative_volume"].fillna(False).astype(bool)
        if "C" in blocks else pd.Series(False, index=source.index)
    )
    volume_ok = volume_flag & treatment_ok & factor_ok & _finite_positive(volume)
    state_text = (
        source["missing_state"].fillna("").astype(str) + "|" +
        source["nontrading_reason"].fillna("").astype(str) + "|" +
        source["coverage_result"].fillna("").astype(str)
    ).str.lower()
    prelisting = state_text.str.contains("prelist|not_yet", regex=True)
    nontrading = state_text.str.contains("nontrading|non_trading|suspend", regex=True)
    price_reason = pd.Series("", index=source.index, dtype="object")
    price_reason = price_reason.mask(~has_bar, "MISSING_PRICE")
    price_reason = price_reason.mask(has_bar & prelisting, "PRELISTING")
    price_reason = price_reason.mask(has_bar & nontrading, "DOCUMENTED_NON_TRADING")
    price_reason = price_reason.mask(has_bar & ~factor_ok, "INVALID_PRICE_BASIS")
    price_reason = price_reason.mask(has_bar & ~treatment_ok, "SOURCE_TREATMENT_UNRESOLVED")
    price_reason = price_reason.mask(price_reason.eq("") & (~price_flag | ~_finite_positive(close)), "INVALID_PRICE_BASIS")
    high_reason = price_reason.mask(price_reason.eq("") & (~_finite_positive(high) | high.lt(close)), "INVALID_PRICE_BASIS")
    low_reason = price_reason.mask(price_reason.eq("") & (~_finite_positive(low) | low.gt(close)), "INVALID_PRICE_BASIS")
    ohlc_reason = high_reason.mask(high_reason.eq("") & low_reason.ne(""), low_reason)
    volume_reason = price_reason.copy()
    volume_reason = volume_reason.mask(volume_reason.eq("") & ~_finite_positive(volume), "MISSING_VOLUME")
    volume_reason = volume_reason.mask(volume_reason.eq("") & ~volume_flag, "VOLUME_NOT_COMPARABLE")
    safe_close = close.where(close_ok)
    simple = safe_close / safe_close.shift(1) - 1.0
    log_return = np.log(safe_close / safe_close.shift(1))
    output = pd.DataFrame(index=source.index)
    eligible: dict[str, pd.Series] = {}
    failure_state: dict[str, pd.Series] = {}

    if "C" in blocks:
        eligible["proximity_to_max_high_252"] = _rolling_all(close_ok & high_ok, 252)
        failure_state["proximity_to_max_high_252"] = _window_failure_state(high_reason, 252)
        output["proximity_to_max_high_252"] = safe_close / high.where(high_ok).rolling(252, min_periods=252).max()
        eligible["proximity_to_max_close_252"] = _rolling_all(close_ok, 252)
        failure_state["proximity_to_max_close_252"] = _window_failure_state(price_reason, 252)
        output["proximity_to_max_close_252"] = safe_close / safe_close.rolling(252, min_periods=252).max()
        momentum_span_ok = _rolling_all(close_ok.shift(21, fill_value=False), 232)
        eligible["momentum_12_1"] = momentum_span_ok
        failure_state["momentum_12_1"] = _window_failure_state(price_reason, 232, shift=21)
        output["momentum_12_1"] = safe_close.shift(21) / safe_close.shift(252) - 1.0
        eligible["return_5"] = _rolling_all(close_ok, 6)
        failure_state["return_5"] = _window_failure_state(price_reason, 6)
        output["return_5"] = safe_close / safe_close.shift(5) - 1.0
        eligible["realized_volatility_20"] = _rolling_all(close_ok, 21)
        failure_state["realized_volatility_20"] = _window_failure_state(price_reason, 21)
        output["realized_volatility_20"] = simple.rolling(20, min_periods=20).std(ddof=1)
        eligible["relative_volume_20"] = _rolling_all(volume_ok, 20)
        failure_state["relative_volume_20"] = _window_failure_state(volume_reason, 20)
        safe_volume = volume.where(volume_ok)
        output["relative_volume_20"] = safe_volume / safe_volume.rolling(20, min_periods=20).mean() - 1.0

    eligible["stock_log_return_20"] = _rolling_all(close_ok, 21)
    failure_state["stock_log_return_20"] = _window_failure_state(price_reason, 21)
    output["stock_log_return_20"] = np.log(safe_close / safe_close.shift(20))
    eligible["stock_log_return_60"] = _rolling_all(close_ok, 61)
    failure_state["stock_log_return_60"] = _window_failure_state(price_reason, 61)
    output["stock_log_return_60"] = np.log(safe_close / safe_close.shift(60))
    eligible["stock_path_efficiency_20"] = _rolling_all(close_ok, 21)
    failure_state["stock_path_efficiency_20"] = _window_failure_state(price_reason, 21)
    path_denominator = log_return.abs().rolling(20, min_periods=20).sum()
    path_numerator = log_return.rolling(20, min_periods=20).sum().abs()
    output["stock_path_efficiency_20"] = (path_numerator / path_denominator).where(path_denominator.ne(0.0), 0.0)
    eligible["stock_positive_return_share_20"] = _rolling_all(close_ok, 21)
    failure_state["stock_positive_return_share_20"] = _window_failure_state(price_reason, 21)
    output["stock_positive_return_share_20"] = log_return.gt(0.0).rolling(20, min_periods=20).mean()
    eligible["stock_drawdown_depth_60"] = _rolling_all(close_ok, 60)
    failure_state["stock_drawdown_depth_60"] = _window_failure_state(price_reason, 60)
    output["stock_drawdown_depth_60"] = safe_close / safe_close.rolling(60, min_periods=60).max() - 1.0
    eligible["stock_recovery_from_low_60"] = _rolling_all(close_ok, 60)
    failure_state["stock_recovery_from_low_60"] = _window_failure_state(price_reason, 60)
    output["stock_recovery_from_low_60"] = safe_close / safe_close.rolling(60, min_periods=60).min() - 1.0
    eligible["stock_volatility_ratio_20_60"] = _rolling_all(close_ok, 61)
    failure_state["stock_volatility_ratio_20_60"] = _window_failure_state(price_reason, 61)
    vol20 = log_return.rolling(20, min_periods=20).std(ddof=1)
    vol60 = log_return.rolling(60, min_periods=60).std(ddof=1)
    eligible["stock_volatility_ratio_20_60"] &= vol60.gt(0.0)
    output["stock_volatility_ratio_20_60"] = vol20 / vol60.where(vol60.gt(0.0)) - 1.0
    eligible["stock_close_location_value_20"] = _rolling_all(close_ok & high_ok & low_ok, 20)
    failure_state["stock_close_location_value_20"] = _window_failure_state(ohlc_reason, 20)
    envelope_high = high.where(high_ok).rolling(20, min_periods=20).max()
    envelope_low = low.where(low_ok).rolling(20, min_periods=20).min()
    envelope = envelope_high - envelope_low
    eligible["stock_close_location_value_20"] &= envelope.gt(0.0)
    output["stock_close_location_value_20"] = (safe_close - envelope_low) / envelope.where(envelope.gt(0.0))

    position = pd.Series(np.arange(len(output)), index=output.index)
    for name, mask in eligible.items():
        final = mask.fillna(False) & output[name].notna() & np.isfinite(output[name])
        output[name] = output[name].where(final)
        output[f"eligible__{name}"] = final
        if name == "relative_volume_20":
            warmup = position.lt(19)
        else:
            lookback = 253 if name == "momentum_12_1" else {
                "proximity_to_max_high_252": 252,
                "proximity_to_max_close_252": 252,
                "return_5": 6,
                "realized_volatility_20": 21,
                "stock_log_return_20": 21,
                "stock_log_return_60": 61,
                "stock_path_efficiency_20": 21,
                "stock_positive_return_share_20": 21,
                "stock_drawdown_depth_60": 60,
                "stock_recovery_from_low_60": 60,
                "stock_volatility_ratio_20_60": 61,
                "stock_close_location_value_20": 20,
            }[name]
            warmup = position.lt(lookback - 1)
        reason = failure_state[name].where(failure_state[name].ne(""), "INVALID_PRICE_BASIS")
        output[f"missing_state__{name}"] = np.select(
            [final, warmup],
            ["", "INSUFFICIENT_EXACT_LOOKBACK"],
            default=reason,
        )
    return output.reset_index()


def compute_stock_feature_history(
    bars: pd.DataFrame,
    calendar: Iterable[object],
    contract: FrozenD0Contract,
    guard: D1ExecutionGuard,
    context: ExecutionContext,
    *,
    blocks: tuple[str, ...] = STOCK_BLOCKS,
) -> pd.DataFrame:
    _reject_predictive_columns(bars, "stock feature input")
    if not set(blocks).issubset(STOCK_BLOCKS):
        raise FeatureContractError("stock history can compute only C and P blocks")
    operation = Operation.COMPUTE_P_STRUCTURAL if context.classification is ExecutionClass.REAL_STRUCTURAL else Operation.COMPUTE_FEATURE_FIXTURE
    guard.require(operation, context)
    if context.classification is ExecutionClass.REAL_STRUCTURAL and blocks != ("P",):
        raise FeatureContractError("real structural execution may calculate only the registered P block")
    required = {
        "security_id", "session_date", "split_adjusted_close", "split_adjusted_high", "split_adjusted_low",
        "price_usable_for_features", "source_treatment_state", "factor_version", "missing_state",
        "nontrading_reason", "coverage_result",
    }
    if "C" in blocks:
        required.update({"split_adjusted_volume", "volume_usable_for_relative_volume"})
    missing = required - set(bars.columns)
    if missing:
        raise FeatureContractError(f"stock bars missing columns: {sorted(missing)}")
    if bars.duplicated(["security_id", "session_date"]).any():
        raise FeatureContractError("duplicate stock bar semantic keys")
    dates = _calendar(calendar)
    requested = [name for block in blocks for name in contract.feature_blocks[block]]
    outputs: list[pd.DataFrame] = []
    expected_factor_version = str(context.metadata.get("factor_version", ""))
    if not expected_factor_version:
        raise FeatureContractError("execution context does not pin a factor version")
    for security_id, group in bars.groupby("security_id", sort=True, dropna=False):
        if pd.isna(security_id):
            raise FeatureContractError("security_id may not be null")
        calculated = _compute_one_security(group, dates, expected_factor_version, blocks)
        calculated.insert(0, "security_id", str(security_id))
        keep = ["security_id", "session_date"]
        for name in requested:
            keep.extend([name, f"eligible__{name}", f"missing_state__{name}"])
        outputs.append(calculated[keep])
    return pd.concat(outputs, ignore_index=True).sort_values(["session_date", "security_id"], kind="mergesort").reset_index(drop=True)


def attach_information_session_features(
    official_membership: pd.DataFrame,
    stock_history: pd.DataFrame,
    calendar: Iterable[object],
    feature_names: Iterable[str],
) -> pd.DataFrame:
    _reject_predictive_columns(official_membership, "official membership input")
    _reject_predictive_columns(stock_history, "stock feature-history input")
    required = {"security_id", "session_date", "official_membership"}
    if required - set(official_membership.columns):
        raise FeatureContractError("official membership is missing required columns")
    membership = official_membership.loc[official_membership["official_membership"].fillna(False)].copy()
    membership["decision_session"] = pd.to_datetime(membership["session_date"]).dt.normalize()
    if membership.duplicated(["security_id", "decision_session"]).any():
        raise FeatureContractError("duplicate official membership semantic keys")
    counts = membership.groupby("decision_session")["security_id"].nunique()
    row_counts = membership.groupby("decision_session").size()
    if len(counts) == 0 or not counts.eq(60).all() or not row_counts.eq(60).all():
        raise FeatureContractError(f"official decision-session denominator must be 60: {counts[counts.ne(60)].to_dict()}")
    dates = _calendar(calendar)
    prior = pd.Series(dates[:-1], index=dates[1:])
    membership["information_session"] = membership["decision_session"].map(prior)
    if membership["information_session"].isna().any():
        raise FeatureContractError("decision session has no preceding official information session")
    names = list(feature_names)
    columns = ["security_id", "session_date"]
    for name in names:
        columns.extend([name, f"eligible__{name}", f"missing_state__{name}"])
    projected = stock_history[columns].rename(columns={"session_date": "information_session"})
    result = membership.merge(projected, on=["security_id", "information_session"], how="left", validate="many_to_one")
    return result.sort_values(["decision_session", "security_id"], kind="mergesort").reset_index(drop=True)


def compute_x_features(observations: pd.DataFrame, minimum_members: int = 45) -> pd.DataFrame:
    if minimum_members != 45:
        raise FeatureContractError("the frozen cross-sectional minimum is exactly 45")
    _reject_predictive_columns(observations, "X-rank input")
    result = observations.copy()
    if result.duplicated(["security_id", "decision_session"]).any():
        raise FeatureContractError("duplicate X-rank semantic keys")
    expected = result.groupby("decision_session")["security_id"].transform("nunique")
    row_counts = result.groupby("decision_session")["security_id"].transform("size")
    if not expected.eq(60).all() or not row_counts.eq(60).all():
        raise FeatureContractError("X ranks require an official denominator of 60")
    for target, source in X_INPUTS.items():
        if source not in result.columns:
            continue
        source_eligible = result[f"eligible__{source}"].fillna(False) if f"eligible__{source}" in result.columns else result[source].notna()
        source_eligible &= result[source].notna()
        eligible_count = source_eligible.groupby(result["decision_session"]).transform("sum").astype("int64")
        ranked = result[source].where(source_eligible).groupby(result["decision_session"]).rank(method="average", ascending=True)
        value = ranked / eligible_count.where(eligible_count.gt(0))
        valid_session = eligible_count.ge(minimum_members)
        result[target] = value.where(source_eligible & valid_session)
        result[f"eligible__{target}"] = source_eligible & valid_session
        result[f"eligible_count__{target}"] = eligible_count
        result[f"official_expected_count__{target}"] = 60
        source_state = result.get(f"missing_state__{source}", pd.Series("MISSING_PRICE", index=result.index)).fillna("MISSING_PRICE")
        source_state = source_state.where(source_state.isin(FROZEN_EXCLUSION_CODES), "MISSING_PRICE")
        result[f"missing_state__{target}"] = np.select(
            [result[f"eligible__{target}"], eligible_count.lt(minimum_members), ~source_eligible],
            ["", "CROSS_SECTION_BELOW_45", source_state],
            default="MISSING_PRICE",
        )
    return result


def compute_market_features(
    wig: pd.DataFrame,
    bars: pd.DataFrame,
    calendar: Iterable[object],
    decision_sessions: Iterable[object],
    guard: D1ExecutionGuard,
    context: ExecutionContext,
    *,
    minimum_members: int = 45,
) -> pd.DataFrame:
    guard.require(Operation.COMPUTE_FEATURE_FIXTURE, context)
    _reject_predictive_columns(bars, "market feature input")
    _reject_predictive_columns(wig, "WIG feature input")
    if minimum_members != 45:
        raise FeatureContractError("the frozen TOP60 aggregation minimum is exactly 45")
    required = {
        "security_id", "session_date", "split_adjusted_close", "official_membership",
        "price_usable_for_features", "source_treatment_state", "factor_version",
        "missing_state", "nontrading_reason", "coverage_result",
    }
    if required - set(bars.columns):
        raise FeatureContractError(f"market feature bars missing columns: {sorted(required - set(bars.columns))}")
    if bars.duplicated(["security_id", "session_date"]).any():
        raise FeatureContractError("duplicate stock bar semantic keys in market feature input")
    dates = _calendar(calendar)
    wig_frame = wig.copy()
    wig_frame["session_date"] = pd.to_datetime(wig_frame["session_date"]).dt.normalize()
    wig_close = pd.to_numeric(wig_frame.set_index("session_date")["close"].reindex(dates), errors="coerce")
    wig_ok = _finite_positive(wig_close)
    wig_log = np.log(wig_close)
    wig_return = wig_log.diff()
    wig_features = pd.DataFrame(index=dates)
    wig_features["wig_log_return_20"] = wig_log - wig_log.shift(20)
    wig_features["wig_log_return_60"] = wig_log - wig_log.shift(60)
    wig_features["wig_trend_200"] = wig_close / wig_close.rolling(200, min_periods=200).mean() - 1.0
    wig_features["wig_trend_acceleration_20_60"] = wig_features["wig_log_return_20"] / 20.0 - wig_features["wig_log_return_60"] / 60.0
    wig_features["wig_drawdown_252"] = wig_close / wig_close.rolling(252, min_periods=252).max() - 1.0
    wig_features["wig_downside_semivolatility_20"] = np.sqrt(wig_return.clip(upper=0.0).pow(2).rolling(20, min_periods=20).mean()) * math.sqrt(252.0)
    wig_vol20 = wig_return.rolling(20, min_periods=20).std(ddof=1)
    wig_vol60 = wig_return.rolling(60, min_periods=60).std(ddof=1)
    wig_features["wig_volatility_ratio_20_60"] = wig_vol20 / wig_vol60.where(wig_vol60.gt(0.0)) - 1.0
    wig_requirements = {"wig_log_return_20": 21, "wig_log_return_60": 61, "wig_trend_200": 200, "wig_trend_acceleration_20_60": 61, "wig_drawdown_252": 252, "wig_downside_semivolatility_20": 21, "wig_volatility_ratio_20_60": 61}
    for name, window in wig_requirements.items():
        wig_features[name] = wig_features[name].where(_rolling_all(wig_ok, window))

    source = bars.copy()
    source["session_date"] = pd.to_datetime(source["session_date"]).dt.normalize()
    expected_factor_version = str(context.metadata.get("factor_version", ""))
    if not expected_factor_version:
        raise FeatureContractError("execution context does not pin a factor version")
    official = source.loc[source["official_membership"].fillna(False)].copy()
    close = source.pivot(index="session_date", columns="security_id", values="split_adjusted_close").reindex(dates)
    source_valid = source["price_usable_for_features"].fillna(False).astype(bool)
    source_treatment = source["source_treatment_state"].fillna("").astype(str)
    source_treatment_ok = ~source_treatment.str.lower().str.contains("unknown|unresolved", regex=True)
    factor_ok = source["factor_version"].eq(expected_factor_version)
    source_valid &= source_treatment_ok & factor_ok
    state_text = (
        source["missing_state"].fillna("").astype(str) + "|" +
        source["nontrading_reason"].fillna("").astype(str) + "|" +
        source["coverage_result"].fillna("").astype(str)
    ).str.lower()
    source_reason = pd.Series("", index=source.index, dtype="object")
    source_reason = source_reason.mask(state_text.str.contains("prelist|not_yet", regex=True), "PRELISTING")
    source_reason = source_reason.mask(state_text.str.contains("nontrading|non_trading|suspend", regex=True), "DOCUMENTED_NON_TRADING")
    source_reason = source_reason.mask(~factor_ok, "INVALID_PRICE_BASIS")
    source_reason = source_reason.mask(~source_treatment_ok, "SOURCE_TREATMENT_UNRESOLVED")
    source_reason = source_reason.mask(source_reason.eq("") & (~source_valid | ~_finite_positive(source["split_adjusted_close"])), "MISSING_PRICE")
    valid = source.assign(_valid=source_valid).pivot(index="session_date", columns="security_id", values="_valid").reindex(dates).fillna(False).astype(bool)
    reasons = source.assign(_reason=source_reason).pivot(index="session_date", columns="security_id", values="_reason").reindex(dates).fillna("MISSING_PRICE")
    close = close.where(valid & close.apply(_finite_positive))
    log_close = np.log(close)
    daily = log_close.diff()
    official_by_date = {date: group for date, group in official.groupby("session_date", sort=False)}
    position = {date: index for index, date in enumerate(dates)}
    requested_decisions = pd.DatetimeIndex(pd.to_datetime(list(decision_sessions))).normalize().sort_values().unique()
    expanded_decisions = set(requested_decisions)
    for decision in requested_decisions:
        pos = position.get(decision)
        if pos is not None and pos >= 10:
            expanded_decisions.add(dates[pos - 10])
    rows: list[dict[str, object]] = []
    for decision in sorted(expanded_decisions):
        pos = position.get(decision)
        if pos is None or pos == 0:
            raise FeatureContractError("decision session is absent from the official calendar")
        info = dates[pos - 1]
        members = official_by_date.get(info)
        if members is None or len(members) != 60 or members["security_id"].nunique() != 60:
            raise FeatureContractError(f"information-session official denominator is not 60 on {info.date()}")
        ids = sorted(members["security_id"].astype(str).unique())
        record: dict[str, object] = {"decision_session": decision, "information_session": info, "official_expected_count": 60}
        for name in wig_requirements:
            record[name] = wig_features.at[info, name]
            record[f"eligible_count__{name}"] = int(pd.notna(record[name]))
            record[f"official_expected_count__{name}"] = 1
            record[f"excluded_count__{name}"] = int(pd.isna(record[name]))
            record[f"exclusion_reason_counts__{name}"] = "{}" if pd.notna(record[name]) else '{"MARKET_FEATURE_UNAVAILABLE":1}'
            record[f"aggregation_state__{name}"] = "" if pd.notna(record[name]) else "MARKET_FEATURE_UNAVAILABLE"
        def endpoint_returns(horizon: int) -> tuple[pd.Series, str]:
            start = pos - 1 - horizon
            if start < 0:
                return pd.Series(dtype=float), json.dumps({"INSUFFICIENT_EXACT_LOOKBACK": 60}, separators=(",", ":"))
            history = log_close.loc[dates[start]:info, ids]
            usable = history.notna().all(axis=0)
            excluded: list[str] = []
            reason_history = reasons.loc[dates[start]:info, ids]
            for security_id in usable.index[~usable]:
                values = reason_history[security_id]
                code = next((item for item in _MISSING_REASON_PRIORITY if values.eq(item).any()), "MISSING_PRICE")
                excluded.append(code)
            return (history.iloc[-1] - history.iloc[0]).loc[usable], json.dumps(dict(sorted(pd.Series(excluded).value_counts().to_dict().items())), separators=(",", ":"))
        ret20, excluded20 = endpoint_returns(20)
        ret60, excluded60 = endpoint_returns(60)
        record["eligible_count__top60_breadth_positive_60"] = len(ret60)
        record["official_expected_count__top60_breadth_positive_60"] = 60
        record["excluded_count__top60_breadth_positive_60"] = 60 - len(ret60)
        record["exclusion_reason_counts__top60_breadth_positive_60"] = excluded60
        record["top60_breadth_positive_60"] = float((ret60 > 0.0).mean()) if len(ret60) >= minimum_members else np.nan
        record["aggregation_state__top60_breadth_positive_60"] = "" if len(ret60) >= minimum_members else "CROSS_SECTION_BELOW_45"
        record["eligible_count__top60_return_dispersion_20"] = len(ret20)
        record["official_expected_count__top60_return_dispersion_20"] = 60
        record["excluded_count__top60_return_dispersion_20"] = 60 - len(ret20)
        record["exclusion_reason_counts__top60_return_dispersion_20"] = excluded20
        record["top60_return_dispersion_20"] = float(ret20.quantile(0.75, interpolation="linear") - ret20.quantile(0.25, interpolation="linear")) if len(ret20) >= minimum_members else np.nan
        record["aggregation_state__top60_return_dispersion_20"] = "" if len(ret20) >= minimum_members else "CROSS_SECTION_BELOW_45"
        positive = ret20.loc[ret20.gt(0.0)].sort_values(ascending=False)
        record["eligible_count__top60_positive_leadership_share_20"] = len(ret20)
        record["official_expected_count__top60_positive_leadership_share_20"] = 60
        record["excluded_count__top60_positive_leadership_share_20"] = 60 - len(ret20)
        record["exclusion_reason_counts__top60_positive_leadership_share_20"] = excluded20
        record["top60_positive_leadership_share_20"] = float(positive.head(5).sum() / positive.sum()) if len(ret20) >= minimum_members and positive.sum() > 0 else np.nan
        record["aggregation_state__top60_positive_leadership_share_20"] = (
            "" if pd.notna(record["top60_positive_leadership_share_20"])
            else ("CROSS_SECTION_BELOW_45" if len(ret20) < minimum_members else "MARKET_FEATURE_UNAVAILABLE")
        )
        start = pos - 60
        vectors: list[np.ndarray] = []
        if start >= 0:
            history = daily.loc[dates[start]:info, ids]
            for security_id in ids:
                vector = history[security_id]
                if len(vector) == 60 and vector.notna().all() and vector.std(ddof=1) > 0.0:
                    vectors.append(vector.to_numpy(dtype=float))
        record["eligible_count__top60_average_pairwise_correlation_60"] = len(vectors)
        record["official_expected_count__top60_average_pairwise_correlation_60"] = 60
        record["excluded_count__top60_average_pairwise_correlation_60"] = 60 - len(vectors)
        pair_reasons = json.loads(excluded60)
        if len(ret60) > len(vectors):
            pair_reasons["MARKET_FEATURE_UNAVAILABLE"] = len(ret60) - len(vectors)
        record["exclusion_reason_counts__top60_average_pairwise_correlation_60"] = json.dumps(dict(sorted(pair_reasons.items())), separators=(",", ":"))
        if len(vectors) >= minimum_members:
            corr = np.corrcoef(np.column_stack(vectors), rowvar=False)
            upper = corr[np.triu_indices_from(corr, k=1)]
            record["top60_average_pairwise_correlation_60"] = float(upper.mean()) if np.isfinite(upper).all() else np.nan
        else:
            record["top60_average_pairwise_correlation_60"] = np.nan
        record["aggregation_state__top60_average_pairwise_correlation_60"] = "" if pd.notna(record["top60_average_pairwise_correlation_60"]) else ("CROSS_SECTION_BELOW_45" if len(vectors) < minimum_members else "MARKET_FEATURE_UNAVAILABLE")
        rows.append(record)
    result = pd.DataFrame(rows).sort_values("decision_session").reset_index(drop=True)
    breadth = result.set_index("decision_session")["top60_breadth_positive_60"]
    breadth_count = result.set_index("decision_session")["eligible_count__top60_breadth_positive_60"]
    prior_decisions = result["decision_session"].map(lambda value: dates[position[value] - 10] if position[value] >= 10 else pd.NaT)
    result["top60_breadth_change_10"] = result["top60_breadth_positive_60"] - prior_decisions.map(breadth)
    result["eligible_count__top60_breadth_change_10"] = np.minimum(
        result["eligible_count__top60_breadth_positive_60"],
        prior_decisions.map(breadth_count),
    )
    result["eligible_count_current__top60_breadth_change_10"] = result["eligible_count__top60_breadth_positive_60"]
    result["eligible_count_lag10__top60_breadth_change_10"] = prior_decisions.map(breadth_count)
    result["official_expected_count__top60_breadth_change_10"] = 60
    result["excluded_count_current__top60_breadth_change_10"] = 60 - result["eligible_count_current__top60_breadth_change_10"]
    result["excluded_count_lag10__top60_breadth_change_10"] = 60 - result["eligible_count_lag10__top60_breadth_change_10"]
    prior_exclusions = result.set_index("decision_session")["exclusion_reason_counts__top60_breadth_positive_60"]
    result["exclusion_reason_counts_current__top60_breadth_change_10"] = result["exclusion_reason_counts__top60_breadth_positive_60"]
    result["exclusion_reason_counts_lag10__top60_breadth_change_10"] = prior_decisions.map(prior_exclusions)
    result["excluded_count__top60_breadth_change_10"] = 60 - result["eligible_count__top60_breadth_change_10"]
    result["exclusion_reason_counts__top60_breadth_change_10"] = result.apply(
        lambda row: json.dumps({"current": row["exclusion_reason_counts_current__top60_breadth_change_10"], "lag10": row["exclusion_reason_counts_lag10__top60_breadth_change_10"]}, sort_keys=True, separators=(",", ":")),
        axis=1,
    )
    result["aggregation_state__top60_breadth_change_10"] = np.where(result["top60_breadth_change_10"].notna(), "", "MARKET_FEATURE_UNAVAILABLE")
    return result.loc[result["decision_session"].isin(requested_decisions)].reset_index(drop=True)


def feature_code_fingerprints(contract: FrozenD0Contract) -> dict[str, str]:
    implementation = inspect.getsource(_compute_one_security) + inspect.getsource(compute_x_features) + inspect.getsource(compute_market_features)
    fingerprints: dict[str, str] = {}
    for name in contract.registry_order:
        payload = json.dumps(contract.feature_specs[name], sort_keys=True, separators=(",", ":")) + implementation
        fingerprints[name] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return fingerprints
