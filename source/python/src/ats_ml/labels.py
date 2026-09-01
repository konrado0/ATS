from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ats_ml.guard import D1ExecutionGuard, ExecutionContext, Operation
from ats_research.hashing import content_hash, logical_frame_hash


class LabelContractError(ValueError):
    pass


_LABEL_SEAL = object()


@dataclass(frozen=True, init=False)
class LabelFrame:
    _frame: pd.DataFrame
    context: ExecutionContext
    input_payload_hash: str

    def __init__(self, frame: pd.DataFrame, context: ExecutionContext, input_payload_hash: str, *, _token: object):
        if _token is not _LABEL_SEAL:
            raise LabelContractError("label frames must be created by the authorized synthetic label builder")
        object.__setattr__(self, "_frame", frame.copy())
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "input_payload_hash", input_payload_hash)

    @property
    def frame(self) -> pd.DataFrame:
        return self._frame.copy()


def label_fixture_payload_hash(bars: pd.DataFrame, observations: pd.DataFrame, calendar: Iterable[object]) -> str:
    bar_columns = ("security_id", "session_date", "split_adjusted_open")
    observation_columns = ("security_id", "decision_session")
    if set(bar_columns) - set(bars.columns) or set(observation_columns) - set(observations.columns):
        raise LabelContractError("label fixture is missing semantic input columns")
    bar_hash = logical_frame_hash(bars.loc[:, list(bar_columns)], ["session_date", "security_id"])
    observation_hash = logical_frame_hash(observations.loc[:, list(observation_columns)], ["decision_session", "security_id"])
    calendar_hash = logical_frame_hash(pd.DataFrame({"session_date": pd.DatetimeIndex(pd.to_datetime(list(calendar))).normalize()}), ["session_date"])
    return content_hash({"bars": bar_hash, "observations": observation_hash, "calendar": calendar_hash})


def label_endpoints(
    decision_sessions: Iterable[object],
    calendar: Iterable[object],
    *,
    horizon_sessions: int = 20,
    timezone: str = "Europe/Warsaw",
) -> pd.DataFrame:
    dates = pd.DatetimeIndex(pd.to_datetime(list(calendar))).normalize().sort_values().unique()
    position = {date: index for index, date in enumerate(dates)}
    rows: list[dict[str, object]] = []
    for decision in pd.DatetimeIndex(pd.to_datetime(list(decision_sessions))).normalize().sort_values().unique():
        index = position.get(decision)
        if index is None:
            raise LabelContractError(f"decision session is not in the official calendar: {decision}")
        endpoint = dates[index + horizon_sessions] if index + horizon_sessions < len(dates) else pd.NaT
        endpoint_ts = pd.NaT if pd.isna(endpoint) else endpoint.tz_localize(timezone) + pd.Timedelta(hours=9)
        rows.append({"decision_session": decision, "label_endpoint_session": endpoint, "label_endpoint_ts": endpoint_ts})
    return pd.DataFrame(rows)


def build_primary_labels(
    bars: pd.DataFrame,
    observations: pd.DataFrame,
    calendar: Iterable[object],
    guard: D1ExecutionGuard,
    context: ExecutionContext,
) -> LabelFrame:
    payload_hash = label_fixture_payload_hash(bars, observations, calendar)
    guard.require_fixture_payload(context, "label_payload", payload_hash)
    required = {"security_id", "session_date", "split_adjusted_open"}
    if required - set(bars.columns):
        raise LabelContractError("primary label input is missing exact open columns")
    if bars.duplicated(["security_id", "session_date"]).any():
        raise LabelContractError("duplicate label price keys")
    endpoints = label_endpoints(observations["decision_session"].unique(), calendar)
    base = observations[["security_id", "decision_session"]].drop_duplicates().merge(endpoints, on="decision_session", validate="many_to_one")
    opens = bars[["security_id", "session_date", "split_adjusted_open"]].copy()
    opens["session_date"] = pd.to_datetime(opens["session_date"]).dt.normalize()
    starts = opens.rename(columns={"session_date": "decision_session", "split_adjusted_open": "label_start_open"})
    ends = opens.rename(columns={"session_date": "label_endpoint_session", "split_adjusted_open": "label_endpoint_open"})
    result = base.merge(starts, on=["security_id", "decision_session"], how="left", validate="many_to_one")
    result = result.merge(ends, on=["security_id", "label_endpoint_session"], how="left", validate="many_to_one")
    start_ok = result["label_start_open"].notna() & np.isfinite(result["label_start_open"]) & result["label_start_open"].gt(0.0)
    end_ok = result["label_endpoint_open"].notna() & np.isfinite(result["label_endpoint_open"]) & result["label_endpoint_open"].gt(0.0)
    result["label__open_to_open__20"] = (result["label_endpoint_open"] / result["label_start_open"] - 1.0).where(start_ok & end_ok)
    result["label_state"] = np.select(
        [result["label_endpoint_session"].isna(), ~start_ok, ~end_ok],
        ["LABEL_RIGHT_CENSORED", "LABEL_START_MISSING", "LABEL_ENDPOINT_MISSING"],
        default="AVAILABLE",
    )
    result = result.sort_values(["decision_session", "security_id"], kind="mergesort").reset_index(drop=True)
    return LabelFrame(result, context, payload_hash, _token=_LABEL_SEAL)
