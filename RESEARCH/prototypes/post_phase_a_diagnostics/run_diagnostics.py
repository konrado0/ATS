from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib_cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import scipy
import yaml


FEATURES = {
    "momentum_12_1__v1": "feature__momentum_12_1__v1",
    "realized_volatility_20__v1": "feature__realized_volatility_20__v1",
    "relative_volume_20__v1": "feature__relative_volume_20__v1",
    "return_5__v1": "feature__return_5__v1",
}
LABELS = {h: f"label__forward_return_{h}__v1" for h in (3, 5, 10, 20)}
EXIT_ISINS = ("PLLOTOS00025", "PLPGNIG00014", "PLSTSHL00012", "PLCIECH00018", "PLTIM0000016")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(json_safe(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def hac_standard_error(values: np.ndarray, max_lag: int) -> float:
    clean = values[np.isfinite(values)]
    n = len(clean)
    if n < 3:
        return float("nan")
    centered = clean - clean.mean()
    lag = min(int(max_lag), n - 1)
    long_variance = float(np.dot(centered, centered) / n)
    for offset in range(1, lag + 1):
        gamma = float(np.dot(centered[offset:], centered[:-offset]) / n)
        long_variance += 2.0 * (1.0 - offset / (lag + 1.0)) * gamma
    return float(np.sqrt(max(long_variance, 0.0) / n))


def block_bootstrap_ci(
    values: np.ndarray, samples: int, block_length: int, confidence_level: float, seed: int
) -> tuple[float, float]:
    clean = values[np.isfinite(values)]
    n = len(clean)
    if n < 3:
        return float("nan"), float("nan")
    block = min(int(block_length), n)
    blocks_needed = math.ceil(n / block)
    offsets = np.arange(block)
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype=float)
    for sample in range(samples):
        starts = rng.integers(0, n, size=blocks_needed)
        selected = ((starts[:, None] + offsets[None, :]) % n).reshape(-1)[:n]
        means[sample] = clean[selected].mean()
    alpha = (1.0 - confidence_level) / 2.0
    return float(np.quantile(means, alpha)), float(np.quantile(means, 1.0 - alpha))


def stable_seed(base: int, tag: str) -> int:
    return int(base + int(hashlib.sha256(tag.encode("utf-8")).hexdigest()[:8], 16)) % (2**32 - 1)


def infer_summary(
    values: Iterable[float], lag: int, cfg: dict[str, Any], tag: str, bootstrap: bool = True
) -> dict[str, Any]:
    clean = np.asarray(list(values), dtype=float)
    clean = clean[np.isfinite(clean)]
    n = len(clean)
    if not n:
        return {
            "sessions": 0,
            "mean": np.nan,
            "median": np.nan,
            "standard_deviation": np.nan,
            "skewness": np.nan,
            "negative_share": np.nan,
            "positive_share": np.nan,
            "zero_share": np.nan,
            "hac_lag_sessions": int(lag),
            "hac_standard_error": np.nan,
            "hac_ci_low": np.nan,
            "hac_ci_high": np.nan,
            "hac_normal_p_value": np.nan,
            "bootstrap_block_sessions": max(int(cfg["bootstrap_block_sessions"]), int(lag)),
            "bootstrap_ci_low": np.nan,
            "bootstrap_ci_high": np.nan,
            "effective_sessions_hac": np.nan,
        }
    series = pd.Series(clean)
    se = hac_standard_error(clean, lag)
    mean = float(clean.mean())
    critical = 1.959963984540054
    z = mean / se if np.isfinite(se) and se > 0 else np.nan
    p_value = math.erfc(abs(z) / math.sqrt(2.0)) if np.isfinite(z) else np.nan
    variance = float(np.var(clean, ddof=1)) if n > 1 else np.nan
    effective = min(float(n), max(1.0, variance / (se * se))) if np.isfinite(variance) and se > 0 else np.nan
    block = max(int(cfg["bootstrap_block_sessions"]), int(lag))
    if bootstrap:
        boot_low, boot_high = block_bootstrap_ci(
            clean,
            int(cfg["bootstrap_samples"]),
            block,
            float(cfg["confidence_level"]),
            stable_seed(int(cfg["seed"]), tag),
        )
    else:
        boot_low, boot_high = np.nan, np.nan
    result = {
        "sessions": n,
        "mean": mean,
        "median": float(np.median(clean)),
        "standard_deviation": float(np.std(clean, ddof=1)) if n > 1 else np.nan,
        "skewness": float(series.skew()) if n > 2 else np.nan,
        "q01": float(np.quantile(clean, 0.01)),
        "q05": float(np.quantile(clean, 0.05)),
        "q10": float(np.quantile(clean, 0.10)),
        "q25": float(np.quantile(clean, 0.25)),
        "q75": float(np.quantile(clean, 0.75)),
        "q90": float(np.quantile(clean, 0.90)),
        "q95": float(np.quantile(clean, 0.95)),
        "q99": float(np.quantile(clean, 0.99)),
        "negative_share": float((clean < 0).mean()),
        "positive_share": float((clean > 0).mean()),
        "zero_share": float((clean == 0).mean()),
        "hac_lag_sessions": int(lag),
        "hac_standard_error": se,
        "hac_ci_low": mean - critical * se if np.isfinite(se) else np.nan,
        "hac_ci_high": mean + critical * se if np.isfinite(se) else np.nan,
        "hac_normal_p_value": p_value,
        "bootstrap_samples": int(cfg["bootstrap_samples"]) if bootstrap else 0,
        "bootstrap_block_sessions": block,
        "bootstrap_ci_low": boot_low,
        "bootstrap_ci_high": boot_high,
        "effective_sessions_hac": effective,
    }
    return result


def benjamini_hochberg(values: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=values.index, dtype=float)
    valid = values.dropna().sort_values()
    m = len(valid)
    if not m:
        return result
    adjusted = valid.to_numpy(float) * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1].clip(0, 1)
    result.loc[valid.index] = adjusted
    return result


def session_rank_ic(frame: pd.DataFrame, x: str, y: str) -> pd.DataFrame:
    work = frame[["session_date", x, y]].dropna().copy()
    work["xr"] = work.groupby("session_date", sort=False)[x].rank(method="average")
    work["yr"] = work.groupby("session_date", sort=False)[y].rank(method="average")
    work["xx"] = work["xr"] ** 2
    work["yy"] = work["yr"] ** 2
    work["xy"] = work["xr"] * work["yr"]
    sums = work.groupby("session_date", as_index=False).agg(
        observations=("xr", "size"), sx=("xr", "sum"), sy=("yr", "sum"),
        sxx=("xx", "sum"), syy=("yy", "sum"), sxy=("xy", "sum")
    )
    n = sums["observations"].astype(float)
    numerator = sums["sxy"] - sums["sx"] * sums["sy"] / n
    denominator = np.sqrt((sums["sxx"] - sums["sx"] ** 2 / n) * (sums["syy"] - sums["sy"] ** 2 / n))
    sums["estimate"] = numerator / denominator.replace(0, np.nan)
    sums.loc[sums["observations"] < 3, "estimate"] = np.nan
    return sums[["session_date", "observations", "estimate"]]


def pearson_closed_form(left: np.ndarray, right: np.ndarray) -> float:
    left_centered = left - left.mean()
    right_centered = right - right.mean()
    denominator = math.sqrt(float(np.dot(left_centered, left_centered) * np.dot(right_centered, right_centered)))
    return float(np.dot(left_centered, right_centered) / denominator) if denominator else np.nan


