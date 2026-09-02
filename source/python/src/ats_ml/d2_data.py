from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ats_ml.contracts import FrozenD0Contract, resolve_pinned_inputs
from ats_ml.features import _compute_one_security
from ats_ml.labels import label_endpoints
from ats_ml.observations import build_observation_matrix
from ats_research.hashing import content_hash, logical_frame_hash


PANEL_FEATURE_COLUMNS = (
    "security_id", "session_date", "split_adjusted_high", "split_adjusted_low",
    "split_adjusted_close", "split_adjusted_volume", "official_membership",
    "price_usable_for_features", "volume_usable_for_relative_volume",
    "source_treatment_state", "factor_version", "missing_state",
    "nontrading_reason", "coverage_result", "volume_ineligibility_reason",
)


def load_official_calendar(contract: FrozenD0Contract) -> pd.DatetimeIndex:
    panel_path = resolve_pinned_inputs(contract)["candidate_panel"]
    frame = pd.read_parquet(panel_path, columns=["session_date"])
    dates = pd.DatetimeIndex(pd.to_datetime(frame["session_date"]).dt.normalize().unique()).sort_values()
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("pinned candidate calendar is invalid")
    return dates


def build_real_observations(contract: FrozenD0Contract) -> tuple[pd.DataFrame, dict[str, Any]]:
    paths = resolve_pinned_inputs(contract)
    panel = pd.read_parquet(paths["candidate_panel"], columns=list(PANEL_FEATURE_COLUMNS))
    panel["session_date"] = pd.to_datetime(panel["session_date"]).dt.normalize()
    if panel.duplicated(["security_id", "session_date"]).any():
        raise ValueError("candidate panel contains duplicate security/session rows")
    calendar = pd.DatetimeIndex(sorted(panel["session_date"].unique()))
    expected_factor = "ats.gpw.split_adjustment.v1"
    histories = []
    for security_id, group in panel.groupby("security_id", sort=True):
        history = _compute_one_security(group, calendar, expected_factor, ("C", "P"))
        history.insert(0, "security_id", str(security_id))
        histories.append(history)
    stock_history = pd.concat(histories, ignore_index=True)
    membership = panel.loc[
        panel["official_membership"].fillna(False),
        [
            "security_id", "session_date", "official_membership", "missing_state", "nontrading_reason",
            "coverage_result", "volume_ineligibility_reason",
        ],
    ].copy()
    market = pd.read_parquet(paths["market_state_feature_artifact"])
    observations = build_observation_matrix(
        membership, stock_history, market, calendar, contract, stock_blocks=("C", "P")
    )
    start = pd.Timestamp(contract.config["observation_contract"]["evaluation_start"])
    end = pd.Timestamp(contract.config["observation_contract"]["evaluation_end"])
    observations = observations.loc[
        observations["decision_session"].between(start, end)
    ].reset_index(drop=True)
    audit = {
        "schema_version": "ats.phase_d2.observation_audit.v1",
        "calendar_start": calendar[0].strftime("%Y-%m-%d"),
        "calendar_end": calendar[-1].strftime("%Y-%m-%d"),
        "calendar_sessions": len(calendar),
        "rows": len(observations),
        "sessions": observations["decision_session"].nunique(),
        "official_denominator_min": int(observations.groupby("decision_session").size().min()),
        "official_denominator_max": int(observations.groupby("decision_session").size().max()),
        "semantic_row_hash": logical_frame_hash(
            observations[["security_id", "decision_session"]],
            sort_by=["decision_session", "security_id"],
        ),
        "feature_matrix_hash": logical_frame_hash(
            observations[["security_id", "decision_session", *contract.registry_order]],
            sort_by=["decision_session", "security_id"],
        ),
        "labels_or_scores_present": any(
            str(column).startswith("label__") or str(column) == "model_score"
            for column in observations.columns
        ),
    }
    if audit["official_denominator_min"] != 60 or audit["official_denominator_max"] != 60:
        raise ValueError("real observation matrix does not preserve denominator 60")
    if audit["labels_or_scores_present"]:
        raise ValueError("Stage 1 observation matrix crossed the label or score boundary")
    audit["audit_hash"] = content_hash(audit)
    return observations, audit


