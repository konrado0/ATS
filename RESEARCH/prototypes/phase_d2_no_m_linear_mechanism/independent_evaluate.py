from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from pathlib import Path

import numpy as np
import pandas as pd


PRIMARY = Path("D:/Stock/data/ATS/phase_d_ml/mechanism_runs/phase-d2-no-m-linear-mechanism-20260903-v1")
REPRO = Path("D:/Stock/data/ATS/phase_d_ml/mechanism_runs/phase-d2-no-m-linear-mechanism-20260903-v1-reproduction")
SOURCE = Path("D:/Stock/data/ATS/phase_d_ml/evaluation_runs/phase-d2-evaluation-20260902-v6")
ROOT = Path("D:/Stock/data/ATS/phase_d_ml/mechanism_reproductions")
RUN_ID = "phase-d2-no-m-linear-mechanism-independent-20260903-v1"
CELLS = ("C_LINEAR", "C_LIGHTGBM", "RICH_NO_M_LINEAR", "RICH_NO_M_LIGHTGBM")
BLOCK_MAP = {
    "MODEL_SELECTION_2023_H1": "RETRO_2023_H1", "MODEL_SELECTION_2023_H2": "RETRO_2023_H2",
    "DEVELOPMENT_2024_H1": "RETRO_2024_H1", "DEVELOPMENT_2024_H2": "RETRO_2024_H2",
    "LOCKED_2025_H1": "RETRO_2025_H1", "LOCKED_2025_H2": "RETRO_2025_H2", "LOCKED_2026_H1": "RETRO_2026_H1",
}
CONTRASTS = {
    "RIDGE_REPRESENTATION": ("RICH_NO_M_LINEAR", "C_LINEAR"),
    "NONLINEAR_INCREMENT": ("RICH_NO_M_LIGHTGBM", "RICH_NO_M_LINEAR"),
    "RIDGE_VS_C_LINEAR": ("RICH_NO_M_LINEAR", "C_LINEAR"),
    "RIDGE_VS_C_LIGHTGBM": ("RICH_NO_M_LINEAR", "C_LIGHTGBM"),
    "LIGHTGBM_VS_C_LINEAR": ("RICH_NO_M_LIGHTGBM", "C_LINEAR"),
    "LIGHTGBM_VS_C_LIGHTGBM": ("RICH_NO_M_LIGHTGBM", "C_LIGHTGBM"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def verify_manifest(root: Path) -> dict:
    value = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for name, record in value["files"].items():
        path = root / name
        if not path.is_file() or path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]:
            raise ValueError(f"manifest mismatch: {path}")
    return value


def spearman(score, outcome) -> float:
    frame = pd.DataFrame({"score": score, "outcome": outcome}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 45 or frame.score.nunique() < 2 or frame.outcome.nunique() < 2:
        return math.nan
    return float(frame.score.rank(method="average").corr(frame.outcome.rank(method="average")))


def bootstrap_indices(n: int) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(20260831))
    starts = rng.integers(0, n, size=(5000, math.ceil(n / 20)))
    return ((starts[:, :, None] + np.arange(20)) % n).reshape(5000, -1)[:, :n]


def interval(values: np.ndarray, indices: np.ndarray) -> dict:
    estimates = np.nanmean(values[indices], axis=1)
    defined = np.isfinite(estimates)
    fraction = float(defined.mean())
    if fraction < 0.99:
        return {"status": "NOT PROVEN", "defined_fraction": fraction, "lower": None, "upper": None}
    return {"status": "PASS", "defined_fraction": fraction, "lower": float(np.quantile(estimates[defined], 0.025, method="linear")), "upper": float(np.quantile(estimates[defined], 0.975, method="linear"))}


def session_table(wide: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (population, session), group in wide.groupby(["population", "decision_session"], sort=True):
        row = {"population": population, "decision_session": session, "semantic_rows": len(group), "outcome_rows": int(np.isfinite(group.outcome).sum())}
        for cell in CELLS:
            row[f"ic__{cell}"] = spearman(group[f"score__{cell}"], group.outcome)
        for name, (candidate, comparator) in CONTRASTS.items():
            row[f"delta__{name}"] = row[f"ic__{candidate}"] - row[f"ic__{comparator}"]
        rows.append(row)
    return pd.DataFrame(rows).sort_values("decision_session", kind="mergesort").reset_index(drop=True)


def leave_security(wide: pd.DataFrame, sessions: pd.DataFrame) -> dict:
    baseline = {name: float(sessions[f"delta__{name}"].mean()) for name in CONTRASTS}
    sums = {name: float(sessions[f"delta__{name}"].sum()) for name in CONTRASTS}
    counts = {name: int(sessions[f"delta__{name}"].notna().sum()) for name in CONTRASTS}
    by_session = sessions.set_index("decision_session")
    securities = sorted(wide.security_id.astype(str).unique())
    reduced = {security: dict(sums) for security in securities}
    reduced_counts = {security: dict(counts) for security in securities}
    for session, group in wide.groupby("decision_session", sort=True):
        ids, outcome = group.security_id.astype(str).to_numpy(), group.outcome.to_numpy(float)
        scores = {cell: group[f"score__{cell}"].to_numpy(float) for cell in CELLS}
        for position, security in enumerate(ids):
            keep = np.arange(len(group)) != position
            cell_ic = {cell: spearman(value[keep], outcome[keep]) for cell, value in scores.items()}
            for name, (candidate, comparator) in CONTRASTS.items():
                original = float(by_session.at[session, f"delta__{name}"])
                if np.isfinite(original):
                    reduced[security][name] -= original; reduced_counts[security][name] -= 1
                value = cell_ic[candidate] - cell_ic[comparator]
                if np.isfinite(value):
                    reduced[security][name] += value; reduced_counts[security][name] += 1
    output = {}
    for name in CONTRASTS:
        leave = {security: reduced[security][name] / reduced_counts[security][name] for security in securities if reduced_counts[security][name]}
        decreases = {security: baseline[name] - value for security, value in leave.items()}
        maximum = max(decreases.values())
        boundary = sorted(security for security, value in decreases.items() if value == maximum)
        positive = {security: max(value, 0.0) for security, value in decreases.items()}; total = sum(positive.values())
        output[name] = {"baseline_mean_delta": baseline[name], "largest_contributor_boundary_set": boundary, "leave_boundary_security_out": {security: leave[security] for security in boundary}, "largest_positive_contribution_share": max(positive.values()) / total if total > 0 else None}
    return output


def calculate() -> tuple[dict, pd.DataFrame]:
    primary_manifest, reproduction_manifest = verify_manifest(PRIMARY), verify_manifest(REPRO)
    if sha(PRIMARY / "predictions.parquet") != sha(REPRO / "predictions.parquet"):
        raise ValueError("prediction reproduction is not byte-identical")
    predictions = pd.read_parquet(PRIMARY / "predictions.parquet")
    if set(predictions.cell_id) != set(CELLS) or set(predictions.block_id) != set(BLOCK_MAP):
        raise ValueError("unexpected cells or blocks")
    keys = ["block_id", "security_id", "decision_session"]
    wide = predictions.pivot(index=keys, columns="cell_id", values="model_score").add_prefix("score__").reset_index()
    outcomes = []
    for stage in ("stage2a", "stage2b", "stage2c"):
        verify_manifest(SOURCE / stage); outcomes.append(pd.read_parquet(SOURCE / stage / "outcomes.parquet"))
    labels = pd.concat(outcomes, ignore_index=True).drop_duplicates(keys)[keys + ["label__open_to_open__20"]].rename(columns={"label__open_to_open__20": "outcome"})
    wide = wide.merge(labels, on=keys, how="left", validate="one_to_one")
    wide["population"] = wide.block_id.map(BLOCK_MAP)
    sessions = session_table(wide)
    indices, influence = bootstrap_indices(len(sessions)), leave_security(wide, sessions)
    results, gates = {}, {}
    for name, (candidate, comparator) in CONTRASTS.items():
        values = sessions[f"delta__{name}"]
        half = {population: float(sessions.loc[sessions.population.eq(population), f"delta__{name}"].mean()) for population in BLOCK_MAP.values()}
        positive = sessions.assign(positive=values.clip(lower=0)).groupby("population").positive.sum(); total = float(positive.sum())
        half_share = float(positive.max() / total) if total > 0 else None
        leave_half = {population: float(sessions.loc[sessions.population.ne(population), f"delta__{name}"].mean()) for population in BLOCK_MAP.values()}
        security = influence[name]
        checks = {"pooled_mean_gt_0_005": float(values.mean()) > .005, "positive_half_years_at_least_5": sum(value > 0 for value in half.values()) >= 5, "median_half_year_positive": float(np.median(list(half.values()))) > 0, "all_leave_half_year_out_positive": all(value > 0 for value in leave_half.values()), "all_tied_largest_security_out_positive": all(value > 0 for value in security["leave_boundary_security_out"].values()), "security_positive_share_below_0_50": security["largest_positive_contribution_share"] is not None and security["largest_positive_contribution_share"] < .5, "half_year_positive_share_below_0_50": half_share is not None and half_share < .5}
        gates[name] = all(checks.values())
        results[name] = {"candidate": candidate, "comparator": comparator, "pooled_mean_delta": float(values.mean()), "pooled_median_delta": float(values.median()), "half_year_mean_deltas": half, "median_half_year_mean_delta": float(np.median(list(half.values()))), "positive_half_year_count": sum(value > 0 for value in half.values()), "positive_session_count": int(values.gt(0).sum()), "positive_session_fraction": float(values.gt(0).sum() / values.notna().sum()), "moving_block_95_interval": interval(values.to_numpy(float), indices), "leave_one_half_year_out": leave_half, "leave_largest_contributing_security_out": security["leave_boundary_security_out"], "largest_contributing_security_boundary_set": security["largest_contributor_boundary_set"], "largest_positive_contribution_share_by_security": security["largest_positive_contribution_share"], "largest_positive_contribution_share_by_half_year": half_share, "broad_increment_checks": checks, "broad_increment": "PASS" if gates[name] else "FAIL"}
    ridge_both = gates["RIDGE_VS_C_LINEAR"] and gates["RIDGE_VS_C_LIGHTGBM"]
    nonlinear = gates["NONLINEAR_INCREMENT"]
    lightgbm = all(results[name]["pooled_mean_delta"] > 0 and results[name]["positive_half_year_count"] >= 4 for name in ("LIGHTGBM_VS_C_LINEAR", "LIGHTGBM_VS_C_LIGHTGBM"))
    verdict = "REPRESENTATION ROBUST — RIDGE SUFFICIENT" if ridge_both and not nonlinear else "REPRESENTATION ROBUST — NONLINEARITY ADDS" if ridge_both and nonlinear else "NONLINEARITY-DEPENDENT — WEAK" if not ridge_both and nonlinear and lightgbm else "NOT ROBUST"
    return {"contrasts": results, "scientific_verdict_if_all_integrity_checks_pass": verdict}, sessions


def main() -> None:
    destination = ROOT / RUN_ID
    if destination.exists():
        raise ValueError(f"immutable independent run exists: {destination}")
    stage = ROOT / f".stage-{RUN_ID}-{uuid.uuid4().hex}"; stage.mkdir(parents=True)
    try:
        core, sessions = calculate()
        results = {"schema_version": "ats.phase_d2_nm_linear_mechanism.independent.v1", "decision_core": core, "decision_core_hash": canonical_hash(core), "imports_primary_metric_functions": False}
        (stage / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        sessions.to_parquet(stage / "per_session.parquet", index=False, compression="zstd", use_dictionary=False)
        files = {path.name: {"bytes": path.stat().st_size, "sha256": sha(path)} for path in stage.iterdir() if path.is_file()}
        logical = {"decision_core_hash": results["decision_core_hash"], "primary_prediction_sha256": sha(PRIMARY / "predictions.parquet"), "reproduction_prediction_sha256": sha(REPRO / "predictions.parquet")}
        manifest = {"schema_version": "ats.phase_d2_nm_linear_mechanism.independent_run.v1", "run_id": RUN_ID, "logical_hash": canonical_hash(logical), "logical_payload": logical, "files": files, "mutable_latest_pointer": False}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(stage, destination)
    except Exception:
        if stage.exists(): os.replace(stage, ROOT / stage.name.replace(".stage-", ".failed-", 1))
        raise
    print(json.dumps({"status": "PASS", "run_dir": str(destination), "decision_core_hash": results["decision_core_hash"]}, indent=2))


if __name__ == "__main__":
    main()

