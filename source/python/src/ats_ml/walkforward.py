from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ats_ml.contracts import FrozenD0Contract
from ats_ml.guard import D1ExecutionGuard, ExecutionContext, Operation
from ats_ml.labels import label_endpoints
from ats_ml.matrices import build_semantic_row_ledger, cell_feature_allowlists
from ats_ml.models import LIGHTGBM_PARAMETERS, RIDGE_PARAMETERS
from ats_research.hashing import content_hash, logical_frame_hash


LOCKED_BLOCK_ORDER = ("LOCKED_2025_H1", "LOCKED_2025_H2", "LOCKED_2026_H1")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
CORE_SCORE_FEATURES = (
    "proximity_to_max_high_252",
    "momentum_12_1",
    "realized_volatility_20",
    "return_5",
)


def _ordered_calendar(values: Iterable[object]) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(list(values), errors="coerce")).normalize()
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("walk-forward calendar must be unique, valid and strictly ordered")
    return dates


def _decision_ts(session: object, timezone: str) -> pd.Timestamp:
    return pd.Timestamp(session).normalize().tz_localize(timezone) + pd.Timedelta(hours=8, minutes=45)


def _calendar_half_bounds(calendar_half: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    if len(calendar_half) != 6 or calendar_half[4] != "H" or calendar_half[-1] not in "12":
        raise ValueError(f"invalid calendar half: {calendar_half}")
    year = int(calendar_half[:4])
    half = int(calendar_half[-1])
    start_month = 1 if half == 1 else 7
    start = pd.Timestamp(year=year, month=start_month, day=1)
    end = start + pd.DateOffset(months=6) - pd.Timedelta(days=1)
    return start, end


def _sessions_between(calendar: pd.DatetimeIndex, start: object, end: object) -> pd.DatetimeIndex:
    return calendar[(calendar >= pd.Timestamp(start)) & (calendar <= pd.Timestamp(end))]


def _first_on_or_after(calendar: pd.DatetimeIndex, boundary: object) -> pd.Timestamp:
    values = calendar[calendar >= pd.Timestamp(boundary)]
    if len(values) == 0:
        raise ValueError(f"official calendar has no session on or after {boundary}")
    return pd.Timestamp(values[0])


def _last_before(calendar: pd.DatetimeIndex, boundary: object) -> pd.Timestamp:
    values = calendar[calendar < pd.Timestamp(boundary)]
    if len(values) == 0:
        raise ValueError(f"official calendar has no session before {boundary}")
    return pd.Timestamp(values[-1])


def _session_strings(values: pd.DatetimeIndex) -> list[str]:
    return [value.strftime("%Y-%m-%d") for value in values]


def _availability_partition(
    endpoints: pd.DataFrame,
    candidate_sessions: pd.DatetimeIndex,
    boundary_session: pd.Timestamp,
    timezone: str,
) -> dict[str, Any]:
    subset = endpoints.loc[endpoints["decision_session"].isin(candidate_sessions)].copy()
    retained = subset["label_endpoint_ts"].notna() & subset["label_endpoint_ts"].lt(_decision_ts(boundary_session, timezone))
    kept = pd.DatetimeIndex(subset.loc[retained, "decision_session"])
    purged = pd.DatetimeIndex(subset.loc[~retained, "decision_session"])
    return {
        "candidate_sessions": len(subset),
        "retained_sessions": len(kept),
        "purged_sessions": len(purged),
        "last_retained_session": kept.max().strftime("%Y-%m-%d") if len(kept) else None,
        "first_purged_session": purged.min().strftime("%Y-%m-%d") if len(purged) else None,
        "retained_session_values": kept,
    }


def derive_walk_forward_plan(calendar: Iterable[object], contract: FrozenD0Contract) -> dict[str, Any]:
    dates = _ordered_calendar(calendar)
    amendment = contract.config.get("v3_amendment")
    if not isinstance(amendment, dict) or amendment.get("schema_version") != "ats.phase_d0.reference.v3":
        raise ValueError("walk-forward planning requires the frozen Phase D0 v3 amendment")
    timezone = contract.config["observation_contract"]["market_timezone"]
    endpoints = label_endpoints(dates, dates, timezone=timezone)
    minimums = amendment["minimums"]
    rows_per_session = int(minimums["qualifying_session_minimum_rows"])
    blocks: list[dict[str, Any]] = []

    for specification in amendment["evidence_blocks"]:
        half_start, half_end = _calendar_half_bounds(specification["calendar_half"])
        evaluation_end_boundary = min(half_end, pd.Timestamp(specification.get("observation_end", half_end)))
        evaluation_sessions = _sessions_between(dates, half_start, evaluation_end_boundary)
        if len(evaluation_sessions) == 0:
            raise ValueError(f"no official evaluation sessions for {specification['block_id']}")
        refit_session = pd.Timestamp(evaluation_sessions[0])
        if refit_session.month not in (1, 7):
            raise ValueError(f"refit is not the first January/July official session: {refit_session}")
        month_start = pd.Timestamp(year=refit_session.year, month=refit_session.month, day=1)
        lower_calendar_boundary = month_start - pd.DateOffset(months=36)
        window_start = _first_on_or_after(dates, lower_calendar_boundary)
        window_end = _last_before(dates, refit_session)
        window_sessions = _sessions_between(dates, window_start, window_end)
        if len(window_sessions) == 0:
            raise ValueError(f"empty estimator window for {specification['block_id']}")

        inner_blocks: list[dict[str, Any]] = []
        for block_number, elapsed_months in enumerate((18, 24, 30), start=1):
            score_calendar_start = lower_calendar_boundary + pd.DateOffset(months=elapsed_months)
            score_calendar_end = lower_calendar_boundary + pd.DateOffset(months=elapsed_months + 6)
            score_start = _first_on_or_after(dates, score_calendar_start)
            score_end = _last_before(dates, score_calendar_end)
            score_sessions = _sessions_between(dates, score_start, score_end)
            fit_candidates = _sessions_between(dates, window_start, _last_before(dates, score_start))
            availability = _availability_partition(endpoints, fit_candidates, score_start, timezone)
            expected_fit = int(availability["retained_sessions"])
            required_fit_sessions = max(120, math.ceil(0.80 * expected_fit))
            inner_blocks.append({
                "score_block_number": block_number,
                "fit_history_months": elapsed_months,
                "fit_start": window_start.strftime("%Y-%m-%d"),
                "fit_end_candidate": fit_candidates[-1].strftime("%Y-%m-%d"),
                "fit_boundary_session": score_start.strftime("%Y-%m-%d"),
                "fit_availability": {key: value for key, value in availability.items() if key != "retained_session_values"},
                "fit_retained_sessions": _session_strings(availability["retained_session_values"]),
                "minimum_qualifying_sessions": required_fit_sessions,
                "minimum_model_rows": max(5400, rows_per_session * required_fit_sessions),
                "score_start": score_start.strftime("%Y-%m-%d"),
                "score_end": score_end.strftime("%Y-%m-%d"),
                "score_expected_sessions": len(score_sessions),
                "score_sessions": _session_strings(score_sessions),
                "score_minimum_qualifying_sessions": math.ceil(0.80 * len(score_sessions)),
            })

        final_availability = _availability_partition(endpoints, window_sessions, refit_session, timezone)
        final_expected = int(final_availability["retained_sessions"])
        final_required_sessions = max(230, math.ceil(0.80 * final_expected))
        evaluation_endpoint_rows = endpoints.loc[endpoints["decision_session"].isin(evaluation_sessions)]
        outcome_available = evaluation_endpoint_rows["label_endpoint_session"].notna()
        complete = bool(specification["complete"])
        outer_required_sessions = math.ceil(0.80 * len(evaluation_sessions)) if complete else 0
        blocks.append({
            "block_id": specification["block_id"],
            "calendar_half": specification["calendar_half"],
            "role": specification["role"],
            "complete": complete,
            "refit_session": refit_session.strftime("%Y-%m-%d"),
            "window_lower_calendar_boundary": lower_calendar_boundary.strftime("%Y-%m-%d"),
            "estimator_window_start": window_start.strftime("%Y-%m-%d"),
            "estimator_window_end": window_end.strftime("%Y-%m-%d"),
            "estimator_window_sessions": _session_strings(window_sessions),
            "inner_score_blocks": inner_blocks,
            "final_fit": {
                "boundary_session": refit_session.strftime("%Y-%m-%d"),
                "availability": {key: value for key, value in final_availability.items() if key != "retained_session_values"},
                "retained_sessions": _session_strings(final_availability["retained_session_values"]),
                "minimum_qualifying_sessions": final_required_sessions,
                "minimum_model_rows": max(10000, rows_per_session * final_required_sessions),
            },
            "evaluation_start": evaluation_sessions[0].strftime("%Y-%m-%d"),
            "evaluation_end": evaluation_sessions[-1].strftime("%Y-%m-%d"),
            "evaluation_sessions": _session_strings(evaluation_sessions),
            "evaluation_expected_sessions": len(evaluation_sessions),
            "evaluation_structurally_outcome_available_sessions": int(outcome_available.sum()),
            "evaluation_right_censored_sessions": int((~outcome_available).sum()),
            "evaluation_minimum_qualifying_sessions": outer_required_sessions,
            "evaluation_minimum_rows": rows_per_session * outer_required_sessions,
            "decisive": complete and specification["role"] != "partial_monitoring",
        })

    return {
        "schema_version": "ats.phase_d1.walk_forward_plan.v3",
        "contract_version": contract.config["contract_version"],
        "calendar_start": dates[0].strftime("%Y-%m-%d"),
        "calendar_end": dates[-1].strftime("%Y-%m-%d"),
        "calendar_hash": content_hash(_session_strings(dates)),
        "block_count": len(blocks),
        "blocks": blocks,
        "evidence_mapping": amendment["evidence_mapping"],
        "locked_prediction_order": list(LOCKED_BLOCK_ORDER),
    }


def derive_core_score_eligibility(panel: pd.DataFrame, calendar: Iterable[object], *, expected_factor_version: str) -> pd.DataFrame:
    """Derive only the label-blind common-score-mask eligibility, never C values."""

    dates = _ordered_calendar(calendar)
    required = {
        "security_id", "session_date", "split_adjusted_close", "split_adjusted_high",
        "official_membership", "price_usable_for_features", "source_treatment_state",
        "factor_version",
    }
    missing = required - set(panel.columns)
    if missing:
        raise ValueError(f"structural eligibility input lacks columns: {sorted(missing)}")
    if any(token in name.lower() for name in panel.columns for token in ("label__", "model_score", "rank_ic", "tail_outcome")):
        raise ValueError("predictive columns are forbidden in structural eligibility")
    if panel.duplicated(["security_id", "session_date"]).any():
        raise ValueError("duplicate structural eligibility keys")
    working = panel.copy()
    working["session_date"] = pd.to_datetime(working["session_date"]).dt.normalize()
    membership = working.loc[working["official_membership"].fillna(False), ["security_id", "session_date"]].copy()
    results: list[pd.DataFrame] = []
    for security_id, group in working.groupby("security_id", sort=True):
        indexed = group.set_index("session_date").reindex(dates)
        treatment = indexed["source_treatment_state"].fillna("").astype(str).str.lower()
        treatment_ok = ~treatment.str.contains("unresolved", regex=False)
        base_ok = indexed["price_usable_for_features"].fillna(False).astype(bool) & indexed["factor_version"].eq(expected_factor_version) & treatment_ok
        close_ok = base_ok & pd.to_numeric(indexed["split_adjusted_close"], errors="coerce").gt(0)
        high_ok = base_ok & pd.to_numeric(indexed["split_adjusted_high"], errors="coerce").gt(0)
        proximity = close_ok.rolling(252, min_periods=252).sum().eq(252) & high_ok.rolling(252, min_periods=252).sum().eq(252)
        momentum = close_ok.shift(21).rolling(232, min_periods=232).sum().eq(232)
        volatility = close_ok.rolling(21, min_periods=21).sum().eq(21)
        return5 = close_ok.rolling(6, min_periods=6).sum().eq(6)
        history = pd.DataFrame({
            "security_id": str(security_id),
            "information_session": dates,
            "core_score_eligible": proximity & momentum & volatility & return5,
        })
        results.append(history)
    history = pd.concat(results, ignore_index=True)
    previous = pd.DataFrame({"decision_session": dates[1:], "information_session": dates[:-1]})
    attached = membership.rename(columns={"session_date": "decision_session"}).merge(previous, on="decision_session", how="left", validate="many_to_one")
    attached = attached.merge(history, on=["security_id", "information_session"], how="left", validate="one_to_one")
    attached["core_score_eligible"] = attached["core_score_eligible"].fillna(False).astype(bool)
    counts = attached.groupby("decision_session", sort=True).agg(
        official_expected_count=("security_id", "nunique"),
        core_score_eligible_rows=("core_score_eligible", "sum"),
    ).reset_index()
    if not counts["official_expected_count"].eq(60).all():
        raise ValueError("structural eligibility requires official denominator 60")
    return counts


def bind_structural_minimums(plan: dict[str, Any], eligibility: pd.DataFrame) -> dict[str, Any]:
    counts = eligibility.copy()
    counts["decision_session"] = pd.to_datetime(counts["decision_session"]).dt.normalize()
    by_session = counts.set_index("decision_session")["core_score_eligible_rows"]
    bound_blocks: list[dict[str, Any]] = []
    for original in plan["blocks"]:
        block = {key: value for key, value in original.items() if key not in {"inner_score_blocks", "final_fit"}}
        inner_bound: list[dict[str, Any]] = []
        for inner in original["inner_score_blocks"]:
            item = dict(inner)
            retained = pd.DatetimeIndex(pd.to_datetime(inner["fit_retained_sessions"]))
            fit_rows = by_session.reindex(retained).fillna(0).astype(int)
            score_dates = pd.DatetimeIndex(pd.to_datetime(inner["score_sessions"]))
            score_rows = by_session.reindex(score_dates).fillna(0).astype(int)
            item["structural_qualifying_fit_sessions"] = int(fit_rows.ge(45).sum())
            item["structural_fit_rows"] = int(fit_rows.sum())
            item["structural_qualifying_score_sessions"] = int(score_rows.ge(45).sum())
            item["fit_minimum_status"] = "PASS" if item["structural_qualifying_fit_sessions"] >= inner["minimum_qualifying_sessions"] and item["structural_fit_rows"] >= inner["minimum_model_rows"] else "FAIL"
            item["score_minimum_status"] = "PASS" if item["structural_qualifying_score_sessions"] >= inner["score_minimum_qualifying_sessions"] else "FAIL"
            inner_bound.append(item)
        final = dict(original["final_fit"])
        final_dates = pd.DatetimeIndex(pd.to_datetime(final["retained_sessions"]))
        final_rows = by_session.reindex(final_dates).fillna(0).astype(int)
        final["structural_qualifying_sessions"] = int(final_rows.ge(45).sum())
        final["structural_model_rows"] = int(final_rows.sum())
        final["minimum_status"] = "PASS" if final["structural_qualifying_sessions"] >= final["minimum_qualifying_sessions"] and final["structural_model_rows"] >= final["minimum_model_rows"] else "FAIL"
        evaluation_dates = pd.DatetimeIndex(pd.to_datetime(original["evaluation_sessions"]))
        evaluation_rows = by_session.reindex(evaluation_dates).fillna(0).astype(int)
        block["structural_qualifying_evaluation_sessions"] = int(evaluation_rows.ge(45).sum())
        block["structural_evaluation_rows"] = int(evaluation_rows.sum())
        block["evaluation_minimum_status"] = (
            "NON_GATING_PARTIAL" if not original["complete"] else
            ("PASS" if block["structural_qualifying_evaluation_sessions"] >= original["evaluation_minimum_qualifying_sessions"] and block["structural_evaluation_rows"] >= original["evaluation_minimum_rows"] else "FAIL")
        )
        block["inner_score_blocks"] = inner_bound
        block["final_fit"] = final
        bound_blocks.append(block)
    failures = []
    for block in bound_blocks:
        failures.extend(
            f"{block['block_id']}:inner{inner['score_block_number']}:{kind}"
            for inner in block["inner_score_blocks"]
            for kind, status in (("fit", inner["fit_minimum_status"]), ("score", inner["score_minimum_status"]))
            if status != "PASS"
        )
        if block["final_fit"]["minimum_status"] != "PASS":
            failures.append(f"{block['block_id']}:final_fit")
        if block["evaluation_minimum_status"] == "FAIL":
            failures.append(f"{block['block_id']}:evaluation")
    if failures:
        raise ValueError(f"frozen structural minima are infeasible: {failures}")
    return {**{key: value for key, value in plan.items() if key != "blocks"}, "blocks": bound_blocks, "minimums_status": "PASS"}


def chronological_bins_for_gate_populations(plan: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    mapping = plan["evidence_mapping"]
    blocks = {item["block_id"]: item for item in plan["blocks"]}
    populations = {
        "MODEL_SELECTION_2023": mapping["model_family_selection"],
        "DEVELOPMENT_CONFIRMATION_2024": mapping["development_confirmation_pooled"],
        "LOCKED_COMPLETE_2025_2026H1": mapping["locked_evidence_pooled"],
    }
    output: dict[str, list[dict[str, Any]]] = {}
    for name, block_ids in populations.items():
        sessions = pd.DatetimeIndex(sorted({session for block_id in block_ids for session in pd.to_datetime(blocks[block_id]["evaluation_sessions"]) } ))
        if len(sessions) < 4:
            raise ValueError(f"four chronological bins are unavailable for {name}")
        output[name] = [
            {
                "bin": index + 1,
                "first_session": pd.Timestamp(values[0]).strftime("%Y-%m-%d"),
                "last_session": pd.Timestamp(values[-1]).strftime("%Y-%m-%d"),
                "session_count": len(values),
            }
            for index, values in enumerate(np.array_split(sessions.to_numpy(), 4))
        ]
    return output


def _new_estimator(model_name: str) -> Any:
    if model_name == "RIDGE":
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=False, keep_empty_features=False)),
            ("scaler", StandardScaler(with_mean=True, with_std=True)),
            ("ridge", Ridge(**RIDGE_PARAMETERS)),
        ])
    if model_name == "LIGHTGBM":
        return lgb.LGBMRegressor(**LIGHTGBM_PARAMETERS)
    raise ValueError(f"unsupported frozen model: {model_name}")