def build_real_labels(
    contract: FrozenD0Contract,
    observations: pd.DataFrame,
    decision_sessions: Iterable[object],
    *,
    horizons: tuple[int, ...] = (20,),
) -> pd.DataFrame:
    paths = resolve_pinned_inputs(contract)
    calendar_frame = pd.read_parquet(paths["candidate_panel"], columns=["session_date"])
    calendar = pd.DatetimeIndex(
        sorted(pd.to_datetime(calendar_frame["session_date"]).dt.normalize().unique())
    )
    requested = pd.DatetimeIndex(pd.to_datetime(list(decision_sessions))).normalize().unique()
    endpoint_tables = {
        horizon: label_endpoints(
            requested, calendar, horizon_sessions=horizon,
            timezone=contract.config["observation_contract"]["market_timezone"],
        )
        for horizon in horizons
    }
    needed_dates = set(requested)
    for endpoints in endpoint_tables.values():
        needed_dates.update(pd.DatetimeIndex(endpoints["label_endpoint_session"].dropna()))
    bars = pd.read_parquet(
        paths["candidate_panel"],
        columns=["security_id", "session_date", "split_adjusted_open"],
        filters=[("session_date", "in", [value.date() for value in sorted(needed_dates)])],
    )
    bars["session_date"] = pd.to_datetime(bars["session_date"]).dt.normalize()
    if bars.duplicated(["security_id", "session_date"]).any():
        raise ValueError("label source contains duplicate security/session rows")
    base = observations.loc[
        observations["decision_session"].isin(requested), ["security_id", "decision_session"]
    ].drop_duplicates()
    starts = bars.rename(
        columns={"session_date": "decision_session", "split_adjusted_open": "label_start_open"}
    )
    result = base.merge(starts, on=["security_id", "decision_session"], how="left", validate="one_to_one")
    for horizon in horizons:
        endpoints = endpoint_tables[horizon].rename(columns={
            "label_endpoint_session": f"label_endpoint_session_{horizon}",
            "label_endpoint_ts": f"label_endpoint_ts_{horizon}",
        })
        result = result.merge(endpoints, on="decision_session", validate="many_to_one")
        ends = bars.rename(columns={
            "session_date": f"label_endpoint_session_{horizon}",
            "split_adjusted_open": f"label_endpoint_open_{horizon}",
        })
        result = result.merge(
            ends,
            on=["security_id", f"label_endpoint_session_{horizon}"],
            how="left",
            validate="many_to_one",
        )
        start = pd.to_numeric(result["label_start_open"], errors="coerce")
        end = pd.to_numeric(result[f"label_endpoint_open_{horizon}"], errors="coerce")
        valid = np.isfinite(start) & start.gt(0.0) & np.isfinite(end) & end.gt(0.0)
        result[f"label__open_to_open__{horizon}"] = (end / start - 1.0).where(valid)
        result[f"label_state_{horizon}"] = np.select(
            [
                result[f"label_endpoint_session_{horizon}"].isna(),
                ~(np.isfinite(start) & start.gt(0.0)),
                ~(np.isfinite(end) & end.gt(0.0)),
            ],
            ["LABEL_RIGHT_CENSORED", "LABEL_START_MISSING", "LABEL_ENDPOINT_MISSING"],
            default="AVAILABLE",
        )
    return result.sort_values(["decision_session", "security_id"], kind="mergesort").reset_index(drop=True)


def attach_primary_outcomes(predictions: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    forbidden = set(predictions.columns) & {
        "label__open_to_open__20", "label_endpoint_session_20", "label_endpoint_ts_20"
    }
    if forbidden:
        raise ValueError(f"sealed prediction table already contains outcomes: {sorted(forbidden)}")
    label_columns = [
        column for column in labels.columns
        if column not in {"label_start_open"} and not column.startswith("label_endpoint_open_")
    ]
    return predictions.merge(
        labels[label_columns], on=["security_id", "decision_session"], how="left", validate="many_to_one"
    )
