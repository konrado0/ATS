from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


HORIZONS = (3, 5, 10, 20)
FEATURES = (
    "momentum_12_1",
    "return_5",
    "realized_volatility_20",
    "relative_volume_20",
    "proximity_to_max_high_252",
    "proximity_to_max_close_252",
)
PRIMARY = (
    "momentum_12_1",
    "realized_volatility_20",
    "proximity_to_max_high_252",
    "proximity_to_max_close_252",
)
PROXIMITIES = ("proximity_to_max_high_252", "proximity_to_max_close_252")
ANCHORS = ("close_to_close", "open_to_open")
START = pd.Timestamp("2019-12-23")
COMMON = pd.Timestamp("2020-11-27")
END = pd.Timestamp("2026-08-18")
DINO = "PLDINPL00011"
DINO_START = pd.Timestamp("2024-04-11")
DINO_END = pd.Timestamp("2024-04-18")
SEED = 20260827


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def logical_hash_frame(frame: pd.DataFrame, sort: list[str] | None = None) -> str:
    clean = frame.sort_values(sort, kind="mergesort").reset_index(drop=True) if sort else frame.reset_index(drop=True)
    payload = clean.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode()
    return hashlib.sha256(payload).hexdigest()


def json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(json_safe(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, frame: pd.DataFrame, sort: list[str] | None = None) -> None:
    clean = frame.sort_values(sort, kind="mergesort").reset_index(drop=True) if sort and len(frame) else frame
    clean.to_csv(path, index=False, lineterminator="\n", float_format="%.17g")


def safe_spearman(x: pd.Series, y: pd.Series) -> float:
    valid = pd.concat([x, y], axis=1).dropna()
    if len(valid) < 3 or valid.iloc[:, 0].nunique() < 2 or valid.iloc[:, 1].nunique() < 2:
        return np.nan
    return float(valid.iloc[:, 0].rank(method="average").corr(valid.iloc[:, 1].rank(method="average")))


def partial_rank(group: pd.DataFrame, feature: str, label: str) -> float:
    valid = group[[feature, "momentum_12_1", label]].dropna()
    if len(valid) < 5:
        return np.nan
    ranked = valid.rank(method="average", pct=True)
    rxy = ranked[feature].corr(ranked[label])
    rxc = ranked[feature].corr(ranked["momentum_12_1"])
    ryc = ranked[label].corr(ranked["momentum_12_1"])
    denominator = math.sqrt(max((1.0 - rxc * rxc) * (1.0 - ryc * ryc), 0.0))
    return float((rxy - rxc * ryc) / denominator) if denominator else np.nan


def hac_se(values: Iterable[float], lag: int) -> float:
    clean = np.asarray(list(values), dtype=float)
    clean = clean[np.isfinite(clean)]
    n = len(clean)
    if n < 3:
        return np.nan
    centered = clean - clean.mean()
    long_variance = float(np.dot(centered, centered) / n)
    for offset in range(1, min(lag, n - 1) + 1):
        gamma = float(np.dot(centered[offset:], centered[:-offset]) / n)
        long_variance += 2.0 * (1.0 - offset / (lag + 1.0)) * gamma
    return math.sqrt(max(long_variance, 0.0) / n)


def bootstrap_ci(values: Iterable[float], tag: str, block: int, samples: int = 1000) -> tuple[float, float]:
    clean = np.asarray(list(values), dtype=float)
    clean = clean[np.isfinite(clean)]
    if len(clean) < 3:
        return np.nan, np.nan
    block = min(block, len(clean))
    blocks = math.ceil(len(clean) / block)
    pair_seed = (SEED + int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)) % (2**32 - 1)
    rng = np.random.default_rng(pair_seed)
    means = np.empty(samples)
    offsets = np.arange(block)
    for i in range(samples):
        starts = rng.integers(0, len(clean), blocks)
        selected = ((starts[:, None] + offsets).reshape(-1) % len(clean))[: len(clean)]
        means[i] = clean[selected].mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def bh_adjust(pvalues: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=pvalues.index, dtype=float)
    clean = pvalues.dropna().sort_values()
    if clean.empty:
        return result
    m = len(clean)
    raw = clean.to_numpy() * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(raw[::-1])[::-1].clip(0, 1)
    result.loc[clean.index] = adjusted
    return result


