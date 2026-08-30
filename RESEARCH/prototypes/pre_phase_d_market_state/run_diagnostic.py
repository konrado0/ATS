from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow
import scipy

from market_state import (
    ADVERSE_LOW,
    ALL_FEATURES,
    BLOCK_FEATURES,
    OPTIONAL_FEATURES,
    TOP60_FEATURES,
    WIG_FEATURES,
    adverse_percentile,
    assign_tercile,
    compute_top60_features,
    compute_wig_features,
    drawdown_episodes,
    moving_block_indices,
    percentile_interval,
    read_stooq_wig,
    safe_spearman,
    sha256_file,
    stable_frame_hash,
    stable_json,
    validate_wig,
)


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=HERE / "config.json")
    parser.add_argument("--output-root", type=Path, default=Path("D:/Stock/data/ATS/pre_phase_d_market_state/runs"))
    parser.add_argument("--reproduction", action="store_true")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def input_path(config: dict[str, Any], role: str) -> Path:
    matches = [Path(row["path"]) for row in config["inputs"] if row["role"] == role]
    if len(matches) != 1:
        raise ValueError(f"Expected one input for {role}, found {len(matches)}")
    return matches[0]


def verify_inputs(config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in config["inputs"]:
        path = Path(item["path"])
        actual_bytes = path.stat().st_size if path.exists() else None
        actual_hash = sha256_file(path) if path.exists() else None
        rows.append(
            {
                "role": item["role"],
                "path": path.as_posix(),
                "expected_bytes": item["bytes"],
                "actual_bytes": actual_bytes,
                "expected_sha256": item["sha256"],
                "actual_sha256": actual_hash,
                "status": "PASS" if actual_bytes == item["bytes"] and actual_hash == item["sha256"] else "FAIL",
            }
        )
    result = pd.DataFrame(rows)
    if not result["status"].eq("PASS").all():
        raise RuntimeError("Pinned input verification failed")
    return result


def attach_state_features(config: dict[str, Any], local_wig: pd.DataFrame, candidate: pd.DataFrame, decision_dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    wig_values = compute_wig_features(local_wig, volatility_ratio_centered=bool(config["volatility_ratio_centered"]))
    calendar = pd.DatetimeIndex(local_wig["session_date"].sort_values().unique())
    top60, coverage = compute_top60_features(
        candidate,
        calendar,
        decision_dates,
        config["minimum_usable_members"],
        leadership_positive_name_count=int(config["leadership_positive_name_count"]),
    )
    positions = {date: i for i, date in enumerate(calendar)}
    mapping = []
    for decision in decision_dates:
        pos = positions[decision]
        mapping.append({"decision_session": decision, "information_session": calendar[pos - 1] if pos > 0 else pd.NaT})
    mapping_frame = pd.DataFrame(mapping)
    wig_attached = mapping_frame.merge(
        wig_values.rename(columns={"session_date": "information_session"}),
        on="information_session",
        how="left",
        validate="many_to_one",
    ).drop(columns=["close"])
    state = wig_attached.merge(top60, on=["decision_session", "information_session"], how="left", validate="one_to_one")
    state["timing_valid"] = state["information_session"] < state["decision_session"]
    return state.sort_values("decision_session").reset_index(drop=True), coverage


def feature_coverage_gate(config: dict[str, Any], state: pd.DataFrame, top60_coverage: pd.DataFrame) -> pd.DataFrame:
    controlling = state.loc[state["decision_session"].between(pd.Timestamp(config["controlling_start"]), pd.Timestamp(config["controlling_end"]))].copy()
    rows = []
    top_cov = top60_coverage.copy()
    for feature in BLOCK_FEATURES:
        valid = controlling[feature].notna()
        timing_violations = int((~controlling.loc[valid, "timing_valid"]).sum())
        denominator_violations = 0
        unavailable_as_negative_violations = 0
        if feature in TOP60_FEATURES:
            cov = top_cov.loc[top_cov["feature"].eq(feature) & top_cov["decision_session"].isin(controlling["decision_session"])]
            denominator_violations = int(cov["official_denominator"].ne(60).sum())
            proof_invalid = cov["unavailable_members_in_aggregation"].ne(0)
            if feature == "top60_breadth_change_10":
                proof_invalid |= cov["aggregation_denominator"].lt(config["minimum_usable_members"])
                proof_invalid |= cov["lag10_aggregation_denominator"].lt(config["minimum_usable_members"])
                proof_invalid |= cov["aggregation_denominator"].gt(60)
                proof_invalid |= cov["lag10_aggregation_denominator"].gt(60)
            else:
                proof_invalid |= cov["aggregation_denominator"].ne(cov["usable_count"])
            unavailable_as_negative_violations = int(proof_invalid.sum())
            valid = controlling[feature].notna()
        valid_fraction = float(valid.mean()) if len(valid) else 0.0
        status = "PASS" if timing_violations == denominator_violations == unavailable_as_negative_violations == 0 and valid_fraction >= config["minimum_valid_session_fraction"] else "NOT PROVEN"
        rows.append(
            {
                "feature": feature,
                "sessions": int(len(controlling)),
                "valid_sessions": int(valid.sum()),
                "valid_fraction": valid_fraction,
                "timing_violations": timing_violations,
                "denominator_violations": denominator_violations,
                "unavailable_as_negative_violations": unavailable_as_negative_violations,
                "status": status,
            }
        )
    frame = pd.DataFrame(rows)
    valid_features = frame.loc[frame["status"].eq("PASS"), "feature"].tolist()
    duplicates = set()
    for i, first in enumerate(valid_features):
        for second in valid_features[i + 1 :]:
            pair = controlling[[first, second]].dropna()
            if len(pair) == len(controlling) and pair[first].equals(pair[second]):
                duplicates.add(second)
            elif len(pair) >= 3 and abs(pair[first].corr(pair[second])) >= 1.0 - config["duplicate_tolerance"]:
                # Correlation alone does not demonstrate algebraic redundancy.
                pass
    frame["mechanical_duplication_failure"] = frame["feature"].isin(duplicates)
    frame.loc[frame["mechanical_duplication_failure"], "status"] = "FAIL"
    return frame


def select_episodes(nav: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    common = nav.loc[nav["period"].eq("common")].copy()
    pivot = common.pivot(index="session_date", columns="portfolio", values="nav").sort_index()
    pivot["relative_wealth"] = pivot["q5"] / pivot["eligible_universe_benchmark"]
    selected = []
    for episode_type, column, count in [("absolute_q5", "q5", 4), ("relative_q5_vs_benchmark", "relative_wealth", 3)]:
        episodes = drawdown_episodes(pivot[column]).sort_values(["drawdown", "peak_date"], ascending=[True, True]).head(count).reset_index(drop=True)
        episodes["episode_type"] = episode_type
        episodes["episode_rank"] = np.arange(1, len(episodes) + 1)
        for idx, row in episodes.iterrows():
            peak = row["peak_date"]
            trough = row["trough_date"]
            q5_loss = float(pivot.loc[trough, "q5"] / pivot.loc[peak, "q5"] - 1.0)
            benchmark_loss = float(pivot.loc[trough, "eligible_universe_benchmark"] / pivot.loc[peak, "eligible_universe_benchmark"] - 1.0)
            relative_loss = float(pivot.loc[trough, "relative_wealth"] / pivot.loc[peak, "relative_wealth"] - 1.0)
            episodes.loc[idx, "q5_loss"] = q5_loss
            episodes.loc[idx, "benchmark_loss"] = benchmark_loss
            episodes.loc[idx, "relative_loss"] = relative_loss
        selected.append(episodes)
    return pd.concat(selected, ignore_index=True), pivot


def session_at_offset(calendar: pd.DatetimeIndex, date: pd.Timestamp, offset: int) -> pd.Timestamp | pd.NaT:
    if date not in calendar:
        return pd.NaT
    position = calendar.get_loc(date) + offset
    return calendar[position] if 0 <= position < len(calendar) else pd.NaT


def attribute_episodes(episodes: pd.DataFrame, state: pd.DataFrame, nav_calendar: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    state_indexed = state.set_index("decision_session")
    percentile = pd.DataFrame(index=state_indexed.index)
    for feature in ALL_FEATURES:
        percentile[feature] = adverse_percentile(state_indexed[feature], feature)
    anchor_rows = []
    classification_rows = []
    for episode in episodes.itertuples(index=False):
        anchors = {
            "peak_minus_20": session_at_offset(nav_calendar, episode.peak_date, -20),
            "peak": episode.peak_date,
            "peak_plus_5": session_at_offset(nav_calendar, episode.peak_date, 5),
            "peak_plus_10": session_at_offset(nav_calendar, episode.peak_date, 10),
            "peak_plus_20": session_at_offset(nav_calendar, episode.peak_date, 20),
            "trough": episode.trough_date,
            "trough_plus_20": session_at_offset(nav_calendar, episode.trough_date, 20),
            "recovery": episode.recovery_date,
        }
        for feature in ALL_FEATURES:
            observed: dict[str, float] = {}
            for label, date in anchors.items():
                value = np.nan
                adverse = np.nan
                info = pd.NaT
                if pd.notna(date) and date in state_indexed.index:
                    value = state_indexed.loc[date, feature]
                    adverse = percentile.loc[date, feature]
                    info = state_indexed.loc[date, "information_session"]
                observed[label] = adverse
                anchor_rows.append(
                    {
                        "episode_type": episode.episode_type,
                        "episode_rank": int(episode.episode_rank),
                        "anchor": label,
                        "decision_session": date,
                        "information_session": info,
                        "feature": feature,
                        "value": value,
                        "adverse_percentile": adverse,
                    }
                )
            classification = "uninformative"
            if pd.notna(observed["peak_minus_20"]) and observed["peak_minus_20"] >= 2.0 / 3.0:
                classification = "leading"
            elif any(pd.notna(observed[label]) and observed[label] >= 2.0 / 3.0 for label in ["peak", "peak_plus_5"]):
                classification = "early-contemporaneous"
            elif any(pd.notna(observed[label]) and observed[label] >= 2.0 / 3.0 for label in ["peak_plus_10", "peak_plus_20", "trough"]):
                classification = "late"
            classification_rows.append(
                {
                    "episode_type": episode.episode_type,
                    "episode_rank": int(episode.episode_rank),
                    "feature": feature,
                    "classification": classification,
                }
            )
    anchors = pd.DataFrame(anchor_rows).merge(pd.DataFrame(classification_rows), on=["episode_type", "episode_rank", "feature"], how="left")
    return anchors, pd.DataFrame(classification_rows)


def prepare_proximity_sessions(config: dict[str, Any], adapted: pd.DataFrame, state: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = adapted.copy()
    data["session_date"] = pd.to_datetime(data["session_date"])
    start = pd.Timestamp(config["controlling_start"])
    end = pd.Timestamp(config["controlling_end"])
    data = data.loc[data["session_date"].between(start, end)].copy()
    eligible_feature = data["eligible__proximity_to_max_high_252"].fillna(False)
    values = data["proximity_to_max_high_252"].where(eligible_feature)
    ranks = values.groupby(data["session_date"]).rank(method="average")
    counts = values.groupby(data["session_date"]).transform("count")
    data["proximity_percentile"] = ranks / counts
    data["proximity_quintile"] = np.ceil(data["proximity_percentile"] * 5.0).clip(1, 5).astype("Int64")
    data["label"] = data["label__open_to_open__20"]
    data["label_available"] = data["label"].notna()
    joint = eligible_feature & data["label_available"]
    rows = []
    for session, group in data.groupby("session_date", sort=True):
        joint_group = group.loc[joint.loc[group.index]]
        q5 = joint_group.loc[joint_group["proximity_quintile"].eq(5)]
        eligible_mean = float(joint_group["label"].mean()) if len(joint_group) else np.nan
        q5_mean = float(q5["label"].mean()) if len(q5) else np.nan
        rows.append(
            {
                "session_date": session,
                "official_denominator": int(group["official_expected"].iloc[0]),
                "feature_usable_count": int(eligible_feature.loc[group.index].sum()),
                "label_available_count": int(group["label_available"].sum()),
                "joint_eligible_count": int(len(joint_group)),
                "q5_count": int(len(q5)),
                "rank_ic": safe_spearman(joint_group["proximity_to_max_high_252"], joint_group["label"]),
                "eligible_mean_return": eligible_mean,
                "q5_mean_return": q5_mean,
                "q5_minus_eligible": q5_mean - eligible_mean if np.isfinite(q5_mean) and np.isfinite(eligible_mean) else np.nan,
                "q5_adverse_5_count": int((q5["label"] <= -0.05).sum()),
                "q5_adverse_10_count": int((q5["label"] <= -0.10).sum()),
            }
        )
    sessions = pd.DataFrame(rows)
    sessions["outcome_population"] = sessions["joint_eligible_count"].gt(0)
    valid_session_dates = pd.DatetimeIndex(sessions.loc[sessions["outcome_population"], "session_date"])
    ordinal = {date: i for i, date in enumerate(valid_session_dates)}
    sessions["offset"] = sessions["session_date"].map(ordinal).astype("Int64") % 20
    sessions["year"] = sessions["session_date"].dt.year
    state_subset = state.rename(columns={"decision_session": "session_date"})[["session_date", *ALL_FEATURES]]
    sessions = sessions.merge(state_subset, on="session_date", how="left", validate="one_to_one")
    data = data.merge(state_subset, on="session_date", how="left", validate="many_to_one")
    data["is_q5_joint"] = joint & data["proximity_quintile"].eq(5)
    return sessions, data


def _summary_row(feature: str, tercile: int, session_group: pd.DataFrame, q5_rows: pd.DataFrame, period_type: str, period: str) -> dict[str, Any]:
    labels = q5_rows["label"].dropna()
    row = {
        "feature": feature,
        "state_tercile": tercile,
        "period_type": period_type,
        "period": period,
        "sessions": int(session_group["session_date"].nunique()),
        "mean_rank_ic": float(session_group["rank_ic"].mean()),
        "median_rank_ic": float(session_group["rank_ic"].median()),
        "mean_q5_forward_return": float(session_group["q5_mean_return"].mean()),
        "mean_q5_minus_eligible": float(session_group["q5_minus_eligible"].mean()),
        "q5_constituent_rows": int(len(labels)),
        "adverse_5_frequency": float((labels <= -0.05).mean()) if len(labels) else np.nan,
        "adverse_10_frequency": float((labels <= -0.10).mean()) if len(labels) else np.nan,
        "downside_min": float(labels.min()) if len(labels) else np.nan,
        "downside_p01": float(labels.quantile(0.01)) if len(labels) else np.nan,
        "downside_p05": float(labels.quantile(0.05)) if len(labels) else np.nan,
        "downside_p10": float(labels.quantile(0.10)) if len(labels) else np.nan,
        "downside_p25": float(labels.quantile(0.25)) if len(labels) else np.nan,
        "conditional_mean_below_5": float(labels.loc[labels <= -0.05].mean()) if (labels <= -0.05).any() else np.nan,
        "conditional_mean_below_10": float(labels.loc[labels <= -0.10].mean()) if (labels <= -0.10).any() else np.nan,
        "official_denominator_min": int(session_group["official_denominator"].min()) if len(session_group) else 0,
        "feature_usable_mean": float(session_group["feature_usable_count"].mean()) if len(session_group) else np.nan,
        "joint_eligible_mean": float(session_group["joint_eligible_count"].mean()) if len(session_group) else np.nan,
        "label_available_mean": float(session_group["label_available_count"].mean()) if len(session_group) else np.nan,
    }
    return row


def conditional_diagnostics(sessions: pd.DataFrame, rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sessions = sessions.loc[sessions["outcome_population"]].copy()
    rows = rows.loc[rows["session_date"].isin(sessions["session_date"])].copy()
    overall = []
    yearly = []
    offsets = []
    assignments = []
    for feature in ALL_FEATURES:
        tercile = assign_tercile(sessions[feature])
        session_work = sessions.copy()
        session_work["state_tercile"] = tercile
        state_map = session_work.set_index("session_date")["state_tercile"]
        row_work = rows.loc[rows["is_q5_joint"]].copy()
        row_work["state_tercile"] = row_work["session_date"].map(state_map).astype("Int64")
        assignments.extend(
            {"session_date": date, "feature": feature, "state_tercile": value}
            for date, value in zip(session_work["session_date"], session_work["state_tercile"])
        )
        for state_tercile in [1, 2, 3]:
            sg = session_work.loc[session_work["state_tercile"].eq(state_tercile)]
            rg = row_work.loc[row_work["state_tercile"].eq(state_tercile)]
            overall.append(_summary_row(feature, state_tercile, sg, rg, "overall", "all"))
            for year, year_sessions in sg.groupby("year", sort=True):
                year_rows = rg.loc[rg["session_date"].dt.year.eq(year)]
                yearly.append(_summary_row(feature, state_tercile, year_sessions, year_rows, "calendar_year", str(year)))
            for offset, offset_sessions in sg.groupby("offset", sort=True):
                offset_rows = rg.loc[rg["session_date"].map(sessions.set_index("session_date")["offset"]).eq(offset)]
                offsets.append(_summary_row(feature, state_tercile, offset_sessions, offset_rows, "non_overlapping_offset", str(offset)))
    return pd.DataFrame(overall), pd.DataFrame(yearly), pd.DataFrame(offsets), pd.DataFrame(assignments)


def bootstrap_uncertainty(config: dict[str, Any], sessions: pd.DataFrame, assignments: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = []
    difference_rows = []
    confidence = config["confidence_level"]
    for feature_index, feature in enumerate(ALL_FEATURES):
        mapping = assignments.loc[assignments["feature"].eq(feature)].set_index("session_date")["state_tercile"]
        work = sessions.loc[sessions["session_date"].isin(mapping.index), ["session_date", "rank_ic", "q5_mean_return", "q5_minus_eligible"]].copy()
        work["state_tercile"] = work["session_date"].map(mapping).astype("Int64")
        work = work.sort_values("session_date").reset_index(drop=True)
        indices = moving_block_indices(len(work), config["bootstrap_block_sessions"], config["bootstrap_samples"], config["seed"] + feature_index)
        boot: dict[tuple[int, str], list[float]] = {(tercile, metric): [] for tercile in [1, 2, 3] for metric in ["rank_ic", "q5_mean_return", "q5_minus_eligible"]}
        differences: dict[str, list[float]] = {"rank_ic": [], "q5_minus_eligible": []}
        for index in indices:
            sample = work.iloc[index]
            means: dict[tuple[int, str], float] = {}
            for tercile in [1, 2, 3]:
                group = sample.loc[sample["state_tercile"].eq(tercile)]
                for metric in ["rank_ic", "q5_mean_return", "q5_minus_eligible"]:
                    value = float(group[metric].mean()) if len(group) else np.nan
                    boot[(tercile, metric)].append(value)
                    means[(tercile, metric)] = value
            for metric in differences:
                differences[metric].append(means[(3, metric)] - means[(1, metric)])
        for (tercile, metric), values in boot.items():
            low, high = percentile_interval(values, confidence)
            output.append({"feature": feature, "state_tercile": tercile, "metric": metric, "ci_low": low, "ci_high": high, "samples": config["bootstrap_samples"], "block_sessions": config["bootstrap_block_sessions"]})
        diff_row = {"feature": feature}
        for metric, values in differences.items():
            low, high = percentile_interval(values, confidence)
            point = float(work.loc[work["state_tercile"].eq(3), metric].mean() - work.loc[work["state_tercile"].eq(1), metric].mean())
            diff_row[f"{metric}_t3_minus_t1"] = point
            diff_row[f"{metric}_ci_low"] = low
            diff_row[f"{metric}_ci_high"] = high
        ic_flag = (diff_row["rank_ic_ci_low"] > 0 or diff_row["rank_ic_ci_high"] < 0) and abs(diff_row["rank_ic_t3_minus_t1"]) >= 0.02
        excess_flag = (diff_row["q5_minus_eligible_ci_low"] > 0 or diff_row["q5_minus_eligible_ci_high"] < 0) and abs(diff_row["q5_minus_eligible_t3_minus_t1"]) >= 0.005
        diff_row["conditional_heterogeneity_flag"] = bool(ic_flag or excess_flag)
        difference_rows.append(diff_row)
    return pd.DataFrame(output), pd.DataFrame(difference_rows)


def drawdown_contributions(episodes: pd.DataFrame, pivot: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    nav_returns = pd.DataFrame(index=pivot.index)
    nav_returns["q5_log_return"] = np.log(pivot["q5"]).diff()
    nav_returns["benchmark_log_return"] = np.log(pivot["eligible_universe_benchmark"]).diff()
    nav_returns["relative_log_return"] = np.log(pivot["relative_wealth"]).diff()
    output = []
    absolute = episodes.loc[episodes["episode_type"].eq("absolute_q5")]
    for episode in absolute.itertuples(index=False):
        window = nav_returns.loc[episode.peak_date:episode.trough_date].copy()
        for feature in ALL_FEATURES:
            mapping = assignments.loc[assignments["feature"].eq(feature)].set_index("session_date")["state_tercile"]
            window["state_tercile"] = window.index.map(mapping)
            negative_total = float((-window["q5_log_return"].clip(upper=0.0)).sum())
            for tercile in [1, 2, 3]:
                group = window.loc[window["state_tercile"].eq(tercile)]
                negative = float((-group["q5_log_return"].clip(upper=0.0)).sum())
                output.append(
                    {
                        "episode_rank": int(episode.episode_rank),
                        "feature": feature,
                        "state_tercile": tercile,
                        "sessions": int(len(group)),
                        "q5_log_return_sum": float(group["q5_log_return"].sum()),
                        "benchmark_log_return_sum": float(group["benchmark_log_return"].sum()),
                        "relative_log_return_sum": float(group["relative_log_return"].sum()),
                        "q5_negative_magnitude": negative,
                        "q5_negative_magnitude_share": negative / negative_total if negative_total > 0 else np.nan,
                    }
                )
    return pd.DataFrame(output)


def build_verdicts(wig_validation: dict[str, Any], coverage_gate: pd.DataFrame, differences: pd.DataFrame, classifications: pd.DataFrame, logical_match: bool | None = None) -> dict[str, Any]:
    wig_status = "PASS" if wig_validation["status"] == "PASS" else "FAIL"
    block_gate = coverage_gate.loc[coverage_gate["feature"].isin(BLOCK_FEATURES)]
    if block_gate["status"].eq("FAIL").any():
        causality = "FAIL"
    elif block_gate["status"].eq("PASS").all():
        causality = "PASS"
    else:
        causality = "NOT PROVEN"
    valid = block_gate.loc[block_gate["status"].eq("PASS"), "feature"]
    flag_count = int(differences.loc[differences["feature"].isin(valid), "conditional_heterogeneity_flag"].sum())
    selected_episode_count = int(classifications[["episode_type", "episode_rank"]].drop_duplicates().shape[0])
    useful = classifications.loc[classifications["classification"].isin(["leading", "early-contemporaneous"])]
    useful_episode_count = int(useful[["episode_type", "episode_rank"]].drop_duplicates().shape[0])
    half_features = len(valid) > 0 and flag_count >= int(np.ceil(len(valid) / 2.0))
    half_episodes = selected_episode_count > 0 and useful_episode_count >= int(np.ceil(selected_episode_count / 2.0))
    counterexamples = classifications["classification"].eq("uninformative").any()
    if wig_status != "PASS" or causality != "PASS":
        association = "NOT PROVEN"
        attribution = "NOT PROVEN"
    elif half_features and half_episodes and not counterexamples:
        association = "MARKET-STATE ASSOCIATION SUPPORTED"
        attribution = "SUPPORTED"
    elif flag_count > 0 or useful_episode_count > 0:
        association = "MIXED"
        attribution = "MIXED"
    else:
        association = "NOT SUPPORTED"
        attribution = "NOT SUPPORTED"
    corr_lead = block_gate.loc[block_gate["feature"].isin(["top60_average_pairwise_correlation_60", "top60_positive_leadership_share_20"])]
    other = block_gate.loc[~block_gate["feature"].isin(corr_lead["feature"])]
    if block_gate["status"].eq("PASS").all():
        frozen_block = "READY WITH CAVEATS"  # candidate-panel and price-only caveats are mandatory.
    elif other["status"].eq("PASS").all() and corr_lead["status"].isin(["PASS", "NOT PROVEN"]).all():
        frozen_block = "READY WITH CAVEATS"
    else:
        frozen_block = "NOT READY"
    safe = wig_status == "PASS" and causality == "PASS" and frozen_block in {"READY", "READY WITH CAVEATS"} and logical_match is True
    return {
        "wig_extension_input_validity": wig_status,
        "market_state_feature_causality_and_coverage": causality,
        "q5_drawdown_attribution": attribution,
        "market_state_association": association,
        "frozen_phase_d_market_state_block": frozen_block,
        "safe_to_proceed_phase_d0_d1": "YES" if safe else "NO",
        "valid_block_features": valid.tolist(),
        "conditional_heterogeneity_flag_count": flag_count,
        "valid_feature_count": int(len(valid)),
        "useful_episode_count": useful_episode_count,
        "selected_episode_count": selected_episode_count,
        "counterexamples_retained": bool(counterexamples),
        "reproduction_logical_match": logical_match,
    }


def write_frame(path: Path, frame: pd.DataFrame, sort_by: list[str]) -> dict[str, Any]:
    work = frame.sort_values(sort_by, kind="mergesort").reset_index(drop=True) if sort_by else frame.reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        work.to_parquet(path, index=False, compression="zstd")
    else:
        work.to_csv(path, index=False, lineterminator="\n", float_format="%.17g")
    return {"path": path.name, "rows": int(len(work)), "bytes": path.stat().st_size, "sha256": sha256_file(path), "logical_hash": stable_frame_hash(work, sort_by)}


def environment_state() -> dict[str, Any]:
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    git_status = subprocess.check_output(["git", "status", "--short"], cwd=REPO, text=True).splitlines()
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "pyarrow": pyarrow.__version__,
        "scipy": scipy.__version__,
        "git_head": git_head,
        "git_status": git_status,
    }


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    run_id = config["reproduction_run_id"] if args.reproduction else config["run_id"]
    final_dir = args.output_root / run_id
    if final_dir.exists():
        raise FileExistsError(f"Immutable output already exists: {final_dir}")
    staging_root = args.output_root.parent / "staging"
    staging = staging_root / f"{run_id}.{os.getpid()}"
    staging.mkdir(parents=True, exist_ok=False)
    tables = staging / "tables"
    tables.mkdir()

    input_manifest = verify_inputs(config)
    candidate = pd.read_parquet(input_path(config, "candidate_panel"))
    official_dates = pd.DatetimeIndex(candidate.loc[candidate["official_membership"].fillna(False), "session_date"].sort_values().unique())
    local_wig = read_stooq_wig(input_path(config, "wig_local_source"))
    accepted_wig = pd.read_parquet(input_path(config, "accepted_phase_a_wig"))
    wig_validation, wig_overlap = validate_wig(local_wig, accepted_wig, official_dates, config["wig_overlap_rtol"], config["wig_overlap_atol"])
    if wig_validation["status"] != "PASS":
        raise RuntimeError("WIG validation failed closed")
    decision_dates = official_dates
    state, top60_coverage = attach_state_features(config, local_wig, candidate, decision_dates)
    coverage_gate = feature_coverage_gate(config, state, top60_coverage)

    nav = pd.read_csv(input_path(config, "accepted_v4_composite_nav"), parse_dates=["session_date"])
    episodes, nav_pivot = select_episodes(nav)
    episode_anchors, episode_classifications = attribute_episodes(episodes, state, pd.DatetimeIndex(nav_pivot.index))

    adapted = pd.read_parquet(input_path(config, "accepted_adapted_panel"))
    proximity_sessions, proximity_rows = prepare_proximity_sessions(config, adapted, state)
    conditional_summary, conditional_yearly, conditional_offsets, assignments = conditional_diagnostics(proximity_sessions, proximity_rows)
    uncertainty, differences = bootstrap_uncertainty(config, proximity_sessions, assignments)
    drawdown_contribution = drawdown_contributions(episodes, nav_pivot, assignments)
    verdicts = build_verdicts(wig_validation, coverage_gate, differences, episode_classifications, logical_match=None)

    # WIG-only features have denominator 1 and no member exclusions; retain them in long coverage.
    wig_coverage_rows = []
    for row in state.itertuples(index=False):
        for feature in WIG_FEATURES:
            valid = pd.notna(getattr(row, feature))
            wig_coverage_rows.append(
                {
                    "decision_session": row.decision_session,
                    "information_session": row.information_session,
                    "feature": feature,
                    "official_denominator": 1,
                    "usable_count": int(valid),
                    "excluded_count": int(not valid),
                    "excluded_member_states": "" if valid else "WIG:lookback_unavailable",
                    "feature_valid": bool(valid),
                    "feature_missing_state": "" if valid else "lookback_unavailable",
                    "aggregation_denominator": int(valid),
                    "lag10_aggregation_denominator": np.nan,
                    "unavailable_members_in_aggregation": 0,
                    "positive_observation_count": np.nan,
                }
            )
    all_coverage = pd.concat([pd.DataFrame(wig_coverage_rows), top60_coverage], ignore_index=True)

    feature_definitions = {
        "schema_version": "ats.pre_phase_d_market_state.feature_definitions.v1",
        "analysis_plan_sha256": sha256_file(HERE / "analysis_plan.md"),
        "config_sha256": sha256_file(args.config),
        "v2_correction_plan_sha256": sha256_file(HERE / "v2_correction_plan.md"),
        "plan_freeze_v2_sha256": sha256_file(HERE / "plan_freeze_v2.json"),
        "code_sha256": {"run_diagnostic.py": sha256_file(Path(__file__)), "market_state.py": sha256_file(HERE / "market_state.py")},
        "block_features": BLOCK_FEATURES,
        "optional_features": OPTIONAL_FEATURES,
        "adverse_low_features": sorted(ADVERSE_LOW),
        "dispersion_definition": config["dispersion_definition"],
        "leadership_positive_name_count": config["leadership_positive_name_count"],
        "volatility_ratio_centered": config["volatility_ratio_centered"],
        "outcome_tercile_population": config["outcome_tercile_population"],
    }

    artifacts: dict[str, Any] = {}
    artifacts["input_manifest.csv"] = write_frame(tables / "input_manifest.csv", input_manifest, ["role"])
    validated_wig = local_wig.loc[local_wig["session_date"] <= official_dates.max()].copy()
    artifacts["validated_wig.parquet"] = write_frame(tables / "validated_wig.parquet", validated_wig, ["session_date"])
    artifacts["wig_overlap_reconciliation.csv"] = write_frame(tables / "wig_overlap_reconciliation.csv", wig_overlap, ["session_date"])
    artifacts["market_state_features.parquet"] = write_frame(tables / "market_state_features.parquet", state, ["decision_session"])
    artifacts["market_state_coverage.csv"] = write_frame(tables / "market_state_coverage.csv", all_coverage, ["decision_session", "feature"])
    artifacts["feature_coverage_gate.csv"] = write_frame(tables / "feature_coverage_gate.csv", coverage_gate, ["feature"])
    artifacts["episodes.csv"] = write_frame(tables / "episodes.csv", episodes, ["episode_type", "episode_rank"])
    artifacts["episode_state_anchors.csv"] = write_frame(tables / "episode_state_anchors.csv", episode_anchors, ["episode_type", "episode_rank", "feature", "decision_session", "anchor"])
    artifacts["episode_classifications.csv"] = write_frame(tables / "episode_classifications.csv", episode_classifications, ["episode_type", "episode_rank", "feature"])
    artifacts["proximity_session_diagnostics.csv"] = write_frame(tables / "proximity_session_diagnostics.csv", proximity_sessions[[column for column in proximity_sessions.columns if column not in ALL_FEATURES]], ["session_date"])
    artifacts["state_tercile_assignments.csv"] = write_frame(tables / "state_tercile_assignments.csv", assignments, ["feature", "session_date"])
    artifacts["conditional_summary.csv"] = write_frame(tables / "conditional_summary.csv", conditional_summary, ["feature", "state_tercile"])
    artifacts["conditional_yearly.csv"] = write_frame(tables / "conditional_yearly.csv", conditional_yearly, ["feature", "state_tercile", "period"])
    artifacts["conditional_offsets.csv"] = write_frame(tables / "conditional_offsets.csv", conditional_offsets, ["feature", "state_tercile", "period"])
    artifacts["block_uncertainty.csv"] = write_frame(tables / "block_uncertainty.csv", uncertainty, ["feature", "state_tercile", "metric"])
    artifacts["tercile_differences.csv"] = write_frame(tables / "tercile_differences.csv", differences, ["feature"])
    artifacts["drawdown_contribution.csv"] = write_frame(tables / "drawdown_contribution.csv", drawdown_contribution, ["episode_rank", "feature", "state_tercile"])

    (staging / "wig_validation.json").write_text(json.dumps(wig_validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (staging / "feature_definitions.json").write_text(json.dumps(feature_definitions, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (staging / "environment_git.json").write_text(json.dumps(environment_state(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    commands = {
        "primary": f"D:/Stock/ATS/RESEARCH/environment/invoke_ats_python.ps1 D:/Stock/ATS/RESEARCH/prototypes/pre_phase_d_market_state/run_diagnostic.py --config {args.config.resolve().as_posix()}",
        "reproduction": f"D:/Stock/ATS/RESEARCH/environment/invoke_ats_python.ps1 D:/Stock/ATS/RESEARCH/prototypes/pre_phase_d_market_state/run_diagnostic.py --config {args.config.resolve().as_posix()} --reproduction",
        "tests": "D:/Stock/ATS/RESEARCH/environment/invoke_ats_python.ps1 -m pytest -q D:/Stock/ATS/RESEARCH/prototypes/pre_phase_d_market_state/tests",
        "tests_working_directory": "D:/Stock/ATS",
    }
    (staging / "commands.json").write_text(json.dumps(commands, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.copy2(HERE / "analysis_plan.md", staging / "analysis_plan.md")
    shutil.copy2(HERE / "v2_correction_plan.md", staging / "v2_correction_plan.md")
    shutil.copy2(args.config, staging / "config.json")
    shutil.copy2(HERE / "plan_freeze_v2.json", staging / "plan_freeze_v2.json")

    logical_payload = {name: item["logical_hash"] for name, item in sorted(artifacts.items())}
    logical_hash = hashlib.sha256(stable_json(logical_payload).encode("utf-8")).hexdigest()
    summary = {
        "schema_version": "ats.pre_phase_d_market_state.summary.v1",
        "logical_run_id": config["run_id"],
        "physical_run_id": run_id,
        "logical_payload_hash": logical_hash,
        "feature_rows": int(len(state)),
        "feature_min_decision_session": state["decision_session"].min().date().isoformat(),
        "feature_max_decision_session": state["decision_session"].max().date().isoformat(),
        "coverage_sessions": int(proximity_sessions["session_date"].nunique()),
        "outcome_diagnostic_sessions": int(proximity_sessions["outcome_population"].sum()),
        "right_censored_sessions_excluded_from_outcome_terciles": int((~proximity_sessions["outcome_population"]).sum()),
        "diagnostic_min_session": proximity_sessions.loc[proximity_sessions["outcome_population"], "session_date"].min().date().isoformat(),
        "diagnostic_max_session": proximity_sessions.loc[proximity_sessions["outcome_population"], "session_date"].max().date().isoformat(),
        "verdicts": verdicts,
    }
    (staging / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_files = {}
    for path in sorted(staging.rglob("*")):
        if path.is_file():
            relative = path.relative_to(staging).as_posix()
            manifest_files[relative] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    manifest = {
        "schema_version": "ats.pre_phase_d_market_state.manifest.v1",
        "logical_run_id": config["run_id"],
        "physical_run_id": run_id,
        "logical_payload_hash": logical_hash,
        "artifacts": artifacts,
        "files": manifest_files,
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_root.mkdir(parents=True, exist_ok=True)
    os.replace(staging, final_dir)
    print(json.dumps({"run_dir": final_dir.as_posix(), "logical_payload_hash": logical_hash, "verdicts": verdicts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
