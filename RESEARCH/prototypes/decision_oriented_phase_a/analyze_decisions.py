from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


HORIZONS = (3, 5, 10, 20)
LABELS = {h: f"label__forward_return_{h}__v1" for h in HORIZONS}
MOMENTUM = "feature__momentum_12_1__v1"
MOMENTUM_PCT = "percentile_rank__momentum_12_1__v1"
MOMENTUM_Q = "quantile__momentum_12_1__v1"
RETURN_5 = "feature__return_5__v1"
EXIT_ISINS = ("PLLOTOS00025", "PLPGNIG00014", "PLSTSHL00012", "PLCIECH00018", "PLTIM0000016")
SEED = 20260820


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(json_safe(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def safe_spearman(group: pd.DataFrame, left: str, right: str) -> float:
    valid = group[[left, right]].dropna()
    if len(valid) < 3 or valid[left].nunique() < 2 or valid[right].nunique() < 2:
        return np.nan
    x = valid[left].rank(method="average").to_numpy(float).copy()
    y = valid[right].rank(method="average").to_numpy(float).copy()
    x -= x.mean()
    y -= y.mean()
    denominator = math.sqrt(float(np.dot(x, x) * np.dot(y, y)))
    return float(np.dot(x, y) / denominator) if denominator else np.nan


def session_ic(frame: pd.DataFrame, feature: str, label: str) -> pd.DataFrame:
    rows = []
    for session, group in frame.groupby("session_date", sort=True):
        valid = group[[feature, label]].dropna()
        rows.append(
            {
                "session_date": session,
                "constituent_observations": len(valid),
                "rank_ic": safe_spearman(valid, feature, label),
            }
        )
    return pd.DataFrame(rows)


def summarize_ic(daily: pd.DataFrame, extra: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for period_type, period, subset in [("overall", "all", daily)]:
        clean = subset["rank_ic"].dropna()
        rows.append(
            extra
            | {
                "period_type": period_type,
                "period": period,
                "mean_rank_ic": clean.mean(),
                "median_rank_ic": clean.median(),
                "sessions": len(clean),
                "constituent_observations": int(subset.loc[subset["rank_ic"].notna(), "constituent_observations"].sum()),
                "positive_session_share": float((clean > 0).mean()) if len(clean) else np.nan,
            }
        )
    for year, subset in daily.groupby(daily["session_date"].dt.year, sort=True):
        clean = subset["rank_ic"].dropna()
        rows.append(
            extra
            | {
                "period_type": "calendar_year",
                "period": str(year),
                "mean_rank_ic": clean.mean(),
                "median_rank_ic": clean.median(),
                "sessions": len(clean),
                "constituent_observations": int(subset.loc[subset["rank_ic"].notna(), "constituent_observations"].sum()),
                "positive_session_share": float((clean > 0).mean()) if len(clean) else np.nan,
            }
        )
    return rows


def daily_cells(frame: pd.DataFrame, bucket: str, label: str, signal: str | None = None) -> pd.DataFrame:
    columns = ["session_date", bucket, label] + ([signal] if signal else [])
    work = frame[columns].dropna(subset=[bucket, label]).copy()
    aggregations: dict[str, tuple[str, str]] = {
        "mean_forward_return": (label, "mean"),
        "constituent_observations": (label, "size"),
    }
    if signal:
        aggregations["mean_signal"] = (signal, "mean")
    return work.groupby(["session_date", bucket], as_index=False, observed=True).agg(**aggregations)


def summarize_cells(daily: pd.DataFrame, bucket: str, extra: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for value, group in daily.groupby(bucket, sort=True, observed=True):
        rows.append(
            extra
            | {
                "period_type": "overall",
                "period": "all",
                bucket: value,
                "mean_forward_return": group["mean_forward_return"].mean(),
                "constituent_observations": int(group["constituent_observations"].sum()),
                "sessions": group["session_date"].nunique(),
                "mean_cell_count": group["constituent_observations"].mean(),
                "min_cell_count": group["constituent_observations"].min(),
                "mean_signal": group["mean_signal"].mean() if "mean_signal" in group else np.nan,
            }
        )
    annual = daily.assign(year=daily["session_date"].dt.year)
    for (year, value), group in annual.groupby(["year", bucket], sort=True, observed=True):
        rows.append(
            extra
            | {
                "period_type": "calendar_year",
                "period": str(year),
                bucket: value,
                "mean_forward_return": group["mean_forward_return"].mean(),
                "constituent_observations": int(group["constituent_observations"].sum()),
                "sessions": group["session_date"].nunique(),
                "mean_cell_count": group["constituent_observations"].mean(),
                "min_cell_count": group["constituent_observations"].min(),
                "mean_signal": group["mean_signal"].mean() if "mean_signal" in group else np.nan,
            }
        )
    return rows


def contrast_series(daily: pd.DataFrame, bucket: str, high: object, low: object) -> pd.DataFrame:
    pivot = daily.pivot(index="session_date", columns=bucket, values="mean_forward_return")
    if high not in pivot or low not in pivot:
        return pd.DataFrame(columns=["session_date", "contrast"])
    result = (pivot[high] - pivot[low]).dropna().rename("contrast").reset_index()
    return result


def summarize_contrast(
    daily: pd.DataFrame,
    bucket: str,
    high: object,
    low: object,
    name: str,
    extra: dict[str, object],
) -> tuple[list[dict[str, object]], pd.DataFrame]:
    series = contrast_series(daily, bucket, high, low)
    rows = [
        extra
        | {
            "period_type": "overall",
            "period": "all",
            "contrast": name,
            "mean_return_difference": series["contrast"].mean(),
            "median_return_difference": series["contrast"].median(),
            "sessions": len(series),
            "positive_session_share": float((series["contrast"] > 0).mean()) if len(series) else np.nan,
        }
    ]
    for year, group in series.groupby(series["session_date"].dt.year, sort=True):
        rows.append(
            extra
            | {
                "period_type": "calendar_year",
                "period": str(year),
                "contrast": name,
                "mean_return_difference": group["contrast"].mean(),
                "median_return_difference": group["contrast"].median(),
                "sessions": len(group),
                "positive_session_share": float((group["contrast"] > 0).mean()),
            }
        )
    return rows, series


def hac_se(values: np.ndarray, lag: int) -> float:
    clean = values[np.isfinite(values)]
    n = len(clean)
    if n < 3:
        return np.nan
    centered = clean - clean.mean()
    long_variance = float(np.dot(centered, centered) / n)
    for offset in range(1, min(lag, n - 1) + 1):
        gamma = float(np.dot(centered[offset:], centered[:-offset]) / n)
        long_variance += 2 * (1 - offset / (lag + 1)) * gamma
    return math.sqrt(max(long_variance, 0) / n)


def block_bootstrap(values: np.ndarray, tag: str, block: int = 20, samples: int = 1000) -> tuple[float, float]:
    clean = values[np.isfinite(values)]
    n = len(clean)
    if n < 3:
        return np.nan, np.nan
    block = min(block, n)
    blocks = math.ceil(n / block)
    seed = (SEED + int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)) % (2**32 - 1)
    rng = np.random.default_rng(seed)
    means = np.empty(samples)
    offsets = np.arange(block)
    for index in range(samples):
        starts = rng.integers(0, n, blocks)
        selected = ((starts[:, None] + offsets).reshape(-1) % n)[:n]
        means[index] = clean[selected].mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def uncertainty_row(series: Iterable[float], horizon: int, diagnostic: str) -> dict[str, object]:
    clean = np.asarray(list(series), dtype=float)
    clean = clean[np.isfinite(clean)]
    mean = clean.mean() if len(clean) else np.nan
    se = hac_se(clean, horizon)
    low, high = block_bootstrap(clean, diagnostic)
    return {
        "diagnostic": diagnostic,
        "horizon_sessions": horizon,
        "mean": mean,
        "sessions": len(clean),
        "hac_lag_sessions": horizon,
        "hac_ci_low": mean - 1.959963984540054 * se if np.isfinite(se) else np.nan,
        "hac_ci_high": mean + 1.959963984540054 * se if np.isfinite(se) else np.nan,
        "bootstrap_block_sessions": 20,
        "bootstrap_samples": 1000,
        "bootstrap_ci_low": low,
        "bootstrap_ci_high": high,
    }


def partial_rank_ic(group: pd.DataFrame, feature: str, label: str, control: str) -> float:
    valid = group[[feature, label, control]].dropna()
    if len(valid) < 5:
        return np.nan
    ranked = valid.rank(method="average", pct=True)
    rxy = ranked[feature].corr(ranked[label])
    rxc = ranked[feature].corr(ranked[control])
    ryc = ranked[label].corr(ranked[control])
    denominator = math.sqrt(max((1 - rxc**2) * (1 - ryc**2), 0))
    return (rxy - rxc * ryc) / denominator if denominator else np.nan


def coverage_group(count: pd.Series) -> pd.Series:
    return pd.Series(
        np.select(
            [count.eq(60), count.between(58, 59), count.eq(57)],
            ["60/60", "58-59/60", "57/60"],
            default="other",
        ),
        index=count.index,
    )


def write_table(tables: Path, name: str, frame: pd.DataFrame, sort: list[str]) -> None:
    clean = frame.sort_values(sort, kind="mergesort").reset_index(drop=True) if len(frame) else frame
    clean.to_csv(tables / name, index=False, lineterminator="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel-run", type=Path, required=True)
    parser.add_argument("--analysis-plan", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    panel_run = args.panel_run.resolve()
    output = args.output.resolve()
    allowed = Path(r"D:\Stock\data\ATS\decision_oriented_phase_a\analysis_runs").resolve()
    if not output.is_relative_to(allowed):
        raise ValueError(f"output must stay beneath {allowed}")
    if output.exists():
        raise FileExistsError(f"immutable output exists: {output}")
    tables = output / "tables"
    figures = output / "figures"
    tables.mkdir(parents=True)
    figures.mkdir()

    artifacts = panel_run / "artifacts"
    panel = pd.read_parquet(artifacts / "research_panel.parquet")
    features = pd.read_parquet(artifacts / "feature_values.parquet")
    panel["session_date"] = pd.to_datetime(panel["session_date"])
    panel["feature_session_date"] = pd.to_datetime(panel["feature_session_date"])
    features["session_date"] = pd.to_datetime(features["session_date"])

    extension_summary = pd.DataFrame(
        [
            {
                "panel_run_id": json.loads((panel_run / "manifest.json").read_text(encoding="utf-8"))["run_id"],
                "panel_start": panel["session_date"].min(),
                "panel_end": panel["session_date"].max(),
                "sessions": panel["session_date"].nunique(),
                "official_rows": len(panel),
                **{
                    f"last_label_eligible_date_h{h}": panel.loc[panel[LABELS[h]].notna(), "session_date"].max()
                    for h in HORIZONS
                },
            }
        ]
    )
    write_table(tables, "extension_summary.csv", extension_summary, ["panel_start"])

    uncertainty: list[dict[str, object]] = []

    # Momentum.
    momentum_cells_rows: list[dict[str, object]] = []
    momentum_ic_rows: list[dict[str, object]] = []
    momentum_contrast_rows: list[dict[str, object]] = []
    momentum_daily: dict[int, pd.DataFrame] = {}
    for horizon, label in LABELS.items():
        daily = daily_cells(panel, MOMENTUM_Q, label, MOMENTUM)
        momentum_daily[horizon] = daily
        momentum_cells_rows.extend(
            summarize_cells(daily, MOMENTUM_Q, {"feature": "momentum_12_1", "horizon_sessions": horizon})
        )
        ic = session_ic(panel, MOMENTUM, label)
        momentum_ic_rows.extend(summarize_ic(ic, {"feature": "momentum_12_1", "horizon_sessions": horizon}))
        uncertainty.append(uncertainty_row(ic["rank_ic"], horizon, f"momentum_rank_ic_h{horizon}"))
        for high, low, name in [(5, 1, "Q5-Q1"), (5, 4, "Q5-Q4"), (4, 5, "Q4-Q5")]:
            rows, series = summarize_contrast(
                daily, MOMENTUM_Q, high, low, name, {"feature": "momentum_12_1", "horizon_sessions": horizon}
            )
            momentum_contrast_rows.extend(rows)
            if name in {"Q5-Q1", "Q4-Q5"}:
                uncertainty.append(
                    uncertainty_row(series["contrast"], horizon, f"momentum_{name.lower()}_h{horizon}")
                )
    momentum_cells = pd.DataFrame(momentum_cells_rows).rename(columns={MOMENTUM_Q: "quantile"})
    momentum_ic = pd.DataFrame(momentum_ic_rows)
    momentum_contrasts = pd.DataFrame(momentum_contrast_rows)
    write_table(tables, "momentum_quintiles.csv", momentum_cells, ["horizon_sessions", "period_type", "period", "quantile"])
    write_table(tables, "momentum_rank_ic.csv", momentum_ic, ["horizon_sessions", "period_type", "period"])
    write_table(tables, "momentum_contrasts.csv", momentum_contrasts, ["horizon_sessions", "contrast", "period_type", "period"])

    # Strong-stock pullback.
    pullback_rows: list[dict[str, object]] = []
    pullback_contrast_rows: list[dict[str, object]] = []
    conditions = {
        "positive_12_1_momentum": panel[MOMENTUM].gt(0),
        "upper_half_momentum_rank": panel[MOMENTUM_PCT].gt(0.5),
    }
    pullback_daily: dict[tuple[str, int], pd.DataFrame] = {}
    for condition, mask in conditions.items():
        conditioned = panel.loc[mask].copy()
        conditioned["pullback_bucket"] = pd.Categorical(
            np.select(
                [conditioned[RETURN_5].le(-0.05), conditioned[RETURN_5].lt(0), conditioned[RETURN_5].ge(0)],
                ["deep_pullback_le_-5pct", "mild_pullback_-5_to_0pct", "nonnegative_5d_return"],
                default=None,
            ),
            categories=["deep_pullback_le_-5pct", "mild_pullback_-5_to_0pct", "nonnegative_5d_return"],
            ordered=True,
        )
        for horizon, label in LABELS.items():
            daily = daily_cells(conditioned, "pullback_bucket", label, RETURN_5)
            pullback_daily[(condition, horizon)] = daily
            pullback_rows.extend(
                summarize_cells(daily, "pullback_bucket", {"condition": condition, "horizon_sessions": horizon})
            )
            rows, series = summarize_contrast(
                daily,
                "pullback_bucket",
                "deep_pullback_le_-5pct",
                "nonnegative_5d_return",
                "deep_pullback-minus-nonnegative",
                {"condition": condition, "horizon_sessions": horizon},
            )
            pullback_contrast_rows.extend(rows)
            uncertainty.append(
                uncertainty_row(series["contrast"], horizon, f"pullback_{condition}_deep_minus_nonnegative_h{horizon}")
            )
    pullback = pd.DataFrame(pullback_rows)
    pullback_contrasts = pd.DataFrame(pullback_contrast_rows)
    write_table(tables, "strong_stock_pullback.csv", pullback, ["condition", "horizon_sessions", "period_type", "period", "pullback_bucket"])
    write_table(tables, "strong_stock_pullback_contrasts.csv", pullback_contrasts, ["condition", "horizon_sessions", "period_type", "period"])

    # Strict proximity to the trailing 252-session high.
    feature_grid = features[["security_id", "session_date", "close"]].sort_values(["security_id", "session_date"]).copy()
    rolling_high = (
        feature_grid.groupby("security_id", sort=False)["close"]
        .rolling(252, min_periods=252)
        .max()
        .reset_index(level=0, drop=True)
    )
    feature_grid["trailing_high_252"] = rolling_high
    feature_grid["proximity_252"] = feature_grid["close"] / feature_grid["trailing_high_252"]
    prox = panel.merge(
        feature_grid.rename(columns={"session_date": "feature_session_date", "close": "proximity_input_close"}),
        on=["security_id", "feature_session_date"],
        how="left",
        validate="many_to_one",
    )
    comparable = prox[["feature_input_close", "proximity_input_close"]].dropna()
    if not np.allclose(comparable["feature_input_close"], comparable["proximity_input_close"], rtol=0, atol=1e-12):
        raise RuntimeError("proximity close does not match the Phase A feature input close")
    eligible_proximity = prox["proximity_252"].where(prox["is_price_usable_member"])
    rank = eligible_proximity.groupby(prox["session_date"]).rank(method="average")
    count = eligible_proximity.groupby(prox["session_date"]).transform("count")
    prox["proximity_percentile_rank"] = rank / count
    prox["proximity_quintile"] = np.ceil(prox["proximity_percentile_rank"] * 5).clip(1, 5).astype("Int64")
    prox["proximity_tercile"] = np.ceil(prox["proximity_percentile_rank"] * 3).clip(1, 3).astype("Int64")
    prox["momentum_tercile"] = np.ceil(prox[MOMENTUM_PCT] * 3).clip(1, 3).astype("Int64")

    proximity_rows: list[dict[str, object]] = []
    proximity_ic_rows: list[dict[str, object]] = []
    proximity_partial_rows: list[dict[str, object]] = []
    proximity_double_rows: list[dict[str, object]] = []
    proximity_daily: dict[int, pd.DataFrame] = {}
    for horizon, label in LABELS.items():
        daily = daily_cells(prox, "proximity_quintile", label, "proximity_252")
        proximity_daily[horizon] = daily
        proximity_rows.extend(summarize_cells(daily, "proximity_quintile", {"horizon_sessions": horizon}))
        ic = session_ic(prox, "proximity_252", label)
        proximity_ic_rows.extend(summarize_ic(ic, {"horizon_sessions": horizon}))
        uncertainty.append(uncertainty_row(ic["rank_ic"], horizon, f"proximity_rank_ic_h{horizon}"))

        partial_daily = (
            prox.groupby("session_date", sort=True)
            .apply(lambda group: partial_rank_ic(group, "proximity_252", label, MOMENTUM), include_groups=False)
            .rename("partial_rank_ic")
            .reset_index()
        )
        for period_type, period, subset in [("overall", "all", partial_daily)]:
            proximity_partial_rows.append(
                {
                    "horizon_sessions": horizon,
                    "period_type": period_type,
                    "period": period,
                    "mean_partial_rank_ic": subset["partial_rank_ic"].mean(),
                    "median_partial_rank_ic": subset["partial_rank_ic"].median(),
                    "sessions": subset["partial_rank_ic"].notna().sum(),
                }
            )
        for year, subset in partial_daily.groupby(partial_daily["session_date"].dt.year, sort=True):
            proximity_partial_rows.append(
                {
                    "horizon_sessions": horizon,
                    "period_type": "calendar_year",
                    "period": str(year),
                    "mean_partial_rank_ic": subset["partial_rank_ic"].mean(),
                    "median_partial_rank_ic": subset["partial_rank_ic"].median(),
                    "sessions": subset["partial_rank_ic"].notna().sum(),
                }
            )
        uncertainty.append(
            uncertainty_row(partial_daily["partial_rank_ic"], horizon, f"proximity_partial_rank_ic_h{horizon}")
        )

        double_daily = (
            prox[["session_date", "momentum_tercile", "proximity_tercile", label]]
            .dropna()
            .groupby(["session_date", "momentum_tercile", "proximity_tercile"], as_index=False)
            .agg(mean_forward_return=(label, "mean"), constituent_observations=(label, "size"))
        )
        for (momentum_tercile, proximity_tercile), group in double_daily.groupby(
            ["momentum_tercile", "proximity_tercile"], sort=True
        ):
            proximity_double_rows.append(
                {
                    "horizon_sessions": horizon,
                    "period_type": "overall",
                    "period": "all",
                    "momentum_tercile": int(momentum_tercile),
                    "proximity_tercile": int(proximity_tercile),
                    "mean_forward_return": group["mean_forward_return"].mean(),
                    "constituent_observations": int(group["constituent_observations"].sum()),
                    "sessions": group["session_date"].nunique(),
                }
            )
        annual_double = double_daily.assign(year=double_daily["session_date"].dt.year)
        for (year, momentum_tercile, proximity_tercile), group in annual_double.groupby(
            ["year", "momentum_tercile", "proximity_tercile"], sort=True
        ):
            proximity_double_rows.append(
                {
                    "horizon_sessions": horizon,
                    "period_type": "calendar_year",
                    "period": str(year),
                    "momentum_tercile": int(momentum_tercile),
                    "proximity_tercile": int(proximity_tercile),
                    "mean_forward_return": group["mean_forward_return"].mean(),
                    "constituent_observations": int(group["constituent_observations"].sum()),
                    "sessions": group["session_date"].nunique(),
                }
            )
    proximity = pd.DataFrame(proximity_rows)
    proximity_ic = pd.DataFrame(proximity_ic_rows)
    proximity_partial = pd.DataFrame(proximity_partial_rows)
    proximity_double = pd.DataFrame(proximity_double_rows)
    proximity_coverage = (
        prox.assign(year=prox["session_date"].dt.year)
        .groupby("year", as_index=False)
        .agg(
            official_rows=("security_id", "size"),
            eligible_rows=("proximity_252", "count"),
            sessions=("session_date", "nunique"),
        )
    )
    proximity_coverage["eligible_ratio"] = proximity_coverage["eligible_rows"] / proximity_coverage["official_rows"]
    write_table(tables, "proximity_quintiles.csv", proximity, ["horizon_sessions", "period_type", "period", "proximity_quintile"])
    write_table(tables, "proximity_rank_ic.csv", proximity_ic, ["horizon_sessions", "period_type", "period"])
    write_table(tables, "proximity_partial_rank_ic.csv", proximity_partial, ["horizon_sessions", "period_type", "period"])
    write_table(tables, "proximity_momentum_3x3.csv", proximity_double, ["horizon_sessions", "period_type", "period", "momentum_tercile", "proximity_tercile"])
    write_table(tables, "proximity_coverage_by_year.csv", proximity_coverage, ["year"])

    # Relative volume and volatility.
    conditioning_specs = {
        "relative_volume_20": (
            "feature__relative_volume_20__v1",
            "quantile__relative_volume_20__v1",
        ),
        "realized_volatility_20": (
            "feature__realized_volatility_20__v1",
            "quantile__realized_volatility_20__v1",
        ),
    }
    conditioning_rows: list[dict[str, object]] = []
    conditioning_ic_rows: list[dict[str, object]] = []
    conditioning_contrast_rows: list[dict[str, object]] = []
    conditioning_daily: dict[tuple[str, int], pd.DataFrame] = {}
    for feature_name, (feature, quantile) in conditioning_specs.items():
        for horizon, label in LABELS.items():
            daily = daily_cells(panel, quantile, label, feature)
            conditioning_daily[(feature_name, horizon)] = daily
            conditioning_rows.extend(
                summarize_cells(daily, quantile, {"feature": feature_name, "horizon_sessions": horizon})
            )
            ic = session_ic(panel, feature, label)
            conditioning_ic_rows.extend(
                summarize_ic(ic, {"feature": feature_name, "horizon_sessions": horizon})
            )
            rows, spread = summarize_contrast(
                daily, quantile, 5, 1, "Q5-Q1", {"feature": feature_name, "horizon_sessions": horizon}
            )
            conditioning_contrast_rows.extend(rows)
            uncertainty.append(uncertainty_row(ic["rank_ic"], horizon, f"{feature_name}_rank_ic_h{horizon}"))
            uncertainty.append(uncertainty_row(spread["contrast"], horizon, f"{feature_name}_q5_minus_q1_h{horizon}"))
    conditioning = pd.DataFrame(conditioning_rows)
    conditioning["quantile"] = conditioning["quantile__relative_volume_20__v1"].combine_first(
        conditioning["quantile__realized_volatility_20__v1"]
    )
    conditioning = conditioning.drop(
        columns=["quantile__relative_volume_20__v1", "quantile__realized_volatility_20__v1"]
    )
    conditioning_ic = pd.DataFrame(conditioning_ic_rows)
    conditioning_contrasts = pd.DataFrame(conditioning_contrast_rows)
    write_table(tables, "relative_volume_volatility_quintiles.csv", conditioning, ["feature", "horizon_sessions", "period_type", "period", "quantile"])
    write_table(tables, "relative_volume_volatility_rank_ic.csv", conditioning_ic, ["feature", "horizon_sessions", "period_type", "period"])
    write_table(tables, "relative_volume_volatility_contrasts.csv", conditioning_contrasts, ["feature", "horizon_sessions", "period_type", "period"])

    # Coverage and missing-member sensitivity.
    session_coverage = panel[["session_date", "official_member_count", "price_usable_member_count"]].drop_duplicates()
    session_coverage["coverage_group"] = coverage_group(session_coverage["price_usable_member_count"])
    session_coverage["year"] = session_coverage["session_date"].dt.year
    coverage_summary = (
        session_coverage.groupby("coverage_group", as_index=False)
        .agg(
            sessions=("session_date", "nunique"),
            first_session=("session_date", "min"),
            last_session=("session_date", "max"),
            mean_usable_members=("price_usable_member_count", "mean"),
        )
    )
    coverage_summary = pd.concat(
        [
            pd.DataFrame(
                [
                    {
                        "coverage_group": "all_dates",
                        "sessions": session_coverage["session_date"].nunique(),
                        "first_session": session_coverage["session_date"].min(),
                        "last_session": session_coverage["session_date"].max(),
                        "mean_usable_members": session_coverage["price_usable_member_count"].mean(),
                    }
                ]
            ),
            coverage_summary,
        ],
        ignore_index=True,
    )
    coverage_year = (
        session_coverage.groupby(["year", "coverage_group"], as_index=False)
        .agg(sessions=("session_date", "nunique"))
    )
    coverage_year["year_sessions"] = coverage_year.groupby("year")["sessions"].transform("sum")
    coverage_year["year_share"] = coverage_year["sessions"] / coverage_year["year_sessions"]

    coverage_momentum_rows: list[dict[str, object]] = []
    date_groups = {"all_dates": set(session_coverage["session_date"])} | {
        name: set(group["session_date"]) for name, group in session_coverage.groupby("coverage_group")
    }
    for name in ["all_dates", "60/60", "58-59/60", "57/60"]:
        dates = date_groups.get(name, set())
        subset = panel.loc[panel["session_date"].isin(dates)]
        for horizon, label in LABELS.items():
            ic = session_ic(subset, MOMENTUM, label)
            daily = daily_cells(subset, MOMENTUM_Q, label, MOMENTUM)
            qmeans = daily.groupby(MOMENTUM_Q)["mean_forward_return"].mean()
            coverage_momentum_rows.append(
                {
                    "coverage_group": name,
                    "horizon_sessions": horizon,
                    "sessions_total": len(dates),
                    "sessions_ic": ic["rank_ic"].notna().sum(),
                    "constituent_observations_ic": int(ic.loc[ic["rank_ic"].notna(), "constituent_observations"].sum()),
                    "mean_rank_ic": ic["rank_ic"].mean(),
                    "q1_mean_return": qmeans.get(1, np.nan),
                    "q4_mean_return": qmeans.get(4, np.nan),
                    "q5_mean_return": qmeans.get(5, np.nan),
                    "q5_minus_q1": qmeans.get(5, np.nan) - qmeans.get(1, np.nan),
                    "q4_minus_q5": qmeans.get(4, np.nan) - qmeans.get(5, np.nan),
                    "feature_eligible_rows": int(subset[f"is_feature_eligible__momentum_12_1__v1"].sum()),
                    "label_eligible_rows": int(subset[[MOMENTUM, label]].dropna().shape[0]),
                }
            )
    coverage_momentum = pd.DataFrame(coverage_momentum_rows)
    panel_with_group = panel.merge(session_coverage[["session_date", "coverage_group"]], on="session_date", how="left")
    missing_reasons = (
        panel_with_group.loc[~panel_with_group["is_price_usable_member"]]
        .assign(year=lambda frame: frame["session_date"].dt.year)
        .groupby(["coverage_group", "year", "price_eligibility_state", "price_exclusion_reason"], dropna=False, as_index=False)
        .size()
        .rename(columns={"size": "member_sessions"})
    )
    exit_exposure = (
        panel.loc[panel["isin"].isin(EXIT_ISINS)]
        .assign(year=lambda frame: frame["session_date"].dt.year)
        .groupby(["isin", "historical_ticker", "year"], dropna=False, as_index=False)
        .agg(
            official_member_sessions=("security_id", "size"),
            usable_price_sessions=("is_price_usable_member", "sum"),
            first_session=("session_date", "min"),
            last_session=("session_date", "max"),
        )
    )
    exit_exposure["missing_price_sessions"] = exit_exposure["official_member_sessions"] - exit_exposure["usable_price_sessions"]
    write_table(tables, "coverage_summary.csv", coverage_summary, ["coverage_group"])
    write_table(tables, "coverage_by_year.csv", coverage_year, ["year", "coverage_group"])
    write_table(tables, "coverage_momentum_sensitivity.csv", coverage_momentum, ["coverage_group", "horizon_sessions"])
    write_table(tables, "missing_reasons_by_coverage_year.csv", missing_reasons, ["coverage_group", "year", "price_eligibility_state", "price_exclusion_reason"])
    write_table(tables, "five_exit_history_exposure.csv", exit_exposure, ["isin", "year"])

    uncertainty_frame = pd.DataFrame(uncertainty)
    write_table(tables, "secondary_uncertainty.csv", uncertainty_frame, ["diagnostic", "horizon_sessions"])

    # Compact figures.
    overall_momentum = momentum_cells.loc[momentum_cells["period_type"].eq("overall")]
    figure, axis = plt.subplots(figsize=(8, 5))
    for horizon, group in overall_momentum.groupby("horizon_sessions"):
        axis.plot(group["quantile"], 100 * group["mean_forward_return"], marker="o", label=f"{horizon} sessions")
    axis.axhline(0, color="black", linewidth=0.7)
    axis.set(xlabel="12-1 momentum quintile (Q1 weak, Q5 strong)", ylabel="Mean diagnostic gross return (%)", title="Momentum quintile profiles")
    axis.legend()
    figure.tight_layout()
    figure.savefig(figures / "momentum_quintile_profiles.png", dpi=160)
    plt.close(figure)

    annual_q45 = momentum_contrasts.loc[
        momentum_contrasts["period_type"].eq("calendar_year") & momentum_contrasts["contrast"].eq("Q4-Q5")
    ].copy()
    figure, axes = plt.subplots(2, 2, figsize=(11, 7), sharey=True)
    for axis, horizon in zip(axes.flat, HORIZONS, strict=True):
        group = annual_q45.loc[annual_q45["horizon_sessions"].eq(horizon)]
        axis.bar(group["period"], 100 * group["mean_return_difference"])
        axis.axhline(0, color="black", linewidth=0.7)
        axis.set_title(f"{horizon} sessions")
        axis.tick_params(axis="x", rotation=45)
    figure.supylabel("Q4 minus Q5 mean return (percentage points)")
    figure.suptitle("Is 'strong but not extreme' persistent by year?")
    figure.tight_layout()
    figure.savefig(figures / "momentum_q4_minus_q5_by_year.png", dpi=160)
    plt.close(figure)

    overall_pullback = pullback.loc[pullback["period_type"].eq("overall")].copy()
    figure, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for axis, (condition, group) in zip(axes, overall_pullback.groupby("condition"), strict=True):
        for horizon, cells in group.groupby("horizon_sessions"):
            axis.plot(cells["pullback_bucket"].astype(str), 100 * cells["mean_forward_return"], marker="o", label=str(horizon))
        axis.set_title(condition.replace("_", " "))
        axis.tick_params(axis="x", rotation=25)
        axis.axhline(0, color="black", linewidth=0.7)
    axes[0].set_ylabel("Mean diagnostic gross return (%)")
    axes[1].legend(title="Sessions")
    figure.suptitle("Five-session pullback buckets within strong stocks")
    figure.tight_layout()
    figure.savefig(figures / "strong_stock_pullback_profiles.png", dpi=160)
    plt.close(figure)

    overall_proximity = proximity.loc[proximity["period_type"].eq("overall")]
    figure, axis = plt.subplots(figsize=(8, 5))
    for horizon, group in overall_proximity.groupby("horizon_sessions"):
        axis.plot(group["proximity_quintile"], 100 * group["mean_forward_return"], marker="o", label=f"{horizon} sessions")
    axis.axhline(0, color="black", linewidth=0.7)
    axis.set(xlabel="Proximity-to-high quintile", ylabel="Mean diagnostic gross return (%)", title="Strict 252-session proximity-to-high")
    axis.legend()
    figure.tight_layout()
    figure.savefig(figures / "proximity_quintile_profiles.png", dpi=160)
    plt.close(figure)

    overall_conditioning = conditioning.loc[conditioning["period_type"].eq("overall")]
    figure, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for axis, (feature_name, group) in zip(axes, overall_conditioning.groupby("feature"), strict=True):
        for horizon, cells in group.groupby("horizon_sessions"):
            axis.plot(cells["quantile"], 100 * cells["mean_forward_return"], marker="o", label=str(horizon))
        axis.set_title(feature_name.replace("_", " "))
        axis.set_xlabel("Quintile")
        axis.axhline(0, color="black", linewidth=0.7)
    axes[0].set_ylabel("Mean diagnostic gross return (%)")
    axes[1].legend(title="Sessions")
    figure.tight_layout()
    figure.savefig(figures / "relative_volume_volatility_profiles.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9, 5))
    coverage_pivot = coverage_year.pivot(index="year", columns="coverage_group", values="sessions").fillna(0)
    coverage_pivot[[column for column in ["60/60", "58-59/60", "57/60", "other"] if column in coverage_pivot]].plot(
        kind="bar", stacked=True, ax=axis
    )
    axis.set(xlabel="Calendar year", ylabel="Decision sessions", title="Coverage groups are confounded with calendar period")
    figure.tight_layout()
    figure.savefig(figures / "coverage_groups_by_year.png", dpi=160)
    plt.close(figure)

    # Retained configuration and source record.
    shutil.copy2(args.analysis_plan.resolve(), output / "analysis_plan.md")
    shutil.copy2(args.config.resolve(), output / "config.yaml")
    with zipfile.ZipFile(output / "source_snapshot.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(Path(__file__).resolve().parent.glob("*")):
            if path.is_file() and path.suffix.lower() in {".py", ".md", ".yaml"}:
                archive.write(path, arcname=path.name)

    table_files = sorted(path.name for path in tables.glob("*.csv"))
    metrics = {
        "analysis_run_created_utc": datetime.now(UTC).isoformat(),
        "panel_run": str(panel_run),
        "panel_run_id": extension_summary.iloc[0]["panel_run_id"],
        "panel_start": extension_summary.iloc[0]["panel_start"],
        "panel_end": extension_summary.iloc[0]["panel_end"],
        "sessions": extension_summary.iloc[0]["sessions"],
        "official_rows": extension_summary.iloc[0]["official_rows"],
        "table_files": table_files,
        "figure_files": sorted(path.name for path in figures.glob("*.png")),
        "definitions": {
            "pullback_buckets": ["return_5 <= -5%", "-5% < return_5 < 0", "return_5 >= 0"],
            "strength_conditions": ["momentum_12_1 > 0", "momentum percentile rank > 0.5"],
            "proximity": "prior available close / trailing 252-session maximum close, current prior close included, full history required",
        },
    }
    write_json(output / "metrics.json", metrics)
    payload_files = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "manifest.json")
    manifest = {
        "analysis_type": "decision_oriented_phase_a",
        "created_utc": datetime.now(UTC).isoformat(),
        "immutable_output": str(output),
        "panel_run": str(panel_run),
        "panel_manifest_sha256": sha256_file(panel_run / "manifest.json"),
        "files": {
            path.relative_to(output).as_posix(): {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in payload_files
        },
    }
    write_json(output / "manifest.json", manifest)
    print(json.dumps(json_safe(metrics), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