def synthetic_prequential_proof(contract: FrozenD0Contract, guard: D1ExecutionGuard, context: ExecutionContext) -> dict[str, Any]:
    guard.require(Operation.FIT, context)
    entry = guard.fixture_entry(str(context.fixture_id))
    if entry.get("kind") != "walkforward" or entry.get("contract_version", contract.config["contract_version"]) != contract.config["contract_version"]:
        raise ValueError("synthetic prequential proof requires the registered v3 walk-forward fixture")
    calendar = pd.bdate_range(str(entry["calendar_start"]), str(entry["calendar_end"]))
    plan = derive_walk_forward_plan(calendar, contract)
    outer = next(item for item in plan["blocks"] if item["calendar_half"] == entry["outer_calendar_half"])
    securities = int(entry["securities"])
    rng = np.random.default_rng(int(entry["seed"]))
    rows = pd.DataFrame({
        "decision_session": np.repeat(calendar, securities),
        "security_id": [f"SYNTH-{number:02d}" for _ in calendar for number in range(securities)],
        "candidate_run_id": str(context.fixture_id),
        "contract_version": contract.config["contract_version"],
    })
    for index, name in enumerate(contract.registry_order):
        base = rng.normal(size=len(rows))
        rows[name] = base + 0.001 * index
    rows["target"] = 0.004 * rows[contract.registry_order[0]] - 0.002 * rows[contract.registry_order[1]] + rng.normal(0.0, 0.01, len(rows))
    cells = {item["cell_id"]: item for item in contract.config["comparison"]["cells"]}
    allowlists = cell_feature_allowlists(contract, tuple(contract.config["v3_amendment"]["unchanged_parent_contract"]["p_survivors"]))
    cell_proofs: dict[str, Any] = {}
    common_score_hashes: dict[int, set[str]] = {1: set(), 2: set(), 3: set()}
    for cell_id in ("C_LINEAR", "C_LIGHTGBM", "RICH_LINEAR", "RICH_LIGHTGBM"):
        features = allowlists[cell_id]
        model_name = cells[cell_id]["model"]
        score_parts: list[np.ndarray] = []
        score_ledger_hashes: list[str] = []
        fit_instances: list[Any] = []
        stages: list[dict[str, Any]] = []
        for inner in outer["inner_score_blocks"]:
            fit_sessions = pd.to_datetime(inner["fit_retained_sessions"])
            score_sessions = pd.to_datetime(inner["score_sessions"])
            fit = rows.loc[rows["decision_session"].isin(fit_sessions)].sort_values(["decision_session", "security_id"], kind="mergesort")
            score = rows.loc[rows["decision_session"].isin(score_sessions)].sort_values(["decision_session", "security_id"], kind="mergesort")
            fit_ledger = build_semantic_row_ledger(fit)
            target_ledger = build_semantic_row_ledger(fit)
            if fit_ledger != target_ledger:
                raise AssertionError("synthetic matrix and target ledgers differ")
            score_ledger = build_semantic_row_ledger(score)
            estimator = _new_estimator(model_name)
            fit_instances.append(estimator)
            estimator.fit(fit.loc[:, list(features)], fit["target"].to_numpy())
            predictions = np.asarray(estimator.predict(score.loc[:, list(features)]), dtype=float)
            if not np.isfinite(predictions).all():
                raise ValueError("synthetic prequential score block emitted nonfinite scores")
            score_parts.append(predictions)
            score_ledger_hashes.append(score_ledger.logical_hash)
            common_score_hashes[int(inner["score_block_number"])].add(score_ledger.logical_hash)
            stages.append({
                "score_block_number": inner["score_block_number"],
                "fit_end": inner["fit_availability"]["last_retained_session"],
                "score_start": inner["score_start"],
                "fit_rows": len(fit),
                "score_rows": len(score),
                "matrix_target_semantic_row_hash": fit_ledger.logical_hash,
                "score_semantic_row_hash": score_ledger.logical_hash,
                "fit_strictly_earlier_than_score": pd.Timestamp(inner["fit_availability"]["last_retained_session"]) < pd.Timestamp(inner["score_start"]),
            })
        pooled = np.concatenate(score_parts)
        threshold = max(0.01, float(np.quantile(pooled, 0.9, method="linear")))
        final_sessions = pd.to_datetime(outer["final_fit"]["retained_sessions"])
        final = rows.loc[rows["decision_session"].isin(final_sessions)].sort_values(["decision_session", "security_id"], kind="mergesort")
        evaluation = rows.loc[rows["decision_session"].isin(pd.to_datetime(outer["evaluation_sessions"]))].sort_values(["decision_session", "security_id"], kind="mergesort")
        final_ledger = build_semantic_row_ledger(final)
        evaluation_ledger = build_semantic_row_ledger(evaluation)
        estimator = _new_estimator(model_name)
        fit_instances.append(estimator)
        estimator.fit(final.loc[:, list(features)], final["target"].to_numpy())
        outer_scores = np.asarray(estimator.predict(evaluation.loc[:, list(features)]), dtype=float)
        if not np.isfinite(outer_scores).all():
            raise ValueError("synthetic final refit emitted nonfinite outer scores")
        cell_proofs[cell_id] = {
            "model": model_name,
            "inner_stage_count": len(stages),
            "inner_stages": stages,
            "preprocessing_and_estimator_recreated": (
                len(fit_instances) == 4
                and len({id(instance) for instance in fit_instances}) == 4
            ),
            "pooled_score_block_count": len(score_parts),
            "pooled_score_count": len(pooled),
            "pooled_score_ledger_hash": content_hash(score_ledger_hashes),
            "threshold_provenance_hash": content_hash({"score_ledgers": score_ledger_hashes, "scores": logical_frame_hash(pd.DataFrame({"score": pooled})), "q": 0.9, "floor": 0.01}),
            "final_fit_rows": len(final),
            "final_fit_semantic_row_hash": final_ledger.logical_hash,
            "final_fit_uses_all_label_mature_window_rows": len(final) == securities * len(outer["final_fit"]["retained_sessions"]),
            "outer_score_rows": len(evaluation),
            "outer_score_semantic_row_hash": evaluation_ledger.logical_hash,
            "outer_labels_used_for_threshold": False,
            "threshold_frozen_before_final_refit": True,
        }
    if any(len(hashes) != 1 for hashes in common_score_hashes.values()):
        raise ValueError("the four cells do not share each inner common score population")
    return {
        "schema_version": "ats.phase_d1.synthetic_prequential_proof.v3",
        "fixture_id": context.fixture_id,
        "outer_block": outer["block_id"],
        "cell_count": len(cell_proofs),
        "cells": cell_proofs,
        "all_cells_share_inner_score_ledgers": True,
        "test_labels_can_affect_threshold": False,
        "synthetic_only_not_model_quality": True,
        "proof_hash": content_hash(cell_proofs),
    }


