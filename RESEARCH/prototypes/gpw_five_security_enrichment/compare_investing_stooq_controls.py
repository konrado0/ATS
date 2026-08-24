from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ats_research.investing_manual import parse_investing_manual_history


COMPARISON_FLOOR = pd.Timestamp("2014-01-01")
CONTROLS = (
    {
        "company": "ORLEN",
        "isin": "PLPKN0000018",
        "investing_file": "pkn.txt",
        "stooq_symbol": "PKN",
        "identity_state": "exact",
    },
    {
        "company": "KGHM",
        "isin": "PLKGHM000017",
        "investing_file": "kgh.txt",
        "stooq_symbol": "KGH",
        "identity_state": "exact",
    },
    {
        "company": "mBank",
        "isin": "PLBRE0000012",
        "investing_file": "mbk.txt",
        "stooq_symbol": "MBK",
        "identity_state": "validity_aware_BRE_to_MBK",
    },
)
PRICE_FIELDS = ("open", "high", "low", "close")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_correlation(left: pd.Series, right: pd.Series, method: str = "pearson") -> float | None:
    valid = pd.concat([left, right], axis=1).dropna()
    if len(valid) < 3 or valid.iloc[:, 0].nunique() < 2 or valid.iloc[:, 1].nunique() < 2:
        return None
    value = valid.iloc[:, 0].corr(valid.iloc[:, 1], method=method)
    return None if pd.isna(value) else float(value)


def read_stooq(path: Path, expected_symbol: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(value).strip("<>").lower() for value in frame.columns]
    required = {"ticker", "per", "date", "time", "open", "high", "low", "close", "vol"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path}: missing Stooq columns {sorted(missing)}")
    symbols = set(frame["ticker"].astype(str).str.upper().unique())
    periods = set(frame["per"].astype(str).str.upper().unique())
    if symbols != {expected_symbol} or periods != {"D"}:
        raise ValueError(f"{path}: unexpected symbols/periods {symbols}/{periods}")
    frame["session_date"] = pd.to_datetime(frame["date"].astype(str), format="%Y%m%d", errors="raise")
    if frame["session_date"].duplicated().any():
        raise ValueError(f"{path}: duplicate Stooq dates")
    frame = frame.rename(columns={"vol": "volume"})
    frame = frame[["session_date", *PRICE_FIELDS, "volume"]].sort_values("session_date").reset_index(drop=True)
    for column in (*PRICE_FIELDS, "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    invalid = (
        frame[list(PRICE_FIELDS)].le(0).any(axis=1)
        | frame["volume"].lt(0)
        | frame["high"].lt(frame[["open", "close", "low"]].max(axis=1))
        | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1))
    )
    if invalid.any():
        raise ValueError(f"{path}: {int(invalid.sum())} invalid Stooq OHLCV rows")
    return frame


