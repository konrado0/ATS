from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ats_research.features.definitions import cross_sectional_feature_columns
from ats_research.labels.forward_returns import label_definitions
from ats_research.panel import (
    feature_count_column,
    feature_coverage_column,
    feature_eligibility_column,
    feature_exclusion_column,
    feature_key,
)


BENIGN_EXIT_ISINS = ("PLLOTOS00025", "PLPGNIG00014", "PLSTSHL00012", "PLCIECH00018", "PLTIM0000016")


@dataclass(frozen=True)
class DiagnosticOutputs:
    cross_section: pd.DataFrame
    coverage: pd.DataFrame
    feature_coverage: pd.DataFrame
    rank_ic: pd.DataFrame
    quantile_returns: pd.DataFrame
    monotonicity: pd.DataFrame
    turnover: pd.DataFrame
    missing_by_session: pd.DataFrame
    missing_overall: pd.DataFrame
    feature_missing_summary: pd.DataFrame
    annual_stability: pd.DataFrame
    regime_stability: pd.DataFrame
    uncertainty: pd.DataFrame
    non_overlapping_ic: pd.DataFrame
    coverage_sensitivity: pd.DataFrame
    exit_period_sensitivity: pd.DataFrame
    exit_exposure_by_session: pd.DataFrame


def _diagnostic_features() -> list[str]:
    return cross_sectional_feature_columns()


def add_cross_sectional_ranks(panel: pd.DataFrame, quantiles: int) -> pd.DataFrame:
    result = panel.copy()
    for column in _diagnostic_features():
        short = feature_key(column)
        eligible = result[feature_eligibility_column(column)]
        eligible_values = result[column].where(eligible)
        rank = eligible_values.groupby(result["session_date"]).rank(method="average", ascending=True)
        denominator = result[feature_count_column(column)].where(eligible)
        percentile = rank / denominator
        result[f"rank__{short}"] = rank
        result[f"percentile_rank__{short}"] = percentile
        result[f"quantile__{short}"] = np.ceil(percentile * quantiles).clip(1, quantiles).astype("Int64")
    return result


def _safe_spearman(group: pd.DataFrame, x: str, y: str) -> float:
    valid = group[[x, y]].dropna()
    if len(valid) < 3 or valid[x].nunique() < 2 or valid[y].nunique() < 2:
        return float("nan")
    left = valid[x].rank(method="average").to_numpy(dtype=float).copy()
    right = valid[y].rank(method="average").to_numpy(dtype=float).copy()
    left -= left.mean()
    right -= right.mean()
    denominator = float(np.sqrt((left * left).sum() * (right * right).sum()))
    return float((left * right).sum() / denominator) if denominator else float("nan")


def _hac_standard_error(values: np.ndarray, max_lag: int) -> float:
    clean = values[np.isfinite(values)]
    n = len(clean)
    if n < 3:
        return float("nan")
    centered = clean - clean.mean()
    lag = min(max_lag, n - 1)
    long_variance = float(np.dot(centered, centered) / n)
    for offset in range(1, lag + 1):
        gamma = float(np.dot(centered[offset:], centered[:-offset]) / n)
        long_variance += 2.0 * (1.0 - offset / (lag + 1.0)) * gamma
    return float(np.sqrt(max(long_variance, 0.0) / n))


def _block_bootstrap_mean_ci(
    values: np.ndarray,
    samples: int,
    block_length: int,
    confidence_level: float,
    seed: int,
) -> tuple[float, float]:
    clean = values[np.isfinite(values)]
    n = len(clean)
    if n < 3:
        return float("nan"), float("nan")
    block = min(block_length, n)
    blocks_needed = math.ceil(n / block)
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype=float)
    offsets = np.arange(block)
    for index in range(samples):
        starts = rng.integers(0, n, size=blocks_needed)
        selected = ((starts[:, None] + offsets[None, :]) % n).reshape(-1)[:n]
        means[index] = clean[selected].mean()
    alpha = (1.0 - confidence_level) / 2.0
    return float(np.quantile(means, alpha)), float(np.quantile(means, 1.0 - alpha))


def _benjamini_hochberg(p_values: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=p_values.index, dtype=float)
    valid = p_values.dropna().sort_values()
    m = len(valid)
    if not m:
        return result
    adjusted = valid.to_numpy(dtype=float) * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1].clip(0, 1)
    result.loc[valid.index] = adjusted
    return result


