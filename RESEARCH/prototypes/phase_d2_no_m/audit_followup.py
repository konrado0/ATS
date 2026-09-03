from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from ats_ml.d2_artifacts import file_inventory, write_json
from ats_research.hashing import content_hash, sha256_file


REPO = Path("D:/Stock/ATS")
PRED = Path("D:/Stock/data/ATS/phase_d_ml/prediction_runs/phase-d2-predictions-20260902-v4")
EVAL = Path("D:/Stock/data/ATS/phase_d_ml/evaluation_runs/phase-d2-evaluation-20260902-v6")
PRIMARY = Path("D:/Stock/data/ATS/phase_d_ml/followup_runs/phase-d2-nm-followup-20260903-v1")
DEST = Path("D:/Stock/data/ATS/phase_d_ml/followup_reproductions/phase-d2-nm-followup-20260903-v1-independent")
NO_M = "RICH_NO_M_LIGHTGBM"
FULL = "RICH_LIGHTGBM"
COMPS = ("C_LINEAR", "C_LIGHTGBM")
CELLS = (*COMPS, NO_M, FULL)
BLOCKS = {
    "MODEL_SELECTION_2023_H1": "RETRO_2023_H1", "MODEL_SELECTION_2023_H2": "RETRO_2023_H2",
    "DEVELOPMENT_2024_H1": "RETRO_2024_H1", "DEVELOPMENT_2024_H2": "RETRO_2024_H2",
    "LOCKED_2025_H1": "RETRO_2025_H1", "LOCKED_2025_H2": "RETRO_2025_H2",
    "LOCKED_2026_H1": "RETRO_2026_H1",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def corr(score, outcome):
    score = np.asarray(score, float); outcome = np.asarray(outcome, float)
    valid = np.isfinite(score) & np.isfinite(outcome)
    if valid.sum() < 45 or np.unique(score[valid]).size < 2 or np.unique(outcome[valid]).size < 2:
        return math.nan
    return float(np.corrcoef(rankdata(score[valid], method="average"), rankdata(outcome[valid], method="average"))[0, 1])


def fractional(scores, k):
    values = np.asarray(scores, float)
    if k == 0: return np.zeros(len(values))
    if k >= len(values): return np.ones(len(values))
    boundary = np.sort(values)[-k]
    above = values > boundary; equal = values == boundary
    return above.astype(float) + equal.astype(float) * ((k - above.sum()) / equal.sum())


def episodes(predictions, calendar, cell):
    frame = predictions.loc[predictions.cell_id.eq(cell), ["security_id", "decision_session", "candidate"]].copy()
    frame = frame.sort_values(["security_id", "decision_session"], kind="mergesort")
    positions = {pd.Timestamp(value): index for index, value in enumerate(sorted(pd.to_datetime(calendar).unique()))}
    frame["anchor"] = False
    for _, indices in frame.groupby("security_id", sort=False).groups.items():
        prior = None
        for index in indices:
            if not bool(frame.at[index, "candidate"]): continue
            current = positions[pd.Timestamp(frame.at[index, "decision_session"])]
            if prior is None or current - prior > 20: frame.at[index, "anchor"] = True
            prior = current
    return frame[["security_id", "decision_session", "anchor"]]


def load_wide():
    predictions = pd.read_parquet(PRED / "predictions.parquet")
    predictions = predictions.loc[predictions.cell_id.isin(CELLS)]
    masks = pd.read_parquet(PRED / "common_score_masks.parquet")
    labels = pd.concat([pd.read_parquet(EVAL / f"{stage}/outcomes.parquet") for stage in ("stage2a", "stage2b", "stage2c")])
    labels = labels[["block_id", "security_id", "decision_session", "label__open_to_open__20"]].drop_duplicates()
    keys = ["block_id", "security_id", "decision_session"]
    scores = predictions.loc[predictions.block_id.isin(BLOCKS)].pivot(index=keys, columns="cell_id", values="model_score").add_prefix("score__")
    candidates = predictions.loc[predictions.block_id.isin(BLOCKS)].pivot(index=keys, columns="cell_id", values="candidate").add_prefix("candidate__")
    wide = scores.join(candidates).reset_index().merge(labels, on=keys, validate="one_to_one")
    wide["population"] = wide.block_id.map(BLOCKS)
    for cell, name in ((NO_M, "no_m"), (FULL, "full")):
        flags = episodes(predictions, masks.decision_session, cell).rename(columns={"anchor": f"anchor__{name}"})
        wide = wide.merge(flags, on=["security_id", "decision_session"], validate="one_to_one")
    return predictions, masks, wide.sort_values(["decision_session", "security_id"], kind="mergesort")


def session_metrics(wide):
    rows = []
    for (population, session), group in wide.groupby(["population", "decision_session"], sort=True):
        row = {"population": population, "decision_session": session}
        for cell in CELLS: row[cell] = corr(group[f"score__{cell}"], group.label__open_to_open__20)
        for comp in (*COMPS, FULL): row[f"delta__{comp}"] = row[NO_M] - row[comp]
        rows.append(row)
    return pd.DataFrame(rows)


def tail_metrics(wide):
    anchors = wide.loc[wide.anchor__no_m & np.isfinite(wide.label__open_to_open__20)].copy()
    rows = []
    for (population, session), group in wide.groupby(["population", "decision_session"], sort=True):
        eligible = group.loc[np.isfinite(group.label__open_to_open__20)]
        chosen = anchors.loc[anchors.decision_session.eq(session)]
        row = {"population": population, "decision_session": session, "anchor_count": len(chosen)}
        if not len(chosen):
            row.update({"eligible_mean": math.nan, "minus_eligible": math.nan, **{f"minus__{comp}": math.nan for comp in COMPS}})
        else:
            y = chosen.label__open_to_open__20.to_numpy(float); all_y = eligible.label__open_to_open__20.to_numpy(float)
            row["eligible_mean"] = float(all_y.mean()); row["minus_eligible"] = float(y.mean() - all_y.mean())
            for comp in COMPS:
                w = fractional(eligible[f"score__{comp}"], len(chosen))
                row[f"minus__{comp}"] = float(y.mean() - np.average(all_y[w > 0], weights=w[w > 0]))
        rows.append(row)
    return pd.DataFrame(rows), anchors


def leave_one_security(wide, base_ic):
    ids = sorted(wide.security_id.astype(str).unique())
    base_sum = {comp: float(base_ic[f"delta__{comp}"].sum()) for comp in COMPS}
    base_count = {comp: int(base_ic[f"delta__{comp}"].notna().sum()) for comp in COMPS}
    sums = {sid: dict(base_sum) for sid in ids}; counts = {sid: dict(base_count) for sid in ids}
    base = base_ic.set_index("decision_session")
    for session, group in wide.groupby("decision_session", sort=True):
        identity = group.security_id.astype(str).to_numpy(); y = group.label__open_to_open__20.to_numpy(float)
        no_m = group[f"score__{NO_M}"].to_numpy(float); comps = {key: group[f"score__{key}"].to_numpy(float) for key in COMPS}
        for position, sid in enumerate(identity):
            keep = np.arange(len(group)) != position; no_m_ic = corr(no_m[keep], y[keep])
            for comp in COMPS:
                old = float(base.at[session, f"delta__{comp}"])
                if np.isfinite(old): sums[sid][comp] -= old; counts[sid][comp] -= 1
                value = no_m_ic - corr(comps[comp][keep], y[keep])
                if np.isfinite(value): sums[sid][comp] += value; counts[sid][comp] += 1
    return {sid: {comp: sums[sid][comp] / counts[sid][comp] for comp in COMPS} for sid in ids}


def main():
    if DEST.exists(): raise RuntimeError(f"immutable independent audit exists: {DEST}")
    contract = read_json(REPO / "source/python/configs/phase_d2_no_m_followup.json")
    manifest = read_json(PRED / "manifest.json")
    derived = read_json(PRED / "derived_contract.json")
    audits = [row for row in read_json(PRED / "fit_calibration_audit.json")["records"] if row.get("cell_id") == NO_M]
    science_pass = (
        sha256_file(REPO / "source/python/configs/phase_d0_feature_registry.json") == contract["accepted_inputs"]["feature_registry_sha256"]
        and manifest["logical_payload"]["prediction_identity"]["logical_hash"] == contract["accepted_inputs"]["prediction_table_logical_hash"]
        and len(derived["cells"][NO_M]["feature_names"]) == 18 and len(audits) == 8
        and all(len(row["inner"]) == 3 and row["model_family"] == "LIGHTGBM" and row["final_fit"]["endpoint_strictly_before_boundary"] for row in audits)
    )
    predictions, masks, wide = load_wide()
    populations = predictions.loc[predictions.block_id.isin(BLOCKS)].groupby(["block_id", "cell_id"]).size().unstack()
    population_pass = all(populations.loc[block, list(CELLS)].nunique() == 1 for block in BLOCKS)
    ic = session_metrics(wide); tail, anchors = tail_metrics(wide)
    half = {}
    for name in BLOCKS.values():
        group = ic.loc[ic.population.eq(name)]
        half[name] = {comp: float(group[f"delta__{comp}"].mean()) for comp in COMPS}
    pooled_delta = {comp: float(ic[f"delta__{comp}"].mean()) for comp in COMPS}
    positive_half = {comp: sum(half[name][comp] > 0 for name in BLOCKS.values()) for comp in COMPS}
    median_half = {comp: float(np.median([half[name][comp] for name in BLOCKS.values()])) for comp in COMPS}
    pooled_ic = {cell: float(ic[cell].mean()) for cell in CELLS}
    pooled_tail = {
        "minus_eligible": float(tail.minus_eligible.mean()),
        "minus_comparator": {comp: float(tail[f"minus__{comp}"].mean()) for comp in COMPS},
        "episode_median": float(anchors.label__open_to_open__20.median()),
    }
    eligible_mean = tail.set_index("decision_session").eligible_mean
    anchors["positive_excess"] = (anchors.label__open_to_open__20 - anchors.decision_session.map(eligible_mean)).clip(lower=0)
    def largest_share(column):
        values = anchors.groupby(column).positive_excess.sum(); return float(values.max() / values.sum()) if values.sum() else 0.0
    sessions = pd.DatetimeIndex(sorted(wide.decision_session.unique()))
    session_values = anchors.groupby("decision_session").positive_excess.sum().reindex(sessions, fill_value=0)
    rank_half_dominance = any(
        (ic.assign(x=ic[f"delta__{comp}"].clip(lower=0)).groupby("population").x.sum().pipe(lambda x: x.max() / x.sum())) >= 0.5
        for comp in COMPS
    )
    influence = leave_one_security(wide, ic)
    boundary = set()
    for comp in COMPS:
        decreases = {sid: pooled_delta[comp] - value[comp] for sid, value in influence.items()}
        maximum = max(decreases.values())
        boundary.update(sid for sid, value in decreases.items() if np.isclose(value, maximum, rtol=0, atol=1e-15))
    contributor_flip = any(pooled_delta[comp] > 0 and any(influence[sid][comp] <= 0 for sid in boundary) for comp in COMPS)
    dominance = {
        "security": largest_share("security_id") >= 0.5, "session": largest_share("decision_session") >= 0.5,
        "half_year_tail": largest_share("population") >= 0.5,
        "rolling_20_sessions": float(session_values.rolling(20, min_periods=1).sum().max() / session_values.sum()) >= 0.5,
        "half_year_rank": bool(rank_half_dominance), "largest_contributor_flip": bool(contributor_flip),
    }
    coherent = pooled_tail["minus_eligible"] > 0 and all(pooled_tail["minus_comparator"][c] > 0 for c in COMPS) and pooled_tail["episode_median"] > 0
    strong = all(pooled_delta[c] >= .005 and positive_half[c] >= 5 and median_half[c] > 0 for c in COMPS) and pooled_ic[NO_M] > pooled_ic[FULL] and coherent and not any(dominance.values())
    weak = all(pooled_delta[c] > 0 and positive_half[c] >= 4 for c in COMPS) and pooled_ic[NO_M] > pooled_ic[FULL] and not any(dominance[k] for k in ("security", "half_year_tail", "half_year_rank", "largest_contributor_flip")) and not strong
    stronger = max(COMPS, key=lambda c: (pooled_ic[c], c == "C_LINEAR"))
    classification = "STRONG RESEARCH DIRECTION" if strong else "WEAK BUT PERSISTENT" if weak else "NEGATIVE" if pooled_delta[stronger] <= 0 and not coherent else "UNSTABLE"
    primary_class = read_json(PRIMARY / "classification.json")
    primary_half = read_json(PRIMARY / "per_half_year.json")["rank"]
    comparisons = {key: bool(value) for key, value in {
        "classification": classification == primary_class["classification"],
        "pooled_delta": all(np.isclose(pooled_delta[c], primary_class["mean_delta"][c], atol=1e-12, rtol=0) for c in COMPS),
        "positive_half_years": positive_half == primary_class["positive_half_years"],
        "median_half_year_delta": all(np.isclose(median_half[c], primary_class["median_half_year_delta"][c], atol=1e-12, rtol=0) for c in COMPS),
        "pooled_no_m_ic": np.isclose(pooled_ic[NO_M], primary_half["RETRO_2023_2026_H1"]["mean_ic"][NO_M], atol=1e-12, rtol=0),
        "coherent_tail": coherent == primary_class["coherent_tail"],
        "dominance": dominance == primary_class["dominance"],
        "largest_contributor_boundary": sorted(boundary) == read_json(PRIMARY / "influence.json")["largest_contributor_boundary_set"],
    }.items()}
    status = "PASS" if science_pass and population_pass and all(comparisons.values()) else "FAIL"
    audit = {
        "schema_version": "ats.phase_d2_nm.independent_audit.v1", "status": status,
        "classification": classification, "scientific_object_pass": bool(science_pass),
        "paired_population_pass": bool(population_pass), "pooled_mean_ic": pooled_ic,
        "pooled_mean_delta": pooled_delta, "positive_half_years": positive_half,
        "median_half_year_delta": median_half, "coherent_tail": coherent,
        "dominance": dominance, "largest_contributor_boundary_set": sorted(boundary),
        "comparisons_to_primary": comparisons,
    }
    audit["scientific_logical_hash"] = content_hash(audit)
    DEST.mkdir(parents=True)
    write_json(DEST / "audit.json", audit)
    write_json(DEST / "manifest.json", {
        "schema_version": "ats.phase_d2_nm.independent_audit_manifest.v1", "run_id": DEST.name,
        "files": file_inventory(DEST), "primary_manifest_sha256": sha256_file(PRIMARY / "manifest.json"),
    })
    print(json.dumps({"status": status, "classification": classification, "run_dir": str(DEST), "scientific_logical_hash": audit["scientific_logical_hash"]}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
