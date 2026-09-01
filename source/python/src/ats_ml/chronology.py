from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ats_ml.contracts import FrozenD0Contract
from ats_ml.guard import D1ExecutionGuard, ExecutionContext, Operation
from ats_ml.labels import label_endpoints


@dataclass(frozen=True)
class BoundaryResolution:
    partition: str
    boundary_decision_session: str | None
    last_retained_session: str | None
    first_purged_session: str | None
    retained_sessions: int
    purged_sessions: int


def _decision_ts(session: object, timezone: str) -> pd.Timestamp:
    return pd.Timestamp(session).normalize().tz_localize(timezone) + pd.Timedelta(hours=8, minutes=45)


def derive_chronological_folds(
    calendar: Iterable[object],
    contract: FrozenD0Contract,
    guard: D1ExecutionGuard,
    context: ExecutionContext,
) -> tuple[pd.DataFrame, dict[str, list[BoundaryResolution]]]:
    guard.require(Operation.RESOLVE_PURGE, context)
    dates = pd.DatetimeIndex(pd.to_datetime(list(calendar))).normalize().sort_values().unique()
    config = contract.config
    timezone = config["observation_contract"]["market_timezone"]
    endpoints = label_endpoints(dates, dates, timezone=timezone)
    rows: list[pd.DataFrame] = []
    resolutions: dict[str, list[BoundaryResolution]] = {}
    folds = config["chronology"]["folds"]
    for fold_index, fold in enumerate(folds):
        fold_rows: list[pd.DataFrame] = []
        fold_resolutions: list[BoundaryResolution] = []
        partitions = (
            ("fit", fold["fit_start"], fold["fit_end"], fold["calibration_start"]),
            ("calibration", fold["calibration_start"], fold["calibration_end"], fold["validation_start"]),
        )
        for partition, start, end, boundary in partitions:
            subset = endpoints.loc[endpoints["decision_session"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
            boundary_ts = _decision_ts(boundary, timezone)
            retained = subset["label_endpoint_ts"].notna() & subset["label_endpoint_ts"].lt(boundary_ts)
            subset["fold_id"] = fold["fold_id"]
            subset["partition"] = partition
            subset["retained"] = retained
            subset["boundary_state"] = np.where(retained, "RETAINED", "BOUNDARY_WITHHELD")
            fold_rows.append(subset)
            retained_sessions = subset.loc[retained, "decision_session"]
            purged_sessions = subset.loc[~retained, "decision_session"]
            fold_resolutions.append(BoundaryResolution(
                partition=partition,
                boundary_decision_session=str(pd.Timestamp(boundary).date()),
                last_retained_session=str(retained_sessions.max().date()) if len(retained_sessions) else None,
                first_purged_session=str(purged_sessions.min().date()) if len(purged_sessions) else None,
                retained_sessions=int(retained.sum()),
                purged_sessions=int((~retained).sum()),
            ))
        subset = endpoints.loc[endpoints["decision_session"].between(pd.Timestamp(fold["validation_start"]), pd.Timestamp(fold["validation_end"]))].copy()
        if fold_index + 1 < len(folds):
            boundary = folds[fold_index + 1]["validation_start"]
            boundary_ts = _decision_ts(boundary, timezone)
            retained = subset["label_endpoint_ts"].notna() & subset["label_endpoint_ts"].lt(boundary_ts)
            state = np.where(retained, "RETAINED", "BOUNDARY_WITHHELD")
        else:
            boundary = None
            retained = subset["label_endpoint_session"].notna() & subset["label_endpoint_session"].le(pd.Timestamp(fold["validation_end"]))
            state = np.where(retained, "RETAINED", "LABEL_RIGHT_CENSORED")
        subset["fold_id"] = fold["fold_id"]
        subset["partition"] = "evaluation"
        subset["retained"] = retained
        subset["boundary_state"] = state
        fold_rows.append(subset)
        retained_sessions = subset.loc[retained, "decision_session"]
        purged_sessions = subset.loc[~retained, "decision_session"]
        fold_resolutions.append(BoundaryResolution(
            partition="evaluation",
            boundary_decision_session=str(pd.Timestamp(boundary).date()) if boundary else None,
            last_retained_session=str(retained_sessions.max().date()) if len(retained_sessions) else None,
            first_purged_session=str(purged_sessions.min().date()) if len(purged_sessions) else None,
            retained_sessions=int(retained.sum()),
            purged_sessions=int((~retained).sum()),
        ))
        rows.extend(fold_rows)
        resolutions[fold["fold_id"]] = fold_resolutions
    result = pd.concat(rows, ignore_index=True).sort_values(["fold_id", "partition", "decision_session"], kind="mergesort")
    return result.reset_index(drop=True), resolutions


def chronological_quartiles(sessions: Iterable[object]) -> list[dict[str, object]]:
    ordered = pd.DatetimeIndex(pd.to_datetime(list(sessions))).normalize().sort_values().unique()
    if len(ordered) < 4:
        raise ValueError("four nonempty chronological bins require at least four sessions")
    bins = np.array_split(ordered.to_numpy(), 4)
    return [
        {
            "bin": index + 1,
            "first_session": str(pd.Timestamp(values[0]).date()),
            "last_session": str(pd.Timestamp(values[-1]).date()),
            "session_count": len(values),
        }
        for index, values in enumerate(bins)
    ]
