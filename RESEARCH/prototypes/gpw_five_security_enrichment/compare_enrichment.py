from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ats_research.investing_manual import load_supplemental_mapping, parse_investing_manual_history


FEATURES = {
    "momentum_12_1__v1": "feature__momentum_12_1__v1",
    "return_5__v1": "feature__return_5__v1",
    "relative_volume_20__v1": "feature__relative_volume_20__v1",
    "realized_volatility_20__v1": "feature__realized_volatility_20__v1",
}
HORIZONS = (3, 5, 10, 20)
RECOVERED_ISINS = ("PLLOTOS00025", "PLPGNIG00014", "PLCIECH00018", "PLSTSHL00012", "PLTIM0000016")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_spearman(frame: pd.DataFrame, left: str, right: str) -> float:
    valid = frame[[left, right]].dropna()
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
        rows.append({"session_date": session, "observations": len(valid), "rank_ic": safe_spearman(valid, feature, label)})
    return pd.DataFrame(rows)


def proximity_panel(panel: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    grid = features[["security_id", "session_date", "close"]].sort_values(["security_id", "session_date"]).copy()
    grid["proximity_252"] = grid["close"] / (
        grid.groupby("security_id", sort=False)["close"].rolling(252, min_periods=252).max().reset_index(level=0, drop=True)
    )
    result = panel.merge(
        grid.rename(columns={"session_date": "feature_session_date"})[["security_id", "feature_session_date", "proximity_252"]],
        on=["security_id", "feature_session_date"],
        how="left",
        validate="many_to_one",
    )
    eligible = result["proximity_252"].where(result["is_price_usable_member"])
    rank = eligible.groupby(result["session_date"]).rank(method="average")
    count = eligible.groupby(result["session_date"]).transform("count")
    result["proximity_percentile_rank"] = rank / count
    result["proximity_quantile"] = np.ceil(result["proximity_percentile_rank"] * 5).clip(1, 5).astype("Int64")
    return result


def longest_missing_run(calendar: pd.Series, observed: set[pd.Timestamp]) -> tuple[int, str | None, str | None]:
    best: list[pd.Timestamp] = []
    current: list[pd.Timestamp] = []
    for value in pd.to_datetime(calendar):
        if value not in observed:
            current.append(value)
            if len(current) > len(best):
                best = current.copy()
        else:
            current = []
    return (
        len(best),
        best[0].date().isoformat() if best else None,
        best[-1].date().isoformat() if best else None,
    )


def source_inspection(new_artifacts: Path, data_root: Path, mapping_path: Path) -> pd.DataFrame:
    base = pd.read_csv(new_artifacts / "supplemental_source_inspection.csv")
    mapping = load_supplemental_mapping(mapping_path)
    assert mapping is not None
    wig = pd.read_csv(data_root / "daily" / "pl" / "wse indices" / "wig.txt")
    wig.columns = [str(value).strip("<>").lower() for value in wig.columns]
    wig_dates = pd.to_datetime(wig["date"].astype(str), format="%Y%m%d")
    additions = []
    for row in mapping["mappings"]:
        path = data_root / str(row["source_file"])
        parsed = parse_investing_manual_history(path).bars
        dates = set(pd.to_datetime(parsed["session_date"]))
        first = parsed["session_date"].min()
        last = parsed["session_date"].max()
        calendar = wig_dates.loc[wig_dates.between(first, last)].sort_values()
        missing = [value for value in calendar if value not in dates]
        run_count, run_first, run_last = longest_missing_run(calendar, dates)
        returns = parsed["close"].pct_change().abs()
        max_index = returns.idxmax()
        listing = pd.Timestamp(str(row["listing_date"]))
        listing_calendar = wig_dates.loc[wig_dates.between(listing, last)]
        bounded_from_listing = (first - listing).days <= 31
        missing_from_listing = [value for value in listing_calendar if value not in dates] if bounded_from_listing else []
        additions.append(
            {
                "isin": row["isin"],
                "listing_date": listing.date().isoformat(),
                "expected_last_trade_date": row["last_trade_date"],
                "terminal_date_matches": last == pd.Timestamp(str(row["last_trade_date"])),
                "missing_wig_sessions_within_observed_range": len(missing),
                "first_missing_wig_session": missing[0].date().isoformat() if missing else None,
                "last_missing_wig_session": missing[-1].date().isoformat() if missing else None,
                "longest_missing_wig_session_run": run_count,
                "longest_missing_run_first": run_first,
                "longest_missing_run_last": run_last,
                "missing_wig_sessions": "|".join(value.date().isoformat() for value in missing),
                "listing_to_first_observation_gap_sessions": len(missing_from_listing) if bounded_from_listing else None,
                "history_scope_start_state": "listing_bounded" if bounded_from_listing else "bounded_2014_history_not_listing_complete",
                "max_absolute_close_return": float(returns.loc[max_index]),
                "max_absolute_close_return_date": parsed.loc[max_index, "session_date"].date().isoformat(),
                "source_overlap_rows": 0,
                "adjustment_state": "vendor_adjusted_semantics_unverified",
                "volume_semantics": "display-rounded; K about +/-5 shares, M about +/-5000 shares",
            }
        )
    return base.merge(pd.DataFrame(additions), on="isin", how="left", validate="one_to_one")


def add_comparison(rows: list[dict[str, object]], section: str, metric: str, old: object, new: object, **keys: object) -> None:
    delta = float(new) - float(old) if isinstance(old, (int, float, np.integer, np.floating)) and isinstance(new, (int, float, np.integer, np.floating)) else None
    rows.append({"section": section, **keys, "metric": metric, "old_value": old, "new_value": new, "delta": delta})


def coverage_comparison(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for metric in ["price_usable_member_count", "complete_matrix_member_count"]:
        add_comparison(rows, "overall", f"{metric}_mean", old.groupby("session_date")[metric].first().mean(), new.groupby("session_date")[metric].first().mean())
        add_comparison(rows, "overall", f"{metric}_min", old.groupby("session_date")[metric].first().min(), new.groupby("session_date")[metric].first().min())
    add_comparison(rows, "overall", "official_member_count", 60, 60)
    add_comparison(rows, "overall", "unresolved_vendor_identity_count", int(old["is_unresolved_exit_member"].groupby(old["isin"]).max().sum()), int(new["is_unresolved_exit_member"].groupby(new["isin"]).max().sum()))
    add_comparison(rows, "overall", "vendor_gap_member_sessions", int((old["price_exclusion_reason"] == "unresolved_vendor_alias").sum()), int((new["price_exclusion_reason"] == "unresolved_vendor_alias").sum()))
    for dataset, frame in [("old", old), ("new", new)]:
        session = frame.groupby("session_date", as_index=False).first()
        for count in (57, 58, 59, 60):
            value = int(session["price_usable_member_count"].eq(count).sum())
            row = next((item for item in rows if item["section"] == "distribution" and item["metric"] == f"sessions_at_{count}_priced_members"), None)
            if row is None:
                row = {"section": "distribution", "metric": f"sessions_at_{count}_priced_members", "old_value": None, "new_value": None, "delta": None}
                rows.append(row)
            row[f"{dataset}_value"] = value
        for year, group in session.groupby(session["session_date"].dt.year):
            partial = "partial" if year in (2020, 2026) else "full_year"
            for metric in ("price_usable_member_count", "complete_matrix_member_count"):
                for statistic in ("mean", "min"):
                    value = getattr(group[metric], statistic)()
                    key = ("annual", str(year), partial, metric, statistic)
                    row = next((item for item in rows if item.get("_key") == key), None)
                    if row is None:
                        row = {"_key": key, "section": "annual", "period": str(year), "period_state": partial, "feature": metric, "metric": statistic, "old_value": None, "new_value": None, "delta": None}
                        rows.append(row)
                    row[f"{dataset}_value"] = value
        for feature in FEATURES:
            column = f"feature_usable_member_count__{feature}"
            annual = frame.groupby("session_date", as_index=False).first()
            for year, group in annual.groupby(annual["session_date"].dt.year):
                partial = "partial" if year in (2020, 2026) else "full_year"
                for statistic in ("mean", "min"):
                    value = getattr(group[column], statistic)()
                    key = ("annual_feature", str(year), feature, statistic)
                    row = next((item for item in rows if item.get("_key") == key), None)
                    if row is None:
                        row = {"_key": key, "section": "annual_feature", "period": str(year), "period_state": partial, "feature": feature, "metric": statistic, "old_value": None, "new_value": None, "delta": None}
                        rows.append(row)
                    row[f"{dataset}_value"] = value
    for row in rows:
        if row.get("old_value") is not None and row.get("new_value") is not None and row.get("delta") is None:
            row["delta"] = float(row["new_value"]) - float(row["old_value"])
    for isin in RECOVERED_ISINS:
        for dataset, frame in [("old", old), ("new", new)]:
            subset = frame.loc[frame["isin"].eq(isin)]
            values = {
                "official_member_sessions": len(subset),
                "price_usable_member_sessions": int(subset["is_price_usable_member"].sum()),
                "momentum_252_eligible_member_sessions": int(subset["is_feature_eligible__momentum_12_1__v1"].sum()),
                "suspended_member_sessions": int(subset["price_exclusion_reason"].eq("suspended_non_tradeable").sum()),
            }
            for metric, value in values.items():
                key = ("membership_episode", isin, metric)
                row = next((item for item in rows if item.get("_key") == key), None)
                if row is None:
                    row = {"_key": key, "section": "membership_episode", "isin": isin, "metric": metric, "old_value": None, "new_value": None, "delta": None}
                    rows.append(row)
                row[f"{dataset}_value"] = value
    for row in rows:
        if row.get("old_value") is not None and row.get("new_value") is not None:
            row["delta"] = float(row["new_value"]) - float(row["old_value"])
        row.pop("_key", None)
    gaps = new.loc[~new["is_price_usable_member"], ["session_date", "isin", "price_exclusion_reason"]]
    for gap in gaps.itertuples(index=False):
        rows.append({"section": "remaining_gap", "period": gap.session_date.date().isoformat(), "isin": gap.isin, "metric": gap.price_exclusion_reason, "old_value": None, "new_value": 1, "delta": None})
    return pd.DataFrame(rows)


def diagnostic_comparison(old_artifacts: Path, new_artifacts: Path, old_panel: pd.DataFrame, new_panel: pd.DataFrame, old_prox: pd.DataFrame, new_prox: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    old_annual = pd.read_csv(old_artifacts / "annual_rank_ic.csv")
    new_annual = pd.read_csv(new_artifacts / "annual_rank_ic.csv")
    old_metrics = json.loads((old_artifacts.parent / "metrics.json").read_text(encoding="utf-8"))
    new_metrics = json.loads((new_artifacts.parent / "metrics.json").read_text(encoding="utf-8"))
    for old_row in old_metrics["rank_ic_summary"]:
        key = (old_row["feature"], old_row["horizon_sessions"])
        new_row = next(item for item in new_metrics["rank_ic_summary"] if (item["feature"], item["horizon_sessions"]) == key)
        for metric in ("count", "mean", "median"):
            add_comparison(rows, "rank_ic_overall", metric, old_row[metric], new_row[metric], feature=key[0], horizon_sessions=key[1], period="all")
    merged = old_annual.merge(new_annual, on=["feature", "label", "horizon_sessions", "year"], suffixes=("_old", "_new"), validate="one_to_one")
    for row in merged.itertuples(index=False):
        for metric in ("sessions", "mean_rank_ic", "median_rank_ic", "positive_share"):
            add_comparison(rows, "rank_ic_annual", metric, getattr(row, f"{metric}_old"), getattr(row, f"{metric}_new"), feature=row.feature, horizon_sessions=row.horizon_sessions, period=str(row.year))
    old_mono = pd.read_csv(old_artifacts / "monotonicity.csv")
    new_mono = pd.read_csv(new_artifacts / "monotonicity.csv")
    merged_mono = old_mono.merge(new_mono, on=["feature", "label", "horizon_sessions", "quantile"], suffixes=("_old", "_new"), validate="one_to_one")
    for row in merged_mono.itertuples(index=False):
        for metric in ("mean_forward_return", "observations", "quantile_return_spearman", "top_minus_bottom_spread"):
            add_comparison(rows, "quantile_diagnostics", metric, getattr(row, f"{metric}_old"), getattr(row, f"{metric}_new"), feature=row.feature, horizon_sessions=row.horizon_sessions, quantile=row.quantile, period="all")
    old_regime = pd.read_csv(old_artifacts / "regime_rank_ic.csv")
    new_regime = pd.read_csv(new_artifacts / "regime_rank_ic.csv")
    regime = old_regime.merge(new_regime, on=["feature", "label", "horizon_sessions", "wig_trend_regime"], suffixes=("_old", "_new"), validate="one_to_one")
    for row in regime.itertuples(index=False):
        for metric in ("sessions", "mean_rank_ic", "median_rank_ic"):
            add_comparison(rows, "wig_regime", metric, getattr(row, f"{metric}_old"), getattr(row, f"{metric}_new"), feature=row.feature, horizon_sessions=row.horizon_sessions, period=row.wig_trend_regime)
    for horizon in HORIZONS:
        label = f"label__forward_return_{horizon}__v1"
        old_ic = session_ic(old_prox, "proximity_252", label)
        new_ic = session_ic(new_prox, "proximity_252", label)
        for metric in ("mean", "median", "count"):
            old_value = getattr(old_ic["rank_ic"].dropna(), metric)() if metric != "count" else old_ic["rank_ic"].notna().sum()
            new_value = getattr(new_ic["rank_ic"].dropna(), metric)() if metric != "count" else new_ic["rank_ic"].notna().sum()
            add_comparison(rows, "proximity_252", metric, old_value, new_value, feature="proximity_252", horizon_sessions=horizon, period="all")
        for year in sorted(old_ic["session_date"].dt.year.unique()):
            old_values = old_ic.loc[old_ic["session_date"].dt.year.eq(year), "rank_ic"].dropna()
            new_values = new_ic.loc[new_ic["session_date"].dt.year.eq(year), "rank_ic"].dropna()
            add_comparison(rows, "proximity_252_annual", "mean_rank_ic", old_values.mean(), new_values.mean(), feature="proximity_252", horizon_sessions=horizon, period=str(year))
        full = session_ic(new_panel, FEATURES["relative_volume_20__v1"], label)
        excluded = session_ic(new_panel.loc[~new_panel["isin"].isin(RECOVERED_ISINS)], FEATURES["relative_volume_20__v1"], label)
        add_comparison(rows, "rounded_volume_sensitivity", "mean_rank_ic", full["rank_ic"].mean(), excluded["rank_ic"].mean(), feature="relative_volume_20__v1", horizon_sessions=horizon, period="all", comparison="new_full_vs_recovered_names_excluded")
    momentum = FEATURES["momentum_12_1__v1"]
    pullback = FEATURES["return_5__v1"]
    for dataset, frame in [("old", old_panel), ("new", new_panel)]:
        strong = frame.loc[frame[momentum].gt(0)].copy()
        strong["pullback_bucket"] = np.select([strong[pullback].le(-0.05), strong[pullback].ge(0)], ["deep", "nonnegative"], default="mild")
        for horizon in HORIZONS:
            label = f"label__forward_return_{horizon}__v1"
            daily = strong.groupby(["session_date", "pullback_bucket"], as_index=False)[label].mean()
            means = daily.groupby("pullback_bucket")[label].mean()
            value = means.get("deep", np.nan) - means.get("nonnegative", np.nan)
            key = ("pullback", horizon)
            row = next((item for item in rows if item.get("_key") == key), None)
            if row is None:
                row = {"_key": key, "section": "pullback", "feature": "strong_momentum_deep_minus_nonnegative", "horizon_sessions": horizon, "period": "all", "metric": "mean_return_difference", "old_value": None, "new_value": None, "delta": None}
                rows.append(row)
            row[f"{dataset}_value"] = value
    for row in rows:
        row.pop("_key", None)
        if row.get("old_value") is not None and row.get("new_value") is not None and row.get("delta") is None:
            row["delta"] = float(row["new_value"]) - float(row["old_value"])
    return pd.DataFrame(rows)


def rank_changes(old: pd.DataFrame, new: pd.DataFrame, old_prox: pd.DataFrame, new_prox: pd.DataFrame) -> pd.DataFrame:
    rows = []
    specs = [(name, f"percentile_rank__{name}", f"quantile__{name}") for name in FEATURES]
    specs.append(("proximity_252", "proximity_percentile_rank", "proximity_quantile"))
    for feature, rank, quantile in specs:
        left = old_prox if feature == "proximity_252" else old
        right = new_prox if feature == "proximity_252" else new
        merged = left[["session_date", "security_id", "isin", rank, quantile]].merge(
            right[["session_date", "security_id", rank, quantile]], on=["session_date", "security_id"], suffixes=("_old", "_new"), validate="one_to_one"
        )
        existing = merged.loc[~merged["isin"].isin(RECOVERED_ISINS) & merged[f"{rank}_old"].notna() & merged[f"{rank}_new"].notna()].copy()
        absolute = (existing[f"{rank}_new"] - existing[f"{rank}_old"]).abs()
        quantile_changed = existing[f"{quantile}_new"].ne(existing[f"{quantile}_old"])
        old_counts = existing.groupby("session_date")[f"{rank}_old"].transform("count")
        distance = np.minimum.reduce([np.abs(existing[f"{rank}_old"].to_numpy(float) - boundary) for boundary in (0.2, 0.4, 0.6, 0.8)])
        near_boundary = distance <= (1 / old_counts.to_numpy(float))
        rows.append(
            {
                "section": "existing_members",
                "feature": feature,
                "observations_compared": len(existing),
                "rank_changed_observations": int(absolute.gt(1e-12).sum()),
                "mean_absolute_percentile_rank_change": absolute.mean(),
                "max_absolute_percentile_rank_change": absolute.max(),
                "quantile_changed_observations": int(quantile_changed.sum()),
                "quantile_changed_rate": quantile_changed.mean(),
                "old_observations_near_quantile_boundary": int(near_boundary.sum()),
                "changed_and_near_boundary": int((quantile_changed.to_numpy() & near_boundary).sum()),
            }
        )
        recovered = right.loc[right["isin"].isin(RECOVERED_ISINS) & right[rank].notna()]
        for quantile_value, group in recovered.groupby(quantile):
            rows.append(
                {
                    "section": "recovered_names",
                    "feature": feature,
                    "quantile": int(quantile_value),
                    "observations_compared": len(group),
                    "rank_changed_observations": None,
                    "quantile_changed_observations": None,
                }
            )
    return pd.DataFrame(rows)


def write_csv(path: Path, frame: pd.DataFrame, sort: list[str]) -> None:
    columns = [value for value in sort if value in frame.columns]
    frame.sort_values(columns, kind="mergesort", na_position="last").to_csv(path, index=False, lineterminator="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-run", type=Path, required=True)
    parser.add_argument("--new-run", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = Path("D:/Stock/data/ATS/five_security_enrichment/runs").resolve()
    if not output.is_relative_to(allowed):
        raise ValueError(f"output must stay under {allowed}")
    if output.exists():
        raise FileExistsError(f"immutable output exists: {output}")
    output.mkdir(parents=True)
    old_artifacts = args.old_run.resolve() / "artifacts"
    new_artifacts = args.new_run.resolve() / "artifacts"
    old = pd.read_parquet(old_artifacts / "research_panel.parquet")
    new = pd.read_parquet(new_artifacts / "research_panel.parquet")
    old_features = pd.read_parquet(old_artifacts / "feature_values.parquet")
    new_features = pd.read_parquet(new_artifacts / "feature_values.parquet")
    for frame in (old, new):
        frame["session_date"] = pd.to_datetime(frame["session_date"])
        frame["feature_session_date"] = pd.to_datetime(frame["feature_session_date"])
    for frame in (old_features, new_features):
        frame["session_date"] = pd.to_datetime(frame["session_date"])
    if len(old) != len(new) or not old[["session_date", "security_id"]].equals(new[["session_date", "security_id"]]):
        raise RuntimeError("old and enriched panels are not aligned over identical member/session keys")
    if not old.groupby("session_date").size().eq(60).all() or not new.groupby("session_date").size().eq(60).all():
        raise RuntimeError("official denominator is not 60")
    old_prox = proximity_panel(old, old_features)
    new_prox = proximity_panel(new, new_features)
    tables = {
        "source_inspection.csv": source_inspection(new_artifacts, Path("D:/Stock/data"), args.mapping.resolve()),
        "coverage_comparison.csv": coverage_comparison(old, new),
        "diagnostic_comparison.csv": diagnostic_comparison(old_artifacts, new_artifacts, old, new, old_prox, new_prox),
        "rank_quantile_changes.csv": rank_changes(old, new, old_prox, new_prox),
    }
    sorts = {
        "source_inspection.csv": ["isin"],
        "coverage_comparison.csv": ["section", "period", "feature", "isin", "metric"],
        "diagnostic_comparison.csv": ["section", "feature", "horizon_sessions", "period", "quantile", "metric"],
        "rank_quantile_changes.csv": ["section", "feature", "quantile"],
    }
    for name, frame in tables.items():
        write_csv(output / name, frame, sorts[name])
    metrics = {
        "created_utc": datetime.now(UTC).isoformat(),
        "old_run": str(args.old_run.resolve()),
        "new_run": str(args.new_run.resolve()),
        "comparison_start": new["session_date"].min().date().isoformat(),
        "comparison_end": new["session_date"].max().date().isoformat(),
        "sessions": int(new["session_date"].nunique()),
        "official_denominator": 60,
        "recovered_isins": list(RECOVERED_ISINS),
        "tables": list(tables),
    }
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files = sorted(path for path in output.iterdir() if path.is_file())
    manifest = {
        "comparison_type": "gpw_five_security_enrichment",
        "immutable_output": str(output),
        "old_manifest_sha256": sha256(args.old_run.resolve() / "manifest.json"),
        "new_manifest_sha256": sha256(args.new_run.resolve() / "manifest.json"),
        "mapping_sha256": sha256(args.mapping.resolve()),
        "files": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in files},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
