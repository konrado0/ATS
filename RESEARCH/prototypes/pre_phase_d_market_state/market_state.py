from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


WIG_FEATURES = [
    "wig_log_return_20",
    "wig_log_return_60",
    "wig_trend_200",
    "wig_trend_acceleration_20_60",
    "wig_drawdown_252",
    "wig_downside_semivolatility_20",
    "wig_volatility_ratio_20_60",
]

TOP60_FEATURES = [
    "top60_breadth_positive_60",
    "top60_breadth_change_10",
    "top60_return_dispersion_20",
    "top60_average_pairwise_correlation_60",
    "top60_positive_leadership_share_20",
]

OPTIONAL_FEATURES = ["top60_share_within_5pct_high_252"]
BLOCK_FEATURES = WIG_FEATURES + TOP60_FEATURES
ALL_FEATURES = BLOCK_FEATURES + OPTIONAL_FEATURES

ADVERSE_LOW = {
    "wig_log_return_20",
    "wig_log_return_60",
    "wig_trend_200",
    "wig_trend_acceleration_20_60",
    "wig_drawdown_252",
    "top60_breadth_positive_60",
    "top60_breadth_change_10",
    "top60_share_within_5pct_high_252",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def stable_frame_hash(frame: pd.DataFrame, sort_by: Iterable[str] | None = None) -> str:
    work = frame.copy()
    if sort_by:
        work = work.sort_values(list(sort_by), kind="mergesort")
    work = work.reset_index(drop=True)
    for column in work.columns:
        if pd.api.types.is_datetime64_any_dtype(work[column]):
            work[column] = pd.to_datetime(work[column]).dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
        elif pd.api.types.is_float_dtype(work[column]):
            work[column] = work[column].map(lambda x: None if pd.isna(x) else format(float(x), ".17g"))
    def json_value(value: Any) -> Any:
        if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
            return None
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        if isinstance(value, np.generic):
            return value.item()
        return value
    records = [{key: json_value(value) for key, value in row.items()} for row in work.to_dict(orient="records")]
    payload = {"columns": list(work.columns), "rows": records}
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def read_stooq_wig(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    expected = ["<TICKER>", "<PER>", "<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>", "<VOL>", "<OPENINT>"]
    if list(raw.columns) != expected:
        raise ValueError(f"Unexpected WIG schema: {list(raw.columns)}")
    result = pd.DataFrame(
        {
            "session_date": pd.to_datetime(raw["<DATE>"].astype(str), format="%Y%m%d", errors="raise"),
            "ticker": raw["<TICKER>"].astype(str),
            "period": raw["<PER>"].astype(str),
            "open": pd.to_numeric(raw["<OPEN>"], errors="raise"),
            "high": pd.to_numeric(raw["<HIGH>"], errors="raise"),
            "low": pd.to_numeric(raw["<LOW>"], errors="raise"),
            "close": pd.to_numeric(raw["<CLOSE>"], errors="raise"),
            "volume": pd.to_numeric(raw["<VOL>"], errors="raise"),
        }
    )
    return result


def validate_wig(local: pd.DataFrame, accepted: pd.DataFrame, official_dates: pd.DatetimeIndex, rtol: float, atol: float) -> tuple[dict[str, Any], pd.DataFrame]:
    checks: dict[str, Any] = {}
    checks["rows"] = int(len(local))
    checks["min_date"] = local["session_date"].min().date().isoformat()
    checks["max_date"] = local["session_date"].max().date().isoformat()
    checks["ticker_values"] = sorted(local["ticker"].unique().tolist())
    checks["period_values"] = sorted(local["period"].unique().tolist())
    checks["duplicate_dates"] = int(local["session_date"].duplicated().sum())
    checks["chronology_violations"] = int((local["session_date"].diff().dropna() <= pd.Timedelta(0)).sum())
    finite = np.isfinite(local[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)).all(axis=1)
    checks["nonfinite_rows"] = int((~finite).sum())
    checks["nonpositive_ohlc_rows"] = int((local[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
    checks["negative_volume_rows"] = int((local["volume"] < 0).sum())
    checks["high_consistency_violations"] = int((local["high"] < local[["open", "close", "low"]].max(axis=1)).sum())
    checks["low_consistency_violations"] = int((local["low"] > local[["open", "close", "high"]].min(axis=1)).sum())
    local_dates = pd.DatetimeIndex(local["session_date"])
    missing_official = official_dates.difference(local_dates)
    checks["official_calendar_dates"] = int(len(official_dates))
    checks["official_calendar_missing"] = int(len(missing_official))
    checks["official_calendar_missing_dates"] = [d.date().isoformat() for d in missing_official]

    accepted_work = accepted[["session_date", "open", "high", "low", "close", "volume"]].copy()
    accepted_work["session_date"] = pd.to_datetime(accepted_work["session_date"])
    overlap = accepted_work.merge(
        local[["session_date", "open", "high", "low", "close", "volume"]],
        on="session_date",
        how="left",
        suffixes=("_accepted", "_local"),
        validate="one_to_one",
    )
    checks["accepted_overlap_rows"] = int(len(overlap))
    checks["accepted_missing_in_local"] = int(overlap["close_local"].isna().sum())
    differences: dict[str, Any] = {}
    mismatch_rows = np.zeros(len(overlap), dtype=bool)
    for column in ["open", "high", "low", "close", "volume"]:
        a = overlap[f"{column}_accepted"].to_numpy(dtype=float)
        b = overlap[f"{column}_local"].to_numpy(dtype=float)
        close = np.isclose(a, b, rtol=rtol, atol=atol, equal_nan=False)
        mismatch_rows |= ~close
        differences[column] = {
            "mismatch_count": int((~close).sum()),
            "max_abs_difference": float(np.nanmax(np.abs(a - b))) if len(a) else 0.0,
        }
    checks["overlap_differences"] = differences
    checks["overlap_mismatch_rows"] = int(mismatch_rows.sum())
    checks["extension_rows"] = int((local["session_date"] > accepted_work["session_date"].max()).sum())
    checks["extension_min_date"] = (
        local.loc[local["session_date"] > accepted_work["session_date"].max(), "session_date"].min().date().isoformat()
        if checks["extension_rows"] else None
    )
    checks["extension_max_date"] = local["session_date"].max().date().isoformat()
    failure_fields = [
        "duplicate_dates", "chronology_violations", "nonfinite_rows", "nonpositive_ohlc_rows",
        "negative_volume_rows", "high_consistency_violations", "low_consistency_violations",
        "official_calendar_missing", "accepted_missing_in_local", "overlap_mismatch_rows",
    ]
    checks["status"] = "PASS" if all(checks[field] == 0 for field in failure_fields) and checks["ticker_values"] == ["WIG"] and checks["period_values"] == ["D"] else "FAIL"
    return checks, overlap


def compute_wig_features(wig: pd.DataFrame, volatility_ratio_centered: bool = True) -> pd.DataFrame:
    result = wig[["session_date", "close"]].sort_values("session_date").reset_index(drop=True).copy()
    close = result["close"].astype(float)
    log_close = np.log(close)
    returns = log_close.diff()
    result["wig_log_return_20"] = log_close - log_close.shift(20)
    result["wig_log_return_60"] = log_close - log_close.shift(60)
    result["wig_trend_200"] = close / close.rolling(200, min_periods=200).mean() - 1.0
    result["wig_trend_acceleration_20_60"] = result["wig_log_return_20"] / 20.0 - result["wig_log_return_60"] / 60.0
    result["wig_drawdown_252"] = close / close.rolling(252, min_periods=252).max() - 1.0
    downside_sq = returns.clip(upper=0.0).pow(2)
    result["wig_downside_semivolatility_20"] = np.sqrt(downside_sq.rolling(20, min_periods=20).mean()) * math.sqrt(252.0)
    vol20 = returns.rolling(20, min_periods=20).std(ddof=1)
    vol60 = returns.rolling(60, min_periods=60).std(ddof=1)
    ratio = vol20 / vol60.where(vol60 != 0.0)
    result["wig_volatility_ratio_20_60"] = ratio - 1.0 if volatility_ratio_centered else ratio
    return result


def _excluded_state(candidate_by_date: dict[pd.Timestamp, pd.DataFrame], information_date: pd.Timestamp, isin: str, history: pd.Series, lookback: int) -> str:
    current = candidate_by_date.get(information_date)
    if current is not None:
        match = current.loc[current["isin"].eq(isin)]
        if len(match):
            row = match.iloc[0]
            for column in ["missing_state", "nontrading_reason", "coverage_result"]:
                if column in row and pd.notna(row[column]) and str(row[column]).strip():
                    value = str(row[column]).strip()
                    if value not in {"covered", "nan"}:
                        return value
    missing = int(history.isna().sum())
    return f"insufficient_exact_{lookback}_history:{missing}_missing"


def compute_top60_features(
    candidate: pd.DataFrame,
    wig_calendar: pd.DatetimeIndex,
    decision_dates: pd.DatetimeIndex,
    minimum_usable: int,
    leadership_positive_name_count: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidate = candidate.copy()
    candidate["session_date"] = pd.to_datetime(candidate["session_date"])
    candidate["isin"] = candidate["isin"].astype(str)
    candidate = candidate.sort_values(["session_date", "isin"], kind="mergesort")
    official = candidate.loc[candidate["official_membership"].fillna(False)].copy()
    official_by_date = {date: group.copy() for date, group in official.groupby("session_date", sort=False)}
    candidate_by_date = {date: group.copy() for date, group in candidate.groupby("session_date", sort=False)}
    closes = candidate.pivot_table(index="session_date", columns="isin", values="split_adjusted_close", aggfunc="first").reindex(wig_calendar)
    closes = closes.where(np.isfinite(closes) & (closes > 0.0))
    log_closes = np.log(closes)
    daily_returns = log_closes.diff()
    calendar_position = {date: i for i, date in enumerate(wig_calendar)}
    rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []

    for decision_date in decision_dates:
        pos = calendar_position.get(decision_date)
        if pos is None or pos == 0:
            continue
        information_date = wig_calendar[pos - 1]
        members = official_by_date.get(information_date)
        if members is None:
            rows.append({"decision_session": decision_date, "information_session": information_date})
            continue
        member_isins = sorted(members["isin"].tolist())
        if len(member_isins) != 60:
            raise ValueError(f"Official denominator is {len(member_isins)} on {information_date.date()}")
        record: dict[str, Any] = {
            "decision_session": decision_date,
            "information_session": information_date,
            "official_denominator": 60,
        }

        definitions = {
            "ret20": (20, log_closes, lambda hist: float(hist.iloc[-1] - hist.iloc[0])),
            "ret60": (60, log_closes, lambda hist: float(hist.iloc[-1] - hist.iloc[0])),
            "ret252": (252, log_closes, lambda hist: float(hist.iloc[-1] - hist.iloc[0])),
        }
        values: dict[str, dict[str, float]] = {}
        excluded: dict[str, list[str]] = {}
        for key, (lookback, matrix, transform) in definitions.items():
            start = pos - 1 - lookback
            end = pos - 1
            values[key] = {}
            excluded[key] = []
            if start < 0:
                excluded[key] = [f"{isin}:calendar_warmup_unavailable" for isin in member_isins]
                continue
            for isin in member_isins:
                history = matrix.loc[wig_calendar[start]:wig_calendar[end], isin] if isin in matrix.columns else pd.Series(dtype=float)
                if len(history) == lookback + 1 and history.notna().all():
                    values[key][isin] = transform(history)
                else:
                    excluded[key].append(f"{isin}:{_excluded_state(candidate_by_date, information_date, isin, history, lookback)}")

        ret20 = pd.Series(values["ret20"], dtype=float)
        ret60 = pd.Series(values["ret60"], dtype=float)
        ret252 = pd.Series(values["ret252"], dtype=float)

        def store_coverage(
            feature: str,
            usable: int,
            excluded_values: list[str],
            valid: bool,
            missing_state: str = "",
            positive_observation_count: int | None = None,
        ) -> None:
            coverage_rows.append(
                {
                    "decision_session": decision_date,
                    "information_session": information_date,
                    "feature": feature,
                    "official_denominator": 60,
                    "usable_count": usable,
                    "excluded_count": 60 - usable,
                    "excluded_member_states": "|".join(sorted(excluded_values)),
                    "feature_valid": bool(valid),
                    "feature_missing_state": missing_state,
                    "aggregation_denominator": usable,
                    "lag10_aggregation_denominator": np.nan,
                    "unavailable_members_in_aggregation": 0,
                    "positive_observation_count": positive_observation_count,
                }
            )

        breadth_valid = len(ret60) >= minimum_usable
        record["top60_breadth_positive_60"] = float((ret60 > 0.0).mean()) if breadth_valid else np.nan
        store_coverage(
            "top60_breadth_positive_60", len(ret60), excluded["ret60"], breadth_valid,
            "" if breadth_valid else "minimum_usable_not_met", int((ret60 > 0.0).sum()),
        )

        dispersion_valid = len(ret20) >= minimum_usable and len(ret20) >= 2
        record["top60_return_dispersion_20"] = float(ret20.quantile(0.75, interpolation="linear") - ret20.quantile(0.25, interpolation="linear")) if dispersion_valid else np.nan
        store_coverage("top60_return_dispersion_20", len(ret20), excluded["ret20"], dispersion_valid, "" if dispersion_valid else "minimum_usable_not_met")

        positive = ret20[ret20 > 0.0].sort_values(ascending=False)
        leadership_valid = len(ret20) >= minimum_usable and float(positive.sum()) > 0.0
        record["top60_positive_leadership_share_20"] = float(positive.head(leadership_positive_name_count).sum() / positive.sum()) if leadership_valid else np.nan
        leadership_missing = "" if leadership_valid else ("no_positive_leadership_denominator" if len(ret20) >= minimum_usable else "minimum_usable_not_met")
        store_coverage(
            "top60_positive_leadership_share_20", len(ret20), excluded["ret20"],
            leadership_valid, leadership_missing, int(len(positive)),
        )

        high_values: dict[str, float] = {}
        high_excluded: list[str] = []
        start252 = pos - 1 - 251
        if start252 >= 0:
            for isin in member_isins:
                history = closes.loc[wig_calendar[start252]:wig_calendar[pos - 1], isin] if isin in closes.columns else pd.Series(dtype=float)
                if len(history) == 252 and history.notna().all():
                    high_values[isin] = float(history.iloc[-1] / history.max())
                else:
                    high_excluded.append(f"{isin}:{_excluded_state(candidate_by_date, information_date, isin, history, 252)}")
        else:
            high_excluded = [f"{isin}:calendar_warmup_unavailable" for isin in member_isins]
        high_series = pd.Series(high_values, dtype=float)
        high_valid = len(high_series) >= minimum_usable
        record["top60_share_within_5pct_high_252"] = float((high_series >= 0.95).mean()) if high_valid else np.nan
        store_coverage(
            "top60_share_within_5pct_high_252", len(high_series), high_excluded, high_valid,
            "" if high_valid else "minimum_usable_not_met", int((high_series >= 0.95).sum()),
        )

        corr_vectors: dict[str, np.ndarray] = {}
        corr_excluded: list[str] = []
        start_ret = pos - 60
        if start_ret >= 0:
            for isin in member_isins:
                history = daily_returns.loc[wig_calendar[start_ret]:wig_calendar[pos - 1], isin] if isin in daily_returns.columns else pd.Series(dtype=float)
                if len(history) == 60 and history.notna().all():
                    vector = history.to_numpy(dtype=float)
                    if np.std(vector, ddof=1) > 0.0:
                        corr_vectors[isin] = vector
                    else:
                        corr_excluded.append(f"{isin}:zero_return_variance")
                else:
                    corr_excluded.append(f"{isin}:{_excluded_state(candidate_by_date, information_date, isin, history, 60)}")
        else:
            corr_excluded = [f"{isin}:calendar_warmup_unavailable" for isin in member_isins]
        corr_valid = len(corr_vectors) >= minimum_usable
        corr_value = np.nan
        corr_missing = "minimum_usable_not_met"
        if corr_valid:
            matrix = np.column_stack([corr_vectors[key] for key in sorted(corr_vectors)])
            corr = np.corrcoef(matrix, rowvar=False)
            upper = corr[np.triu_indices_from(corr, k=1)]
            if len(upper) == len(corr_vectors) * (len(corr_vectors) - 1) // 2 and np.isfinite(upper).all():
                corr_value = float(upper.mean())
                corr_missing = ""
            else:
                corr_valid = False
                corr_missing = "nonfinite_or_incomplete_pairwise_correlations"
        record["top60_average_pairwise_correlation_60"] = corr_value
        store_coverage("top60_average_pairwise_correlation_60", len(corr_vectors), corr_excluded, corr_valid, corr_missing)
        rows.append(record)

    features = pd.DataFrame(rows).sort_values("decision_session").reset_index(drop=True)
    features["top60_breadth_change_10"] = features["top60_breadth_positive_60"] - features["top60_breadth_positive_60"].shift(10)
    coverage = pd.DataFrame(coverage_rows)
    breadth_cov = coverage.loc[coverage["feature"].eq("top60_breadth_positive_60")].sort_values("decision_session").reset_index(drop=True)
    change_cov = breadth_cov.copy()
    change_cov["feature"] = "top60_breadth_change_10"
    prior_valid = breadth_cov["feature_valid"].shift(10).fillna(False)
    change_cov["feature_valid"] = breadth_cov["feature_valid"] & prior_valid
    change_cov["usable_count"] = np.minimum(breadth_cov["usable_count"], breadth_cov["usable_count"].shift(10).fillna(0)).astype(int)
    change_cov["excluded_count"] = 60 - change_cov["usable_count"]
    change_cov["aggregation_denominator"] = breadth_cov["aggregation_denominator"]
    change_cov["lag10_aggregation_denominator"] = breadth_cov["aggregation_denominator"].shift(10)
    change_cov["unavailable_members_in_aggregation"] = 0
    change_cov["positive_observation_count"] = np.nan
    change_cov["feature_missing_state"] = np.where(change_cov["feature_valid"], "", "current_or_lag10_breadth_invalid")
    change_cov["excluded_member_states"] = np.where(
        change_cov["feature_valid"], "",
        breadth_cov["excluded_member_states"].fillna("") + "|lag10:" + breadth_cov["excluded_member_states"].shift(10).fillna("unavailable"),
    )
    coverage = pd.concat([coverage, change_cov], ignore_index=True).sort_values(["decision_session", "feature"]).reset_index(drop=True)
    return features, coverage


def drawdown_episodes(series: pd.Series) -> pd.DataFrame:
    values = series.dropna().astype(float).sort_index()
    if values.empty:
        return pd.DataFrame()
    running_max = values.cummax()
    underwater = values / running_max - 1.0
    rows: list[dict[str, Any]] = []
    in_episode = False
    start_pos = 0
    dates = values.index
    for i, value in enumerate(underwater.to_numpy()):
        if value < 0.0 and not in_episode:
            in_episode = True
            start_pos = max(i - 1, 0)
        recovered = in_episode and value >= -1e-15
        final = in_episode and i == len(values) - 1
        if recovered or final:
            segment_end = i if recovered else i + 1
            segment = values.iloc[start_pos:segment_end]
            peak_value = float(values.iloc[start_pos])
            relative = segment / peak_value - 1.0
            trough_date = relative.idxmin()
            recovery_date = dates[i] if recovered else pd.NaT
            rows.append(
                {
                    "peak_date": dates[start_pos],
                    "trough_date": trough_date,
                    "recovery_date": recovery_date,
                    "drawdown": float(relative.loc[trough_date]),
                    "recovered": bool(recovered),
                }
            )
            in_episode = False
    return pd.DataFrame(rows)


def safe_spearman(x: pd.Series, y: pd.Series) -> float:
    valid = pd.concat([x, y], axis=1).dropna()
    if len(valid) < 3 or valid.iloc[:, 0].nunique() < 2 or valid.iloc[:, 1].nunique() < 2:
        return np.nan
    return float(valid.iloc[:, 0].rank(method="average").corr(valid.iloc[:, 1].rank(method="average")))


def assign_tercile(series: pd.Series) -> pd.Series:
    valid = series.notna()
    output = pd.Series(pd.NA, index=series.index, dtype="Int64")
    if valid.any():
        percentile = series.loc[valid].rank(method="average", pct=True)
        output.loc[valid] = np.ceil(percentile * 3.0).clip(1, 3).astype("Int64")
    return output


def adverse_percentile(series: pd.Series, feature: str) -> pd.Series:
    percentile = series.rank(method="average", pct=True)
    return 1.0 - percentile if feature in ADVERSE_LOW else percentile


def moving_block_indices(n: int, block: int, samples: int, seed: int) -> list[np.ndarray]:
    if n <= 0:
        return []
    if n < block:
        return [np.arange(n, dtype=int) for _ in range(samples)]
    rng = np.random.default_rng(seed)
    starts = np.arange(n - block + 1)
    blocks_needed = math.ceil(n / block)
    output = []
    for _ in range(samples):
        chosen = rng.choice(starts, size=blocks_needed, replace=True)
        index = np.concatenate([np.arange(start, start + block) for start in chosen])[:n]
        output.append(index)
    return output


def percentile_interval(values: list[float], confidence: float) -> tuple[float, float]:
    clean = np.asarray([value for value in values if np.isfinite(value)], dtype=float)
    if not len(clean):
        return np.nan, np.nan
    alpha = (1.0 - confidence) / 2.0
    return float(np.quantile(clean, alpha)), float(np.quantile(clean, 1.0 - alpha))
