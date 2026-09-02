from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from typing import Any

import numpy as np
import pandas as pd


COMPARATORS = ("C_LINEAR", "C_LIGHTGBM")


def require_identical_population(left: pd.DataFrame, right: pd.DataFrame) -> None:
    keys = ["security_id", "decision_session"]
    if set(keys) - set(left.columns) or set(keys) - set(right.columns):
        raise ValueError("population comparison lacks semantic keys")
    left_keys = left[keys].sort_values(keys, kind="mergesort").reset_index(drop=True)
    right_keys = right[keys].sort_values(keys, kind="mergesort").reset_index(drop=True)
    if not left_keys.equals(right_keys):
        raise ValueError("ablation or model populations differ")


def spearman_ic(scores: Iterable[float], labels: Iterable[float], *, minimum_rows: int = 45) -> float:
    frame = pd.DataFrame({"score": scores, "label": labels}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < minimum_rows or frame["score"].nunique() < 2 or frame["label"].nunique() < 2:
        return math.nan
    return float(frame["score"].rank(method="average").corr(frame["label"].rank(method="average")))


def fractional_boundary_weights(scores: Iterable[float], k: int) -> np.ndarray:
    values = np.asarray(list(scores), dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all() or k < 0:
        raise ValueError("frequency matching requires finite one-dimensional scores and k >= 0")
    if k == 0:
        return np.zeros(len(values), dtype=float)
    if k >= len(values):
        return np.ones(len(values), dtype=float)
    boundary = float(np.partition(values, len(values) - k)[len(values) - k])
    above = values > boundary
    equal = values == boundary
    fraction = (k - int(above.sum())) / int(equal.sum())
    result = above.astype(float) + equal.astype(float) * fraction
    if not np.isclose(result.sum(), float(k), rtol=0.0, atol=1e-12):
        raise AssertionError("fractional boundary weights do not sum exactly to k")
    return result


def weighted_mean(values: Iterable[float], weights: Iterable[float]) -> float:
    x = np.asarray(list(values), dtype=float)
    w = np.asarray(list(weights), dtype=float)
    valid = np.isfinite(x) & np.isfinite(w) & (w > 0.0)
    return float(np.average(x[valid], weights=w[valid])) if valid.any() else math.nan


def weighted_quantile(values: Iterable[float], weights: Iterable[float], q: float) -> float:
    if not 0.0 <= q <= 1.0:
        raise ValueError("weighted quantile requires q in [0,1]")
    frame = pd.DataFrame({"value": values, "weight": weights}).replace([np.inf, -np.inf], np.nan).dropna()
    frame = frame.loc[frame["weight"].gt(0.0)]
    if frame.empty:
        return math.nan
    combined = frame.groupby("value", sort=True, as_index=False)["weight"].sum()
    target = q * float(combined["weight"].sum())
    index = int(np.searchsorted(combined["weight"].cumsum().to_numpy(), target, side="left"))
    return float(combined.iloc[min(index, len(combined) - 1)]["value"])


def episode_anchor_flags(candidates: pd.DataFrame, calendar: Iterable[object], *, horizon: int = 20) -> pd.DataFrame:
    required = {"security_id", "decision_session", "candidate"}
    if required - set(candidates.columns):
        raise ValueError("episode input lacks semantic candidate columns")
    dates = pd.DatetimeIndex(pd.to_datetime(list(calendar))).normalize().sort_values().unique()
    position = {date: number for number, date in enumerate(dates)}
    working = candidates[["security_id", "decision_session", "candidate"]].copy()
    working["decision_session"] = pd.to_datetime(working["decision_session"]).dt.normalize()
    working = working.sort_values(["security_id", "decision_session"], kind="mergesort")
    working["episode_anchor"] = False
    working["episode_number"] = pd.array([pd.NA] * len(working), dtype="Int64")
    for _, indices in working.groupby("security_id", sort=False).groups.items():
        prior_signal: int | None = None
        episode = 0
        for index in indices:
            if not bool(working.at[index, "candidate"]):
                continue
            current = position.get(pd.Timestamp(working.at[index, "decision_session"]))
            if current is None:
                raise ValueError("candidate session is absent from official calendar")
            if prior_signal is None or current - prior_signal > horizon:
                episode += 1
                working.at[index, "episode_anchor"] = True
            working.at[index, "episode_number"] = episode
            prior_signal = current
    return working.sort_values(["decision_session", "security_id"], kind="mergesort").reset_index(drop=True)


def circular_bootstrap_indices(n: int, *, samples: int = 5000, block: int = 20, seed: int = 20260831) -> np.ndarray:
    if n <= 0 or samples <= 0 or block <= 0:
        raise ValueError("bootstrap dimensions must be positive")
    rng = np.random.Generator(np.random.PCG64(seed))
    starts = rng.integers(0, n, size=(samples, math.ceil(n / block)))
    offsets = np.arange(block)
    return ((starts[:, :, None] + offsets) % n).reshape(samples, -1)[:, :n]


def bootstrap_vector(values: np.ndarray, indices: np.ndarray, reducer: Callable[[np.ndarray], float] | None = None) -> dict[str, Any]:
    vector = np.asarray(values, dtype=float)
    reduce = reducer or (lambda value: float(np.nanmean(value)) if np.isfinite(value).any() else math.nan)
    estimates = np.asarray([reduce(vector[index]) for index in indices], dtype=float)
    defined = np.isfinite(estimates)
    fraction = float(defined.mean())
    if fraction < 0.99:
        return {"status": "NOT PROVEN", "defined_fraction": fraction, "lower": None, "upper": None}
    valid = estimates[defined]
    return {
        "status": "PASS",
        "defined_fraction": fraction,
        "lower": float(np.quantile(valid, 0.025, method="linear")),
        "upper": float(np.quantile(valid, 0.975, method="linear")),
    }


def bootstrap_episode_median(anchor_values: Mapping[pd.Timestamp, np.ndarray], sessions: pd.DatetimeIndex, indices: np.ndarray) -> dict[str, Any]:
    values: list[float] = []
    for sample in indices:
        pieces = [anchor_values.get(pd.Timestamp(sessions[index]), np.empty(0)) for index in sample]
        merged = np.concatenate(pieces) if pieces else np.empty(0)
        values.append(float(np.median(merged)) if len(merged) else math.nan)
    return bootstrap_vector(np.asarray(values), np.arange(len(values))[:, None], reducer=lambda x: float(x[0]))


def choose_model_family(statistics: Mapping[str, float], linear: str, tree: str, *, tie: float = 0.002) -> dict[str, Any]:
    left = float(statistics.get(linear, math.nan))
    right = float(statistics.get(tree, math.nan))
    if not np.isfinite(left) or not np.isfinite(right):
        return {"selected": None, "status": "NOT PROVEN", "absolute_difference": None, "ridge_tie_rule_applied": False}
    difference = abs(left - right)
    selected = linear if difference <= tie or left > right else tree
    return {
        "selected": selected,
        "status": "PASS",
        "absolute_difference": difference,
        "ridge_tie_rule_applied": difference <= tie,
    }


def wide_prediction_frame(predictions: pd.DataFrame, masks: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    keys = ["block_id", "security_id", "decision_session"]
    score = predictions.pivot(index=keys, columns="cell_id", values="model_score").add_prefix("score__")
    candidate = predictions.pivot(index=keys, columns="cell_id", values="candidate").add_prefix("candidate__")
    wide = score.join(candidate).reset_index()
    mask_columns = [
        "block_id", "security_id", "decision_session", "model_score_eligible",
        "proximity_to_max_high_252", "scored_count", "excluded_count",
    ]
    wide = wide.merge(masks[mask_columns], on=keys, how="left", validate="one_to_one")
    label_columns = [
        column for column in labels.columns
        if column not in {"label_start_open"} and not column.startswith("label_endpoint_open_")
    ]
    wide = wide.merge(
        labels[label_columns], on=["security_id", "decision_session"], how="left", validate="many_to_one"
    )
    return wide.sort_values(["decision_session", "security_id"], kind="mergesort").reset_index(drop=True)


def session_ic_table(wide: pd.DataFrame, cells: Iterable[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for session, group in wide.groupby("decision_session", sort=True):
        record: dict[str, Any] = {
            "decision_session": session,
            "outcome_rows": int(np.isfinite(group["label__open_to_open__20"]).sum()),
        }
        for cell in cells:
            record[f"ic__{cell}"] = spearman_ic(group[f"score__{cell}"], group["label__open_to_open__20"])
        rows.append(record)
    return pd.DataFrame(rows)


def _status(value: float | int | None, operator: str, threshold: float | int, *, exclusive: bool = False) -> str:
    if value is None or not np.isfinite(float(value)):
        return "NOT PROVEN"
    if operator == "min":
        passed = value > threshold if exclusive else value >= threshold
    elif operator == "max":
        passed = value < threshold if exclusive else value <= threshold
    else:
        raise ValueError(operator)
    return "PASS" if passed else "FAIL"


def gate(name: str, category: str, value: Any, operator: str, threshold: Any, *, population: str, comparator: str | None = None, exclusive: bool = False) -> dict[str, Any]:
    return {
        "gate_id": name,
        "category": category,
        "population": population,
        "comparator": comparator,
        "value": value,
        "operator": (">" if operator == "min" else "<") if exclusive else (">=" if operator == "min" else "<="),
        "threshold": threshold,
        "status": _status(value, operator, threshold, exclusive=exclusive),
    }


def _tail_sessions(wide: pd.DataFrame, selected_rich: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    anchors = wide.loc[wide["episode_anchor"] & np.isfinite(wide["label__open_to_open__20"])].copy()
    rows: list[dict[str, Any]] = []
    hurdle = 0.01
    for session, group in wide.groupby("decision_session", sort=True):
        eligible = group.loc[np.isfinite(group["label__open_to_open__20"])].copy()
        rich = anchors.loc[anchors["decision_session"].eq(session)]
        record: dict[str, Any] = {"decision_session": session, "anchor_count": len(rich)}
        if rich.empty or eligible.empty:
            for name in (
                "rich_mean", "eligible_mean", "rich_minus_eligible", "rich_severe_rate",
                "rich_hit_rate", "rich_median",
            ):
                record[name] = math.nan
            for comparator in COMPARATORS:
                for name in ("matched_mean", "rich_minus", "severe_difference", "matched_hit_rate", "matched_median"):
                    record[f"{name}__{comparator}"] = math.nan
            rows.append(record)
            continue
        labels = rich["label__open_to_open__20"].to_numpy(dtype=float)
        record["rich_mean"] = float(labels.mean())
        record["rich_median"] = float(np.median(labels))
        record["eligible_mean"] = float(eligible["label__open_to_open__20"].mean())
        record["rich_minus_eligible"] = record["rich_mean"] - record["eligible_mean"]
        record["rich_severe_rate"] = float((labels <= -0.10).mean())
        record["rich_hit_rate"] = float((labels > hurdle).mean())
        for comparator in COMPARATORS:
            weights = fractional_boundary_weights(eligible[f"score__{comparator}"], len(rich))
            outcomes = eligible["label__open_to_open__20"].to_numpy(dtype=float)
            matched_mean = weighted_mean(outcomes, weights)
            matched_severe = weighted_mean((outcomes <= -0.10).astype(float), weights)
            record[f"matched_mean__{comparator}"] = matched_mean
            record[f"rich_minus__{comparator}"] = record["rich_mean"] - matched_mean
            record[f"severe_difference__{comparator}"] = record["rich_severe_rate"] - matched_severe
            record[f"matched_hit_rate__{comparator}"] = weighted_mean((outcomes > hurdle).astype(float), weights)
            record[f"matched_median__{comparator}"] = weighted_quantile(outcomes, weights, 0.5)
        rows.append(record)
    return pd.DataFrame(rows), anchors


def _concentration(wide: pd.DataFrame, anchors: pd.DataFrame, tail: pd.DataFrame, sessions: pd.DatetimeIndex) -> dict[str, Any]:
    counts = anchors.groupby("security_id").size().astype(float)
    total = float(counts.sum())
    shares = counts / total if total else counts
    chunks = np.array_split(sessions.to_numpy(), 4)
    quartile_counts = [int(anchors["decision_session"].isin(values).sum()) for values in chunks]
    eligible_mean = tail.set_index("decision_session")["eligible_mean"]
    contributions = anchors.assign(
        contribution=anchors["label__open_to_open__20"] - anchors["decision_session"].map(eligible_mean)
    ).groupby("security_id")["contribution"].sum().abs().sort_values(ascending=False)
    if len(contributions) >= 5:
        boundary = float(contributions.iloc[4])
        boundary_set = sorted(contributions.loc[contributions.ge(boundary)].index.astype(str))
    else:
        boundary = math.nan
        boundary_set = sorted(contributions.index.astype(str))
    return {
        "episode_count": int(total),
        "distinct_securities": int(len(counts)),
        "largest_security_episode_share": float(shares.max()) if total else math.nan,
        "top5_security_episode_share": float(shares.nlargest(5).sum()) if total else math.nan,
        "security_episode_hhi": float(shares.pow(2).sum()) if total else math.nan,
        "chronological_quartile_episode_counts": quartile_counts,
        "largest_chronological_quartile_share": max(quartile_counts) / total if total else math.nan,
        "top_contribution_boundary": boundary,
        "top_contribution_boundary_set": boundary_set,
    }


def evaluate_population(
    predictions: pd.DataFrame,
    masks: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    block_ids: list[str],
    selected_rich: str,
    contract: Mapping[str, Any],
    population_name: str,
) -> dict[str, Any]:
    all_wide = wide_prediction_frame(predictions, masks, labels)
    rich_history = predictions.loc[predictions["cell_id"].eq(selected_rich), ["security_id", "decision_session", "candidate"]]
    calendar = pd.DatetimeIndex(sorted(masks["decision_session"].unique()))
    anchor_flags = episode_anchor_flags(rich_history, calendar)
    wide = all_wide.loc[all_wide["block_id"].isin(block_ids)].merge(
        anchor_flags[["security_id", "decision_session", "episode_anchor", "episode_number"]],
        on=["security_id", "decision_session"], how="left", validate="one_to_one",
    )
    wide["episode_anchor"] = wide["episode_anchor"].fillna(False)
    sessions = pd.DatetimeIndex(sorted(wide["decision_session"].unique()))
    cells = [*COMPARATORS, selected_rich, "RICH_NO_M_LIGHTGBM"]
    ic = session_ic_table(wide, cells)
    for comparator in COMPARATORS:
        ic[f"delta__{comparator}"] = ic[f"ic__{selected_rich}"] - ic[f"ic__{comparator}"]
    tail, anchors = _tail_sessions(wide, selected_rich)
    bootstrap_indices = circular_bootstrap_indices(len(sessions))
    delta_bootstrap = {
        comparator: bootstrap_vector(ic[f"delta__{comparator}"].to_numpy(dtype=float), bootstrap_indices)
        for comparator in COMPARATORS
    }
    tail_bootstrap: dict[str, Any] = {
        "rich_minus_eligible": bootstrap_vector(tail["rich_minus_eligible"].to_numpy(dtype=float), bootstrap_indices),
    }
    for comparator in COMPARATORS:
        tail_bootstrap[f"rich_minus__{comparator}"] = bootstrap_vector(
            tail[f"rich_minus__{comparator}"].to_numpy(dtype=float), bootstrap_indices
        )
        tail_bootstrap[f"severe_difference__{comparator}"] = bootstrap_vector(
            tail[f"severe_difference__{comparator}"].to_numpy(dtype=float), bootstrap_indices
        )
    by_session = {
        pd.Timestamp(session): group["label__open_to_open__20"].to_numpy(dtype=float)
        for session, group in anchors.groupby("decision_session", sort=False)
    }
    tail_bootstrap["rich_episode_median"] = bootstrap_episode_median(by_session, sessions, bootstrap_indices)
    raw_candidates = int(wide[f"candidate__{selected_rich}"].sum())
    raw_anchors = wide.loc[wide["episode_anchor"]]
    scored_rows = len(wide)
    outcome_rows = int(np.isfinite(wide["label__open_to_open__20"]).sum())
    evaluable_anchors = len(anchors)
    anchor_evaluable_fraction = evaluable_anchors / len(raw_anchors) if len(raw_anchors) else math.nan
    scored_evaluable_fraction = outcome_rows / scored_rows if scored_rows else math.nan
    defined_fraction = float(ic[f"ic__{selected_rich}"].notna().mean()) if len(ic) else math.nan
    concentration = _concentration(wide, anchors, tail, sessions)
    influence: dict[str, Any] = {}
    for security_id in concentration["top_contribution_boundary_set"]:
        reduced = wide.loc[wide["security_id"].astype(str).ne(str(security_id))].copy()
        reduced_ic = session_ic_table(reduced, [*COMPARATORS, selected_rich])
        reduced_tail, _ = _tail_sessions(reduced, selected_rich)
        influence[str(security_id)] = {
            "mean_delta_ic": {
                comparator: float(
                    (reduced_ic[f"ic__{selected_rich}"] - reduced_ic[f"ic__{comparator}"]).mean()
                ) for comparator in COMPARATORS
            },
            "rich_minus_conventional_tail": {
                comparator: float(reduced_tail[f"rich_minus__{comparator}"].mean())
                for comparator in COMPARATORS
            },
        }
    frequency_by_block: dict[str, Any] = {}
    block_metrics: dict[str, Any] = {}
    for block_id, group in wide.groupby("block_id", sort=True):
        counts = group.groupby("decision_session")[f"candidate__{selected_rich}"].sum().reindex(
            sorted(group["decision_session"].unique()), fill_value=0
        )
        block_ic = ic.loc[ic["decision_session"].isin(group["decision_session"].unique())]
        block_tail = tail.loc[tail["decision_session"].isin(group["decision_session"].unique())]
        frequency_by_block[block_id] = {
            "candidate_row_fraction": float(group[f"candidate__{selected_rich}"].mean()),
            "opportunity_session_fraction": float(counts.gt(0).mean()),
            "idle_session_fraction": float(counts.eq(0).mean()),
            "session_candidate_count_p95": float(np.quantile(counts, 0.95, method="linear")),
            "scored_rows": len(group),
            "sessions": len(counts),
        }
        block_metrics[block_id] = {
            "mean_ic": {cell: float(block_ic[f"ic__{cell}"].mean()) for cell in [*COMPARATORS, selected_rich]},
            "mean_delta_ic": {comparator: float(block_ic[f"delta__{comparator}"].mean()) for comparator in COMPARATORS},
            "rich_minus_conventional_tail": {
                comparator: float(block_tail[f"rich_minus__{comparator}"].mean()) for comparator in COMPARATORS
            },
        }
    metrics = {
        "population": population_name,
        "block_ids": block_ids,
        "selected_rich": selected_rich,
        "sessions": len(sessions),
        "scored_rows": scored_rows,
        "outcome_evaluable_rows": outcome_rows,
        "scored_row_outcome_evaluable_fraction": scored_evaluable_fraction,
        "raw_candidate_rows": raw_candidates,
        "raw_episode_anchors": len(raw_anchors),
        "outcome_evaluable_episode_anchors": evaluable_anchors,
        "rich_episode_anchor_outcome_evaluable_fraction": anchor_evaluable_fraction,
        "absolute_episode_vs_scored_evaluable_fraction_gap": abs(anchor_evaluable_fraction - scored_evaluable_fraction) if np.isfinite(anchor_evaluable_fraction) else math.nan,
        "paired_ic_defined_session_fraction": defined_fraction,
        "mean_session_ic": {cell: float(ic[f"ic__{cell}"].mean()) for cell in [*COMPARATORS, selected_rich]},
        "median_session_ic": {cell: float(ic[f"ic__{cell}"].median()) for cell in [*COMPARATORS, selected_rich]},
        "mean_delta_ic": {comparator: float(ic[f"delta__{comparator}"].mean()) for comparator in COMPARATORS},
        "relative_improvement": {
            comparator: (
                float(ic[f"delta__{comparator}"].mean()) / abs(float(ic[f"ic__{comparator}"].mean()))
                if float(ic[f"ic__{comparator}"].mean()) > 0 else None
            ) for comparator in COMPARATORS
        },
        "delta_ic_bootstrap": delta_bootstrap,
        "rich_opportunity_mean_return": float(anchors["label__open_to_open__20"].mean()),
        "rich_opportunity_median_return": float(anchors["label__open_to_open__20"].median()),
        "rich_opportunity_hit_rate_above_1pct": float(anchors["label__open_to_open__20"].gt(0.01).mean()),
        "rich_minus_eligible_mean_return": float(tail["rich_minus_eligible"].mean()),
        "rich_minus_conventional_mean_return": {
            comparator: float(tail[f"rich_minus__{comparator}"].mean()) for comparator in COMPARATORS
        },
        "severe_rate_difference": {
            comparator: float(tail[f"severe_difference__{comparator}"].mean()) for comparator in COMPARATORS
        },
        "tail_bootstrap": tail_bootstrap,
        "distinct_opportunity_sessions": int(tail["anchor_count"].gt(0).sum()),
        "distinct_opportunity_securities": int(anchors["security_id"].nunique()),
        "raw_candidate_rows_per_episode": raw_candidates / len(raw_anchors) if len(raw_anchors) else math.nan,
        "frequency_by_block": frequency_by_block,
        "block_metrics": block_metrics,
        "concentration": concentration,
        "leave_top_contributor_out": influence,
    }
    gate_rows = population_gates(metrics, contract, population_name)
    return {
        "metrics": metrics,
        "gates": gate_rows,
        "session_ic": ic,
        "tail_sessions": tail,
        "episode_anchors": anchors,
        "wide": wide,
    }


def population_gates(metrics: Mapping[str, Any], contract: Mapping[str, Any], population_name: str) -> list[dict[str, Any]]:
    decision = contract["decision_gate"]
    validity = decision["validity"]
    gates = [
        gate("scored_row_outcome_evaluable_fraction", "validity", metrics["scored_row_outcome_evaluable_fraction"], "min", validity["scored_row_outcome_evaluable_fraction_min"], population=population_name),
        gate("rich_episode_anchor_outcome_evaluable_fraction", "validity", metrics["rich_episode_anchor_outcome_evaluable_fraction"], "min", validity["rich_episode_anchor_outcome_evaluable_fraction_min"], population=population_name),
        gate("episode_vs_scored_evaluable_fraction_gap", "validity", metrics["absolute_episode_vs_scored_evaluable_fraction_gap"], "max", validity["absolute_episode_vs_scored_evaluable_fraction_gap_max"], population=population_name),
        gate("paired_ic_defined_session_fraction", "validity", metrics["paired_ic_defined_session_fraction"], "min", validity["paired_ic_defined_session_fraction_min"], population=population_name),
    ]
    incremental = decision["incremental_rank_information"]
    prefix = "development_confirmation" if population_name == "DEVELOPMENT_CONFIRMATION_2024" else "locked_evidence"
    tail_gate = decision["tail_outcome_separation"]
    for comparator in COMPARATORS:
        gates.append(gate(
            f"{prefix}_mean_delta_ic__{comparator}", "incremental_rank_information",
            metrics["mean_delta_ic"][comparator], "min",
            incremental[f"{prefix}_mean_delta_ic_min_against_each_conventional"],
            population=population_name, comparator=comparator,
        ))
        gates.append(gate(
            f"{prefix}_paired_delta_ic_lower__{comparator}", "incremental_rank_information",
            metrics["delta_ic_bootstrap"][comparator]["lower"], "min",
            incremental[f"{prefix}_paired_95pct_lower_bound_min_exclusive_against_each_conventional"],
            population=population_name, comparator=comparator, exclusive=True,
        ))
        relative = metrics["relative_improvement"][comparator]
        if metrics["mean_session_ic"][comparator] > 0:
            gates.append(gate(
                f"relative_improvement__{comparator}", "incremental_rank_information", relative, "min",
                incremental["relative_improvement_min_when_named_conventional_ic_positive"],
                population=population_name, comparator=comparator,
            ))
        gates.append(gate(
            f"rich_minus_frequency_matched_mean__{comparator}", "tail_outcome_separation",
            metrics["rich_minus_conventional_mean_return"][comparator], "min",
            tail_gate["rich_minus_each_frequency_matched_conventional_mean_return_min"],
            population=population_name, comparator=comparator,
        ))
        gates.append(gate(
            f"rich_minus_frequency_matched_lower__{comparator}", "tail_outcome_separation",
            metrics["tail_bootstrap"][f"rich_minus__{comparator}"]["lower"], "min",
            tail_gate["rich_minus_each_conventional_95pct_lower_bound_min_exclusive"],
            population=population_name, comparator=comparator, exclusive=True,
        ))
        gates.append(gate(
            f"severe_rate_difference__{comparator}", "tail_outcome_separation",
            metrics["severe_rate_difference"][comparator], "max",
            tail_gate["rich_severe_adverse_rate_minus_each_frequency_matched_conventional_max"],
            population=population_name, comparator=comparator,
        ))
        gates.append(gate(
            f"severe_rate_difference_upper__{comparator}", "tail_outcome_separation",
            metrics["tail_bootstrap"][f"severe_difference__{comparator}"]["upper"], "max",
            tail_gate["severe_rate_difference_95pct_upper_bound_max"],
            population=population_name, comparator=comparator,
        ))
    gates.extend([
        gate("rich_minus_eligible_mean", "tail_outcome_separation", metrics["rich_minus_eligible_mean_return"], "min", tail_gate["rich_opportunity_minus_eligible_mean_return_min"], population=population_name),
        gate("rich_minus_eligible_lower", "tail_outcome_separation", metrics["tail_bootstrap"]["rich_minus_eligible"]["lower"], "min", tail_gate["rich_minus_eligible_95pct_lower_bound_min_exclusive"], population=population_name, exclusive=True),
        gate("rich_episode_median", "tail_outcome_separation", metrics["rich_opportunity_median_return"], "min", tail_gate["rich_opportunity_median_return_min_exclusive"], population=population_name, exclusive=True),
        gate("rich_episode_median_lower", "tail_outcome_separation", metrics["tail_bootstrap"]["rich_episode_median"]["lower"], "min", tail_gate["rich_episode_median_95pct_lower_bound_min_exclusive"], population=population_name, exclusive=True),
    ])
    opportunity = decision["opportunity_evidence"]
    if population_name == "DEVELOPMENT_CONFIRMATION_2024":
        episode_floor = opportunity["development_confirmation_effective_security_episodes_min"]
        session_floor = opportunity["distinct_opportunity_sessions_development_confirmation_min"]
    else:
        episode_floor = opportunity["locked_evidence_effective_security_episodes_min"]
        session_floor = opportunity["distinct_opportunity_sessions_locked_evidence_min"]
    gates.extend([
        gate("effective_security_episodes", "opportunity_evidence", metrics["outcome_evaluable_episode_anchors"], "min", episode_floor, population=population_name),
        gate("distinct_opportunity_securities", "opportunity_evidence", metrics["distinct_opportunity_securities"], "min", opportunity["distinct_securities_min_in_each_required_population"], population=population_name),
        gate("distinct_opportunity_sessions", "opportunity_evidence", metrics["distinct_opportunity_sessions"], "min", session_floor, population=population_name),
        gate("raw_candidate_rows_per_episode", "opportunity_evidence", metrics["raw_candidate_rows_per_episode"], "max", opportunity["raw_candidate_rows_per_episode_max"], population=population_name),
    ])
    frequency = decision["frequency_and_abstention"]
    for block_id, values in metrics["frequency_by_block"].items():
        gates.extend([
            gate(f"candidate_row_fraction__{block_id}", "frequency_and_abstention", values["candidate_row_fraction"], "max", frequency["candidate_row_fraction_max"], population=population_name),
            gate(f"opportunity_session_fraction_min__{block_id}", "frequency_and_abstention", values["opportunity_session_fraction"], "min", frequency["opportunity_session_fraction_min"], population=population_name),
            gate(f"opportunity_session_fraction_max__{block_id}", "frequency_and_abstention", values["opportunity_session_fraction"], "max", frequency["opportunity_session_fraction_max"], population=population_name),
            gate(f"idle_session_fraction__{block_id}", "frequency_and_abstention", values["idle_session_fraction"], "min", frequency["idle_session_fraction_min"], population=population_name),
            gate(f"session_candidate_count_p95__{block_id}", "frequency_and_abstention", values["session_candidate_count_p95"], "max", frequency["session_candidate_count_p95_max"], population=population_name),
        ])
    stability = decision["chronological_stability"]
    for comparator in COMPARATORS:
        for block_id, values in metrics["block_metrics"].items():
            if population_name == "DEVELOPMENT_CONFIRMATION_2024":
                threshold = stability["each_development_block_delta_ic_min_against_each_conventional"]
                exclusive = False
            else:
                threshold = stability["each_locked_block_delta_ic_floor_against_each_conventional"]
                exclusive = False
            gates.append(gate(
                f"block_delta_ic__{block_id}__{comparator}", "chronological_stability",
                values["mean_delta_ic"][comparator], "min", threshold,
                population=population_name, comparator=comparator, exclusive=exclusive,
            ))
            if population_name != "DEVELOPMENT_CONFIRMATION_2024":
                gates.append(gate(
                    f"block_tail__{block_id}__{comparator}", "chronological_stability",
                    values["rich_minus_conventional_tail"][comparator], "min",
                    stability["each_locked_block_rich_minus_each_conventional_tail_floor"],
                    population=population_name, comparator=comparator, exclusive=True,
                ))
        if population_name == "DEVELOPMENT_CONFIRMATION_2024":
            for omitted in metrics["block_metrics"]:
                retained = [value for key, value in metrics["block_metrics"].items() if key != omitted]
                leave_value = float(np.mean([value["mean_delta_ic"][comparator] for value in retained]))
                gates.append(gate(
                    f"leave_development_block_out__{omitted}__{comparator}", "chronological_stability",
                    leave_value, "min", stability["leave_one_development_block_out_delta_ic_min_against_each_conventional"],
                    population=population_name, comparator=comparator,
                ))
    concentration = decision["concentration"]
    values = metrics["concentration"]
    gates.extend([
        gate("largest_security_episode_share", "concentration", values["largest_security_episode_share"], "max", concentration["largest_security_episode_share_max"], population=population_name),
        gate("top5_security_episode_share", "concentration", values["top5_security_episode_share"], "max", concentration["top5_security_episode_share_max"], population=population_name),
        gate("security_episode_hhi", "concentration", values["security_episode_hhi"], "max", concentration["security_episode_hhi_max"], population=population_name),
        gate("largest_chronological_quartile_share", "concentration", values["largest_chronological_quartile_share"], "max", concentration["largest_chronological_quartile_share_max"], population=population_name),
    ])
    for security_id, influence in metrics["leave_top_contributor_out"].items():
        for comparator in COMPARATORS:
            gates.append(gate(
                f"leave_security_out_delta_ic__{security_id}__{comparator}", "concentration",
                influence["mean_delta_ic"][comparator], "min",
                concentration["leave_each_top5_boundary_set_security_out_delta_ic_min_against_each_conventional"],
                population=population_name, comparator=comparator,
            ))
            gates.append(gate(
                f"leave_security_out_tail__{security_id}__{comparator}", "concentration",
                influence["rich_minus_conventional_tail"][comparator], "min",
                concentration["leave_each_top5_security_out_rich_minus_each_conventional_tail_min_exclusive"],
                population=population_name, comparator=comparator, exclusive=True,
            ))
    return gates


def mechanical_verdict(gates: Iterable[Mapping[str, Any]], *, complete: bool) -> str:
    rows = list(gates)
    if not complete or not rows:
        return "NOT PROVEN"
    validity_categories = {"validity", "execution_integrity", "reproducibility", "comparability", "leakage"}
    if any(row.get("category") in validity_categories and row.get("status") != "PASS" for row in rows):
        return "NOT PROVEN"
    if any(row.get("status") == "NOT PROVEN" for row in rows):
        return "NOT PROVEN"
    return "CONTINUE" if all(row.get("status") == "PASS" for row in rows) else "STOP"