def _stability_tables(rank_ic: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    usable = rank_ic.dropna(subset=["rank_ic"]).copy()
    usable["year"] = pd.to_datetime(usable["session_date"]).dt.year
    annual = usable.groupby(["feature", "label", "horizon_sessions", "year"], as_index=False).agg(
        sessions=("rank_ic", "size"), mean_rank_ic=("rank_ic", "mean"),
        median_rank_ic=("rank_ic", "median"), positive_share=("rank_ic", lambda values: float((values > 0).mean())),
    )
    regime = usable.groupby(["feature", "label", "horizon_sessions", "wig_trend_regime"], as_index=False).agg(
        sessions=("rank_ic", "size"), mean_rank_ic=("rank_ic", "mean"),
        median_rank_ic=("rank_ic", "median"), positive_share=("rank_ic", lambda values: float((values > 0).mean())),
    )
    non_overlap_rows: list[dict[str, object]] = []
    for keys, group in usable.groupby(["feature", "label", "horizon_sessions"], sort=True):
        feature, label, horizon = keys
        ordered = group.sort_values("session_date").reset_index(drop=True)
        for offset in range(int(horizon)):
            values = ordered.loc[np.arange(len(ordered)) % int(horizon) == offset, "rank_ic"]
            non_overlap_rows.append(
                {
                    "feature": feature, "label": label, "horizon_sessions": int(horizon), "offset": offset,
                    "sessions": len(values), "mean_rank_ic": float(values.mean()),
                    "median_rank_ic": float(values.median()), "positive_share": float((values > 0).mean()),
                }
            )
    non_overlap = pd.DataFrame(non_overlap_rows)
    sensitivity = usable.groupby(
        ["feature", "label", "horizon_sessions", "price_usable_member_count", "unresolved_exit_member_count"], as_index=False
    ).agg(
        sessions=("rank_ic", "size"), mean_rank_ic=("rank_ic", "mean"),
        median_rank_ic=("rank_ic", "median"), positive_share=("rank_ic", lambda values: float((values > 0).mean())),
    )
    return annual, regime, non_overlap, sensitivity


def _uncertainty_table(
    rank_ic: pd.DataFrame,
    seed: int,
    bootstrap_samples: int,
    bootstrap_block_sessions: int,
    confidence_level: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    critical = 1.959963984540054
    for (feature, label, horizon), group in rank_ic.groupby(["feature", "label", "horizon_sessions"], sort=True):
        values = group.sort_values("session_date")["rank_ic"].dropna().to_numpy(dtype=float)
        hac_lag = int(horizon)
        se = _hac_standard_error(values, hac_lag)
        mean = float(values.mean()) if len(values) else float("nan")
        pair_seed = seed + int(hashlib.sha256(f"{feature}:{horizon}".encode()).hexdigest()[:8], 16)
        block_length = max(bootstrap_block_sessions, int(horizon))
        bootstrap_low, bootstrap_high = _block_bootstrap_mean_ci(
            values, bootstrap_samples, block_length, confidence_level, pair_seed
        )
        z_score = mean / se if se and np.isfinite(se) else float("nan")
        p_value = math.erfc(abs(z_score) / math.sqrt(2.0)) if np.isfinite(z_score) else float("nan")
        rows.append(
            {
                "feature": feature, "label": label, "horizon_sessions": int(horizon), "sessions": len(values),
                "mean_rank_ic": mean, "hac_lag_sessions": hac_lag, "hac_standard_error": se,
                "hac_ci_95_low": mean - critical * se if np.isfinite(se) else float("nan"),
                "hac_ci_95_high": mean + critical * se if np.isfinite(se) else float("nan"),
                "hac_normal_p_value": p_value, "bootstrap_samples": bootstrap_samples,
                "bootstrap_block_sessions": block_length, "bootstrap_ci_low": bootstrap_low,
                "bootstrap_ci_high": bootstrap_high,
                "inference_caveat": "HAC and moving-block bootstrap are dependence-aware diagnostics, not proof of alpha",
            }
        )
    result = pd.DataFrame(rows)
    result["benjamini_hochberg_q_value"] = _benjamini_hochberg(result["hac_normal_p_value"])
    return result


def compute_diagnostics(
    panel: pd.DataFrame,
    horizons: tuple[int, ...],
    quantiles: int,
    seed: int = 0,
    bootstrap_samples: int = 1_000,
    bootstrap_block_sessions: int = 20,
    confidence_level: float = 0.95,
) -> DiagnosticOutputs:
    cross = add_cross_sectional_ranks(panel, quantiles)
    coverage = cross.groupby("session_date", as_index=False).agg(
        official_member_count=("official_member_count", "first"),
        price_usable_member_count=("price_usable_member_count", "first"),
        price_coverage_ratio=("price_coverage_ratio", "first"),
        complete_matrix_member_count=("complete_matrix_member_count", "first"),
        complete_matrix_coverage_ratio=("complete_matrix_coverage_ratio", "first"),
        unresolved_exit_member_count=("unresolved_exit_member_count", "first"),
        wig_trend_regime=("wig_trend_regime", "first"),
    )
    active = cross.loc[cross["is_unresolved_exit_member"]].groupby("session_date")["isin"].agg(lambda values: "|".join(sorted(set(values))))
    coverage["active_unresolved_exit_isins"] = coverage["session_date"].map(active).fillna("")
    coverage["usable_member_count"] = coverage["price_usable_member_count"]
    coverage["coverage_ratio"] = coverage["price_coverage_ratio"]

    feature_coverage_frames: list[pd.DataFrame] = []
    for column in _diagnostic_features():
        projected = cross.groupby("session_date", as_index=False).agg(
            official_member_count=("official_member_count", "first"),
            price_usable_member_count=("price_usable_member_count", "first"),
            feature_usable_member_count=(feature_count_column(column), "first"),
            feature_coverage_ratio=(feature_coverage_column(column), "first"),
        )
        projected["feature"] = feature_key(column)
        feature_coverage_frames.append(projected)
    feature_coverage = pd.concat(feature_coverage_frames, ignore_index=True)

    label_defs = label_definitions(horizons)
    ic_frames: list[pd.DataFrame] = []
    quantile_frames: list[pd.DataFrame] = []
    for feature_col in _diagnostic_features():
        feature_name = feature_key(feature_col)
        eligible_col = feature_eligibility_column(feature_col)
        feature_count = feature_count_column(feature_col)
        feature_ratio = feature_coverage_column(feature_col)
        session_base = cross.groupby("session_date", as_index=False).agg(
            official_member_count=("official_member_count", "first"),
            price_usable_member_count=("price_usable_member_count", "first"),
            price_coverage_ratio=("price_coverage_ratio", "first"),
            feature_usable_member_count=(feature_count, "first"),
            feature_coverage_ratio=(feature_ratio, "first"),
            unresolved_exit_member_count=("unresolved_exit_member_count", "first"),
            wig_trend_regime=("wig_trend_regime", "first"),
        )
        for definition in label_defs:
            label_col = definition.column
            quantile_col = f"quantile__{feature_name}"
            work = cross.loc[cross[eligible_col], ["session_date", feature_col, label_col, quantile_col]].dropna(subset=[feature_col, label_col]).copy()
            work["x_rank"] = work.groupby("session_date")[feature_col].rank(method="average")
            work["y_rank"] = work.groupby("session_date")[label_col].rank(method="average")
            work["xx"] = work["x_rank"] ** 2
            work["yy"] = work["y_rank"] ** 2
            work["xy"] = work["x_rank"] * work["y_rank"]
            sums = work.groupby("session_date", as_index=False).agg(
                label_usable_count=("x_rank", "size"), sx=("x_rank", "sum"), sy=("y_rank", "sum"),
                sxx=("xx", "sum"), syy=("yy", "sum"), sxy=("xy", "sum"),
            )
            n = sums["label_usable_count"].astype(float)
            numerator = sums["sxy"] - sums["sx"] * sums["sy"] / n
            denominator = np.sqrt((sums["sxx"] - sums["sx"] ** 2 / n) * (sums["syy"] - sums["sy"] ** 2 / n))
            sums["rank_ic"] = numerator / denominator.replace(0, np.nan)
            ic = session_base.merge(sums[["session_date", "label_usable_count", "rank_ic"]], on="session_date", how="left")
            ic["label_usable_count"] = ic["label_usable_count"].fillna(0).astype("int64")
            ic["feature"] = feature_name
            ic["label"] = definition.name
            ic["horizon_sessions"] = definition.horizon_sessions
            ic_frames.append(ic)

            aggregate = work.groupby(["session_date", quantile_col], as_index=False).agg(
                quantile_count=(label_col, "size"), mean_forward_return=(label_col, "mean"),
                median_forward_return=(label_col, "median"),
            ).rename(columns={quantile_col: "quantile"})
            complete_index = pd.MultiIndex.from_product(
                [session_base["session_date"], range(1, quantiles + 1)], names=["session_date", "quantile"]
            ).to_frame(index=False)
            aggregate = complete_index.merge(aggregate, on=["session_date", "quantile"], how="left")
            aggregate["quantile_count"] = aggregate["quantile_count"].fillna(0).astype("int64")
            aggregate = aggregate.merge(session_base, on="session_date", how="left", validate="many_to_one")
            aggregate = aggregate.merge(ic[["session_date", "label_usable_count"]], on="session_date", how="left", validate="many_to_one")
            aggregate["feature"] = feature_name
            aggregate["label"] = definition.name
            aggregate["horizon_sessions"] = definition.horizon_sessions
            quantile_frames.append(aggregate)
    rank_ic = pd.concat(ic_frames, ignore_index=True)
    quantile_returns = pd.concat(quantile_frames, ignore_index=True)

    monotonic_rows: list[dict[str, object]] = []
    for (feature, label, horizon), group in quantile_returns.groupby(["feature", "label", "horizon_sessions"], sort=True):
        by_q = group.groupby("quantile", as_index=False).agg(
            mean_forward_return=("mean_forward_return", "mean"),
            sessions_with_values=("quantile_count", lambda values: int((values > 0).sum())),
            observations=("quantile_count", "sum"),
        )
        lookup = by_q.set_index("quantile")["mean_forward_return"]
        for row in by_q.itertuples(index=False):
            monotonic_rows.append(
                {
                    "feature": feature, "label": label, "horizon_sessions": int(horizon),
                    "quantile": int(row.quantile), "mean_forward_return": row.mean_forward_return,
                    "sessions_with_values": int(row.sessions_with_values), "observations": int(row.observations),
                    "quantile_return_spearman": _safe_spearman(by_q, "quantile", "mean_forward_return"),
                    "top_minus_bottom_spread": float(lookup.get(quantiles, np.nan) - lookup.get(1, np.nan)),
                }
            )
    monotonicity = pd.DataFrame(monotonic_rows)

    turnover_rows: list[dict[str, object]] = []
    for feature_col in _diagnostic_features():
        feature_name = feature_key(feature_col)
        qcol = f"quantile__{feature_name}"
        previous: set[str] | None = None
        for session, group in cross.groupby("session_date", sort=True):
            current = set(group.loc[group[qcol].eq(quantiles), "security_id"].dropna().astype(str))
            overlap = len(current & previous) if previous is not None else 0
            denominator = len(previous) if previous else 0
            turnover_rows.append(
                {
                    "session_date": session, "feature": feature_name, "top_quantile": quantiles,
                    "current_count": len(current), "previous_count": denominator, "overlap_count": overlap,
                    "turnover_proxy": 1.0 - overlap / denominator if denominator else float("nan"),
                    "official_member_count": int(group["official_member_count"].iloc[0]),
                    "price_usable_member_count": int(group["price_usable_member_count"].iloc[0]),
                    "feature_usable_member_count": int(group[feature_count_column(feature_col)].iloc[0]),
                }
            )
            previous = current
    turnover = pd.DataFrame(turnover_rows)

    missing_by_session = cross.groupby(
        ["session_date", "price_eligibility_state", "price_exclusion_reason"], dropna=False, as_index=False
    ).size().rename(columns={"size": "member_count"})
    missing_by_session = missing_by_session.merge(coverage, on="session_date", how="left", validate="many_to_one")
    missing_overall = cross.groupby(
        ["price_eligibility_state", "price_exclusion_reason"], dropna=False, as_index=False
    ).size().rename(columns={"size": "member_sessions"})
    feature_missing_frames: list[pd.DataFrame] = []
    for column in _diagnostic_features():
        reason = cross[feature_exclusion_column(column)].fillna("eligible")
        summary = reason.value_counts(dropna=False).rename_axis("feature_eligibility_state").reset_index(name="member_sessions")
        summary["feature"] = feature_key(column)
        feature_missing_frames.append(summary)
    feature_missing_summary = pd.concat(feature_missing_frames, ignore_index=True)

    annual, regime, non_overlap, coverage_sensitivity = _stability_tables(rank_ic)
    uncertainty = _uncertainty_table(
        rank_ic, seed, bootstrap_samples, bootstrap_block_sessions, confidence_level
    )
    exit_rows: list[dict[str, object]] = []
    exposure_sessions = {
        isin: set(cross.loc[cross["is_unresolved_exit_member"] & cross["isin"].eq(isin), "session_date"])
        for isin in BENIGN_EXIT_ISINS
    }
    for isin, sessions in exposure_sessions.items():
        marked = rank_ic.copy()
        marked["period"] = np.where(marked["session_date"].isin(sessions), "official_member_unresolved", "outside_member_period")
        grouped = marked.dropna(subset=["rank_ic"]).groupby(
            ["feature", "label", "horizon_sessions", "period"], as_index=False
        ).agg(sessions=("rank_ic", "size"), mean_rank_ic=("rank_ic", "mean"), median_rank_ic=("rank_ic", "median"))
        grouped["exit_isin"] = isin
        exit_rows.extend(grouped.to_dict("records"))
    exit_period_sensitivity = pd.DataFrame(exit_rows)
    exit_exposure_by_session = coverage[[
        "session_date", "official_member_count", "price_usable_member_count", "price_coverage_ratio",
        "unresolved_exit_member_count", "active_unresolved_exit_isins", "wig_trend_regime",
    ]].copy()
    return DiagnosticOutputs(
        cross, coverage, feature_coverage, rank_ic, quantile_returns, monotonicity, turnover,
        missing_by_session, missing_overall, feature_missing_summary, annual, regime, uncertainty,
        non_overlap, coverage_sensitivity, exit_period_sensitivity, exit_exposure_by_session,
    )