def add_vendor_returns(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    result = frame.sort_values("session_date").copy()
    result[f"{prefix}_previous_session_date"] = result["session_date"].shift(1)
    result[f"{prefix}_close_return"] = result["close"].pct_change()
    return result


def as_json_number(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def compare_control(
    control: dict[str, str], reference_root: Path, data_root: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    investing_path = reference_root / control["investing_file"]
    stooq_path = data_root / "daily" / "pl" / "wse stocks" / f"{control['stooq_symbol'].lower()}.txt"
    parsed = parse_investing_manual_history(
        investing_path,
        allow_missing_display_volume=True,
        allow_dot_thousands_in_prices=True,
    )
    investing = parsed.bars[["session_date", *PRICE_FIELDS, "volume", "volume_rounding_uncertainty_shares"]].copy()
    stooq = read_stooq(stooq_path, control["stooq_symbol"])

    # The owner requested a hard 2014 floor. Pre-2014 Stooq rows never enter a metric or output row.
    investing = investing.loc[investing["session_date"].ge(COMPARISON_FLOOR)].copy()
    stooq = stooq.loc[stooq["session_date"].ge(COMPARISON_FLOOR)].copy()
    if investing.empty or stooq.empty:
        raise ValueError(f"{control['company']}: no observations on/after {COMPARISON_FLOOR.date()}")
    comparison_start = max(COMPARISON_FLOOR, investing["session_date"].min())
    comparison_end = min(investing["session_date"].max(), stooq["session_date"].max())
    if comparison_end < comparison_start:
        raise ValueError(f"{control['company']}: no bounded date intersection")

    investing_window = investing.loc[investing["session_date"].between(comparison_start, comparison_end)].copy()
    stooq_window = stooq.loc[stooq["session_date"].between(comparison_start, comparison_end)].copy()
    investing_dates = set(investing_window["session_date"])
    stooq_dates = set(stooq_window["session_date"])

    session_rows = []
    for date in sorted(investing_dates.symmetric_difference(stooq_dates)):
        session_rows.append(
            {
                **control,
                "comparison_floor": COMPARISON_FLOOR.date().isoformat(),
                "session_date": date.date().isoformat(),
                "investing_present": date in investing_dates,
                "stooq_present": date in stooq_dates,
                "state": "investing_only" if date in investing_dates else "stooq_only",
            }
        )

    investing_returns = add_vendor_returns(investing_window, "investing").rename(
        columns={column: f"investing_{column}" for column in (*PRICE_FIELDS, "volume", "volume_rounding_uncertainty_shares")}
    )
    stooq_returns = add_vendor_returns(stooq_window, "stooq").rename(
        columns={column: f"stooq_{column}" for column in (*PRICE_FIELDS, "volume")}
    )
    overlap = investing_returns.merge(stooq_returns, on="session_date", how="inner", validate="one_to_one")
    overlap["return_previous_session_aligned"] = overlap["investing_previous_session_date"].eq(
        overlap["stooq_previous_session_date"]
    )
    for field in PRICE_FIELDS:
        overlap[f"{field}_investing_to_stooq_ratio"] = overlap[f"investing_{field}"] / overlap[f"stooq_{field}"]
        overlap[f"{field}_raw_relative_difference"] = (
            overlap[f"investing_{field}"] - overlap[f"stooq_{field}"]
        ) / overlap[f"stooq_{field}"]
    overlap["close_return_difference_pp"] = (
        overlap["investing_close_return"] - overlap["stooq_close_return"]
    ) * 100.0
    overlap.loc[~overlap["return_previous_session_aligned"], "close_return_difference_pp"] = np.nan
    overlap["volume_investing_to_stooq_ratio"] = overlap["investing_volume"] / overlap["stooq_volume"].replace(0, np.nan)
    overlap["price_volume_ratio_product"] = (
        overlap["close_investing_to_stooq_ratio"] * overlap["volume_investing_to_stooq_ratio"]
    )
    overlap.insert(0, "isin", control["isin"])
    overlap.insert(0, "company", control["company"])

    ratio = overlap["close_investing_to_stooq_ratio"]
    ratio_change = ratio.pct_change()
    overlap["close_ratio_change_pct"] = ratio_change * 100.0
    prior_date = overlap["session_date"].shift(1)
    change_points = overlap.loc[ratio_change.abs().gt(0.005)].copy()
    change_points.insert(change_points.columns.get_loc("session_date") + 1, "previous_overlap_session_date", prior_date.loc[change_points.index])
    change_points["close_ratio_change_pct"] = ratio_change.loc[change_points.index] * 100.0
    prior_medians = []
    forward_medians = []
    persistent_states = []
    for index in change_points.index:
        position = overlap.index.get_loc(index)
        prior_median = ratio.iloc[max(0, position - 5) : position].median()
        forward_median = ratio.iloc[position : min(len(ratio), position + 5)].median()
        prior_medians.append(prior_median)
        forward_medians.append(forward_median)
        persistent_states.append(
            "persistent_scale_step"
            if abs(forward_median / prior_median - 1.0) > 0.005
            else "transient_ratio_dislocation"
        )
    change_points["prior_5_overlap_ratio_median"] = prior_medians
    change_points["forward_5_overlap_ratio_median"] = forward_medians
    change_points["scale_step_state"] = persistent_states
    change_points = change_points[
        [
            "company",
            "isin",
            "session_date",
            "previous_overlap_session_date",
            "investing_close",
            "stooq_close",
            "close_investing_to_stooq_ratio",
            "close_ratio_change_pct",
            "prior_5_overlap_ratio_median",
            "forward_5_overlap_ratio_median",
            "scale_step_state",
            "investing_close_return",
            "stooq_close_return",
            "close_return_difference_pp",
            "return_previous_session_aligned",
        ]
    ]

    annual = overlap.assign(year=overlap["session_date"].dt.year).groupby("year", as_index=False).agg(
        overlap_sessions=("session_date", "size"),
        median_close_investing_to_stooq_ratio=("close_investing_to_stooq_ratio", "median"),
        min_close_investing_to_stooq_ratio=("close_investing_to_stooq_ratio", "min"),
        max_close_investing_to_stooq_ratio=("close_investing_to_stooq_ratio", "max"),
        median_volume_investing_to_stooq_ratio=("volume_investing_to_stooq_ratio", "median"),
        median_price_volume_ratio_product=("price_volume_ratio_product", "median"),
    )
    annual.insert(0, "isin", control["isin"])
    annual.insert(0, "company", control["company"])

    aligned_returns = overlap.loc[overlap["return_previous_session_aligned"]].dropna(
        subset=["investing_close_return", "stooq_close_return"]
    )
    return_diff = aligned_returns["close_return_difference_pp"].abs()
    stable_ratio_returns = aligned_returns.loc[aligned_returns["close_ratio_change_pct"].abs().le(0.5)].copy()
    stable_return_diff = stable_ratio_returns["close_return_difference_pp"].abs()
    volume_valid = overlap.loc[overlap["stooq_volume"].gt(0)].copy()
    price_volume_product_error = (volume_valid["price_volume_ratio_product"] - 1.0).abs()
    metrics: dict[str, object] = {
        **control,
        "comparison_floor": COMPARISON_FLOOR.date().isoformat(),
        "comparison_start": comparison_start.date().isoformat(),
        "comparison_end": comparison_end.date().isoformat(),
        "investing_first_date_on_or_after_floor": investing["session_date"].min().date().isoformat(),
        "investing_last_date": investing["session_date"].max().date().isoformat(),
        "stooq_first_date_used": stooq_window["session_date"].min().date().isoformat(),
        "stooq_last_date_used": stooq_window["session_date"].max().date().isoformat(),
        "investing_rows_in_window": len(investing_window),
        "stooq_rows_in_window": len(stooq_window),
        "overlap_sessions": len(overlap),
        "investing_only_sessions": len(investing_dates - stooq_dates),
        "stooq_only_sessions": len(stooq_dates - investing_dates),
        "overlap_share_of_investing_sessions": len(overlap) / len(investing_window),
        "aligned_return_pairs": len(aligned_returns),
        "close_return_pearson": safe_correlation(aligned_returns["investing_close_return"], aligned_returns["stooq_close_return"]),
        "close_return_spearman": safe_correlation(
            aligned_returns["investing_close_return"], aligned_returns["stooq_close_return"], method="spearman"
        ),
        "close_return_median_abs_difference_pp": return_diff.median(),
        "close_return_p95_abs_difference_pp": return_diff.quantile(0.95),
        "close_return_max_abs_difference_pp": return_diff.max(),
        "close_return_pairs_within_0_05pp_share": return_diff.le(0.05).mean(),
        "close_return_pairs_within_0_10pp_share": return_diff.le(0.10).mean(),
        "stable_ratio_return_pairs": len(stable_ratio_returns),
        "stable_ratio_close_return_pearson": safe_correlation(
            stable_ratio_returns["investing_close_return"], stable_ratio_returns["stooq_close_return"]
        ),
        "stable_ratio_close_return_median_abs_difference_pp": stable_return_diff.median(),
        "stable_ratio_close_return_p95_abs_difference_pp": stable_return_diff.quantile(0.95),
        "stable_ratio_close_return_max_abs_difference_pp": stable_return_diff.max(),
        "stable_ratio_close_return_pairs_within_0_05pp_share": stable_return_diff.le(0.05).mean(),
        "close_level_ratio_median": ratio.median(),
        "close_level_ratio_min": ratio.min(),
        "close_level_ratio_max": ratio.max(),
        "close_level_ratio_first": ratio.iloc[0],
        "close_level_ratio_last": ratio.iloc[-1],
        "close_ratio_change_points_over_0_5pct": len(change_points),
        "persistent_close_scale_steps_over_0_5pct": int(change_points["scale_step_state"].eq("persistent_scale_step").sum()),
        "transient_close_ratio_dislocations_over_0_5pct": int(
            change_points["scale_step_state"].eq("transient_ratio_dislocation").sum()
        ),
        "raw_close_exact_match_share": overlap["investing_close"].eq(overlap["stooq_close"]).mean(),
        "volume_pearson": safe_correlation(volume_valid["investing_volume"], volume_valid["stooq_volume"]),
        "volume_spearman": safe_correlation(
            volume_valid["investing_volume"], volume_valid["stooq_volume"], method="spearman"
        ),
        "volume_ratio_median": volume_valid["volume_investing_to_stooq_ratio"].median(),
        "volume_ratio_p05": volume_valid["volume_investing_to_stooq_ratio"].quantile(0.05),
        "volume_ratio_p95": volume_valid["volume_investing_to_stooq_ratio"].quantile(0.95),
        "price_volume_ratio_product_median": volume_valid["price_volume_ratio_product"].median(),
        "price_volume_ratio_product_p95_abs_error_from_one": price_volume_product_error.quantile(0.95),
        "investing_sha256": sha256(investing_path),
        "stooq_sha256": sha256(stooq_path),
        "investing_parser_inspection": parsed.inspection,
        "pre_2014_stooq_rows_excluded": int(read_stooq(stooq_path, control["stooq_symbol"])["session_date"].lt(COMPARISON_FLOOR).sum()),
    }
    return overlap, pd.DataFrame(session_rows), change_points, annual, {key: as_json_number(value) for key, value in metrics.items()}


def write_csv(path: Path, frame: pd.DataFrame, sort: list[str]) -> None:
    result = frame.sort_values(sort, kind="mergesort").copy() if not frame.empty else frame.copy()
    for column in result.select_dtypes(include=["datetime64[ns]"]).columns:
        result[column] = result[column].dt.strftime("%Y-%m-%d")
    result.to_csv(path, index=False, lineterminator="\n", float_format="%.12g")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded 2014+ Investing.com versus Stooq GPW overlap controls")
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {output}")
    output.mkdir(parents=True)

    overlaps = []
    sessions = []
    changes = []
    annuals = []
    summaries = []
    for control in CONTROLS:
        overlap, session, change, annual, summary = compare_control(
            control, args.reference_root.resolve(), args.data_root.resolve()
        )
        overlaps.append(overlap)
        sessions.append(session)
        changes.append(change)
        annuals.append(annual)
        summaries.append(summary)

    overlap_frame = pd.concat(overlaps, ignore_index=True)
    session_frame = pd.concat(sessions, ignore_index=True) if any(not frame.empty for frame in sessions) else pd.DataFrame(
        columns=["company", "isin", "investing_file", "stooq_symbol", "identity_state", "comparison_floor", "session_date", "investing_present", "stooq_present", "state"]
    )
    change_frame = pd.concat(changes, ignore_index=True)
    annual_frame = pd.concat(annuals, ignore_index=True)
    summary_frame = pd.DataFrame([{key: value for key, value in row.items() if key != "investing_parser_inspection"} for row in summaries])

    write_csv(output / "daily_overlap.csv", overlap_frame, ["isin", "session_date"])
    write_csv(output / "session_disagreements.csv", session_frame, ["isin", "session_date"])
    write_csv(output / "close_ratio_change_points.csv", change_frame, ["isin", "session_date"])
    write_csv(output / "annual_scale_summary.csv", annual_frame, ["isin", "year"])
    write_csv(output / "vendor_overlap_summary.csv", summary_frame, ["isin"])
    (output / "metrics.json").write_text(
        json.dumps(
            {
                "comparison_contract": {
                    "comparison_floor": COMPARISON_FLOOR.date().isoformat(),
                    "pre_floor_stooq_data_used": False,
                    "session_metrics_window": "max(2014-01-01, investing first date) through min(vendor last dates)",
                    "return_pair_rule": "same current session and same previous vendor session",
                    "price_level_rule": "raw levels and Investing-to-Stooq ratios; no vendor series transformed or spliced",
                    "volume_rule": "Investing volume is display-rounded and is not treated as exact share volume",
                },
                "controls": summaries,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    script_path = Path(__file__).resolve()
    produced = sorted(path for path in output.iterdir() if path.name != "manifest.json")
    manifest = {
        "comparison_floor": COMPARISON_FLOOR.date().isoformat(),
        "script": {"path": str(script_path), "sha256": sha256(script_path)},
        "identity_map_source": str(args.data_root.resolve() / "reference" / "gpw_indices" / "stooq_symbol_map.csv"),
        "identity_map_sha256": sha256(args.data_root.resolve() / "reference" / "gpw_indices" / "stooq_symbol_map.csv"),
        "inputs": [
            {
                **control,
                "investing_path": str(args.reference_root.resolve() / control["investing_file"]),
                "investing_sha256": sha256(args.reference_root.resolve() / control["investing_file"]),
                "stooq_path": str(args.data_root.resolve() / "daily" / "pl" / "wse stocks" / f"{control['stooq_symbol'].lower()}.txt"),
                "stooq_sha256": sha256(args.data_root.resolve() / "daily" / "pl" / "wse stocks" / f"{control['stooq_symbol'].lower()}.txt"),
            }
            for control in CONTROLS
        ],
        "outputs": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in produced},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "controls": summaries}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