def session_partial_diagnostics(frame: pd.DataFrame, x: str, y: str, control: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for session, group in frame[["session_date", x, y, control]].dropna().groupby("session_date", sort=True):
        if len(group) < 5:
            continue
        ranked = group[[x, y, control]].rank(method="average", pct=True)
        xv = ranked[x].to_numpy(float)
        yv = ranked[y].to_numpy(float)
        cv = ranked[control].to_numpy(float)
        rxy = pearson_closed_form(xv, yv)
        rxc = pearson_closed_form(xv, cv)
        ryc = pearson_closed_form(yv, cv)
        partial_denominator = math.sqrt(max((1.0 - rxc * rxc) * (1.0 - ryc * ryc), 0.0))
        partial = (rxy - rxc * ryc) / partial_denominator if partial_denominator else np.nan
        coefficient_denominator = 1.0 - rxc * rxc
        coefficient = (rxy - rxc * ryc) / coefficient_denominator if coefficient_denominator else np.nan
        rows.append({"session_date": session, "observations": len(group), "partial_rank_ic": partial, "standardized_coefficient": coefficient})
    return pd.DataFrame(rows)


def period_masks(dates: pd.Series, split_date: str) -> list[tuple[str, str, np.ndarray]]:
    normalized = pd.to_datetime(dates).dt.normalize()
    split = pd.Timestamp(split_date)
    result: list[tuple[str, str, np.ndarray]] = [("full", "full_sample", np.ones(len(normalized), dtype=bool))]
    for year in sorted(normalized.dt.year.unique()):
        result.append(("calendar_year", str(int(year)), normalized.dt.year.eq(year).to_numpy()))
    result.extend(
        [
            ("early_late", "early_through_2023_06_30", normalized.lt(split).to_numpy()),
            ("early_late", "late_from_2023_07_01", normalized.ge(split).to_numpy()),
            ("episode", "2020_2021", normalized.dt.year.le(2021).to_numpy()),
            ("episode", "2022_2025", normalized.dt.year.ge(2022).to_numpy()),
        ]
    )
    return result


@dataclass
class OutputStore:
    run_dir: Path
    records: dict[str, dict[str, Any]]

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.records = {}

    def _record(self, path: Path, fmt: str, rows: int | None = None, logical_hash: str | None = None) -> None:
        relative = path.relative_to(self.run_dir).as_posix()
        digest = sha256_file(path)
        self.records[relative] = {
            "format": fmt,
            "rows": rows,
            "bytes": path.stat().st_size,
            "sha256": digest,
            "logical_hash": logical_hash or digest,
        }

    def csv(self, name: str, frame: pd.DataFrame, sort_by: list[str] | None = None) -> Path:
        path = self.run_dir / "tables" / name
        ordered = frame.copy()
        if sort_by:
            ordered = ordered.sort_values([c for c in sort_by if c in ordered.columns], kind="mergesort", na_position="last")
        ordered = ordered.reset_index(drop=True)
        ordered.to_csv(path, index=False, encoding="utf-8", lineterminator="\n", float_format="%.12g", date_format="%Y-%m-%d")
        self._record(path, "csv", len(ordered), sha256_file(path))
        return path

    def parquet(self, relative: str, frame: pd.DataFrame, sort_by: list[str]) -> Path:
        path = self.run_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = frame.sort_values(sort_by, kind="mergesort", na_position="last").reset_index(drop=True)
        table = pa.Table.from_pandas(ordered, preserve_index=False)
        pq.write_table(table, path, compression="zstd", compression_level=3, row_group_size=122880)
        self._record(path, "parquet", len(ordered), sha256_file(path))
        return path

    def json(self, relative: str, value: Any) -> Path:
        path = self.run_dir / relative
        write_json(path, value)
        self._record(path, "json", None, canonical_hash(json_safe(value)))
        return path

    def copy(self, source: Path, relative: str, fmt: str) -> Path:
        path = self.run_dir / relative
        shutil.copy2(source, path)
        self._record(path, fmt, None, sha256_file(path))
        return path

    def figure(self, relative: str) -> None:
        path = self.run_dir / relative
        self._record(path, "png", None, sha256_file(path))


def run_command(command: list[str], cwd: Path, env: dict[str, str], log_path: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    rendered = subprocess.list2cmdline(command)
    log_path.write_text(
        f"COMMAND: {rendered}\nCWD: {cwd}\nEXIT_CODE: {completed.returncode}\n\nSTDOUT\n{completed.stdout}\nSTDERR\n{completed.stderr}",
        encoding="utf-8",
    )
    return {"command": rendered, "cwd": str(cwd), "exit_code": completed.returncode, "log": log_path.name}


def create_source_snapshot(source_root: Path, output: Path) -> None:
    names = ["analysis_plan.md", "config.yaml", "run_diagnostics.py"]
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in names:
            data = (source_root / name).read_bytes()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)


def aggregate_session_cells(
    frame: pd.DataFrame, cell_columns: list[str], value_column: str, split_date: str,
    session_metadata: pd.DataFrame | None = None,
) -> pd.DataFrame:
    session_cells = frame.groupby(["session_date", *cell_columns], dropna=False, as_index=False).agg(
        cell_mean=(value_column, "mean"), cell_median=(value_column, "median"), constituent_observations=(value_column, "size")
    )
    if session_metadata is None:
        totals = session_cells.groupby("session_date", as_index=False)["constituent_observations"].sum()
        totals["official_member_count"] = 60
        totals["price_usable_count"] = np.nan
        totals["feature_eligible_count"] = totals["constituent_observations"]
        totals["label_eligible_count"] = totals["constituent_observations"]
        session_metadata = totals.drop(columns="constituent_observations")
    session_cells = session_cells.merge(session_metadata, on="session_date", how="left", validate="many_to_one")
    rows: list[dict[str, Any]] = []
    for period_type, period, mask in period_masks(session_cells["session_date"], split_date):
        subset = session_cells.loc[mask]
        for keys, group in subset.groupby(cell_columns, dropna=False, sort=True):
            if not isinstance(keys, tuple):
                keys = (keys,)
            row = dict(zip(cell_columns, keys))
            row.update(
                {
                    "period_type": period_type,
                    "period": period,
                    "sessions": int(group["session_date"].nunique()),
                    "constituent_observations": int(group["constituent_observations"].sum()),
                    "mean_constituents_per_session": float(group["constituent_observations"].mean()),
                    "minimum_constituents_per_session": int(group["constituent_observations"].min()),
                    "maximum_constituents_per_session": int(group["constituent_observations"].max()),
                    "official_member_count": int(group["official_member_count"].max()),
                    "price_usable_count_mean": float(group["price_usable_count"].mean()),
                    "price_usable_count_min": int(group["price_usable_count"].min()) if group["price_usable_count"].notna().any() else np.nan,
                    "feature_eligible_count_mean": float(group["feature_eligible_count"].mean()),
                    "feature_eligible_count_min": int(group["feature_eligible_count"].min()),
                    "label_eligible_count_mean": float(group["label_eligible_count"].mean()),
                    "label_eligible_count_min": int(group["label_eligible_count"].min()),
                    "mean_diagnostic_gross_return": float(group["cell_mean"].mean()),
                    "median_session_diagnostic_gross_return": float(group["cell_mean"].median()),
                    "median_constituent_return": float(group["cell_median"].median()),
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def session_denominators(frame: pd.DataFrame, feature_mask: pd.Series, label_mask: pd.Series) -> pd.DataFrame:
    work = frame[["session_date", "official_member_count", "price_usable_member_count"]].copy()
    work["_feature_ok"] = feature_mask.to_numpy(bool)
    work["_label_ok"] = label_mask.to_numpy(bool)
    return work.groupby("session_date", as_index=False).agg(
        official_member_count=("official_member_count", "first"),
        price_usable_count=("price_usable_member_count", "first"),
        feature_eligible_count=("_feature_ok", "sum"),
        label_eligible_count=("_label_ok", "sum"),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config_container = config_path.parent
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    source_root = Path(cfg["diagnostic_source_root"]).resolve()
    analysis = cfg["analysis"]
    output_root = Path(cfg["output_root"])
    run_dir = output_root / args.run_id
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing immutable run: {run_dir}")
    run_dir.mkdir(parents=True)
    (run_dir / "tables").mkdir()
    (run_dir / "figures").mkdir()
    (run_dir / "logs").mkdir()
    shutil.copy2(config_path, run_dir / "config.yaml")
    retained_plan = config_container / "analysis_plan.md"
    shutil.copy2(retained_plan if retained_plan.is_file() else source_root / "analysis_plan.md", run_dir / "analysis_plan.md")
    store = OutputStore(run_dir)
    store._record(run_dir / "config.yaml", "yaml", None, sha256_file(run_dir / "config.yaml"))
    store._record(run_dir / "analysis_plan.md", "markdown", None, sha256_file(run_dir / "analysis_plan.md"))

    trusted_run = Path(cfg["trusted_phase_a_run_dir"])
    artifacts = trusted_run / "artifacts"
    trusted_manifest = json.loads((trusted_run / "manifest.json").read_text(encoding="utf-8"))
    reproduction = json.loads(Path(cfg["trusted_reproduction_report"]).read_text(encoding="utf-8"))
    if not reproduction.get("passed"):
        raise RuntimeError("trusted Phase A reproduction report does not pass")

    # Retain the integrity commands and run them before loading analytical frames.
    python = str(Path(cfg["python_executable"]))
    snapshot = Path(cfg["phase_a_snapshot_source"])
    command_env = os.environ.copy()
    command_env["PYTHONPATH"] = str(snapshot / "src")
    command_env["PYTHONDONTWRITEBYTECODE"] = "1"
    commands = []
    commands.append(
        run_command(
            [python, "-m", "pytest", "-p", "no:cacheprovider", str(snapshot / "tests")],
            Path("D:/Stock/ATS"), command_env, run_dir / "logs" / "phase_a_tests.txt"
        )
    )
    commands.append(
        run_command(
            [python, "-m", "ats_research", "validate", "--run-dir", str(trusted_run)],
            Path("D:/Stock/ATS"), command_env, run_dir / "logs" / "phase_a_archive_validation.txt"
        )
    )
    if any(command["exit_code"] != 0 for command in commands):
        raise RuntimeError("integrity command failed; see retained logs")

    expected_outputs = trusted_manifest["output_artifact_hashes"]
    trusted_hashes_before: dict[str, str] = {}
    for relative, record in expected_outputs.items():
        actual = sha256_file(trusted_run / relative)
        if actual != record["sha256"]:
            raise RuntimeError(f"trusted artifact changed or corrupt: {relative}")
        trusted_hashes_before[relative] = actual

    current_phase_a_root = Path("D:/Stock/ATS/source/python")
    current_code_mismatches = []
    for relative, expected in trusted_manifest["code_file_hashes"].items():
        current = current_phase_a_root / relative
        actual = sha256_file(current) if current.is_file() else None
        if actual != expected:
            current_code_mismatches.append({"path": relative, "expected_sha256": expected, "current_sha256": actual})

    panel = pd.read_parquet(artifacts / "research_panel.parquet")
    rank_ic = pd.read_parquet(artifacts / "rank_ic.parquet")
    quantile_returns = pd.read_parquet(artifacts / "quantile_returns.parquet")
    bars = pd.read_parquet(artifacts / "validated_daily_bars.parquet")
    wig = pd.read_parquet(artifacts / "wig_daily.parquet")
    membership = pd.read_parquet(artifacts / "membership_intervals.parquet")
    for frame in (panel, rank_ic, quantile_returns, bars, wig):
        if "session_date" in frame:
            frame["session_date"] = pd.to_datetime(frame["session_date"]).dt.normalize()
    panel["feature_session_date"] = pd.to_datetime(panel["feature_session_date"]).dt.normalize()

    horizons = [int(h) for h in analysis["horizons"]]
    if horizons != [3, 5, 10, 20]:
        raise ValueError("this diagnostic version is pinned to Phase A horizons 3/5/10/20")

    # Denominator and missing-state audit.
    denominator_rows: list[dict[str, Any]] = []
    exclusion_rows: list[dict[str, Any]] = []
    grouped_panel_size = panel.groupby("session_date").size()
    if not grouped_panel_size.eq(60).all() or not panel["official_member_count"].eq(60).all():
        raise RuntimeError("official TOP60 denominator is not retained")
    if panel.loc[~panel["is_price_usable_member"], "price_exclusion_reason"].isna().any():
        raise RuntimeError("excluded price member lacks a missing-state reason")
    for feature, column in FEATURES.items():
        eligible_col = f"is_feature_eligible__{feature}"
        reason_col = f"feature_exclusion_reason__{feature}"
        count_col = f"feature_usable_member_count__{feature}"
        expected_count = panel.groupby("session_date")[eligible_col].transform("sum").astype(int)
        if not np.array_equal(panel[count_col].to_numpy(dtype=int), expected_count.to_numpy(dtype=int)):
            raise RuntimeError(f"feature denominator mismatch: {feature}")
        if panel.loc[~panel[eligible_col], reason_col].isna().any():
            raise RuntimeError(f"excluded feature member lacks a missing-state reason: {feature}")
        for horizon in horizons:
            label_col = LABELS[horizon]
            per_session = panel.assign(_label_ok=panel[eligible_col] & panel[label_col].notna()).groupby("session_date", as_index=False).agg(
                official_member_count=("official_member_count", "first"),
                price_usable_member_count=("price_usable_member_count", "first"),
                feature_eligible_count=(eligible_col, "sum"),
                label_eligible_count=("_label_ok", "sum"),
            )
            phase_a_count = rank_ic.loc[(rank_ic["feature"] == feature) & (rank_ic["horizon_sessions"] == horizon), ["session_date", "label_usable_count"]]
            check = per_session.merge(phase_a_count, on="session_date", how="left", validate="one_to_one")
            if not check["label_eligible_count"].eq(check["label_usable_count"]).all():
                raise RuntimeError(f"label denominator mismatch: {feature}, h={horizon}")
            per_session["feature"] = feature
            per_session["horizon_sessions"] = horizon
            denominator_rows.extend(per_session.to_dict("records"))
            reasons = panel.assign(
                missing_state=np.select(
                    [~panel["is_price_usable_member"], ~panel[eligible_col], panel[label_col].isna()],
                    [
                        "price:" + panel["price_exclusion_reason"].fillna("unknown").astype(str),
                        "feature:" + panel[reason_col].fillna("unknown").astype(str),
                        "label:missing_exact_start_or_end",
                    ],
                    default="eligible",
                )
            ).groupby(["session_date", "missing_state"], as_index=False).size().rename(columns={"size": "member_count"})
            reasons["feature"] = feature
            reasons["horizon_sessions"] = horizon
            exclusion_rows.extend(reasons.to_dict("records"))
    denominator_audit = pd.DataFrame(denominator_rows)
    exclusion_audit = pd.DataFrame(exclusion_rows)
    store.csv("cross_section_denominator_audit.csv", denominator_audit, ["feature", "horizon_sessions", "session_date"])
    store.csv("cross_section_missing_state_audit.csv", exclusion_audit, ["feature", "horizon_sessions", "session_date", "missing_state"])

    # Confirmatory IC distribution, uncertainty, periods, rolling windows, and all non-overlapping offsets.
    ic_summary_rows: list[dict[str, Any]] = []
    period_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    offset_rows: list[dict[str, Any]] = []
    endpoint_rows: list[dict[str, Any]] = []
    master_dates = pd.Index(sorted(panel["session_date"].unique()))
    date_index = {date: index for index, date in enumerate(master_dates)}
    shift = int(analysis["endpoint_shift_sessions"])
    for (feature, horizon), group in rank_ic.groupby(["feature", "horizon_sessions"], sort=True):
        group = group.sort_values("session_date").copy()
        stats = infer_summary(group["rank_ic"], int(horizon), analysis, f"confirmatory:{feature}:{horizon}")
        stats.update(
            {
                "family": "phase_a_confirmatory_rank_ic",
                "feature": feature,
                "label": f"forward_return_{int(horizon)}",
                "horizon_sessions": int(horizon),
                "constituent_observations": int(group["label_usable_count"].sum()),
                "official_member_count": 60,
                "price_usable_count_mean": float(group["price_usable_member_count"].mean()),
                "price_usable_count_min": int(group["price_usable_member_count"].min()),
                "feature_eligible_count_mean": float(group["feature_usable_member_count"].mean()),
                "feature_eligible_count_min": int(group["feature_usable_member_count"].min()),
                "label_eligible_count_mean": float(group["label_usable_count"].mean()),
                "label_eligible_count_min": int(group["label_usable_count"].min()),
            }
        )
        ic_summary_rows.append(stats)
        for period_type, period, mask in period_masks(group["session_date"], analysis["early_late_split_date"]):
            subset = group.loc[mask]
            pstats = infer_summary(subset["rank_ic"], int(horizon), analysis, f"period:{feature}:{horizon}:{period}", bootstrap=False)
            pstats.update(
                {
                    "feature": feature,
                    "horizon_sessions": int(horizon),
                    "period_type": period_type,
                    "period": period,
                    "constituent_observations": int(subset["label_usable_count"].sum()),
                    "official_member_count": 60,
                    "price_usable_count_mean": float(subset["price_usable_member_count"].mean()) if len(subset) else np.nan,
                    "feature_eligible_count_mean": float(subset["feature_usable_member_count"].mean()) if len(subset) else np.nan,
                    "label_eligible_count_mean": float(subset["label_usable_count"].mean()) if len(subset) else np.nan,
                }
            )
            period_rows.append(pstats)
        ordered = group.set_index("session_date").reindex(master_dates)
        rolling = ordered["rank_ic"].rolling(
            int(analysis["rolling_window_sessions"]), min_periods=int(analysis["rolling_min_sessions"])
        ).agg(["mean", "count"])
        for date, row in rolling.dropna(subset=["mean"]).iterrows():
            rolling_rows.append(
                {"session_date": date, "feature": feature, "horizon_sessions": int(horizon), "rolling_mean_rank_ic": row["mean"], "sessions_in_window": int(row["count"])}
            )
        group["global_session_index"] = group["session_date"].map(date_index)
        for offset in range(int(horizon)):
            subset = group.loc[group["global_session_index"].mod(int(horizon)).eq(offset) & group["rank_ic"].notna()]
            ostats = infer_summary(subset["rank_ic"], 1, analysis, f"offset:{feature}:{horizon}:{offset}", bootstrap=False)
            ostats.update(
                {
                    "feature": feature,
                    "horizon_sessions": int(horizon),
                    "offset": offset,
                    "constituent_observations": int(subset["label_usable_count"].sum()),
                    "official_member_count": 60,
                    "price_usable_count_mean": float(subset["price_usable_member_count"].mean()) if len(subset) else np.nan,
                    "feature_eligible_count_mean": float(subset["feature_usable_member_count"].mean()) if len(subset) else np.nan,
                    "label_eligible_count_mean": float(subset["label_usable_count"].mean()) if len(subset) else np.nan,
                    "offset_rule": "full WIG decision-session index modulo horizon",
                }
            )
            offset_rows.append(ostats)
        endpoint_subsets = {
            "full": group,
            "drop_first_20": group.loc[group["session_date"].isin(master_dates[shift:])],
            "drop_last_20": group.loc[group["session_date"].isin(master_dates[:-shift])],
            "drop_first_and_last_20": group.loc[group["session_date"].isin(master_dates[shift:-shift])],
        }
        for name, subset in endpoint_subsets.items():
            endpoint_rows.append(
                {
                    "feature": feature,
                    "horizon_sessions": int(horizon),
                    "endpoint_sample": name,
                    "sessions": int(subset["rank_ic"].notna().sum()),
                    "mean_rank_ic": float(subset["rank_ic"].mean()),
                    "median_rank_ic": float(subset["rank_ic"].median()),
                    "positive_share": float((subset["rank_ic"].dropna() > 0).mean()),
                    "constituent_observations": int(subset["label_usable_count"].sum()),
                }
            )
    ic_summary = pd.DataFrame(ic_summary_rows)
    ic_summary["benjamini_hochberg_q_value"] = benjamini_hochberg(ic_summary["hac_normal_p_value"])
    period_ic = pd.DataFrame(period_rows)
    rolling_ic = pd.DataFrame(rolling_rows)
    non_overlap = pd.DataFrame(offset_rows)
    endpoint_sensitivity = pd.DataFrame(endpoint_rows)
    store.csv("ic_distribution_uncertainty.csv", ic_summary, ["feature", "horizon_sessions"])
    store.csv("annual_period_ic.csv", period_ic, ["feature", "horizon_sessions", "period_type", "period"])
    store.csv("rolling_ic_252.csv", rolling_ic, ["feature", "horizon_sessions", "session_date"])
    store.csv("non_overlapping_offset_ic.csv", non_overlap, ["feature", "horizon_sessions", "offset"])
    store.csv("endpoint_shift_sensitivity.csv", endpoint_sensitivity, ["feature", "horizon_sessions", "endpoint_sample"])

    # Fixed Phase A quantile profiles and monotonicity.
    quantile_period_rows: list[dict[str, Any]] = []
    for (feature, horizon), group in quantile_returns.groupby(["feature", "horizon_sessions"], sort=True):
        for period_type, period, mask in period_masks(group["session_date"], analysis["early_late_split_date"]):
            subset = group.loc[mask]
            for quantile, cell in subset.groupby("quantile", sort=True):
                valid = cell.loc[cell["quantile_count"] > 0]
                quantile_period_rows.append(
                    {
                        "feature": feature,
                        "horizon_sessions": int(horizon),
                        "period_type": period_type,
                        "period": period,
                        "quantile": int(quantile),
                        "sessions": int(len(valid)),
                        "constituent_observations": int(valid["quantile_count"].sum()),
                        "mean_diagnostic_gross_return": float(valid["mean_forward_return"].mean()),
                        "median_session_diagnostic_gross_return": float(valid["mean_forward_return"].median()),
                        "official_member_count": 60,
                        "price_usable_count_mean": float(valid["price_usable_member_count"].mean()),
                        "feature_eligible_count_mean": float(valid["feature_usable_member_count"].mean()),
                        "label_eligible_count_mean": float(valid["label_usable_count"].mean()),
                        "mean_cell_count": float(valid["quantile_count"].mean()),
                        "min_cell_count": int(valid["quantile_count"].min()) if len(valid) else 0,
                    }
                )
    quantile_period = pd.DataFrame(quantile_period_rows)
    monotonic_rows: list[dict[str, Any]] = []
    adjacent_rows: list[dict[str, Any]] = []
    for keys, group in quantile_period.groupby(["feature", "horizon_sessions", "period_type", "period"], sort=True):
        feature, horizon, period_type, period = keys
        ordered = group.sort_values("quantile")
        x = ordered["quantile"].to_numpy(float)
        y = ordered["mean_diagnostic_gross_return"].to_numpy(float)
        valid = np.isfinite(y)
        if valid.sum() >= 3:
            x_valid = x[valid]
            y_valid = y[valid]
            x_centered = x_valid - x_valid.mean()
            slope = float(np.dot(x_centered, y_valid - y_valid.mean()) / np.dot(x_centered, x_centered))
            intercept = float(y_valid.mean() - slope * x_valid.mean())
            fitted = intercept + slope * x[valid]
            ss_total = float(np.sum((y[valid] - y[valid].mean()) ** 2))
            r2 = 1.0 - float(np.sum((y[valid] - fitted) ** 2)) / ss_total if ss_total else np.nan
            x_rank = pd.Series(x[valid]).rank(method="average").to_numpy(float)
            y_rank = pd.Series(y[valid]).rank(method="average").to_numpy(float)
            spearman = pearson_closed_form(x_rank, y_rank)
        else:
            slope = r2 = spearman = np.nan
        lookup = ordered.set_index("quantile")["mean_diagnostic_gross_return"]
        top_bottom = float(lookup.get(5, np.nan) - lookup.get(1, np.nan))
        interior = float((lookup.get(4, np.nan) - lookup.get(2, np.nan)) / 2.0)
        edge_top = float(lookup.get(5, np.nan) - lookup.get(4, np.nan))
        edge_bottom = float(lookup.get(2, np.nan) - lookup.get(1, np.nan))
        differences = np.diff(y)
        monotonic_rows.append(
            {
                "feature": feature,
                "horizon_sessions": int(horizon),
                "period_type": period_type,
                "period": period,
                "quantile_rank_spearman": spearman,
                "linear_rank_gradient_per_quantile": slope,
                "linear_rank_gradient_r_squared": r2,
                "top_minus_bottom": top_bottom,
                "interior_q2_to_q4_gradient_per_step": interior,
                "top_edge_q5_minus_q4": edge_top,
                "bottom_edge_q2_minus_q1": edge_bottom,
                "monotonic_increasing": bool(np.all(differences >= 0)) if np.isfinite(differences).all() else False,
                "monotonic_decreasing": bool(np.all(differences <= 0)) if np.isfinite(differences).all() else False,
                "minimum_cell_count": int(ordered["min_cell_count"].min()),
                "sessions_min_across_quantiles": int(ordered["sessions"].min()),
                "constituent_observations": int(ordered["constituent_observations"].sum()),
            }
        )
        for index in range(1, len(ordered)):
            lower = ordered.iloc[index - 1]
            upper = ordered.iloc[index]
            adjacent_rows.append(
                {
                    "feature": feature,
                    "horizon_sessions": int(horizon),
                    "period_type": period_type,
                    "period": period,
                    "lower_quantile": int(lower["quantile"]),
                    "upper_quantile": int(upper["quantile"]),
                    "adjacent_difference": float(upper["mean_diagnostic_gross_return"] - lower["mean_diagnostic_gross_return"]),
                    "lower_observations": int(lower["constituent_observations"]),
                    "upper_observations": int(upper["constituent_observations"]),
                }
            )
    quantile_monotonicity = pd.DataFrame(monotonic_rows)
    adjacent = pd.DataFrame(adjacent_rows)
    store.csv("quantile_results_by_period.csv", quantile_period, ["feature", "horizon_sessions", "period_type", "period", "quantile"])
    store.csv("quantile_monotonicity.csv", quantile_monotonicity, ["feature", "horizon_sessions", "period_type", "period"])
    store.csv("quantile_adjacent_differences.csv", adjacent, ["feature", "horizon_sessions", "period_type", "period", "lower_quantile"])

    # Trend-conditioned short-term pullback diagnostics.
    trend_cell_frames: list[pd.DataFrame] = []
    trend_double_frames: list[pd.DataFrame] = []
    trend_partial_rows: list[dict[str, Any]] = []
    trend_period_rows: list[dict[str, Any]] = []
    return_pct = "percentile_rank__return_5__v1"
    momentum_pct = "percentile_rank__momentum_12_1__v1"
    for horizon in horizons:
        label_col = LABELS[horizon]
        trend_base = panel[["session_date", "wig_trend_regime", return_pct, momentum_pct, label_col, "official_member_count", "price_usable_member_count"]].copy()
        trend_feature_ok = trend_base[[return_pct, momentum_pct, "wig_trend_regime"]].notna().all(axis=1)
        trend_label_ok = trend_feature_ok & trend_base[label_col].notna()
        trend_denominators = session_denominators(trend_base, trend_feature_ok, trend_label_ok)
        work = trend_base.loc[trend_label_ok].copy()
        work["pullback_tercile"] = np.ceil(work[return_pct] * 3).clip(1, 3).astype(int)
        work["momentum_tercile"] = np.ceil(work[momentum_pct] * 3).clip(1, 3).astype(int)
        work["horizon_sessions"] = horizon
        cells = aggregate_session_cells(work, ["wig_trend_regime", "pullback_tercile"], label_col, analysis["early_late_split_date"], trend_denominators)
        cells["horizon_sessions"] = horizon
        trend_cell_frames.append(cells)
        positive = work.loc[work["wig_trend_regime"].eq("positive")]
        positive_denominators = trend_denominators.loc[trend_denominators["session_date"].isin(positive["session_date"].unique())]
        doubles = aggregate_session_cells(positive, ["momentum_tercile", "pullback_tercile"], label_col, analysis["early_late_split_date"], positive_denominators)
        doubles["horizon_sessions"] = horizon
        trend_double_frames.append(doubles)
        for regime, subset in work.groupby("wig_trend_regime", sort=True):
            diagnostics = session_partial_diagnostics(subset, return_pct, label_col, momentum_pct)
            stats = infer_summary(diagnostics["partial_rank_ic"], horizon, analysis, f"trend:{regime}:{horizon}")
            stats.update(
                {
                    "family": "trend_conditioned_partial_ic" if regime == "positive" else "descriptive_comparator",
                    "wig_trend_regime": regime,
                    "horizon_sessions": horizon,
                    "constituent_observations": int(diagnostics["observations"].sum()) if len(diagnostics) else 0,
                    "session_observations_mean": float(diagnostics["observations"].mean()) if len(diagnostics) else np.nan,
                }
            )
            diagnostic_denominators = trend_denominators.loc[trend_denominators["session_date"].isin(diagnostics["session_date"])]
            stats.update({
                "official_member_count": 60,
                "price_usable_count_mean": float(diagnostic_denominators["price_usable_count"].mean()),
                "feature_eligible_count_mean": float(diagnostic_denominators["feature_eligible_count"].mean()),
                "label_eligible_count_mean": float(diagnostic_denominators["label_eligible_count"].mean()),
            })
            trend_partial_rows.append(stats)
            diagnostics["year"] = diagnostics["session_date"].dt.year
            for year, year_group in diagnostics.groupby("year"):
                year_denominators = trend_denominators.loc[trend_denominators["session_date"].isin(year_group["session_date"])]
                trend_period_rows.append(
                    {
                        "wig_trend_regime": regime,
                        "horizon_sessions": horizon,
                        "year": int(year),
                        "sessions": len(year_group),
                        "constituent_observations": int(year_group["observations"].sum()),
                        "mean_partial_rank_ic": float(year_group["partial_rank_ic"].mean()),
                        "median_partial_rank_ic": float(year_group["partial_rank_ic"].median()),
                        "positive_share": float((year_group["partial_rank_ic"] > 0).mean()),
                        "official_member_count": 60,
                        "price_usable_count_mean": float(year_denominators["price_usable_count"].mean()),
                        "feature_eligible_count_mean": float(year_denominators["feature_eligible_count"].mean()),
                        "label_eligible_count_mean": float(year_denominators["label_eligible_count"].mean()),
                    }
                )
    trend_cells = pd.concat(trend_cell_frames, ignore_index=True)
    trend_doubles = pd.concat(trend_double_frames, ignore_index=True)
    trend_partial = pd.DataFrame(trend_partial_rows)
    positive_mask = trend_partial["family"].eq("trend_conditioned_partial_ic")
    trend_partial.loc[positive_mask, "benjamini_hochberg_q_value"] = benjamini_hochberg(
        trend_partial.loc[positive_mask, "hac_normal_p_value"]
    )
    trend_period = pd.DataFrame(trend_period_rows)
    store.csv("trend_conditioned_pullback_cells.csv", trend_cells, ["horizon_sessions", "wig_trend_regime", "period_type", "period", "pullback_tercile"])
    store.csv("trend_momentum_double_sort.csv", trend_doubles, ["horizon_sessions", "period_type", "period", "momentum_tercile", "pullback_tercile"])
    store.csv("trend_conditioned_partial_ic.csv", trend_partial, ["wig_trend_regime", "horizon_sessions"])
    store.csv("trend_conditioned_period_stability.csv", trend_period, ["wig_trend_regime", "horizon_sessions", "year"])

    # Proximity to a prior 252-session high, computed only from validated bars and pre-decision sessions.
    calendar = pd.Index(sorted(wig["session_date"].unique()))
    proximity_frames: list[pd.DataFrame] = []
    lookback = int(analysis["proximity_lookback_sessions"])
    relaxed_min = int(analysis["proximity_relaxed_min_observations"])
    for security_id, security_bars in bars.groupby("security_id", sort=True):
        grid = security_bars.set_index("session_date")[["close", "high"]].reindex(calendar)
        rolling_max = grid["high"].rolling(lookback, min_periods=1).max()
        rolling_count = grid["high"].rolling(lookback, min_periods=1).count()
        base = pd.DataFrame(
            {
                "security_id": security_id,
                "feature_session_date": calendar,
                "prior_close": grid["close"].to_numpy(),
                "trailing_high_252": rolling_max.to_numpy(),
                "high_observations_252": rolling_count.to_numpy(dtype=int),
            }
        )
        ratio = base["prior_close"] / base["trailing_high_252"]
        base["proximity_strict"] = ratio.where(base["high_observations_252"].eq(lookback))
        base["proximity_relaxed_240"] = ratio.where(base["high_observations_252"].ge(relaxed_min))
        proximity_frames.append(base)
    proximity_grid = pd.concat(proximity_frames, ignore_index=True)
    prox_panel = panel.merge(proximity_grid, on=["security_id", "feature_session_date"], how="left", validate="many_to_one")
    close_match = np.isclose(
        prox_panel["feature_input_close"].to_numpy(float), prox_panel["prior_close"].to_numpy(float), equal_nan=True
    )
    if not close_match.all():
        raise RuntimeError("proximity prior close does not match retained feature input close")
    proximity_coverage_rows: list[dict[str, Any]] = []
    proximity_test_rows: list[dict[str, Any]] = []
    proximity_period_rows: list[dict[str, Any]] = []
    proximity_double_frames: list[pd.DataFrame] = []
    prox_defs = {"strict_252_of_252": "proximity_strict", "relaxed_240_of_252": "proximity_relaxed_240"}
    for definition, prox_col in prox_defs.items():
        prox_panel[f"rank__{prox_col}"] = prox_panel.groupby("session_date")[prox_col].rank(method="average", pct=True)
        coverage_by_date = prox_panel.groupby("session_date", as_index=False).agg(
            official_member_count=("official_member_count", "first"),
            price_usable_count=("is_price_usable_member", "sum"),
            proximity_eligible_count=(prox_col, lambda x: int(x.notna().sum())),
            momentum_eligible_count=("is_feature_eligible__momentum_12_1__v1", "sum"),
        )
        coverage_by_date["definition"] = definition
        proximity_coverage_rows.extend(coverage_by_date.to_dict("records"))
        for horizon in horizons:
            label_col = LABELS[horizon]
            prox_base = prox_panel[["session_date", prox_col, FEATURES["momentum_12_1__v1"], label_col, "official_member_count", "price_usable_member_count"]].copy()
            prox_feature_ok = prox_base[[prox_col, FEATURES["momentum_12_1__v1"]]].notna().all(axis=1)
            prox_label_ok = prox_feature_ok & prox_base[label_col].notna()
            prox_denominators = session_denominators(prox_base, prox_feature_ok, prox_label_ok)
            subset = prox_base.loc[prox_label_ok]
            diagnostics = session_partial_diagnostics(subset, prox_col, label_col, FEATURES["momentum_12_1__v1"])
            for method, value_col in (("partial_rank_ic", "partial_rank_ic"), ("standardized_rank_regression_coefficient", "standardized_coefficient")):
                stats = infer_summary(diagnostics[value_col], horizon, analysis, f"proximity:{definition}:{method}:{horizon}")
                stats.update(
                    {
                        "family": "proximity_incremental",
                        "definition": definition,
                        "method": method,
                        "horizon_sessions": horizon,
                        "constituent_observations": int(diagnostics["observations"].sum()) if len(diagnostics) else 0,
                        "session_observations_mean": float(diagnostics["observations"].mean()) if len(diagnostics) else np.nan,
                        "official_member_count": 60,
                        "price_usable_count_mean": float(prox_denominators["price_usable_count"].mean()),
                        "feature_eligible_count_mean": float(prox_denominators["feature_eligible_count"].mean()),
                        "label_eligible_count_mean": float(prox_denominators["label_eligible_count"].mean()),
                    }
                )
                proximity_test_rows.append(stats)
            diagnostics["year"] = diagnostics["session_date"].dt.year
            for year, year_group in diagnostics.groupby("year"):
                year_denominators = prox_denominators.loc[prox_denominators["session_date"].isin(year_group["session_date"])]
                proximity_period_rows.append(
                    {
                        "definition": definition,
                        "horizon_sessions": horizon,
                        "year": int(year),
                        "sessions": len(year_group),
                        "constituent_observations": int(year_group["observations"].sum()),
                        "mean_partial_rank_ic": float(year_group["partial_rank_ic"].mean()),
                        "mean_standardized_coefficient": float(year_group["standardized_coefficient"].mean()),
                        "partial_ic_positive_share": float((year_group["partial_rank_ic"] > 0).mean()),
                        "official_member_count": 60,
                        "price_usable_count_mean": float(year_denominators["price_usable_count"].mean()),
                        "feature_eligible_count_mean": float(year_denominators["feature_eligible_count"].mean()),
                        "label_eligible_count_mean": float(year_denominators["label_eligible_count"].mean()),
                    }
                )
            if definition == "strict_252_of_252":
                double_work = subset.copy()
                double_work["momentum_tercile"] = np.ceil(
                    double_work.groupby("session_date")[FEATURES["momentum_12_1__v1"]].rank(method="average", pct=True) * 3
                ).clip(1, 3).astype(int)
                double_work["proximity_tercile"] = np.ceil(
                    double_work.groupby("session_date")[prox_col].rank(method="average", pct=True) * 3
                ).clip(1, 3).astype(int)
                double_table = aggregate_session_cells(
                    double_work, ["momentum_tercile", "proximity_tercile"], label_col, analysis["early_late_split_date"], prox_denominators
                )
                double_table["horizon_sessions"] = horizon
                double_table["definition"] = definition
                proximity_double_frames.append(double_table)
    proximity_coverage = pd.DataFrame(proximity_coverage_rows)
    proximity_tests = pd.DataFrame(proximity_test_rows)
    proximity_tests["benjamini_hochberg_q_value"] = benjamini_hochberg(proximity_tests["hac_normal_p_value"])
    proximity_period = pd.DataFrame(proximity_period_rows)
    proximity_doubles = pd.concat(proximity_double_frames, ignore_index=True)
    near_threshold = float(analysis["proximity_near_high_ratio"])
    near_counts = prox_panel.assign(
        proximity_state=np.select(
            [prox_panel["proximity_strict"].isna(), prox_panel["proximity_strict"].ge(near_threshold)],
            ["missing_strict_history", "at_or_above_0.95"], default="below_0.95"
        )
    ).groupby([prox_panel["session_date"].dt.year.rename("year"), "proximity_state"], as_index=False).size().rename(columns={"size": "member_sessions"})
    store.csv("proximity_coverage.csv", proximity_coverage, ["definition", "session_date"])
    store.csv("proximity_incremental_tests.csv", proximity_tests, ["definition", "method", "horizon_sessions"])
    store.csv("proximity_period_stability.csv", proximity_period, ["definition", "horizon_sessions", "year"])
    store.csv("proximity_momentum_double_sort.csv", proximity_doubles, ["horizon_sessions", "period_type", "period", "momentum_tercile", "proximity_tercile"])
    store.csv("proximity_near_high_counts.csv", near_counts, ["year", "proximity_state"])

    # Alternative decision-aligned labels from exact WIG-session bar observations.
    bar_index = bars.set_index(["security_id", "session_date"])[["open", "close"]].sort_index()
    panel_keys = pd.MultiIndex.from_frame(panel[["security_id", "session_date"]])
    mapped_positions = panel["session_date"].map({date: i for i, date in enumerate(calendar)})
    if mapped_positions.isna().any():
        raise RuntimeError("a Phase A decision session is absent from the retained WIG calendar")
    session_positions = mapped_positions.to_numpy(dtype=int)
    anchor_state_rows: list[dict[str, Any]] = []
    anchor_comparison_rows: list[dict[str, Any]] = []
    anchor_annual_rows: list[dict[str, Any]] = []
    anchor_quantile_rows: list[dict[str, Any]] = []
    anchor_member_state_frames: list[pd.DataFrame] = []
    for horizon in horizons:
        exit_positions = session_positions + horizon
        exit_dates = pd.DatetimeIndex([calendar[int(pos)] if 0 <= pos < len(calendar) else pd.NaT for pos in exit_positions])
        exit_keys = pd.MultiIndex.from_arrays([panel["security_id"], exit_dates], names=["security_id", "session_date"])
        entry_prices = bar_index.reindex(panel_keys)
        exit_prices = bar_index.reindex(exit_keys)
        trusted_recalc = exit_prices["close"].to_numpy() / entry_prices["close"].to_numpy() - 1.0
        trusted_values = panel[LABELS[horizon]].to_numpy(float)
        if not np.allclose(trusted_recalc, trusted_values, equal_nan=True, rtol=1e-12, atol=1e-12):
            raise RuntimeError(f"trusted label reconstruction mismatch at horizon {horizon}")
        anchors = {
            "decision_open_t_to_close_t_plus_h": (entry_prices["open"].to_numpy(), exit_prices["close"].to_numpy(), "open[t]", "close[t+h]", "open-to-close; h WIG-session gaps plus the exit-session intraday interval"),
            "decision_open_t_to_open_t_plus_h": (entry_prices["open"].to_numpy(), exit_prices["open"].to_numpy(), "open[t]", "open[t+h]", "h WIG-session open-to-open intervals"),
        }
        for anchor, (entry, exit_, entry_name, exit_name, exposure) in anchors.items():
            alt = exit_ / entry - 1.0
            state = np.select(
                [np.isnan(entry) & np.isnan(exit_), np.isnan(entry), np.isnan(exit_)],
                ["missing_entry_and_exit", "missing_entry", "missing_exit"], default="eligible"
            )
            state_frame = panel[["session_date", "security_id", "isin", "official_member_count", "price_usable_member_count"]].copy()
            state_frame["anchor"] = anchor
            state_frame["horizon_sessions"] = horizon
            state_frame["entry_observation"] = entry_name
            state_frame["exit_observation"] = exit_name
            state_frame["entry_present"] = ~np.isnan(entry)
            state_frame["exit_present"] = ~np.isnan(exit_)
            state_frame["eligibility_state"] = state
            state_frame["alternative_label"] = alt
            anchor_member_state_frames.append(state_frame)
            grouped_state = state_frame.assign(year=state_frame["session_date"].dt.year).groupby(
                ["anchor", "horizon_sessions", "year", "eligibility_state"], as_index=False
            ).size().rename(columns={"size": "member_sessions"})
            grouped_state["entry_observation"] = entry_name
            grouped_state["exit_observation"] = exit_name
            grouped_state["actual_exposure_semantics"] = exposure
            anchor_state_rows.extend(grouped_state.to_dict("records"))
            working = panel.copy()
            working["_alt_label"] = alt
            working["_trusted_label"] = trusted_values
            for feature, feature_col in FEATURES.items():
                anchor_feature_ok = working[feature_col].notna()
                anchor_label_ok = anchor_feature_ok & working["_alt_label"].notna()
                anchor_denominators = session_denominators(working, anchor_feature_ok, anchor_label_ok)
                alt_ic = session_rank_ic(working, feature_col, "_alt_label")
                paired = working.dropna(subset=[feature_col, "_alt_label", "_trusted_label"])
                paired_alt_ic = session_rank_ic(paired, feature_col, "_alt_label")
                paired_trusted_ic = session_rank_ic(paired, feature_col, "_trusted_label")
                stats = infer_summary(alt_ic["estimate"], horizon, analysis, f"anchor:{anchor}:{feature}:{horizon}")
                trusted_phase_a = ic_summary.loc[(ic_summary["feature"] == feature) & (ic_summary["horizon_sessions"] == horizon)].iloc[0]
                stats.update(
                    {
                        "family": "label_anchor_sensitivity",
                        "anchor": anchor,
                        "entry_observation": entry_name,
                        "exit_observation": exit_name,
                        "actual_exposure_semantics": exposure,
                        "feature": feature,
                        "horizon_sessions": horizon,
                        "constituent_observations": int(alt_ic["observations"].sum()),
                        "trusted_constituent_observations": int(trusted_phase_a["constituent_observations"]),
                        "trusted_mean_rank_ic": float(trusted_phase_a["mean"]),
                        "mean_rank_ic_difference_vs_trusted_full_samples": float(stats["mean"] - trusted_phase_a["mean"]),
                        "paired_alt_mean_rank_ic": float(paired_alt_ic["estimate"].mean()),
                        "paired_trusted_mean_rank_ic": float(paired_trusted_ic["estimate"].mean()),
                        "paired_mean_difference": float(paired_alt_ic.set_index("session_date")["estimate"].sub(paired_trusted_ic.set_index("session_date")["estimate"]).mean()),
                        "paired_constituent_observations": int(len(paired)),
                        "official_member_count": 60,
                        "price_usable_count_mean": float(anchor_denominators["price_usable_count"].mean()),
                        "feature_eligible_count_mean": float(anchor_denominators["feature_eligible_count"].mean()),
                        "label_eligible_count_mean": float(anchor_denominators["label_eligible_count"].mean()),
                    }
                )
                anchor_comparison_rows.append(stats)
                alt_ic["year"] = alt_ic["session_date"].dt.year
                for year, year_group in alt_ic.groupby("year"):
                    year_denominators = anchor_denominators.loc[anchor_denominators["session_date"].isin(year_group["session_date"])]
                    anchor_annual_rows.append(
                        {
                            "anchor": anchor,
                            "feature": feature,
                            "horizon_sessions": horizon,
                            "year": int(year),
                            "sessions": int(year_group["estimate"].notna().sum()),
                            "constituent_observations": int(year_group["observations"].sum()),
                            "mean_rank_ic": float(year_group["estimate"].mean()),
                            "median_rank_ic": float(year_group["estimate"].median()),
                            "positive_share": float((year_group["estimate"].dropna() > 0).mean()),
                            "official_member_count": 60,
                            "price_usable_count_mean": float(year_denominators["price_usable_count"].mean()),
                            "feature_eligible_count_mean": float(year_denominators["feature_eligible_count"].mean()),
                            "label_eligible_count_mean": float(year_denominators["label_eligible_count"].mean()),
                        }
                    )
            # Momentum quantiles are kept exactly as assigned by Phase A.
            momentum_quantile = "quantile__momentum_12_1__v1"
            qwork = working[["session_date", momentum_quantile, "_alt_label"]].dropna()
            qwork[momentum_quantile] = qwork[momentum_quantile].astype(int)
            momentum_feature_ok = working[FEATURES["momentum_12_1__v1"]].notna()
            momentum_label_ok = momentum_feature_ok & working["_alt_label"].notna()
            momentum_denominators = session_denominators(working, momentum_feature_ok, momentum_label_ok)
            qtable = aggregate_session_cells(qwork, [momentum_quantile], "_alt_label", analysis["early_late_split_date"], momentum_denominators)
            qtable = qtable.rename(columns={momentum_quantile: "quantile"})
            qtable["anchor"] = anchor
            qtable["horizon_sessions"] = horizon
            anchor_quantile_rows.extend(qtable.to_dict("records"))
    anchor_states = pd.DataFrame(anchor_state_rows)
    anchor_comparison = pd.DataFrame(anchor_comparison_rows)
    anchor_comparison["benjamini_hochberg_q_value"] = benjamini_hochberg(anchor_comparison["hac_normal_p_value"])
    anchor_annual = pd.DataFrame(anchor_annual_rows)
    anchor_quantiles = pd.DataFrame(anchor_quantile_rows)
    anchor_member_states = pd.concat(anchor_member_state_frames, ignore_index=True)
    store.csv("label_anchor_state_counts.csv", anchor_states, ["anchor", "horizon_sessions", "year", "eligibility_state"])
    store.csv("label_anchor_comparison.csv", anchor_comparison, ["anchor", "feature", "horizon_sessions"])
    store.csv("label_anchor_annual_stability.csv", anchor_annual, ["anchor", "feature", "horizon_sessions", "year"])
    store.csv("label_anchor_momentum_quantiles.csv", anchor_quantiles, ["anchor", "horizon_sessions", "period_type", "period", "quantile"])
    store.parquet("audit/label_anchor_member_states.parquet", anchor_member_states, ["anchor", "horizon_sessions", "session_date", "security_id"])

    # Coverage, membership-change, exit, and missingness sensitivity.
    membership_dates = sorted(pd.to_datetime(membership["effective_from"]).dt.normalize().dropna().unique())
    change_indices: set[int] = set()
    for date in membership_dates:
        pos = master_dates.searchsorted(date)
        if pos < len(master_dates):
            change_indices.add(int(pos))
    near_change_indices = {
        idx for base in change_indices for idx in range(max(0, base - int(analysis["membership_change_window_sessions"])), min(len(master_dates), base + int(analysis["membership_change_window_sessions"]) + 1))
    }
    date_meta = panel.groupby("session_date", as_index=False).agg(
        official_member_count=("official_member_count", "first"),
        price_usable_member_count=("price_usable_member_count", "first"),
        unresolved_exit_member_count=("unresolved_exit_member_count", "first"),
        wig_trend_regime=("wig_trend_regime", "first"),
    )
    date_meta["session_index"] = date_meta["session_date"].map(date_index)
    date_meta["near_membership_change"] = date_meta["session_index"].isin(near_change_indices)
    coverage_groups = {
        "usable_60_of_60": set(date_meta.loc[date_meta["price_usable_member_count"].eq(60), "session_date"]),
        "usable_below_60": set(date_meta.loc[date_meta["price_usable_member_count"].lt(60), "session_date"]),
        "usable_57_lowest": set(date_meta.loc[date_meta["price_usable_member_count"].eq(int(analysis["low_coverage_member_count"])), "session_date"]),
        "usable_58_to_59": set(date_meta.loc[date_meta["price_usable_member_count"].between(58, 59), "session_date"]),
        "near_membership_change_pm5": set(date_meta.loc[date_meta["near_membership_change"], "session_date"]),
        "outside_membership_change_pm5": set(date_meta.loc[~date_meta["near_membership_change"], "session_date"]),
        "active_unresolved_exit": set(date_meta.loc[date_meta["unresolved_exit_member_count"].gt(0), "session_date"]),
        "no_active_unresolved_exit": set(date_meta.loc[date_meta["unresolved_exit_member_count"].eq(0), "session_date"]),
    }
    coverage_ic_rows: list[dict[str, Any]] = []
    coverage_quantile_rows: list[dict[str, Any]] = []
    coverage_missing_rows: list[dict[str, Any]] = []
    for group_name, dates in coverage_groups.items():
        for (feature, horizon), group in rank_ic.loc[rank_ic["session_date"].isin(dates)].groupby(["feature", "horizon_sessions"], sort=True):
            stats = infer_summary(group["rank_ic"], int(horizon), analysis, f"coverage:{group_name}:{feature}:{horizon}", bootstrap=False)
            stats.update(
                {
                    "coverage_group": group_name,
                    "feature": feature,
                    "horizon_sessions": int(horizon),
                    "constituent_observations": int(group["label_usable_count"].sum()),
                    "official_member_count": 60,
                    "price_usable_count_mean": float(group["price_usable_member_count"].mean()),
                    "feature_eligible_count_mean": float(group["feature_usable_member_count"].mean()),
                    "label_eligible_count_mean": float(group["label_usable_count"].mean()),
                }
            )
            coverage_ic_rows.append(stats)
        qsubset = quantile_returns.loc[quantile_returns["session_date"].isin(dates)]
        for (feature, horizon, quantile), group in qsubset.groupby(["feature", "horizon_sessions", "quantile"], sort=True):
            valid = group.loc[group["quantile_count"] > 0]
            coverage_quantile_rows.append(
                {
                    "coverage_group": group_name,
                    "feature": feature,
                    "horizon_sessions": int(horizon),
                    "quantile": int(quantile),
                    "sessions": len(valid),
                    "constituent_observations": int(valid["quantile_count"].sum()),
                    "mean_diagnostic_gross_return": float(valid["mean_forward_return"].mean()),
                    "official_member_count": 60,
                    "price_usable_count_mean": float(valid["price_usable_member_count"].mean()),
                    "feature_eligible_count_mean": float(valid["feature_usable_member_count"].mean()),
                    "label_eligible_count_mean": float(valid["label_usable_count"].mean()),
                    "minimum_cell_count": int(valid["quantile_count"].min()) if len(valid) else 0,
                }
            )
        psubset = panel.loc[panel["session_date"].isin(dates)]
        price_reasons = psubset.assign(reason=psubset["price_exclusion_reason"].fillna("eligible")).groupby("reason", as_index=False).size()
        for row in price_reasons.itertuples(index=False):
            coverage_missing_rows.append({"coverage_group": group_name, "missing_layer": "price", "feature": "", "reason": row.reason, "member_sessions": int(row.size)})
        for feature in FEATURES:
            reason_col = f"feature_exclusion_reason__{feature}"
            reasons = psubset.assign(reason=psubset[reason_col].fillna("eligible")).groupby("reason", as_index=False).size()
            for row in reasons.itertuples(index=False):
                coverage_missing_rows.append({"coverage_group": group_name, "missing_layer": "feature", "feature": feature, "reason": row.reason, "member_sessions": int(row.size)})
    coverage_ic = pd.DataFrame(coverage_ic_rows)
    coverage_quantile = pd.DataFrame(coverage_quantile_rows)
    coverage_missing = pd.DataFrame(coverage_missing_rows)
    store.csv("coverage_missingness_ic.csv", coverage_ic, ["coverage_group", "feature", "horizon_sessions"])
    store.csv("coverage_missingness_quantiles.csv", coverage_quantile, ["coverage_group", "feature", "horizon_sessions", "quantile"])
    store.csv("coverage_missing_reason_distribution.csv", coverage_missing, ["coverage_group", "missing_layer", "feature", "reason"])

    exit_ic_rows: list[dict[str, Any]] = []
    exit_quantile_rows: list[dict[str, Any]] = []
    window = int(analysis["exit_before_after_window_sessions"])
    for isin in EXIT_ISINS:
        exposure_dates = sorted(panel.loc[panel["isin"].eq(isin) & panel["is_unresolved_exit_member"], "session_date"].unique())
        if not exposure_dates:
            continue
        start_idx = date_index[exposure_dates[0]]
        end_idx = date_index[exposure_dates[-1]]
        exit_periods = {
            "before_20_sessions": set(master_dates[max(0, start_idx - window):start_idx]),
            "during_official_member_exposure": set(exposure_dates),
            "after_20_sessions": set(master_dates[end_idx + 1:min(len(master_dates), end_idx + 1 + window)]),
        }
        for period, dates in exit_periods.items():
            subset = rank_ic.loc[rank_ic["session_date"].isin(dates)]
            for (feature, horizon), group in subset.groupby(["feature", "horizon_sessions"], sort=True):
                exit_ic_rows.append(
                    {
                        "exit_isin": isin,
                        "period": period,
                        "feature": feature,
                        "horizon_sessions": int(horizon),
                        "sessions": int(group["rank_ic"].notna().sum()),
                        "constituent_observations": int(group["label_usable_count"].sum()),
                        "mean_rank_ic": float(group["rank_ic"].mean()),
                        "median_rank_ic": float(group["rank_ic"].median()),
                        "positive_share": float((group["rank_ic"].dropna() > 0).mean()),
                        "official_member_count": 60,
                        "price_usable_count_mean": float(group["price_usable_member_count"].mean()),
                        "feature_eligible_count_mean": float(group["feature_usable_member_count"].mean()),
                        "label_eligible_count_mean": float(group["label_usable_count"].mean()),
                    }
                )
            qsubset = quantile_returns.loc[quantile_returns["session_date"].isin(dates)]
            for (feature, horizon, quantile), group in qsubset.groupby(["feature", "horizon_sessions", "quantile"], sort=True):
                valid = group.loc[group["quantile_count"] > 0]
                exit_quantile_rows.append(
                    {
                        "exit_isin": isin,
                        "period": period,
                        "feature": feature,
                        "horizon_sessions": int(horizon),
                        "quantile": int(quantile),
                        "sessions": len(valid),
                        "constituent_observations": int(valid["quantile_count"].sum()),
                        "mean_diagnostic_gross_return": float(valid["mean_forward_return"].mean()),
                        "minimum_cell_count": int(valid["quantile_count"].min()) if len(valid) else 0,
                        "official_member_count": 60,
                        "price_usable_count_mean": float(valid["price_usable_member_count"].mean()),
                        "feature_eligible_count_mean": float(valid["feature_usable_member_count"].mean()),
                        "label_eligible_count_mean": float(valid["label_usable_count"].mean()),
                    }
                )
    exit_ic = pd.DataFrame(exit_ic_rows)
    exit_quantile = pd.DataFrame(exit_quantile_rows)
    store.csv("membership_change_exit_ic.csv", exit_ic, ["exit_isin", "period", "feature", "horizon_sessions"])
    store.csv("membership_change_exit_quantiles.csv", exit_quantile, ["exit_isin", "period", "feature", "horizon_sessions", "quantile"])

    # Missingness relationship with market conditions and observable outcomes.
    wig_series = wig.set_index("session_date")["close"].sort_index()
    market_rows = []
    for horizon in horizons:
        wig_forward = wig_series.shift(-horizon) / wig_series - 1.0
        temp = date_meta.copy()
        temp["missing_member_count"] = 60 - temp["price_usable_member_count"]
        temp["wig_forward_return"] = temp["session_date"].map(wig_forward)
        valid = temp.dropna(subset=["wig_forward_return"])
        market_rows.append(
            {
                "horizon_sessions": horizon,
                "sessions": len(valid),
                "correlation_missing_count_with_wig_forward_return": pearson_closed_form(
                    valid["missing_member_count"].to_numpy(float), valid["wig_forward_return"].to_numpy(float)
                ),
                "mean_wig_forward_return_full_coverage": float(valid.loc[valid["missing_member_count"].eq(0), "wig_forward_return"].mean()),
                "mean_wig_forward_return_incomplete_coverage": float(valid.loc[valid["missing_member_count"].gt(0), "wig_forward_return"].mean()),
                "positive_wig_trend_share_full_coverage": float(valid.loc[valid["missing_member_count"].eq(0), "wig_trend_regime"].eq("positive").mean()),
                "positive_wig_trend_share_incomplete_coverage": float(valid.loc[valid["missing_member_count"].gt(0), "wig_trend_regime"].eq("positive").mean()),
            }
        )
    missing_observable_rows = []
    for feature in FEATURES:
        eligible_col = f"is_feature_eligible__{feature}"
        for horizon in horizons:
            label_col = LABELS[horizon]
            observable = panel.loc[panel[label_col].notna()].copy()
            for state, group in observable.groupby(eligible_col):
                missing_observable_rows.append(
                    {
                        "feature": feature,
                        "horizon_sessions": horizon,
                        "feature_eligible": bool(state),
                        "security_date_observations": len(group),
                        "sessions": int(group["session_date"].nunique()),
                        "mean_observable_forward_return": float(group[label_col].mean()),
                        "median_observable_forward_return": float(group[label_col].median()),
                        "q05_observable_forward_return": float(group[label_col].quantile(0.05)),
                        "q95_observable_forward_return": float(group[label_col].quantile(0.95)),
                    }
                )
    store.csv("missingness_market_relationship.csv", pd.DataFrame(market_rows), ["horizon_sessions"])
    store.csv("feature_missing_observable_outcomes.csv", pd.DataFrame(missing_observable_rows), ["feature", "horizon_sessions", "feature_eligible"])

    # Declared multiple-testing families in one retained table.
    family_tables = []
    family_tables.append(ic_summary[["family", "feature", "horizon_sessions", "mean", "hac_normal_p_value", "benjamini_hochberg_q_value"]].assign(method="rank_ic", definition="trusted_label"))
    family_tables.append(trend_partial.loc[positive_mask, ["family", "horizon_sessions", "mean", "hac_normal_p_value", "benjamini_hochberg_q_value"]].assign(feature="return_5__v1", method="partial_rank_ic", definition="positive_wig_trend"))
    family_tables.append(proximity_tests[["family", "horizon_sessions", "mean", "hac_normal_p_value", "benjamini_hochberg_q_value", "method", "definition"]].assign(feature="proximity_to_high"))
    family_tables.append(anchor_comparison[["family", "feature", "horizon_sessions", "mean", "hac_normal_p_value", "benjamini_hochberg_q_value", "anchor"]].rename(columns={"anchor": "definition"}).assign(method="rank_ic"))
    testing_families = pd.concat(family_tables, ignore_index=True, sort=False)
    testing_families["rejected_at_fdr_0_05"] = testing_families["benjamini_hochberg_q_value"].le(0.05)
    store.csv("multiple_testing_families.csv", testing_families, ["family", "feature", "definition", "method", "horizon_sessions"])

    # Data-quality evidence and explicit unresolved items.
    adjustment_states = bars[["adjustment_state", "adjustment_version"]].drop_duplicates()
    data_quality = pd.DataFrame(
        [
            {"issue": "official_universe_denominator", "status": "passed", "evidence": "60 members on every one of 1,272 decision sessions"},
            {"issue": "duplicate_member_session_keys", "status": "passed", "evidence": str(int(panel.duplicated(["session_date", "security_id"]).sum()))},
            {"issue": "duplicate_validated_bar_keys", "status": "passed", "evidence": str(int(bars.duplicated(["session_date", "security_id"]).sum()))},
            {"issue": "phase_a_archive_integrity", "status": "passed", "evidence": "30 manifest artifacts; physical/logical hashes and source snapshot validated"},
            {"issue": "phase_a_reproduction", "status": "passed", "evidence": str(Path(cfg["trusted_reproduction_report"]))},
            {"issue": "price_adjustment_semantics", "status": "unresolved", "evidence": adjustment_states.to_json(orient="records")},
            {"issue": "five_benign_exit_vendor_series", "status": "unresolved", "evidence": "five official-member identities have no validated local Stooq mapping; no bars synthesized"},
            {"issue": "alternative_open_execution_precision", "status": "unresolved", "evidence": "daily open observations do not establish auction availability, fillability, or exact execution timing"},
            {"issue": "survivorship_and_membership", "status": "partially_mitigated", "evidence": "validity-dated official snapshots retained; snapshot interval assumptions and source completeness remain limitations"},
            {"issue": "ticker_issuer_continuity", "status": "partially_mitigated", "evidence": "UUIDv5 security_id over official ISIN and validity-dated aliases; unresolved mappings retained"},
        ]
    )
    store.csv("data_quality_risk_register.csv", data_quality, ["issue"])

    # Figure rendering is deliberately omitted: a two-point isolated matplotlib
    # smoke test terminates in this pinned environment's native NumPy stack.
    # The tables retain every plotted value and all sample sizes.
    figure_note = run_dir / "figures" / "README.txt"
    figure_note.write_text(
        "PNG rendering omitted. In the pinned ats-stack-research environment, a minimal two-point "
        "matplotlib Agg savefig call exits with Windows status -1066598273. No package or environment "
        "was changed. Use tables/rolling_ic_252.csv, tables/quantile_results_by_period.csv, and "
        "tables/coverage_missingness_ic.csv; all retain sample sizes.\n",
        encoding="utf-8",
    )
    store._record(figure_note, "text", None, sha256_file(figure_note))

    # Environment, inputs, metrics, and validation evidence.
    store.copy(artifacts / "environment_lock.json", "environment_lock.json", "json")
    input_hashes = {
        "trusted_phase_a_run_id": cfg["trusted_phase_a_run_id"],
        "trusted_manifest_sha256": sha256_file(trusted_run / "manifest.json"),
        "trusted_manifest_logical_hash": trusted_manifest["manifest_logical_hash"],
        "trusted_artifact_hashes": trusted_hashes_before,
        "trusted_source_file_hashes": trusted_manifest["source_file_hashes"],
        "trusted_code_file_hashes": trusted_manifest["code_file_hashes"],
        "trusted_reproduction_report_sha256": sha256_file(Path(cfg["trusted_reproduction_report"])),
        "architecture_document_hashes": {
            path.name: sha256_file(path)
            for path in sorted(Path(cfg["architecture_root"]).glob("*.md"))
        },
    }
    store.json("input_hashes.json", input_hashes)

    momentum_summary = ic_summary.loc[ic_summary["feature"].eq("momentum_12_1__v1")].sort_values("horizon_sessions")
    metrics = {
        "analysis_name": cfg["analysis_name"],
        "analysis_version": cfg["analysis_version"],
        "trusted_phase_a_run_id": cfg["trusted_phase_a_run_id"],
        "phase_a_git_commit": cfg["phase_a_commit"],
        "sessions": int(panel["session_date"].nunique()),
        "official_member_rows": len(panel),
        "official_member_count_min": int(panel["official_member_count"].min()),
        "official_member_count_max": int(panel["official_member_count"].max()),
        "price_usable_count_min": int(panel["price_usable_member_count"].min()),
        "price_usable_count_max": int(panel["price_usable_member_count"].max()),
        "sessions_full_price_coverage": int(date_meta["price_usable_member_count"].eq(60).sum()),
        "sessions_below_full_price_coverage": int(date_meta["price_usable_member_count"].lt(60).sum()),
        "momentum_rank_ic": momentum_summary[["horizon_sessions", "sessions", "mean", "median", "hac_ci_low", "hac_ci_high", "bootstrap_ci_low", "bootstrap_ci_high", "benjamini_hochberg_q_value", "effective_sessions_hac"]].to_dict("records"),
        "confirmatory_tests_rejected_fdr_0_05": int(ic_summary["benjamini_hochberg_q_value"].le(0.05).sum()),
        "trend_positive_tests_rejected_fdr_0_05": int(trend_partial.loc[positive_mask, "benjamini_hochberg_q_value"].le(0.05).sum()),
        "proximity_tests_rejected_fdr_0_05": int(proximity_tests["benjamini_hochberg_q_value"].le(0.05).sum()),
        "alternative_anchor_tests_rejected_fdr_0_05": int(anchor_comparison["benjamini_hochberg_q_value"].le(0.05).sum()),
        "research_disclaimer": "All returns are diagnostic gross outcomes, not executable portfolio returns or evidence of deployable alpha.",
    }
    store.json("metrics.json", metrics)

    validation_report = {
        "passed": True,
        "phase_a_tests": commands[0],
        "phase_a_archive_validation": commands[1],
        "trusted_reproduction_report_passed": bool(reproduction["passed"]),
        "trusted_reproduction_report": reproduction,
        "official_denominator_check": True,
        "feature_denominator_checks": True,
        "label_denominator_checks": True,
        "excluded_member_state_checks": True,
        "trusted_label_reconstruction_check": True,
        "proximity_prior_close_alignment_check": True,
        "current_checkout_code_mismatches_vs_phase_a_snapshot": current_code_mismatches,
        "current_checkout_note": "Pre-existing or concurrent Phase B edits are listed explicitly in current_checkout_code_mismatches_vs_phase_a_snapshot; validation from the archived Phase A source passes. No checkout file was changed by this run.",
        "package_versions": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyarrow": pa.__version__,
            "scipy": scipy.__version__,
            "matplotlib": matplotlib.__version__,
        },
    }
    store.json("validation_report.json", validation_report)
    for log in (run_dir / "logs").glob("*.txt"):
        store._record(log, "text", None, sha256_file(log))

    source_snapshot = run_dir / "source_snapshot.zip"
    create_source_snapshot(source_root, source_snapshot)
    store._record(source_snapshot, "zip", None, sha256_file(source_snapshot))

    commands_text = "\n".join(
        [
            f"{item['command']}  # exit {item['exit_code']}" for item in commands
        ]
        + [f"{subprocess.list2cmdline([python, str(Path(__file__).resolve()), '--config', str(config_path), '--run-id', args.run_id])}  # current command"]
    ) + "\n"
    (run_dir / "logs" / "commands.txt").write_text(commands_text, encoding="utf-8")
    store._record(run_dir / "logs" / "commands.txt", "text", None, sha256_file(run_dir / "logs" / "commands.txt"))

    trusted_hashes_after = {relative: sha256_file(trusted_run / relative) for relative in expected_outputs}
    if trusted_hashes_after != trusted_hashes_before:
        raise RuntimeError("trusted Phase A run changed during diagnostics")

    manifest = {
        "run_id": args.run_id,
        "analysis_name": cfg["analysis_name"],
        "analysis_version": cfg["analysis_version"],
        "trusted_phase_a_run_id": cfg["trusted_phase_a_run_id"],
        "trusted_phase_a_manifest_logical_hash": trusted_manifest["manifest_logical_hash"],
        "phase_a_git_commit": cfg["phase_a_commit"],
        "logical_dataset_version": trusted_manifest["logical_dataset_version"],
        "universe_version": trusted_manifest["universe_version"],
        "schema_version": trusted_manifest["schema_version"],
        "feature_definitions": trusted_manifest["feature_definitions"],
        "label_definitions": trusted_manifest["label_definitions"],
        "timestamp_semantics": trusted_manifest["timestamp_semantics"],
        "analysis_plan_sha256": sha256_file(run_dir / "analysis_plan.md"),
        "configuration_sha256": sha256_file(run_dir / "config.yaml"),
        "environment_lock_sha256": sha256_file(run_dir / "environment_lock.json"),
        "source_snapshot_sha256": sha256_file(source_snapshot),
        "artifact_hashes": store.records,
        "table_logical_hashes": {path: record["logical_hash"] for path, record in store.records.items() if path.startswith("tables/")},
        "protected_input_immutability": {
            "trusted_phase_a_hashes_unchanged_during_run": True,
            "shared_checkout_writes": [],
            "authorized_write_roots": [str(source_root), str(output_root.parent)],
        },
    }
    stable_manifest = dict(manifest)
    manifest["manifest_logical_hash"] = canonical_hash(stable_manifest)
    write_json(run_dir / "manifest.json", manifest)

    # Final internal manifest check.
    for relative, record in manifest["artifact_hashes"].items():
        if sha256_file(run_dir / relative) != record["sha256"]:
            raise RuntimeError(f"post-write artifact hash mismatch: {relative}")
    print(json.dumps({"run_id": args.run_id, "run_dir": str(run_dir), "tables": sum(p.startswith('tables/') for p in store.records), "manifest_logical_hash": manifest["manifest_logical_hash"], "passed": True}, indent=2))


if __name__ == "__main__":
    main()
