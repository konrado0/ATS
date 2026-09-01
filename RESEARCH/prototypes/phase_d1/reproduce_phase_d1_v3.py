from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "source/python/src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from ats_research.hashing import content_hash, sha256_file  # noqa: E402


CONFIG = ROOT / "source/python/configs/phase_d0_reference_v3.json"
RESOLUTION = ROOT / "source/python/configs/phase_d1_structural_resolution_v3.json"
RUN_ROOT = Path("D:/Stock/data/ATS/phase_d_ml/structural_runs")
CANDIDATE = Path("D:/Stock/data/ATS/gpw_split_normalization/runs/gpw-split-normalization-20260826-v4/candidate_panel.parquet")
FORBIDDEN = {"split_adjusted_open", "label__open_to_open__20", "model_score", "rank_ic", "tail_outcome", "economic_result"}


def _half_bounds(value: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    year = int(value[:4])
    start = pd.Timestamp(year, 1 if value.endswith("H1") else 7, 1)
    return start, start + pd.DateOffset(months=6) - pd.Timedelta(days=1)


def _endpoint_table(calendar: pd.DatetimeIndex) -> pd.DataFrame:
    endpoint = pd.Series(pd.NaT, index=np.arange(len(calendar)), dtype="datetime64[ns]")
    if len(calendar) > 20:
        endpoint.iloc[:-20] = calendar[20:].to_numpy()
    return pd.DataFrame({"decision_session": calendar, "endpoint_session": endpoint})


def _availability(endpoints: pd.DataFrame, candidates: pd.DatetimeIndex, boundary: pd.Timestamp) -> dict[str, Any]:
    subset = endpoints.loc[endpoints["decision_session"].isin(candidates)]
    retained = subset["endpoint_session"].notna() & subset["endpoint_session"].lt(boundary)
    kept = pd.DatetimeIndex(subset.loc[retained, "decision_session"])
    purged = pd.DatetimeIndex(subset.loc[~retained, "decision_session"])
    return {
        "candidate_sessions": len(subset),
        "retained_sessions": int(retained.sum()),
        "purged_sessions": int((~retained).sum()),
        "last_retained_session": kept.max().strftime("%Y-%m-%d") if len(kept) else None,
        "first_purged_session": purged.min().strftime("%Y-%m-%d") if len(purged) else None,
    }


def _bins(sessions: pd.DatetimeIndex) -> list[dict[str, Any]]:
    return [
        {
            "bin": number + 1,
            "first_session": pd.Timestamp(values[0]).strftime("%Y-%m-%d"),
            "last_session": pd.Timestamp(values[-1]).strftime("%Y-%m-%d"),
            "session_count": len(values),
        }
        for number, values in enumerate(np.array_split(sessions.to_numpy(), 4))
    ]


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    resolution = json.loads(RESOLUTION.read_text(encoding="utf-8"))
    run_dir = RUN_ROOT / resolution["run_id"]
    projection = ["session_date", "official_membership"]
    if set(projection) & FORBIDDEN:
        raise AssertionError("independent reproduction projection includes predictive fields")
    panel = pd.read_parquet(CANDIDATE, columns=projection)
    calendar = pd.DatetimeIndex(sorted(pd.to_datetime(panel["session_date"]).dt.normalize().unique()))
    endpoints = _endpoint_table(calendar)
    official = panel.loc[panel["official_membership"].fillna(False)].groupby("session_date").size()
    if official.min() != 60 or official.max() != 60:
        raise ValueError("independent reproduction did not retain denominator 60")
    stored = {item["block_id"]: item for item in resolution["walk_forward_resolution"]["blocks"]}
    reproduced: dict[str, Any] = {}
    evaluation_sessions: dict[str, pd.DatetimeIndex] = {}

    for specification in config["evidence_blocks"]:
        block_id = specification["block_id"]
        half_start, half_end = _half_bounds(specification["calendar_half"])
        end = min(half_end, pd.Timestamp(specification.get("observation_end", half_end)))
        evaluation = calendar[(calendar >= half_start) & (calendar <= end)]
        evaluation_sessions[block_id] = evaluation
        refit = pd.Timestamp(evaluation[0])
        month_start = pd.Timestamp(refit.year, refit.month, 1)
        lower = month_start - pd.DateOffset(months=36)
        window = calendar[(calendar >= lower) & (calendar < refit)]
        final = _availability(endpoints, window, refit)
        inner = []
        for number, months in enumerate((18, 24, 30), start=1):
            score_lower = lower + pd.DateOffset(months=months)
            score_upper = lower + pd.DateOffset(months=months + 6)
            score = calendar[(calendar >= score_lower) & (calendar < score_upper)]
            fit = calendar[(calendar >= window[0]) & (calendar < score[0])]
            availability = _availability(endpoints, fit, pd.Timestamp(score[0]))
            minimum_sessions = max(120, math.ceil(0.80 * availability["retained_sessions"]))
            inner.append({
                "score_block_number": number,
                "fit_availability": availability,
                "minimum_qualifying_sessions": minimum_sessions,
                "minimum_model_rows": max(5400, 45 * minimum_sessions),
                "score_start": score[0].strftime("%Y-%m-%d"),
                "score_end": score[-1].strftime("%Y-%m-%d"),
                "score_expected_sessions": len(score),
                "score_minimum_qualifying_sessions": math.ceil(0.80 * len(score)),
            })
        outcome_available = endpoints.loc[endpoints["decision_session"].isin(evaluation), "endpoint_session"].notna()
        reproduced[block_id] = {
            "refit_session": refit.strftime("%Y-%m-%d"),
            "window_lower_calendar_boundary": lower.strftime("%Y-%m-%d"),
            "estimator_window_start": window[0].strftime("%Y-%m-%d"),
            "estimator_window_end": window[-1].strftime("%Y-%m-%d"),
            "final_fit": {
                "availability": final,
                "minimum_qualifying_sessions": max(230, math.ceil(0.80 * final["retained_sessions"])),
            },
            "inner_score_blocks": inner,
            "evaluation_start": evaluation[0].strftime("%Y-%m-%d"),
            "evaluation_end": evaluation[-1].strftime("%Y-%m-%d"),
            "evaluation_expected_sessions": len(evaluation),
            "evaluation_structurally_outcome_available_sessions": int(outcome_available.sum()),
            "evaluation_right_censored_sessions": int((~outcome_available).sum()),
            "evaluation_minimum_qualifying_sessions": math.ceil(0.80 * len(evaluation)) if specification["complete"] else 0,
        }

    mismatches: list[str] = []
    for block_id, actual in reproduced.items():
        expected = stored[block_id]
        for key in (
            "refit_session", "window_lower_calendar_boundary", "estimator_window_start", "estimator_window_end",
            "evaluation_start", "evaluation_end", "evaluation_expected_sessions",
            "evaluation_structurally_outcome_available_sessions", "evaluation_right_censored_sessions",
            "evaluation_minimum_qualifying_sessions",
        ):
            if actual[key] != expected[key]:
                mismatches.append(f"{block_id}:{key}")
        for key in ("availability", "minimum_qualifying_sessions"):
            if actual["final_fit"][key] != expected["final_fit"][key]:
                mismatches.append(f"{block_id}:final_fit:{key}")
        for actual_inner, expected_inner in zip(actual["inner_score_blocks"], expected["inner_score_blocks"], strict=True):
            for key in (
                "score_block_number", "fit_availability", "minimum_qualifying_sessions", "minimum_model_rows",
                "score_start", "score_end", "score_expected_sessions", "score_minimum_qualifying_sessions",
            ):
                if actual_inner[key] != expected_inner[key]:
                    mismatches.append(f"{block_id}:inner{actual_inner['score_block_number']}:{key}")
    if mismatches:
        raise ValueError(f"independent chronology reproduction differs: {mismatches}")

    mapping = config["evidence_mapping"]
    populations = {
        "MODEL_SELECTION_2023": mapping["model_family_selection"],
        "DEVELOPMENT_CONFIRMATION_2024": mapping["development_confirmation_pooled"],
        "LOCKED_COMPLETE_2025_2026H1": mapping["locked_evidence_pooled"],
    }
    reproduced_bins = {
        name: _bins(pd.DatetimeIndex(sorted({session for block_id in block_ids for session in evaluation_sessions[block_id]})))
        for name, block_ids in populations.items()
    }
    if reproduced_bins != resolution["chronological_concentration_bins"]:
        raise ValueError("independent concentration-bin reproduction differs")
    run_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in run_manifest["files"].items():
        if sha256_file(run_dir / name) != digest:
            raise ValueError(f"immutable v3 run hash mismatch: {name}")
    if sha256_file(RESOLUTION) != run_manifest["files"]["structural_resolution.json"]:
        raise ValueError("repository and immutable v3 structural resolutions differ")
    print(json.dumps({
        "schema_version": "ats.phase_d1.independent_reproduction.v3",
        "status": "PASS",
        "calendar_sessions": len(calendar),
        "outer_blocks": len(reproduced),
        "inner_blocks": sum(len(item["inner_score_blocks"]) for item in reproduced.values()),
        "concentration_populations": len(reproduced_bins),
        "reproduction_hash": content_hash({"blocks": reproduced, "bins": reproduced_bins}),
        "candidate_columns_loaded": projection,
        "realized_labels_scores_metrics_or_outcomes_loaded": False,
        "structural_run_id": run_manifest["run_id"],
        "structural_logical_hash": run_manifest["logical_hash"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