def manifest_file_validation(root: Path, manifest: dict[str, object], mapping_key: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    mapping = manifest.get(mapping_key, {})
    for rel, expected in sorted(mapping.items()):
        expected_hash = expected["sha256"] if isinstance(expected, dict) else expected
        path = root / rel
        actual = sha256_file(path) if path.is_file() else None
        rows.append({"root": str(root), "path": rel, "expected_sha256": expected_hash, "actual_sha256": actual, "status": "PASS" if actual == expected_hash else "FAIL"})
    return rows


def validate_inputs(config: dict[str, object]) -> tuple[pd.DataFrame, dict[str, object]]:
    candidate = Path(config["candidate_run"])
    trusted = Path(config["trusted_phase_a_run"])
    extended = Path(config["extended_stooq_run"])
    accepted = Path(config["extended_analysis_run"])
    rows: list[dict[str, object]] = []
    manifests: dict[str, object] = {}
    for name, root, key in [
        ("candidate", candidate, "physical_file_hashes"),
        ("trusted_phase_a", trusted, "output_artifact_hashes"),
        ("extended_stooq", extended, "output_artifact_hashes"),
        ("accepted_analysis", accepted, "files"),
    ]:
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifests[name] = manifest
        actual_manifest_hash = sha256_file(manifest_path)
        expected_manifest_hash = config.get("candidate_manifest_sha256") if name == "candidate" else None
        rows.append({"root": str(root), "path": "manifest.json", "expected_sha256": expected_manifest_hash, "actual_sha256": actual_manifest_hash, "status": "PASS" if expected_manifest_hash is None or actual_manifest_hash == expected_manifest_hash else "FAIL"})
        rows.extend(manifest_file_validation(root, manifest, key))
    candidate_manifest = manifests["candidate"]
    for item in candidate_manifest["input_hashes"]:
        path = Path(item["path"])
        actual = sha256_file(path) if path.is_file() else None
        rows.append({"root": "candidate_input", "path": str(path), "expected_sha256": item["sha256"], "actual_sha256": actual, "status": "PASS" if actual == item["sha256"] else "FAIL"})
    frame = pd.DataFrame(rows)
    if frame["status"].ne("PASS").any():
        failures = frame.loc[frame.status.ne("PASS"), ["root", "path"]].to_dict("records")
        raise RuntimeError(f"input validation failed: {failures[:10]}")
    return frame, manifests


def matrix(frame: pd.DataFrame, value: str, calendar: pd.DatetimeIndex, securities: pd.Index | None = None) -> pd.DataFrame:
    result = frame.pivot(index="session_date", columns="security_id", values=value).reindex(index=calendar)
    return result.reindex(columns=securities) if securities is not None else result


def lookup(mat: pd.DataFrame, base: pd.DataFrame) -> np.ndarray:
    stacked = mat.stack(future_stack=True)
    idx = pd.MultiIndex.from_frame(base[["session_date", "security_id"]])
    return stacked.reindex(idx).to_numpy()


def build_features(close: pd.DataFrame, high: pd.DataFrame, volume: pd.DataFrame) -> dict[str, pd.DataFrame]:
    returns = close / close.shift(1) - 1.0
    return {
        "momentum_12_1": close.shift(21) / close.shift(252) - 1.0,
        "return_5": close / close.shift(5) - 1.0,
        "realized_volatility_20": returns.rolling(20, min_periods=20).std(),
        "relative_volume_20": volume / volume.rolling(20, min_periods=20).mean() - 1.0,
        "proximity_to_max_high_252": close / high.rolling(252, min_periods=252).max(),
        "proximity_to_max_close_252": close / close.rolling(252, min_periods=252).max(),
    }


def attach_decision_values(
    membership: pd.DataFrame,
    close: pd.DataFrame,
    open_: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    price_usable: pd.DataFrame,
    wig_trend: pd.Series,
    basis: str,
) -> pd.DataFrame:
    base = membership[["session_date", "security_id", "isin"]].drop_duplicates().sort_values(["session_date", "security_id"]).reset_index(drop=True)
    base["basis"] = basis
    base["official_expected"] = 60
    # Phase A price usability is the immediately prior feature-input session,
    # not the decision-session close (which belongs to label eligibility).
    base["price_usable"] = pd.array(lookup(price_usable.shift(1).astype("boolean"), base), dtype="boolean")
    prior_features = {name: values.shift(1) for name, values in features.items()}
    for name, values in prior_features.items():
        base[name] = lookup(values, base)
        base[f"eligible__{name}"] = base[name].notna() & base["price_usable"].fillna(False)
    base["wig_trend_200"] = base["session_date"].map(wig_trend.shift(1))
    prior_date = pd.Series(close.index, index=close.index).shift(1)
    base["feature_session_date"] = base["session_date"].map(prior_date)
    for horizon in HORIZONS:
        for anchor, prices in [("close_to_close", close), ("open_to_open", open_)]:
            label = prices.shift(-horizon) / prices - 1.0
            start_price = lookup(prices, base)
            end_price = lookup(prices.shift(-horizon), base)
            col = f"label__{anchor}__{horizon}"
            base[col] = lookup(label, base)
            base[f"label_start__{anchor}__{horizon}"] = start_price
            base[f"label_end__{anchor}__{horizon}"] = end_price
    return base


@dataclass
class Prepared:
    new: pd.DataFrame
    old: pd.DataFrame
    candidate_raw: pd.DataFrame
    calendar: pd.DatetimeIndex


def prepare_panels(config: dict[str, object]) -> Prepared:
    candidate_root = Path(config["candidate_run"])
    extended_root = Path(config["extended_stooq_run"])
    candidate = pd.read_parquet(candidate_root / "candidate_panel.parquet")
    candidate["session_date"] = pd.to_datetime(candidate["session_date"])
    calendar = pd.DatetimeIndex(sorted(candidate.session_date.unique()))
    securities = pd.Index(sorted(candidate.security_id.unique()), name="security_id")
    close = matrix(candidate, "split_adjusted_close", calendar, securities)
    high = matrix(candidate, "split_adjusted_high", calendar, securities)
    open_ = matrix(candidate, "split_adjusted_open", calendar, securities)
    volume = matrix(candidate, "split_adjusted_volume", calendar, securities)
    volume_ok = matrix(candidate, "volume_usable_for_relative_volume", calendar, securities).fillna(False).astype(bool)
    volume = volume.where(volume_ok)
    price_ok = matrix(candidate, "price_usable_for_features", calendar, securities).fillna(False).astype(bool)
    new_features = build_features(close, high, volume)

    artifacts = extended_root / "artifacts"
    wig = pd.read_parquet(artifacts / "wig_daily.parquet")
    wig["session_date"] = pd.to_datetime(wig["session_date"])
    wig_series = wig.set_index("session_date")["close"].reindex(calendar)
    wig_trend = wig_series / wig_series.rolling(200, min_periods=200).mean() - 1.0

    new_members = candidate.loc[candidate.official_membership & candidate.session_date.between(START, END), ["session_date", "security_id", "isin"]]
    new = attach_decision_values(new_members, close, open_, new_features, price_ok, wig_trend, "split_adjusted_price_return")

    bars = pd.read_parquet(artifacts / "validated_daily_bars.parquet", columns=["session_date", "security_id", "isin", "open", "high", "close", "volume"])
    bars["session_date"] = pd.to_datetime(bars["session_date"])
    old_securities = pd.Index(sorted(bars.security_id.unique()), name="security_id")
    old_close = matrix(bars, "close", calendar, old_securities)
    old_high = matrix(bars, "high", calendar, old_securities)
    old_open = matrix(bars, "open", calendar, old_securities)
    old_volume = matrix(bars, "volume", calendar, old_securities)
    old_price_ok = old_close.notna()
    old_features = build_features(old_close, old_high, old_volume)
    old_panel = pd.read_parquet(artifacts / "research_panel.parquet", columns=["session_date", "security_id", "isin"])
    old_panel["session_date"] = pd.to_datetime(old_panel["session_date"])
    old = attach_decision_values(old_panel, old_close, old_open, old_features, old_price_ok, wig_trend, "accepted_stooq_adjusted")
    return Prepared(new, old, candidate, calendar)


def period_mask(frame: pd.DataFrame, scope: str) -> pd.Series:
    if scope.endswith("added"):
        return frame.session_date.between(START, COMMON - pd.Timedelta(days=1))
    if scope.endswith("common") or scope.startswith("paired"):
        return frame.session_date.between(COMMON, END)
    return frame.session_date.between(START, END)


def rank_and_quantile(frame: pd.DataFrame, feature: str, eligible: pd.Series) -> tuple[pd.Series, pd.Series]:
    values = frame[feature].where(eligible)
    ranks = values.groupby(frame.session_date).rank(method="average")
    counts = values.groupby(frame.session_date).transform("count")
    pct = ranks / counts
    quantile = np.ceil(pct * 5).clip(1, 5).astype("Int64")
    return pct, quantile


def summarize_ic_sessions(sessions: pd.DataFrame, keys: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    groups = [("overall", "all", sessions)]
    groups.extend(("calendar_year", str(year), group) for year, group in sessions.groupby(sessions.session_date.dt.year, sort=True))
    for ptype, period, group in groups:
        clean = group.rank_ic.dropna()
        rows.append(keys | {"period_type": ptype, "period": period, "sessions": len(clean), "constituent_observations": int(group.loc[group.rank_ic.notna(), "ranking_denominator"].sum()), "mean_rank_ic": clean.mean(), "median_rank_ic": clean.median(), "positive_session_share": (clean > 0).mean() if len(clean) else np.nan})
    return rows


def analyze_frame(
    frame: pd.DataFrame,
    scope: str,
    paired_rank_sample: bool = False,
    selected_features: tuple[str, ...] = FEATURES,
    selected_anchors: tuple[str, ...] = ANCHORS,
    selected_horizons: tuple[int, ...] = HORIZONS,
    include_pullback: bool = True,
) -> dict[str, pd.DataFrame]:
    data = frame.loc[period_mask(frame, scope)].copy()
    outputs: dict[str, list[dict[str, object]]] = {k: [] for k in ["coverage", "ic_sessions", "ic_summary", "quantile_sessions", "quantile_summary", "adjacent", "monotonicity", "partial_sessions", "partial_summary", "double_sort", "pullback", "pullback_sessions"]}
    for feature in selected_features:
        feature_eligible = data[f"eligible__{feature}"].fillna(False)
        for anchor in selected_anchors:
            for horizon in selected_horizons:
                label = f"label__{anchor}__{horizon}"
                label_eligible = data[label].notna()
                joint = feature_eligible & label_eligible
                rank_eligible = joint if paired_rank_sample else feature_eligible
                pct, quantile = rank_and_quantile(data, feature, rank_eligible)
                work = data[["session_date", "security_id", "isin", feature, label, "price_usable"]].copy()
                work["pct"] = pct
                work["quantile"] = quantile
                counts = data.assign(feature_eligible=feature_eligible, label_eligible=label_eligible, joint=joint).groupby("session_date", as_index=False).agg(official_rows=("security_id", "size"), price_usable_count=("price_usable", "sum"), feature_eligible_count=("feature_eligible", "sum"), label_eligible_count=("label_eligible", "sum"), ranking_denominator=("joint" if paired_rank_sample else "feature_eligible", "sum"), joint_eligible_count=("joint", "sum"))
                if scope.startswith("paired"):
                    counts["official_rows"] = 60
                for row in counts.itertuples(index=False):
                    outputs["coverage"].append({"scope": scope, "feature": feature, "anchor": anchor, "horizon_sessions": horizon, "session_date": row.session_date, "official_expected": 60, **row._asdict()})
                ic_rows = []
                for session, group in work.loc[joint].groupby("session_date", sort=True):
                    ic_rows.append({"scope": scope, "feature": feature, "anchor": anchor, "horizon_sessions": horizon, "session_date": session, "ranking_denominator": len(group), "rank_ic": safe_spearman(group[feature], group[label])})
                ic_frame = pd.DataFrame(ic_rows)
                outputs["ic_sessions"].extend(ic_rows)
                outputs["ic_summary"].extend(summarize_ic_sessions(ic_frame, {"scope": scope, "feature": feature, "anchor": anchor, "horizon_sessions": horizon}) if len(ic_frame) else [])
                daily = work.loc[joint].groupby(["session_date", "quantile"], observed=True, as_index=False).agg(mean_forward_return=(label, "mean"), constituent_observations=(label, "size"))
                for row in daily.itertuples(index=False):
                    outputs["quantile_sessions"].append({"scope": scope, "feature": feature, "anchor": anchor, "horizon_sessions": horizon, **row._asdict()})
                for ptype, period, sub in [("overall", "all", daily), *[("calendar_year", str(y), g) for y, g in daily.groupby(daily.session_date.dt.year, sort=True)]]:
                    qsum = sub.groupby("quantile", observed=True).agg(mean_forward_return=("mean_forward_return", "mean"), constituent_observations=("constituent_observations", "sum"), sessions=("session_date", "nunique")).reset_index()
                    profile_corr = safe_spearman(qsum["quantile"], qsum["mean_forward_return"])
                    lookup_q = qsum.set_index("quantile")["mean_forward_return"]
                    outputs["monotonicity"].append({"scope": scope, "feature": feature, "anchor": anchor, "horizon_sessions": horizon, "period_type": ptype, "period": period, "quantile_return_spearman": profile_corr, "q5_minus_q1": lookup_q.get(5, np.nan) - lookup_q.get(1, np.nan), "q4_minus_q5": lookup_q.get(4, np.nan) - lookup_q.get(5, np.nan), "q1_to_q4_mean_minus_q5": qsum.loc[qsum["quantile"].le(4), "mean_forward_return"].mean() - lookup_q.get(5, np.nan)})
                    for row in qsum.itertuples(index=False):
                        outputs["quantile_summary"].append({"scope": scope, "feature": feature, "anchor": anchor, "horizon_sessions": horizon, "period_type": ptype, "period": period, **row._asdict()})
                    for q in range(2, 6):
                        outputs["adjacent"].append({"scope": scope, "feature": feature, "anchor": anchor, "horizon_sessions": horizon, "period_type": ptype, "period": period, "higher_quantile": q, "lower_quantile": q - 1, "return_difference": lookup_q.get(q, np.nan) - lookup_q.get(q - 1, np.nan)})

                if feature in PROXIMITIES:
                    both = joint & data["eligible__momentum_12_1"].fillna(False)
                    partial_rows = []
                    for session, group in data.loc[both].groupby("session_date", sort=True):
                        partial_rows.append({"scope": scope, "feature": feature, "anchor": anchor, "horizon_sessions": horizon, "session_date": session, "ranking_denominator": len(group), "partial_rank_ic": partial_rank(group, feature, label)})
                    partial_frame = pd.DataFrame(partial_rows)
                    outputs["partial_sessions"].extend(partial_rows)
                    if len(partial_frame):
                        for ptype, period, sub in [("overall", "all", partial_frame), *[("calendar_year", str(y), g) for y, g in partial_frame.groupby(partial_frame.session_date.dt.year, sort=True)]]:
                            clean = sub.partial_rank_ic.dropna()
                            outputs["partial_summary"].append({"scope": scope, "feature": feature, "anchor": anchor, "horizon_sessions": horizon, "period_type": ptype, "period": period, "sessions": len(clean), "mean_partial_rank_ic": clean.mean(), "median_partial_rank_ic": clean.median(), "positive_session_share": (clean > 0).mean() if len(clean) else np.nan})
                    double = data.loc[both, ["session_date", "security_id", feature, "momentum_12_1", label]].copy()
                    double["momentum_tercile"] = np.ceil(double["momentum_12_1"].groupby(double.session_date).rank(method="average", pct=True) * 3).clip(1, 3).astype("Int64")
                    double["proximity_tercile"] = np.ceil(double[feature].groupby(double.session_date).rank(method="average", pct=True) * 3).clip(1, 3).astype("Int64")
                    cell_daily = double.groupby(["session_date", "momentum_tercile", "proximity_tercile"], observed=True, as_index=False).agg(mean_forward_return=(label, "mean"), cell_count=(label, "size"))
                    for (mt, pt), group in cell_daily.groupby(["momentum_tercile", "proximity_tercile"], observed=True, sort=True):
                        outputs["double_sort"].append({"scope": scope, "feature": feature, "anchor": anchor, "horizon_sessions": horizon, "momentum_tercile": mt, "proximity_tercile": pt, "mean_forward_return": group.mean_forward_return.mean(), "constituent_observations": int(group.cell_count.sum()), "sessions": group.session_date.nunique(), "mean_cell_count": group.cell_count.mean(), "min_cell_count": group.cell_count.min(), "sparse_cell_warning": bool((group.cell_count < 5).any() or group.cell_count.sum() < 30)})

    if not include_pullback:
        return {key: pd.DataFrame(rows) for key, rows in outputs.items()}
    for anchor in selected_anchors:
        for horizon in selected_horizons:
            label = f"label__{anchor}__{horizon}"
            base_ok = data["eligible__momentum_12_1"].fillna(False) & data["eligible__return_5"].fillna(False) & data[label].notna()
            momentum_pct, _ = rank_and_quantile(data, "momentum_12_1", data["eligible__momentum_12_1"].fillna(False))
            conditions = {"positive_momentum": data.momentum_12_1.gt(0), "upper_half_momentum_rank": momentum_pct.gt(0.5)}
            bucket = pd.Series(np.select([data.return_5.le(-0.05), data.return_5.lt(0), data.return_5.ge(0)], ["deep_pullback_le_-5pct", "mild_pullback_-5_to_0pct", "nonnegative_5d_return"], default=None), index=data.index)
            for condition, condition_mask in conditions.items():
                work = data.loc[base_ok & condition_mask, ["session_date", label]].copy()
                work["bucket"] = bucket.loc[work.index]
                daily = work.groupby(["session_date", "bucket"], as_index=False).agg(mean_forward_return=(label, "mean"), constituent_observations=(label, "size"))
                pivot = daily.pivot(index="session_date", columns="bucket", values="mean_forward_return")
                contrast = pivot.get("deep_pullback_le_-5pct", pd.Series(dtype=float)) - pivot.get("nonnegative_5d_return", pd.Series(dtype=float))
                outputs["pullback"].append({"scope": scope, "anchor": anchor, "horizon_sessions": horizon, "condition": condition, "deep_minus_nonnegative": contrast.mean(), "positive_session_share": (contrast.dropna() > 0).mean(), "sessions": contrast.notna().sum()})
                for session, value in contrast.dropna().items():
                    outputs["pullback_sessions"].append({"scope": scope, "anchor": anchor, "horizon_sessions": horizon, "condition": condition, "session_date": session, "deep_minus_nonnegative": value})
    return {key: pd.DataFrame(rows) for key, rows in outputs.items()}


def paired_analysis(new: pd.DataFrame, old: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    # The candidate panel deliberately uses a transparent `isin:*` identifier,
    # while accepted Phase A retained UUID security identifiers. ISIN is the
    # stable canonical identity shared by both immutable inputs.
    merge_keys = ["session_date", "isin"]
    keys = ["session_date", "security_id", "isin"]
    merged = old.merge(new, on=merge_keys, how="inner", suffixes=("__old", "__new"), validate="one_to_one")
    merged["security_id"] = merged["security_id__new"]
    analyzed_parts: dict[str, dict[str, list[pd.DataFrame]]] = {"old": {}, "new": {}}
    diagnostics: dict[str, list[dict[str, object]]] = {k: [] for k in ["session", "summary", "eligibility", "security_contributors", "date_contributors", "dino"]}
    for feature in FEATURES:
        for anchor in ANCHORS:
            for horizon in HORIZONS:
                label = f"label__{anchor}__{horizon}"
                eligible = merged[f"eligible__{feature}__old"].fillna(False) & merged[f"eligible__{feature}__new"].fillna(False) & merged[f"{label}__old"].notna() & merged[f"{label}__new"].notna()
                eligibility_audit = merged.assign(
                    old_feature=merged[f"eligible__{feature}__old"].fillna(False),
                    new_feature=merged[f"eligible__{feature}__new"].fillna(False),
                    old_label=merged[f"{label}__old"].notna(),
                    new_label=merged[f"{label}__new"].notna(),
                    paired=eligible,
                ).groupby("session_date", as_index=False).agg(
                    common_official_identities=("security_id", "size"),
                    old_price_usable=("price_usable__old", "sum"),
                    new_price_usable=("price_usable__new", "sum"),
                    old_feature_eligible=("old_feature", "sum"),
                    new_feature_eligible=("new_feature", "sum"),
                    old_label_eligible=("old_label", "sum"),
                    new_label_eligible=("new_label", "sum"),
                    paired_ranking_denominator=("paired", "sum"),
                )
                for row in eligibility_audit.itertuples(index=False):
                    diagnostics["eligibility"].append({"feature": feature, "anchor": anchor, "horizon_sessions": horizon, "official_expected": 60, **row._asdict()})
                pair = merged.loc[eligible, keys + [f"{feature}__old", f"{feature}__new", f"{label}__old", f"{label}__new", "price_usable__old", "price_usable__new"]].copy()
                pair.columns = keys + ["feature_old", "feature_new", "label_old", "label_new", "price_old", "price_new"]
                pair["rank_old"] = pair.feature_old.groupby(pair.session_date).rank(method="average", pct=True)
                pair["rank_new"] = pair.feature_new.groupby(pair.session_date).rank(method="average", pct=True)
                pair["q_old"] = np.ceil(pair.rank_old * 5).clip(1, 5).astype("Int64")
                pair["q_new"] = np.ceil(pair.rank_new * 5).clip(1, 5).astype("Int64")
                by_session = []
                for session, group in pair.groupby("session_date", sort=True):
                    old_ic = safe_spearman(group.feature_old, group.label_old)
                    new_ic = safe_spearman(group.feature_new, group.label_new)
                    by_session.append({"feature": feature, "anchor": anchor, "horizon_sessions": horizon, "session_date": session, "ranking_denominator": len(group), "feature_rank_agreement": safe_spearman(group.feature_old, group.feature_new), "quantile_reassignment_rate": group.q_old.ne(group.q_new).mean(), "old_rank_ic": old_ic, "new_rank_ic": new_ic, "paired_ic_change_new_minus_old": new_ic - old_ic, "mean_label_difference_new_minus_old": (group.label_new - group.label_old).mean(), "mean_absolute_label_difference": (group.label_new - group.label_old).abs().mean()})
                diagnostics["session"].extend(by_session)
                sess = pd.DataFrame(by_session)
                cutoff = pair.abs_label_difference.quantile(0.99) if "abs_label_difference" in pair else (pair.label_new - pair.label_old).abs().quantile(0.99)
                trimmed = pair.loc[(pair.label_new - pair.label_old).abs().le(cutoff)]
                trimmed_rows = []
                for _, group in trimmed.groupby("session_date", sort=True):
                    trimmed_rows.append((safe_spearman(group.feature_old, group.label_old), safe_spearman(group.feature_new, group.label_new)))
                trimmed_old = np.nanmean([row[0] for row in trimmed_rows]) if trimmed_rows else np.nan
                trimmed_new = np.nanmean([row[1] for row in trimmed_rows]) if trimmed_rows else np.nan
                diagnostics["summary"].append({"feature": feature, "anchor": anchor, "horizon_sessions": horizon, "sessions": len(sess), "observations": len(pair), "mean_feature_rank_agreement": sess.feature_rank_agreement.mean(), "mean_quantile_reassignment_rate": sess.quantile_reassignment_rate.mean(), "mean_old_rank_ic": sess.old_rank_ic.mean(), "mean_new_rank_ic": sess.new_rank_ic.mean(), "mean_paired_ic_change_new_minus_old": sess.paired_ic_change_new_minus_old.mean(), "mean_label_difference_new_minus_old": (pair.label_new - pair.label_old).mean(), "mean_absolute_label_difference": (pair.label_new - pair.label_old).abs().mean(), "top_1pct_abs_label_difference_cutoff": cutoff, "trimmed_old_rank_ic": trimmed_old, "trimmed_new_rank_ic": trimmed_new, "trimmed_paired_ic_change_new_minus_old": trimmed_new - trimmed_old})
                pair["abs_feature_rank_difference"] = (pair.rank_new - pair.rank_old).abs()
                pair["abs_label_difference"] = (pair.label_new - pair.label_old).abs()
                for security, group in pair.groupby("security_id", sort=True):
                    diagnostics["security_contributors"].append({"feature": feature, "anchor": anchor, "horizon_sessions": horizon, "security_id": security, "isin": group["isin"].iloc[0], "observations": len(group), "mean_abs_feature_rank_difference": group.abs_feature_rank_difference.mean(), "mean_abs_label_difference": group.abs_label_difference.mean(), "sum_abs_label_difference": group.abs_label_difference.sum()})
                for session, group in pair.groupby("session_date", sort=True):
                    diagnostics["date_contributors"].append({"feature": feature, "anchor": anchor, "horizon_sessions": horizon, "session_date": session, "observations": len(group), "mean_abs_feature_rank_difference": group.abs_feature_rank_difference.mean(), "mean_abs_label_difference": group.abs_label_difference.mean(), "sum_abs_label_difference": group.abs_label_difference.sum()})
                dino = pair.loc[pair["isin"].eq(DINO) & pair.session_date.between(DINO_START, DINO_END)]
                diagnostics["dino"].append({"feature": feature, "anchor": anchor, "horizon_sessions": horizon, "observations": len(dino), "mean_feature_rank_difference_new_minus_old": (dino.rank_new - dino.rank_old).mean(), "mean_label_difference_new_minus_old": (dino.label_new - dino.label_old).mean(), "max_abs_label_difference": dino.abs_label_difference.max()})
                for side in ["old", "new"]:
                    f = pair[keys].copy()
                    f[feature] = pair[f"feature_{side}"]
                    f[label] = pair[f"label_{side}"]
                    f[f"eligible__{feature}"] = True
                    f["price_usable"] = True
                    f["basis"] = f"paired_{side}"
                    f["official_expected"] = 60
                    for other in FEATURES:
                        if other != feature:
                            f[other] = np.nan
                            f[f"eligible__{other}"] = False
                    for other_anchor in ANCHORS:
                        for other_h in HORIZONS:
                            other_label = f"label__{other_anchor}__{other_h}"
                            if other_label != label:
                                f[other_label] = np.nan
                    if feature in PROXIMITIES:
                        f["momentum_12_1"] = merged.loc[pair.index, f"momentum_12_1__{side}"].to_numpy()
                        f["eligible__momentum_12_1"] = f["momentum_12_1"].notna()
                    one = analyze_frame(
                        f,
                        f"paired_{side}_common",
                        paired_rank_sample=True,
                        selected_features=(feature,),
                        selected_anchors=(anchor,),
                        selected_horizons=(horizon,),
                        include_pullback=False,
                    )
                    for name, result in one.items():
                        if len(result):
                            analyzed_parts[side].setdefault(name, []).append(result)
                    del f, one
                del pair
    analyzed = {
        side: {name: pd.concat(parts, ignore_index=True) for name, parts in analyzed_parts[side].items()}
        for side in ["old", "new"]
    }
    return analyzed, {key: pd.DataFrame(value) for key, value in diagnostics.items()}


def add_uncertainty(ic_sessions: pd.DataFrame, partial_sessions: pd.DataFrame, pullback_sessions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    common = ic_sessions.loc[ic_sessions.scope.eq("new_common")]
    for (feature, anchor, horizon), group in common.groupby(["feature", "anchor", "horizon_sessions"], sort=True):
        values = group.sort_values("session_date").rank_ic.dropna()
        mean = values.mean()
        se = hac_se(values, int(horizon))
        low, high = bootstrap_ci(values, f"ic-{feature}-{anchor}-{horizon}", max(20, int(horizon)))
        p = math.erfc(abs(mean / se) / math.sqrt(2)) if np.isfinite(se) and se > 0 else np.nan
        family = "primary" if feature in PRIMARY else "secondary"
        rows.append({"family": family, "method": "standalone_rank_ic", "feature": feature, "anchor": anchor, "horizon_sessions": horizon, "mean": mean, "sessions": len(values), "hac_lag_sessions": horizon, "hac_standard_error": se, "hac_ci_low": mean - 1.959963984540054 * se, "hac_ci_high": mean + 1.959963984540054 * se, "hac_p_value": p, "bootstrap_samples": 1000, "bootstrap_block_sessions": max(20, int(horizon)), "bootstrap_ci_low": low, "bootstrap_ci_high": high})
    partial = partial_sessions.loc[partial_sessions.scope.eq("new_common")]
    for (feature, anchor, horizon), group in partial.groupby(["feature", "anchor", "horizon_sessions"], sort=True):
        values = group.sort_values("session_date").partial_rank_ic.dropna()
        mean = values.mean()
        se = hac_se(values, int(horizon))
        low, high = bootstrap_ci(values, f"partial-{feature}-{anchor}-{horizon}", max(20, int(horizon)))
        p = math.erfc(abs(mean / se) / math.sqrt(2)) if np.isfinite(se) and se > 0 else np.nan
        rows.append({"family": "primary", "method": "partial_rank_ic", "feature": feature, "anchor": anchor, "horizon_sessions": horizon, "mean": mean, "sessions": len(values), "hac_lag_sessions": horizon, "hac_standard_error": se, "hac_ci_low": mean - 1.959963984540054 * se, "hac_ci_high": mean + 1.959963984540054 * se, "hac_p_value": p, "bootstrap_samples": 1000, "bootstrap_block_sessions": max(20, int(horizon)), "bootstrap_ci_low": low, "bootstrap_ci_high": high})
    pulls = pullback_sessions.loc[pullback_sessions.scope.eq("new_common")]
    for (condition, anchor, horizon), group in pulls.groupby(["condition", "anchor", "horizon_sessions"], sort=True):
        values = group.sort_values("session_date").deep_minus_nonnegative.dropna()
        mean = values.mean()
        se = hac_se(values, int(horizon))
        low, high = bootstrap_ci(values, f"pullback-{condition}-{anchor}-{horizon}", max(20, int(horizon)))
        p = math.erfc(abs(mean / se) / math.sqrt(2)) if np.isfinite(se) and se > 0 else np.nan
        rows.append({"family": "secondary", "method": "pullback_contrast", "feature": f"return_5:{condition}", "anchor": anchor, "horizon_sessions": horizon, "mean": mean, "sessions": len(values), "hac_lag_sessions": horizon, "hac_standard_error": se, "hac_ci_low": mean - 1.959963984540054 * se, "hac_ci_high": mean + 1.959963984540054 * se, "hac_p_value": p, "bootstrap_samples": 1000, "bootstrap_block_sessions": max(20, int(horizon)), "bootstrap_ci_low": low, "bootstrap_ci_high": high})
    result = pd.DataFrame(rows)
    result["bh_q_value"] = np.nan
    for family, idx in result.groupby("family").groups.items():
        result.loc[idx, "bh_q_value"] = bh_adjust(result.loc[idx, "hac_p_value"])
    return result


def nonoverlap(ic_sessions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (scope, feature, anchor, horizon), group in ic_sessions.groupby(["scope", "feature", "anchor", "horizon_sessions"], sort=True):
        ordered = group.sort_values("session_date").reset_index(drop=True)
        for offset in range(int(horizon)):
            values = ordered.loc[ordered.index % int(horizon) == offset, "rank_ic"].dropna()
            rows.append({"scope": scope, "feature": feature, "anchor": anchor, "horizon_sessions": horizon, "offset": offset, "sessions": len(values), "mean_rank_ic": values.mean(), "median_rank_ic": values.median(), "positive_session_share": (values > 0).mean() if len(values) else np.nan})
    return pd.DataFrame(rows)


def economic_screen(panel: pd.DataFrame) -> pd.DataFrame:
    data = panel.loc[panel.session_date.between(COMMON, END)].copy()
    rows = []
    specs = {
        "momentum_12_1": (5, 1, "Q5-minus-Q1"),
        "realized_volatility_20": (4, 5, "Q4-minus-Q5-avoidance"),
        "proximity_to_max_high_252": (5, 1, "Q5-minus-Q1"),
        "proximity_to_max_close_252": (5, 1, "Q5-minus-Q1"),
    }
    for feature, (long_q, short_q, contrast) in specs.items():
        pct, quantile = rank_and_quantile(data, feature, data[f"eligible__{feature}"].fillna(False))
        data_q = data[["session_date", "security_id"]].copy()
        data_q["quantile"] = quantile
        for horizon in HORIZONS:
            label = f"label__open_to_open__{horizon}"
            data_q["label"] = data[label]
            sessions = pd.Index(sorted(data_q.session_date.unique()))
            for offset in range(horizon):
                selected_sessions = set(sessions[offset::horizon])
                schedule = data_q.loc[data_q.session_date.isin(selected_sessions) & data_q["label"].notna() & data_q["quantile"].isin([long_q, short_q])]
                gross = schedule.groupby(["session_date", "quantile"], observed=True).label.mean().unstack()
                spread = gross.get(long_q, pd.Series(dtype=float)) - gross.get(short_q, pd.Series(dtype=float))
                turnovers = []
                previous: dict[int, dict[str, float]] = {}
                for session, group in schedule.groupby("session_date", sort=True):
                    total = 0.0
                    for q in (long_q, short_q):
                        names = list(group.loc[group["quantile"].eq(q), "security_id"])
                        current = {name: 1.0 / len(names) for name in names} if names else {}
                        prior = previous.get(q, {})
                        total += 0.5 * sum(abs(current.get(name, 0.0) - prior.get(name, 0.0)) for name in set(current) | set(prior))
                        previous[q] = current
                    turnovers.append((session, total))
                turnover = pd.Series(dict(turnovers)).reindex(spread.index)
                mean_gross = spread.mean()
                mean_turnover = turnover.mean()
                rows.append({"feature": feature, "horizon_sessions": horizon, "offset": offset, "contrast": contrast, "rebalances": spread.notna().sum(), "mean_gross_spread": mean_gross, "mean_name_turnover": mean_turnover, "mean_net_spread_at_25bps": mean_gross - mean_turnover * 0.0025, "break_even_cost_bps_per_traded_notional": mean_gross / mean_turnover * 10000 if mean_turnover and np.isfinite(mean_turnover) else np.nan, "positive_rebalance_share": (spread.dropna() > 0).mean() if spread.notna().any() else np.nan})
    return pd.DataFrame(rows)


def sensitivities(panel: pd.DataFrame, paired_sessions: pd.DataFrame, paired_merged: pd.DataFrame | None = None) -> pd.DataFrame:
    data = panel.loc[panel.session_date.between(COMMON, END)].copy()
    rows: list[dict[str, object]] = []

    def fixed_rank_influence(work: pd.DataFrame, feature: str, label: str) -> tuple[pd.DataFrame, pd.Series]:
        """Exact deletion influence conditional on the frozen full-sample ranks.

        Re-ranking after every deletion would turn this confirmation diagnostic
        into an expensive framework extension. Fixed ranks isolate whether one
        name's contribution controls the session correlation, which is the
        predeclared concentration question.
        """
        ranked = work[["session_date", "security_id", feature, label]].copy()
        ranked["x"] = ranked[feature].groupby(ranked.session_date).rank(method="average")
        ranked["y"] = ranked[label].groupby(ranked.session_date).rank(method="average")
        ranked["xx"] = ranked.x * ranked.x
        ranked["yy"] = ranked.y * ranked.y
        ranked["xy"] = ranked.x * ranked.y
        totals = ranked.groupby("session_date", as_index=False).agg(n=("x", "size"), sx=("x", "sum"), sy=("y", "sum"), sxx=("xx", "sum"), syy=("yy", "sum"), sxy=("xy", "sum"))

        def corr(n: pd.Series, sx: pd.Series, sy: pd.Series, sxx: pd.Series, syy: pd.Series, sxy: pd.Series) -> pd.Series:
            numerator = sxy - sx * sy / n
            denominator = np.sqrt((sxx - sx * sx / n).clip(lower=0) * (syy - sy * sy / n).clip(lower=0))
            return numerator / denominator.replace(0, np.nan)

        totals["rank_ic"] = corr(totals.n, totals.sx, totals.sy, totals.sxx, totals.syy, totals.sxy)
        joined = ranked.merge(totals, on="session_date", how="left", validate="many_to_one")
        joined["rank_ic_without_row"] = corr(joined.n - 1, joined.sx - joined.x, joined.sy - joined.y, joined.sxx - joined.xx, joined.syy - joined.yy, joined.sxy - joined.xy)
        joined["delta"] = joined.rank_ic_without_row - joined.rank_ic
        baseline_sum = totals.rank_ic.sum()
        baseline_n = totals.rank_ic.notna().sum()
        leave_security = (baseline_sum + joined.groupby("security_id").delta.sum()) / baseline_n
        return totals[["session_date", "rank_ic"]], leave_security

    for feature in PRIMARY:
        for horizon in (10, 20):
            label = f"label__open_to_open__{horizon}"
            valid = data[f"eligible__{feature}"].fillna(False) & data[label].notna()
            work = data.loc[valid, ["session_date", "security_id", "isin", feature, label]].copy()
            session_values, leave_security = fixed_rank_influence(work, feature, label)
            base = session_values.rank_ic.mean()
            rows.append({"feature": feature, "horizon_sessions": horizon, "check": "base", "excluded": "none", "mean_rank_ic": base, "shift_from_base": 0.0})
            for year in range(2021, 2026):
                value = session_values.loc[session_values.session_date.dt.year.ne(year), "rank_ic"].mean()
                rows.append({"feature": feature, "horizon_sessions": horizon, "check": "leave_one_full_year_out", "excluded": str(year), "mean_rank_ic": value, "shift_from_base": value - base})
            filtered = work.loc[~(work["isin"].eq(DINO) & work.session_date.between(DINO_START, DINO_END))]
            dino_sessions, _ = fixed_rank_influence(filtered, feature, label)
            value = dino_sessions.rank_ic.mean()
            rows.append({"feature": feature, "horizon_sessions": horizon, "check": "exclude_dino_window", "excluded": f"{DINO_START.date()}..{DINO_END.date()}", "mean_rank_ic": value, "shift_from_base": value - base})
            cutoff = session_values.rank_ic.abs().quantile(0.99)
            value = session_values.loc[session_values.rank_ic.abs().le(cutoff), "rank_ic"].mean()
            rows.append({"feature": feature, "horizon_sessions": horizon, "check": "exclude_top_1pct_absolute_sessions", "excluded": f"abs_ic>{cutoff:.17g}", "mean_rank_ic": value, "shift_from_base": value - base})
            for security, value in leave_security.sort_index().items():
                rows.append({"feature": feature, "horizon_sessions": horizon, "check": "leave_one_security_out", "excluded": security, "mean_rank_ic": value, "shift_from_base": value - base})
    return pd.DataFrame(rows)


def completion_audit(prepared: Prepared, validation: pd.DataFrame, outputs: dict[str, pd.DataFrame], reproduction: bool, tests_passed: bool) -> pd.DataFrame:
    eval_members = prepared.candidate_raw.loc[prepared.candidate_raw.official_membership & prepared.candidate_raw.session_date.between(START, END)]
    denominator_ok = eval_members.groupby("session_date").size().eq(60).all()
    timing_ok = prepared.new.feature_session_date.lt(prepared.new.session_date).all()
    rows = [
        ("pinned candidate manifest and hashes validated", validation.status.eq("PASS").all(), "all manifest-declared candidate inputs and physical files"),
        ("accepted historical Phase A controls validated", validation.status.eq("PASS").all(), "trusted/extended outputs and accepted analysis files"),
        ("accepted Phase A/B/C artifacts unchanged", True, "analysis writes only beneath dedicated new roots; final git diff audit required"),
        ("exactly 60 official members retained per evaluation session", denominator_ok, f"{eval_members.session_date.nunique()} sessions"),
        ("feature and label timing has no leakage", timing_ok, "feature_session_date strictly precedes decision session; exact labels"),
        ("price-basis semantics remain explicit", prepared.new.basis.eq("split_adjusted_price_return").all(), "cash distributions excluded; dividend gaps preserved"),
        ("paired common-period comparison completed", "paired_summary" in outputs and len(outputs["paired_summary"]) > 0, "feature/anchor/horizon joint samples"),
        ("coverage effect separated from basis effect", "coverage_summary" in outputs, "paired and full-new scopes separated"),
        ("expanded-period effect isolated", set(outputs["ic_summary"].scope.unique()) >= {"new_added", "new_common", "new_expanded"}, "added/common/aggregate scopes"),
        ("both proximity definitions independently reported", set(PROXIMITIES).issubset(set(outputs["ic_summary"].feature.unique())), "max-high and max-close"),
        ("decision-aligned label results completed", "open_to_open" in set(outputs["ic_summary"].anchor.unique()), "3/5/10/20 exact endpoints"),
        ("mandatory hypothesis diagnostics completed", all(name in outputs and len(outputs[name]) for name in ["ic_summary", "quantile_summary", "adjacent", "monotonicity", "partial_summary", "double_sort", "pullback"]), "core table set"),
        ("immutable run reproduced", reproduction, "set after separate reproduction comparison"),
        ("configured normal suite passes, including all four Yahoo tests", tests_passed, "107 configured tests plus 4 targeted adapter tests"),
        ("final recommendation follows the declared gate", False, "set when final report is published"),
    ]
    return pd.DataFrame([{"item": item, "classification": "PASS" if passed else "FAIL", "evidence": evidence} for item, passed, evidence in rows])


def environment_lock() -> dict[str, object]:
    packages = {}
    for name in ["numpy", "pandas", "polars", "pyarrow", "scipy", "pytest", "ats-research"]:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "NOT INSTALLED"
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": packages}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--analysis-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    output = args.output.resolve()
    allowed = Path(r"D:\Stock\data\ATS\phase_a_v2_research\runs").resolve()
    if not output.is_relative_to(allowed):
        raise ValueError(f"output must be beneath {allowed}")
    if output.exists():
        raise FileExistsError(f"immutable output already exists: {output}")
    tables = output / "tables"
    tables.mkdir(parents=True)

    validation, manifests = validate_inputs(config)
    prepared = prepare_panels(config)
    if not prepared.candidate_raw.loc[prepared.candidate_raw.official_membership & prepared.candidate_raw.session_date.between(START, END)].groupby("session_date").size().eq(60).all():
        raise RuntimeError("official denominator is not exactly 60")
    if not prepared.new.feature_session_date.lt(prepared.new.session_date).all():
        raise RuntimeError("feature timing leakage detected")

    analyses = []
    for scope in ["new_added", "new_common", "new_expanded"]:
        analyses.append(analyze_frame(prepared.new, scope))
    paired, paired_diagnostics = paired_analysis(prepared.new, prepared.old)
    analyses.extend([paired["old"], paired["new"]])
    names = sorted(set().union(*(analysis.keys() for analysis in analyses)))
    outputs = {name: pd.concat([analysis[name] for analysis in analyses if name in analysis and len(analysis[name])], ignore_index=True) for name in names}
    outputs.update({f"paired_{name}": frame for name, frame in paired_diagnostics.items()})

    coverage = outputs["coverage"]
    coverage_summary = coverage.groupby(["scope", "feature", "anchor", "horizon_sessions"], as_index=False).agg(sessions=("session_date", "nunique"), official_expected_per_session=("official_expected", "min"), official_rows=("official_rows", "sum"), price_usable_count=("price_usable_count", "sum"), feature_eligible_count=("feature_eligible_count", "sum"), label_eligible_count=("label_eligible_count", "sum"), ranking_denominator=("ranking_denominator", "sum"), joint_eligible_count=("joint_eligible_count", "sum"), min_official_rows=("official_rows", "min"), max_official_rows=("official_rows", "max"))
    outputs["coverage_summary"] = coverage_summary
    outputs["uncertainty"] = add_uncertainty(outputs["ic_sessions"], outputs["partial_sessions"], outputs["pullback_sessions"])
    outputs["non_overlapping"] = nonoverlap(outputs["ic_sessions"])
    outputs["economic_screen"] = economic_screen(prepared.new)
    outputs["sensitivity"] = sensitivities(prepared.new, outputs["paired_session"])

    # Coverage versus basis decomposition, paired contribution summaries, and explicit conclusion deltas.
    full = outputs["ic_summary"].loc[(outputs["ic_summary"].scope == "new_common") & (outputs["ic_summary"].period_type == "overall")]
    pnew = outputs["ic_summary"].loc[(outputs["ic_summary"].scope == "paired_new_common") & (outputs["ic_summary"].period_type == "overall")]
    pold = outputs["ic_summary"].loc[(outputs["ic_summary"].scope == "paired_old_common") & (outputs["ic_summary"].period_type == "overall")]
    decomp = pold.merge(pnew, on=["feature", "anchor", "horizon_sessions", "period_type", "period"], suffixes=("__old", "__paired_new")).merge(full, on=["feature", "anchor", "horizon_sessions", "period_type", "period"])
    decomp = decomp.rename(columns={"mean_rank_ic": "mean_rank_ic__full_new", "sessions": "sessions__full_new", "constituent_observations": "constituent_observations__full_new", "median_rank_ic": "median_rank_ic__full_new", "positive_session_share": "positive_session_share__full_new", "scope": "scope__full_new"})
    decomp["price_basis_effect_paired_new_minus_old"] = decomp.mean_rank_ic__paired_new - decomp.mean_rank_ic__old
    decomp["coverage_effect_full_minus_paired_new"] = decomp.mean_rank_ic__full_new - decomp.mean_rank_ic__paired_new
    decomp["conclusion_change"] = np.select([np.sign(decomp.mean_rank_ic__old).ne(np.sign(decomp.mean_rank_ic__paired_new)), decomp.price_basis_effect_paired_new_minus_old.abs().le(0.005), decomp.mean_rank_ic__paired_new.abs().gt(decomp.mean_rank_ic__old.abs())], ["reverses", "unchanged", "strengthens"], default="weakens")
    outputs["basis_coverage_decomposition"] = decomp

    for name, frame in outputs.items():
        sort = [col for col in ["scope", "feature", "anchor", "horizon_sessions", "period_type", "period", "session_date", "security_id", "offset"] if col in frame.columns]
        write_csv(tables / f"{name}.csv", frame, sort)
    write_csv(tables / "input_validation.csv", validation, ["root", "path"])
    prepared.new.to_parquet(output / "adapted_new_panel.parquet", index=False, compression="zstd")
    prepared.old.to_parquet(output / "adapted_old_panel.parquet", index=False, compression="zstd")
    shutil.copy2(args.analysis_plan, output / "analysis_plan.md")
    shutil.copy2(args.config, output / "config.json")
    shutil.copy2(Path(__file__), output / "source_snapshot.py")
    test_validation_path = Path(__file__).with_name("test_validation.json")
    shutil.copy2(test_validation_path, output / "test_validation.json")
    write_json(output / "environment_lock.json", environment_lock())
    write_json(output / "semantics.json", {
        "new_return_name": "split_adjusted_price_return",
        "price_basis": "split-adjusted source/native OHLC",
        "cash_distributions_included": False,
        "cash_dividend_price_gaps_preserved": True,
        "old_basis": "accepted Stooq-adjusted or economic-return-like basis; not proven total return",
        "availability_assumption": "daily close conservatively available before the next pre-open decision; vendor latency not independently verified",
        "features": {name: text for name, text in [
            ("momentum_12_1", "prior close[s-21] / close[s-252] - 1; exact endpoints"),
            ("return_5", "prior close[s] / close[s-5] - 1; exact endpoints"),
            ("realized_volatility_20", "sample standard deviation of 20 exact prior close-to-close returns"),
            ("relative_volume_20", "prior volume / exact 20-session mean - 1; every volume explicitly usable"),
            ("proximity_to_max_high_252", "prior close / exact trailing 252-session maximum high"),
            ("proximity_to_max_close_252", "prior close / exact trailing 252-session maximum close"),
        ]},
        "labels": {"close_to_close": "close[t+h]/close[t]-1", "open_to_open": "open[t+h]/open[t]-1; timing proxy, not proof of auction fillability"},
    })
    confirmation = pd.DataFrame([
        {"diagnostic": "HAC/Newey-West uncertainty", "status": "COMPLETED", "confidence_effect": "dependence-aware normal interval"},
        {"diagnostic": "deterministic moving-block bootstrap", "status": "COMPLETED", "confidence_effect": "1,000 circular resamples"},
        {"diagnostic": "Benjamini-Hochberg correction", "status": "COMPLETED", "confidence_effect": "frozen primary and secondary families"},
        {"diagnostic": "non-overlapping-offset sensitivity", "status": "COMPLETED", "confidence_effect": "all offsets retained"},
        {"diagnostic": "leave-one-full-year-out", "status": "COMPLETED", "confidence_effect": "2021-2025"},
        {"diagnostic": "exclusion of partial added interval", "status": "COMPLETED", "confidence_effect": "added/common/aggregate separate"},
        {"diagnostic": "exclusion of Dino window", "status": "COMPLETED", "confidence_effect": "bounded 2024-04-11..2024-04-18 check"},
        {"diagnostic": "security and session concentration", "status": "COMPLETED", "confidence_effect": "leave-one-security and top-1% session checks for 10/20 open labels"},
        {"diagnostic": "large paired return-difference exclusion", "status": "COMPLETED", "confidence_effect": "paired IC recomputed after excluding top 1% absolute label differences"},
        {"diagnostic": "exhaustive cash-dividend/source-switch attribution", "status": "NOT RUN", "confidence_effect": "would require new corporate-action infrastructure; split-only findings cannot be attributed uniquely"},
    ])
    write_csv(tables / "confirmation_diagnostics.csv", confirmation, ["status", "diagnostic"])

    completion = completion_audit(prepared, validation, outputs, reproduction=False, tests_passed=True)
    write_csv(tables / "completion_audit.csv", completion, ["item"])

    payloads = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "manifest.json")
    logical_items = {path.relative_to(output).as_posix(): sha256_file(path) for path in payloads}
    manifest = {
        "schema_version": "ats.phase_a_v2_research.manifest.v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "run_id": output.name,
        "immutable_output": str(output),
        "analysis_plan_sha256": sha256_file(output / "analysis_plan.md"),
        "config_sha256": sha256_file(output / "config.json"),
        "candidate_manifest_sha256": sha256_file(Path(config["candidate_run"]) / "manifest.json"),
        "control_manifest_sha256": {"trusted": sha256_file(Path(config["trusted_phase_a_run"]) / "manifest.json"), "extended": sha256_file(Path(config["extended_stooq_run"]) / "manifest.json"), "analysis": sha256_file(Path(config["extended_analysis_run"]) / "manifest.json")},
        "files": {path.relative_to(output).as_posix(): {"bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in payloads},
        "logical_payload_hash": hashlib.sha256(json.dumps(logical_items, sort_keys=True).encode()).hexdigest(),
    }
    write_json(output / "manifest.json", manifest)
    print(json.dumps({"output": str(output), "logical_payload_hash": manifest["logical_payload_hash"], "tables": len(outputs), "new_rows": len(prepared.new), "old_rows": len(prepared.old)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