@dataclass(frozen=True)
class LockedEvaluationPermit:
    sequence_fingerprint: str


def locked_availability_proof_identity(block: Mapping[str, Any]) -> str:
    block_id = str(block.get("block_id"))
    if block_id not in LOCKED_BLOCK_ORDER:
        raise ValueError(f"not a locked evidence block: {block_id}")
    refit_session = str(pd.Timestamp(block.get("refit_session")).date())
    final_fit = block.get("final_fit")
    if not isinstance(final_fit, Mapping):
        raise ValueError(f"locked block lacks final-fit availability proof: {block_id}")
    if str(pd.Timestamp(final_fit.get("boundary_session")).date()) != refit_session:
        raise ValueError(f"locked block final-fit boundary differs from refit: {block_id}")
    retained_sessions = final_fit.get("retained_sessions")
    if not isinstance(retained_sessions, list) or not retained_sessions:
        raise ValueError(f"locked block lacks retained-session identities: {block_id}")
    if final_fit.get("minimum_status") != "PASS":
        raise ValueError(f"locked block minimums are not validated: {block_id}")
    availability = final_fit.get("availability")
    if not isinstance(availability, Mapping) or availability.get("retained_sessions") != len(retained_sessions):
        raise ValueError(f"locked block availability counts do not bind retained sessions: {block_id}")
    return content_hash({
        "schema_version": "ats.phase_d1.locked_availability_proof.v3",
        "block_id": block_id,
        "expected_refit_session": refit_session,
        "final_fit_boundary_session": str(pd.Timestamp(final_fit["boundary_session"]).date()),
        "retained_sessions_hash": content_hash(retained_sessions),
        "availability": dict(availability),
        "minimum_qualifying_sessions": final_fit.get("minimum_qualifying_sessions"),
        "minimum_model_rows": final_fit.get("minimum_model_rows"),
        "structural_qualifying_sessions": final_fit.get("structural_qualifying_sessions"),
        "structural_model_rows": final_fit.get("structural_model_rows"),
    })


