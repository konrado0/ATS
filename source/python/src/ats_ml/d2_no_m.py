from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from ats_ml.contracts import REPOSITORY_ROOT
from ats_ml.d2_artifacts import (
    D2ArtifactError,
    frame_identity,
    publish_immutable,
    read_json,
    validate_manifest,
    write_json,
    write_parquet,
)
from ats_ml.d2_metrics import (
    bootstrap_vector,
    circular_bootstrap_indices,
    episode_anchor_flags,
    fractional_boundary_weights,
    spearman_ic,
    weighted_mean,
)
from ats_ml.models import LIGHTGBM_PARAMETERS
from ats_research.hashing import content_hash, sha256_file


CONTRACT_PATH = REPOSITORY_ROOT / "source/python/configs/phase_d2_no_m_followup.json"
PREDICTION_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/prediction_runs/phase-d2-predictions-20260902-v4")
EVALUATION_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/evaluation_runs/phase-d2-evaluation-20260902-v6")
OUTPUT_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/followup_runs")
RUN_ID = "phase-d2-nm-followup-20260903-v1"
SCHEMA = "ats.phase_d2_nm.followup_run.v1"
COMPARATORS = ("C_LINEAR", "C_LIGHTGBM")
NO_M = "RICH_NO_M_LIGHTGBM"
FULL_RICH = "RICH_LIGHTGBM"
CELLS = (*COMPARATORS, NO_M, FULL_RICH)
BLOCK_MAP = {
    "MODEL_SELECTION_2023_H1": "RETRO_2023_H1",
    "MODEL_SELECTION_2023_H2": "RETRO_2023_H2",
    "DEVELOPMENT_2024_H1": "RETRO_2024_H1",
    "DEVELOPMENT_2024_H2": "RETRO_2024_H2",
    "LOCKED_2025_H1": "RETRO_2025_H1",
    "LOCKED_2025_H2": "RETRO_2025_H2",
    "LOCKED_2026_H1": "RETRO_2026_H1",
}


def _finite_mean(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    return float(np.nanmean(array)) if np.isfinite(array).any() else math.nan


def _finite_median(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    return float(np.nanmedian(array)) if np.isfinite(array).any() else math.nan


def load_contract() -> dict[str, Any]:
    contract = read_json(CONTRACT_PATH)
    if contract.get("schema_version") != "ats.phase_d2_nm.followup.v1":
        raise D2ArtifactError("unexpected Phase D2-NM contract schema")
    if contract.get("contract_id") != "phase-d2-nm-followup-20260903-v1":
        raise D2ArtifactError("unexpected Phase D2-NM contract ID")
    return contract


def _manifest_file_check(run_dir: Path) -> dict[str, Any]:
    manifest = read_json(run_dir / "manifest.json")
    for relative, record in manifest.get("files", {}).items():
        path = run_dir / relative
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha256_file(path) != record.get("sha256"):
            raise D2ArtifactError(f"accepted artifact hash mismatch: {path}")
    return manifest


def verify_scientific_object() -> dict[str, Any]:
    contract = load_contract()
    if sha256_file(REPOSITORY_ROOT / "source/python/configs/phase_d0_feature_registry.json") != contract["accepted_inputs"]["feature_registry_sha256"]:
        raise D2ArtifactError("feature-registry hash mismatch")
    manifest = _manifest_file_check(PREDICTION_ROOT)
    logical = manifest["logical_payload"]["prediction_identity"]
    if manifest.get("run_id") != contract["accepted_inputs"]["prediction_run_id"]:
        raise D2ArtifactError("accepted prediction run ID mismatch")
    if logical.get("logical_hash") != contract["accepted_inputs"]["prediction_table_logical_hash"]:
        raise D2ArtifactError("accepted prediction-table logical hash mismatch")
    derived = read_json(PREDICTION_ROOT / "derived_contract.json")
    expected_features = list(derived["cells"][NO_M]["feature_names"])
    if len(expected_features) != 18 or derived["cells"][NO_M].get("features") != "C+P+X":
        raise D2ArtifactError("accepted no-M feature allowlist is not exact C+P+X(18)")
    records = [row for row in read_json(PREDICTION_ROOT / "fit_calibration_audit.json")["records"] if row.get("cell_id") == NO_M]
    if len(records) != 8:
        raise D2ArtifactError("accepted no-M cell lacks one independent fit record per refit")
    record_proofs: list[dict[str, Any]] = []
    for row in sorted(records, key=lambda value: value["block_id"]):
        checks = {
            "feature_allowlist_exact": row.get("feature_names") == expected_features,
            "model_family_exact": row.get("model_family") == "LIGHTGBM",
            "model_parameters_exact": row.get("model_parameters") == LIGHTGBM_PARAMETERS,
            "three_calibration_blocks": len(row.get("inner", [])) == 3,
            "inner_estimators_recreated": all(item.get("estimator_recreated") is True for item in row.get("inner", [])),
            "inner_endpoint_purge": all(item.get("fit", {}).get("endpoint_strictly_before_boundary") is True for item in row.get("inner", [])),
            "final_endpoint_purge": row.get("final_fit", {}).get("endpoint_strictly_before_boundary") is True,
            "threshold_frozen_before_final_refit": row.get("threshold_frozen_before_final_refit") is True,
            "outer_outcomes_inaccessible": row.get("outer_outcomes_accessed") is False,
            "fit_and_score_rows_positive": row.get("final_fit", {}).get("rows", 0) > 0 and row.get("outer_score", {}).get("rows", 0) > 0,
            "prediction_hashes_present": bool(row.get("pooled_inner_score_hash")) and all(bool(item.get("score_values_hash")) for item in row.get("inner", [])),
        }
        if not all(checks.values()) or not np.isfinite(float(row.get("threshold", math.nan))):
            raise D2ArtifactError(f"accepted no-M independent-fit proof failed for {row.get('block_id')}")
        record_proofs.append({
            "block_id": row["block_id"],
            "feature_count": len(row["feature_names"]),
            "final_fit_rows": row["final_fit"]["rows"],
            "outer_score_rows": row["outer_score"]["rows"],
            "threshold": row["threshold"],
            "pooled_inner_score_hash": row["pooled_inner_score_hash"],
            "outer_score_semantic_row_hash": row["outer_score"]["semantic_row_hash"],
            "checks": checks,
        })
    predictions = pd.read_parquet(PREDICTION_ROOT / "predictions.parquet")
    counts = predictions.groupby(["block_id", "cell_id"]).size().unstack(fill_value=0)
    for block_id in BLOCK_MAP:
        values = counts.loc[block_id, list(CELLS)]
        if values.nunique() != 1:
            raise D2ArtifactError(f"paired prediction populations differ in {block_id}")
    validation = read_json(PREDICTION_ROOT / "validation.json")
    if validation.get("status") != "PASS" or validation.get("outcome_columns_absent") is not True:
        raise D2ArtifactError("accepted prediction validation is not a label-free PASS")
    return {
        "status": "PASS",
        "independently_fitted": True,
        "feature_registry_sha256": contract["accepted_inputs"]["feature_registry_sha256"],
        "prediction_run_id": manifest["run_id"],
        "prediction_table_logical_hash": logical["logical_hash"],
        "prediction_rows": logical["rows"],
        "no_m_features": expected_features,
        "no_m_refit_count": len(records),
        "records": record_proofs,
        "common_population_by_block": {block: int(counts.loc[block, NO_M]) for block in BLOCK_MAP},
        "stage1_validation": validation,
    }


def load_analysis_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    predictions = pd.read_parquet(PREDICTION_ROOT / "predictions.parquet")
    predictions = predictions.loc[predictions["cell_id"].isin(CELLS)].copy()
    masks = pd.read_parquet(PREDICTION_ROOT / "common_score_masks.parquet")
    labels = pd.concat([
        pd.read_parquet(EVALUATION_ROOT / "stage2a/outcomes.parquet"),
        pd.read_parquet(EVALUATION_ROOT / "stage2b/outcomes.parquet"),
        pd.read_parquet(EVALUATION_ROOT / "stage2c/outcomes.parquet"),
    ], ignore_index=True)
    labels = labels[["block_id", "security_id", "decision_session", "label_endpoint_session_20", "label_endpoint_ts_20", "label__open_to_open__20", "label_state_20"]]
    labels = labels.drop_duplicates(["block_id", "security_id", "decision_session"])
    return predictions, masks, labels


def build_wide(predictions: pd.DataFrame, masks: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    keys = ["block_id", "security_id", "decision_session"]
    selected = predictions.loc[predictions["block_id"].isin(BLOCK_MAP)].copy()
    pieces = []
    for value, prefix in (("model_score", "score"), ("threshold", "threshold"), ("candidate", "candidate")):
        pieces.append(selected.pivot(index=keys, columns="cell_id", values=value).add_prefix(f"{prefix}__"))
    wide = pieces[0].join(pieces[1:]).reset_index()
    mask_cols = keys + ["information_session", "decision_ts", "official_expected_count", "scored_count", "excluded_count", "model_exclusion_reason"]
    wide = wide.merge(masks[mask_cols], on=keys, how="left", validate="one_to_one")
    wide = wide.merge(labels, on=keys, how="left", validate="one_to_one")
    wide["population"] = wide["block_id"].map(BLOCK_MAP)
    if wide["population"].isna().any() or wide["official_expected_count"].ne(60).any():
        raise D2ArtifactError("historical population or official denominator mismatch")
    for cell in CELLS:
        if wide[f"score__{cell}"].isna().any() or (wide[f"candidate__{cell}"] != (wide[f"score__{cell}"] > wide[f"threshold__{cell}"])).any():
            raise D2ArtifactError(f"score or strict threshold mismatch for {cell}")
    return wide.sort_values(["decision_session", "security_id"], kind="mergesort").reset_index(drop=True)


def attach_episode_flags(wide: pd.DataFrame, predictions: pd.DataFrame, masks: pd.DataFrame, cell: str, name: str) -> pd.DataFrame:
    history = predictions.loc[predictions["cell_id"].eq(cell), ["security_id", "decision_session", "candidate"]]
    flags = episode_anchor_flags(history, sorted(masks["decision_session"].unique()))
    renamed = flags.rename(columns={"episode_anchor": f"anchor__{name}", "episode_number": f"episode__{name}"})
    return wide.merge(renamed[["security_id", "decision_session", f"anchor__{name}", f"episode__{name}"]], on=["security_id", "decision_session"], how="left", validate="one_to_one")


def session_ic_frame(wide: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (population, session), group in wide.groupby(["population", "decision_session"], sort=True):
        row: dict[str, Any] = {
            "population": population,
            "decision_session": session,
            "semantic_rows": len(group),
            "outcome_rows": int(np.isfinite(group["label__open_to_open__20"]).sum()),
            "distinct_securities": int(group["security_id"].nunique()),
        }
        for cell in CELLS:
            row[f"ic__{cell}"] = spearman_ic(group[f"score__{cell}"], group["label__open_to_open__20"])
        for other in (*COMPARATORS, FULL_RICH):
            row[f"delta__{other}"] = row[f"ic__{NO_M}"] - row[f"ic__{other}"]
        rows.append(row)
    result = pd.DataFrame(rows).sort_values("decision_session", kind="mergesort").reset_index(drop=True)
    for other in (*COMPARATORS, FULL_RICH):
        result[f"cumulative_delta__{other}"] = result[f"delta__{other}"].fillna(0.0).cumsum()
        result[f"cumulative_mean_delta__{other}"] = result[f"delta__{other}"].expanding().mean()
    return result


def tail_frame(wide: pd.DataFrame, *, cell: str, anchor_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    anchor_col = f"anchor__{anchor_name}"
    anchors = wide.loc[wide[anchor_col].fillna(False) & np.isfinite(wide["label__open_to_open__20"])].copy()
    rows: list[dict[str, Any]] = []
    for (population, session), group in wide.groupby(["population", "decision_session"], sort=True):
        eligible = group.loc[np.isfinite(group["label__open_to_open__20"])]
        selected = anchors.loc[anchors["decision_session"].eq(session)]
        row: dict[str, Any] = {"population": population, "decision_session": session, "anchor_count": len(selected)}
        if selected.empty or eligible.empty:
            for key in ("opportunity_mean", "opportunity_median", "eligible_mean", "minus_eligible", "severe_rate"):
                row[key] = math.nan
            for comparator in COMPARATORS:
                row[f"matched_mean__{comparator}"] = math.nan
                row[f"minus__{comparator}"] = math.nan
                row[f"severe_difference__{comparator}"] = math.nan
        else:
            outcomes = selected["label__open_to_open__20"].to_numpy(float)
            eligible_outcomes = eligible["label__open_to_open__20"].to_numpy(float)
            row["opportunity_mean"] = float(outcomes.mean())
            row["opportunity_median"] = float(np.median(outcomes))
            row["eligible_mean"] = float(eligible_outcomes.mean())
            row["minus_eligible"] = row["opportunity_mean"] - row["eligible_mean"]
            row["severe_rate"] = float((outcomes <= -0.10).mean())
            for comparator in COMPARATORS:
                weights = fractional_boundary_weights(eligible[f"score__{comparator}"], len(selected))
                matched = weighted_mean(eligible_outcomes, weights)
                severe = weighted_mean((eligible_outcomes <= -0.10).astype(float), weights)
                row[f"matched_mean__{comparator}"] = matched
                row[f"minus__{comparator}"] = row["opportunity_mean"] - matched
                row[f"severe_difference__{comparator}"] = row["severe_rate"] - severe
        rows.append(row)
    return pd.DataFrame(rows), anchors


def _interval(values: pd.Series) -> dict[str, Any]:
    indices = circular_bootstrap_indices(len(values))
    return bootstrap_vector(values.to_numpy(float), indices)


def rank_summary(ic: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {}
    groups = [(name, ic.loc[ic["population"].eq(name)]) for name in BLOCK_MAP.values()]
    groups.append(("RETRO_2023_2026_H1", ic))
    for name, group in groups:
        row: dict[str, Any] = {
            "sessions": len(group),
            "semantic_rows": int(group["semantic_rows"].sum()),
            "outcome_rows": int(group["outcome_rows"].sum()),
            "distinct_security_session_min": int(group["distinct_securities"].min()),
            "mean_ic": {cell: _finite_mean(group[f"ic__{cell}"]) for cell in CELLS},
            "median_ic": {cell: _finite_median(group[f"ic__{cell}"]) for cell in CELLS},
            "defined_sessions": {cell: int(group[f"ic__{cell}"].notna().sum()) for cell in CELLS},
            "ic_interval": {cell: _interval(group[f"ic__{cell}"]) for cell in CELLS},
            "paired": {},
        }
        for other in (*COMPARATORS, FULL_RICH):
            values = group[f"delta__{other}"]
            row["paired"][other] = {
                "mean": _finite_mean(values), "median": _finite_median(values),
                "positive_sessions": int(values.gt(0).sum()),
                "positive_fraction": float(values.gt(0).sum() / values.notna().sum()) if values.notna().any() else None,
                "interval": _interval(values),
            }
        result[name] = row
    pooled = result["RETRO_2023_2026_H1"]
    pooled["leave_half_year_out"] = {
        omitted: {other: _finite_mean(ic.loc[ic["population"].ne(omitted), f"delta__{other}"]) for other in COMPARATORS}
        for omitted in BLOCK_MAP.values()
    }
    return result


def tail_summary(wide: pd.DataFrame, tail: pd.DataFrame, anchors: pd.DataFrame, *, cell: str, anchor_name: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    populations = [*BLOCK_MAP.values(), "RETRO_2023_2026_H1"]
    for name in populations:
        group = wide if name.endswith("H1") and name == "RETRO_2023_2026_H1" else wide.loc[wide["population"].eq(name)]
        t = tail if name == "RETRO_2023_2026_H1" else tail.loc[tail["population"].eq(name)]
        a = anchors if name == "RETRO_2023_2026_H1" else anchors.loc[anchors["population"].eq(name)]
        counts = group.groupby("decision_session")[f"candidate__{cell}"].sum()
        candidate_rows = int(group[f"candidate__{cell}"].sum())
        result[name] = {
            "scored_rows": len(group), "sessions": int(group["decision_session"].nunique()),
            "candidate_rows": candidate_rows, "candidate_row_fraction": float(group[f"candidate__{cell}"].mean()),
            "opportunity_sessions": int(counts.gt(0).sum()), "opportunity_session_fraction": float(counts.gt(0).mean()),
            "idle_sessions": int(counts.eq(0).sum()), "idle_session_fraction": float(counts.eq(0).mean()),
            "effective_episodes": len(a), "represented_securities": int(a["security_id"].nunique()),
            "episode_mean_outcome": _finite_mean(a["label__open_to_open__20"]),
            "episode_median_outcome": _finite_median(a["label__open_to_open__20"]),
            "severe_outcome_frequency": float(a["label__open_to_open__20"].le(-0.10).mean()) if len(a) else None,
            "minus_eligible": _finite_mean(t["minus_eligible"]),
            "minus_comparator": {other: _finite_mean(t[f"minus__{other}"]) for other in COMPARATORS},
            "severe_difference": {other: _finite_mean(t[f"severe_difference__{other}"]) for other in COMPARATORS},
            "intervals": {
                "minus_eligible": _interval(t["minus_eligible"]),
                **{f"minus__{other}": _interval(t[f"minus__{other}"]) for other in COMPARATORS},
            },
        }
    return result


def _shares(values: pd.Series) -> dict[str, Any]:
    positive = values.clip(lower=0.0).groupby(level=0).sum().sort_values(ascending=False)
    total = float(positive.sum())
    shares = positive / total if total > 0 else positive * 0.0
    return {
        "positive_total": total,
        "largest_share": float(shares.iloc[0]) if len(shares) else 0.0,
        "top5_share": float(shares.head(5).sum()) if len(shares) else 0.0,
        "hhi": float((shares**2).sum()) if len(shares) else 0.0,
        "largest_key": str(shares.index[0]) if len(shares) else None,
    }


def concentration_summary(wide: pd.DataFrame, ic: pd.DataFrame, tail: pd.DataFrame, anchors: pd.DataFrame) -> dict[str, Any]:
    eligible = tail.set_index("decision_session")["eligible_mean"]
    contribution = (anchors["label__open_to_open__20"] - anchors["decision_session"].map(eligible)).clip(lower=0.0)
    enriched = anchors.assign(positive_excess=contribution)
    security = _shares(enriched.set_index("security_id")["positive_excess"])
    session = _shares(enriched.set_index("decision_session")["positive_excess"])
    half_year = _shares(enriched.set_index("population")["positive_excess"])
    ordered_sessions = pd.DatetimeIndex(sorted(wide["decision_session"].unique()))
    session_excess = enriched.groupby("decision_session")["positive_excess"].sum().reindex(ordered_sessions, fill_value=0.0)
    rolling = session_excess.rolling(20, min_periods=1).sum()
    rolling_share = float(rolling.max() / session_excess.sum()) if session_excess.sum() > 0 else 0.0
    chunks = np.array_split(ordered_sessions.to_numpy(), 4)
    quartile = pd.Series({str(i + 1): float(enriched.loc[enriched["decision_session"].isin(chunk), "positive_excess"].sum()) for i, chunk in enumerate(chunks)})
    quartile_shares = quartile / quartile.sum() if quartile.sum() > 0 else quartile * 0.0
    rank_half_year: dict[str, Any] = {}
    for comparator in COMPARATORS:
        positive = ic.assign(value=ic[f"delta__{comparator}"].clip(lower=0.0)).groupby("population")["value"].sum()
        total = float(positive.sum())
        rank_half_year[comparator] = {
            "largest_positive_delta_share": float(positive.max() / total) if total > 0 else 0.0,
            "largest_half_year": str(positive.idxmax()) if len(positive) else None,
        }
    return {
        "security_positive_excess": security,
        "session_positive_excess": session,
        "half_year_positive_excess": half_year,
        "chronological_quartile_positive_excess_shares": {str(key): float(value) for key, value in quartile_shares.items()},
        "largest_chronological_quartile_share": float(quartile_shares.max()) if len(quartile_shares) else 0.0,
        "largest_rolling_20_session_positive_excess_share": rolling_share,
        "rank_half_year_positive_delta": rank_half_year,
    }


def episode_count_concentration(wide: pd.DataFrame, anchors: pd.DataFrame) -> dict[str, Any]:
    def measures(column: str) -> dict[str, float]:
        counts = anchors.groupby(column).size().astype(float).sort_values(ascending=False)
        shares = counts / counts.sum() if counts.sum() else counts
        return {
            "largest_share": float(shares.iloc[0]) if len(shares) else 0.0,
            "top5_share": float(shares.head(5).sum()) if len(shares) else 0.0,
            "hhi": float((shares**2).sum()) if len(shares) else 0.0,
        }
    sessions = pd.DatetimeIndex(sorted(wide["decision_session"].unique()))
    chunks = np.array_split(sessions.to_numpy(), 4)
    quartile_counts = [int(anchors["decision_session"].isin(chunk).sum()) for chunk in chunks]
    total = len(anchors)
    return {
        "episodes": total,
        "security": measures("security_id"),
        "session": measures("decision_session"),
        "half_year": measures("population"),
        "largest_chronological_quartile_share": max(quartile_counts) / total if total else 0.0,
    }


def contributor_influence(wide: pd.DataFrame, ic: pd.DataFrame) -> dict[str, Any]:
    baseline = {other: _finite_mean(ic[f"delta__{other}"]) for other in COMPARATORS}
    security_ids = sorted(wide["security_id"].astype(str).unique())
    baseline_sums = {key: float(ic[f"delta__{key}"].dropna().sum()) for key in COMPARATORS}
    baseline_counts = {key: int(ic[f"delta__{key}"].notna().sum()) for key in COMPARATORS}
    sums = {security_id: dict(baseline_sums) for security_id in security_ids}
    counts = {security_id: dict(baseline_counts) for security_id in security_ids}
    baseline_by_session = ic.set_index("decision_session")

    def correlation(scores: np.ndarray, labels: np.ndarray) -> float:
        valid = np.isfinite(scores) & np.isfinite(labels)
        if valid.sum() < 45:
            return math.nan
        x = scores[valid]
        y = labels[valid]
        if np.unique(x).size < 2 or np.unique(y).size < 2:
            return math.nan
        return float(np.corrcoef(rankdata(x, method="average"), rankdata(y, method="average"))[0, 1])

    for session, group in wide.groupby("decision_session", sort=True):
        ids = group["security_id"].astype(str).to_numpy()
        labels = group["label__open_to_open__20"].to_numpy(float)
        no_m_scores = group[f"score__{NO_M}"].to_numpy(float)
        comparator_scores = {key: group[f"score__{key}"].to_numpy(float) for key in COMPARATORS}
        for position, security_id in enumerate(ids):
            keep = np.arange(len(group)) != position
            no_m_ic = correlation(no_m_scores[keep], labels[keep])
            for other in COMPARATORS:
                original = float(baseline_by_session.at[session, f"delta__{other}"])
                if np.isfinite(original):
                    sums[security_id][other] -= original
                    counts[security_id][other] -= 1
                value = no_m_ic - correlation(comparator_scores[other][keep], labels[keep])
                if np.isfinite(value):
                    sums[security_id][other] += value
                    counts[security_id][other] += 1
    all_rows = [
        {
            "security_id": security_id,
            **{
                f"mean_delta__{key}": sums[security_id][key] / counts[security_id][key]
                if counts[security_id][key] else math.nan
                for key in COMPARATORS
            },
        }
        for security_id in security_ids
    ]
    frame = pd.DataFrame(all_rows)
    boundary: set[str] = set()
    for other in COMPARATORS:
        decreases = baseline[other] - frame[f"mean_delta__{other}"]
        maximum = float(decreases.max())
        boundary.update(frame.loc[np.isclose(decreases, maximum, rtol=0.0, atol=1e-15), "security_id"].astype(str))
    detailed: dict[str, Any] = {}
    for security_id in sorted(boundary):
        reduced = wide.loc[wide["security_id"].astype(str).ne(security_id)].copy()
        reduced_tail, _ = tail_frame(reduced, cell=NO_M, anchor_name="no_m")
        detailed[security_id] = {
            "mean_delta": {other: float(frame.loc[frame["security_id"].eq(security_id), f"mean_delta__{other}"].iloc[0]) for other in COMPARATORS},
            "tail_minus_comparator": {other: _finite_mean(reduced_tail[f"minus__{other}"]) for other in COMPARATORS},
            "tail_minus_eligible": _finite_mean(reduced_tail["minus_eligible"]),
        }
    return {"baseline_mean_delta": baseline, "largest_contributor_boundary_set": sorted(boundary), "details": detailed}


def classify(rank: Mapping[str, Any], tail: Mapping[str, Any], concentration: Mapping[str, Any], influence: Mapping[str, Any], *, validity_pass: bool) -> dict[str, Any]:
    pooled_rank = rank["RETRO_2023_2026_H1"]
    pooled_tail = tail["RETRO_2023_2026_H1"]
    mean_delta = {key: pooled_rank["paired"][key]["mean"] for key in COMPARATORS}
    positive_half_years = {key: sum(rank[name]["paired"][key]["mean"] > 0 for name in BLOCK_MAP.values()) for key in COMPARATORS}
    median_half_year_delta = {key: float(np.median([rank[name]["paired"][key]["mean"] for name in BLOCK_MAP.values()])) for key in COMPARATORS}
    coherent_tail = (
        pooled_tail["minus_eligible"] > 0
        and all(pooled_tail["minus_comparator"][key] > 0 for key in COMPARATORS)
        and pooled_tail["episode_median_outcome"] > 0
    )
    threshold = 0.50
    dominance = {
        "security": concentration["security_positive_excess"]["largest_share"] >= threshold,
        "session": concentration["session_positive_excess"]["largest_share"] >= threshold,
        "half_year_tail": concentration["half_year_positive_excess"]["largest_share"] >= threshold,
        "rolling_20_sessions": concentration["largest_rolling_20_session_positive_excess_share"] >= threshold,
        "half_year_rank": any(concentration["rank_half_year_positive_delta"][key]["largest_positive_delta_share"] >= threshold for key in COMPARATORS),
        "largest_contributor_flip": any(
            mean_delta[key] > 0 and any(value["mean_delta"][key] <= 0 for value in influence["details"].values())
            for key in COMPARATORS
        ),
    }
    no_m_exceeds_full = pooled_rank["mean_ic"][NO_M] > pooled_rank["mean_ic"][FULL_RICH]
    strong = (
        all(mean_delta[key] >= 0.005 for key in COMPARATORS)
        and all(positive_half_years[key] >= 5 for key in COMPARATORS)
        and all(median_half_year_delta[key] > 0 for key in COMPARATORS)
        and no_m_exceeds_full and coherent_tail and not any(dominance.values()) and validity_pass
    )
    weak = (
        all(mean_delta[key] > 0 for key in COMPARATORS)
        and all(positive_half_years[key] >= 4 for key in COMPARATORS)
        and no_m_exceeds_full
        and not dominance["security"] and not dominance["half_year_tail"] and not dominance["half_year_rank"]
        and not dominance["largest_contributor_flip"] and validity_pass and not strong
    )
    stronger = max(COMPARATORS, key=lambda key: (pooled_rank["mean_ic"][key], key == "C_LINEAR"))
    if not validity_pass:
        classification = "NOT PROVEN"
    elif mean_delta[stronger] <= 0 and not coherent_tail:
        classification = "NEGATIVE"
    elif strong:
        classification = "STRONG RESEARCH DIRECTION"
    elif weak:
        classification = "WEAK BUT PERSISTENT"
    else:
        classification = "UNSTABLE"
    return {
        "classification": classification,
        "prospective_monitoring_justified": classification in {"STRONG RESEARCH DIRECTION", "WEAK BUT PERSISTENT"},
        "stronger_conventional": stronger,
        "mean_delta": mean_delta,
        "positive_half_years": positive_half_years,
        "median_half_year_delta": median_half_year_delta,
        "no_m_exceeds_full_rich": no_m_exceeds_full,
        "coherent_tail": coherent_tail,
        "dominance": dominance,
        "validity_pass": validity_pass,
    }


def calculate() -> dict[str, Any]:
    verification = verify_scientific_object()
    predictions, masks, labels = load_analysis_frames()
    wide = build_wide(predictions, masks, labels)
    wide = attach_episode_flags(wide, predictions, masks, NO_M, "no_m")
    wide = attach_episode_flags(wide, predictions, masks, FULL_RICH, "full_rich")
    ic = session_ic_frame(wide)
    no_m_tail, no_m_anchors = tail_frame(wide, cell=NO_M, anchor_name="no_m")
    full_tail, full_anchors = tail_frame(wide, cell=FULL_RICH, anchor_name="full_rich")
    rank = rank_summary(ic)
    tails = tail_summary(wide, no_m_tail, no_m_anchors, cell=NO_M, anchor_name="no_m")
    full_tails = tail_summary(wide, full_tail, full_anchors, cell=FULL_RICH, anchor_name="full_rich")
    concentration = concentration_summary(wide, ic, no_m_tail, no_m_anchors)
    influence = contributor_influence(wide, ic)
    classification = classify(rank, tails, concentration, influence, validity_pass=True)
    direct = {
        "pooled_mean_ic_improvement": rank["RETRO_2023_2026_H1"]["paired"][FULL_RICH]["mean"],
        "positive_half_years": sum(rank[name]["paired"][FULL_RICH]["mean"] > 0 for name in BLOCK_MAP.values()),
        "no_m_episode_mean": tails["RETRO_2023_2026_H1"]["episode_mean_outcome"],
        "full_rich_episode_mean": full_tails["RETRO_2023_2026_H1"]["episode_mean_outcome"],
        "no_m_episode_median": tails["RETRO_2023_2026_H1"]["episode_median_outcome"],
        "full_rich_episode_median": full_tails["RETRO_2023_2026_H1"]["episode_median_outcome"],
        "no_m_candidate_fraction": tails["RETRO_2023_2026_H1"]["candidate_row_fraction"],
        "full_rich_candidate_fraction": full_tails["RETRO_2023_2026_H1"]["candidate_row_fraction"],
        "no_m_episode_concentration": episode_count_concentration(wide, no_m_anchors),
        "full_rich_episode_concentration": episode_count_concentration(wide, full_anchors),
    }
    return {
        "verification": verification, "wide": wide, "session_ic": ic,
        "tail_sessions": no_m_tail, "episode_anchors": no_m_anchors,
        "rank": rank, "tail": tails, "full_rich_tail": full_tails,
        "concentration": concentration, "influence": influence,
        "direct_no_m_vs_full_rich": direct, "classification": classification,
    }


def validate_run(run_dir: Path) -> dict[str, Any]:
    required = {
        "scientific_object_verification.json", "per_session.parquet", "per_half_year.json",
        "tail_by_session.parquet", "episode_anchors.parquet", "concentration.json",
        "influence.json", "direct_no_m_vs_full_rich.json", "classification.json", "provenance.json",
    }
    manifest = validate_manifest(run_dir, schema_version=SCHEMA, required_files=required)
    classification = read_json(run_dir / "classification.json")
    if classification.get("classification") not in {
        "STRONG RESEARCH DIRECTION", "WEAK BUT PERSISTENT", "UNSTABLE", "NEGATIVE", "NOT PROVEN"
    }:
        raise D2ArtifactError("invalid retrospective classification")
    if read_json(run_dir / "scientific_object_verification.json").get("status") != "PASS":
        raise D2ArtifactError("scientific-object verification did not pass")
    return {"status": "PASS", "logical_hash": manifest["logical_hash"], "classification": classification["classification"]}


def publish() -> Path:
    contract = load_contract()

    def build(stage: Path) -> dict[str, Any]:
        result = calculate()
        write_json(stage / "scientific_object_verification.json", result["verification"])
        write_parquet(stage / "per_session.parquet", result["session_ic"])
        write_json(stage / "per_half_year.json", {"rank": result["rank"], "tail": result["tail"], "full_rich_tail": result["full_rich_tail"]})
        write_parquet(stage / "tail_by_session.parquet", result["tail_sessions"])
        write_parquet(stage / "episode_anchors.parquet", result["episode_anchors"][["population", "security_id", "decision_session", "label__open_to_open__20"]])
        write_json(stage / "concentration.json", result["concentration"])
        write_json(stage / "influence.json", result["influence"])
        write_json(stage / "direct_no_m_vs_full_rich.json", result["direct_no_m_vs_full_rich"])
        write_json(stage / "classification.json", result["classification"])
        provenance = {
            "contract_id": contract["contract_id"], "contract_sha256": sha256_file(CONTRACT_PATH),
            "prediction_manifest_sha256": sha256_file(PREDICTION_ROOT / "manifest.json"),
            "evaluation_stage_manifest_sha256": {
                stage_name: sha256_file(EVALUATION_ROOT / stage_name / "manifest.json")
                for stage_name in ("stage2a", "stage2b", "stage2c")
            },
            "historical_evidence_label": "retrospective hypothesis-development and robustness",
            "prospective_or_deployment_claim": False,
        }
        provenance["provenance_hash"] = content_hash(provenance)
        write_json(stage / "provenance.json", provenance)
        return {
            "contract_sha256": provenance["contract_sha256"],
            "prediction_table_logical_hash": result["verification"]["prediction_table_logical_hash"],
            "classification": result["classification"],
            "per_session": frame_identity(result["session_ic"], sort_by=["decision_session"]),
            "tail_by_session": frame_identity(result["tail_sessions"], sort_by=["decision_session"]),
            "episode_anchors": frame_identity(result["episode_anchors"][["population", "security_id", "decision_session", "label__open_to_open__20"]], sort_by=["decision_session", "security_id"]),
            "rank_hash": content_hash(result["rank"]), "tail_hash": content_hash(result["tail"]),
            "concentration_hash": content_hash(result["concentration"]), "influence_hash": content_hash(result["influence"]),
        }

    return publish_immutable(OUTPUT_ROOT, RUN_ID, build, schema_version=SCHEMA, validate=validate_run)