def expected_locked_sequence_bindings(plan: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    if tuple(plan.get("locked_prediction_order", ())) != LOCKED_BLOCK_ORDER:
        raise ValueError("walk-forward plan does not preserve the frozen locked block order")
    raw_blocks = plan.get("blocks")
    if not isinstance(raw_blocks, list):
        raise ValueError("walk-forward plan lacks locked blocks")
    blocks = {str(block["block_id"]): block for block in raw_blocks}
    if any(block_id not in blocks for block_id in LOCKED_BLOCK_ORDER):
        raise ValueError("walk-forward plan lacks a required locked block")
    return {
        block_id: {
            "expected_refit_session": str(pd.Timestamp(blocks[block_id]["refit_session"]).date()),
            "availability_proof_hash": locked_availability_proof_identity(blocks[block_id]),
        }
        for block_id in LOCKED_BLOCK_ORDER
    }


class LockedSequenceFirewall:
    def __init__(self, expected_bindings: Mapping[str, Mapping[str, str]]) -> None:
        if tuple(expected_bindings) != LOCKED_BLOCK_ORDER:
            raise ValueError("locked firewall bindings must contain the exact frozen block order")
        self._expected_bindings: dict[str, dict[str, str]] = {}
        for block_id in LOCKED_BLOCK_ORDER:
            binding = expected_bindings[block_id]
            refit = str(pd.Timestamp(binding.get("expected_refit_session")).date())
            availability_hash = str(binding.get("availability_proof_hash", ""))
            if not SHA256_PATTERN.fullmatch(availability_hash):
                raise ValueError(f"invalid validated availability-proof identity: {block_id}")
            self._expected_bindings[block_id] = {
                "expected_refit_session": refit,
                "availability_proof_hash": availability_hash,
            }
        self._records: list[dict[str, str]] = []
        self._fingerprint: str | None = None

    def record_prediction(self, block_id: str, *, prediction_hash: str, refit_session: str, availability_proof_hash: str) -> None:
        if self._fingerprint is not None:
            raise PermissionError("locked prediction sequence is already fingerprinted")
        expected = LOCKED_BLOCK_ORDER[len(self._records)] if len(self._records) < len(LOCKED_BLOCK_ORDER) else None
        if block_id != expected:
            raise PermissionError(f"locked prediction order violation: expected={expected}, received={block_id}")
        if not SHA256_PATTERN.fullmatch(prediction_hash):
            raise ValueError("locked prediction requires a lowercase SHA-256 identity")
        expected_binding = self._expected_bindings[block_id]
        normalized_refit = str(pd.Timestamp(refit_session).date())
        if normalized_refit != expected_binding["expected_refit_session"]:
            raise PermissionError(
                f"locked refit-date binding violation for {block_id}: "
                f"expected={expected_binding['expected_refit_session']}, received={normalized_refit}"
            )
        if availability_proof_hash != expected_binding["availability_proof_hash"]:
            raise PermissionError(f"locked availability-proof identity violation for {block_id}")
        if not SHA256_PATTERN.fullmatch(availability_proof_hash):
            raise ValueError("locked prediction and availability proofs require SHA-256 identities")
        self._records.append({
            "block_id": block_id,
            "prediction_hash": prediction_hash,
            "refit_session": normalized_refit,
            "availability_proof_hash": availability_proof_hash,
        })

    def fingerprint_complete_sequence(self) -> str:
        if tuple(item["block_id"] for item in self._records) != LOCKED_BLOCK_ORDER:
            raise PermissionError("locked metrics remain inaccessible until all three prediction blocks exist")
        self._fingerprint = content_hash(self._records)
        return self._fingerprint

    def evaluation_permit(self) -> LockedEvaluationPermit:
        if self._fingerprint is None:
            raise PermissionError("locked outcome attachment and metrics are inaccessible before sequence fingerprinting")
        return LockedEvaluationPermit(self._fingerprint)

    def require_evaluation_permit(self, permit: LockedEvaluationPermit) -> None:
        if not isinstance(permit, LockedEvaluationPermit) or permit.sequence_fingerprint != self._fingerprint:
            raise PermissionError("invalid locked evaluation permit")
