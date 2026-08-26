from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd


NATIVE_BASIS = "source_native"
DERIVED_BASIS = "split_adjusted_price"
TREATMENT_STATES = {
    "source_unadjusted_for_event",
    "source_already_adjusted_for_event",
    "not_applicable",
    "unknown",
}
VOLUME_PRECISION_STATES = {
    "exact_source_reported_shares",
    "vendor_displayed_rounded_volume",
    "unknown_precision",
    "missing_volume",
}
NATIVE_PRICE_COLUMNS = ("native_open", "native_high", "native_low", "native_close")


def _stable_records_hash(frame: pd.DataFrame, sort: Iterable[str]) -> str:
    ordered = frame.sort_values(list(sort), kind="mergesort").copy()
    for column in ordered.select_dtypes(include=["datetime64[ns]"]).columns:
        ordered[column] = ordered[column].dt.strftime("%Y-%m-%d")
    payload = ordered.replace({np.nan: None}).to_dict(orient="records")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def select_whole_bars(source_frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Select one complete vendor row by explicit priority; never mix fields."""
    if not source_frames:
        return pd.DataFrame()
    required = {"security_id", "session_date", "source_priority"}
    normalized: list[pd.DataFrame] = []
    for frame in source_frames:
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"source frame missing columns: {sorted(missing)}")
        if frame.duplicated(["security_id", "session_date"]).any():
            raise ValueError("duplicate semantic keys within source frame")
        normalized.append(frame.copy())
    combined = pd.concat(normalized, ignore_index=True, sort=False)
    combined["session_date"] = pd.to_datetime(combined["session_date"], errors="raise")
    combined = combined.sort_values(
        ["security_id", "session_date", "source_priority"], kind="mergesort"
    )
    return combined.drop_duplicates(["security_id", "session_date"], keep="first").reset_index(drop=True)


def transform_split_adjusted(
    native: pd.DataFrame,
    events: pd.DataFrame,
    treatments: pd.DataFrame,
    *,
    factor_version: str,
) -> pd.DataFrame:
    required = {
        "security_id",
        "isin",
        "session_date",
        "selected_source",
        "source_series_version",
        "data_basis",
        "native_open",
        "native_high",
        "native_low",
        "native_close",
        "native_volume",
        "volume_basis",
        "volume_precision_state",
        "volume_usable_for_relative_volume",
        "volume_ineligibility_reason",
        "source_lineage",
        "source_hash",
    }
    missing = required - set(native.columns)
    if missing:
        raise ValueError(f"native input missing columns: {sorted(missing)}")
    if not native["data_basis"].eq(NATIVE_BASIS).all():
        raise ValueError("derived or non-native input is prohibited")
    if any(column.startswith("split_adjusted_") for column in native.columns):
        raise ValueError("input already contains split-adjusted derived fields")
    if native.duplicated(["security_id", "session_date"]).any():
        raise ValueError("duplicate native semantic keys")
    if not native["volume_precision_state"].isin(VOLUME_PRECISION_STATES).all():
        raise ValueError("unsupported volume precision state")

    event_required = {
        "event_id",
        "security_id",
        "event_status",
        "first_post_event_session",
        "pre_event_ohlc_multiplier",
        "pre_event_volume_multiplier",
    }
    treatment_required = {"event_id", "source_series_version", "treatment_state"}
    if event_required - set(events.columns):
        raise ValueError("event ledger is missing required columns")
    if treatment_required - set(treatments.columns):
        raise ValueError("source treatment ledger is missing required columns")
    if events.duplicated("event_id").any() or treatments.duplicated(
        ["event_id", "source_series_version"]
    ).any():
        raise ValueError("duplicate event or treatment keys")
    if not treatments["treatment_state"].isin(TREATMENT_STATES).all():
        raise ValueError("unsupported source treatment state")

    result = native.copy()
    result["session_date"] = pd.to_datetime(result["session_date"], errors="raise")
    result["cumulative_price_factor"] = 1.0
    result["cumulative_volume_factor"] = 1.0
    applied: list[list[str]] = [[] for _ in range(len(result))]
    states: list[list[str]] = [[] for _ in range(len(result))]

    for event in events.sort_values("first_post_event_session", kind="mergesort").itertuples(index=False):
        if str(event.event_status) != "confirmed":
            continue
        price_factor = float(event.pre_event_ohlc_multiplier)
        volume_factor = float(event.pre_event_volume_multiplier)
        if not np.isfinite(price_factor) or not np.isfinite(volume_factor) or price_factor <= 0 or volume_factor <= 0:
            raise ValueError(f"invalid split ratio for event {event.event_id}")
        effective = pd.Timestamp(event.first_post_event_session)
        security_mask = result["security_id"].eq(str(event.security_id))
        if not security_mask.any():
            continue
        relevant = result.loc[security_mask]
        crosses = relevant["session_date"].lt(effective).any() and relevant["session_date"].ge(effective).any()
        lookup = treatments.loc[treatments["event_id"].eq(str(event.event_id))].set_index(
            "source_series_version"
        )["treatment_state"]
        series = set(relevant["source_series_version"].astype(str))
        missing_treatments = series - set(lookup.index.astype(str))
        if missing_treatments:
            raise ValueError(f"missing source treatment for event {event.event_id}: {sorted(missing_treatments)}")
        if crosses and any(str(lookup.loc[value]) == "unknown" for value in series):
            raise ValueError(f"unknown treatment across event boundary {event.event_id}")
        for index in result.index[security_mask]:
            series_version = str(result.at[index, "source_series_version"])
            state = str(lookup.loc[series_version])
            states[index].append(f"{event.event_id}={state}")
            if result.at[index, "session_date"] < effective and state == "source_unadjusted_for_event":
                result.at[index, "cumulative_price_factor"] *= price_factor
                result.at[index, "cumulative_volume_factor"] *= volume_factor
                applied[index].append(str(event.event_id))

    for native_column in NATIVE_PRICE_COLUMNS:
        suffix = native_column.removeprefix("native_")
        result[f"split_adjusted_{suffix}"] = (
            result[native_column] * result["cumulative_price_factor"]
        )
    result["split_adjusted_volume"] = (
        result["native_volume"] * result["cumulative_volume_factor"]
    )
    result.loc[result["native_volume"].isna(), "split_adjusted_volume"] = np.nan
    result["applied_event_ids"] = ["|".join(values) for values in applied]
    result["source_treatment_state"] = ["|".join(values) for values in states]
    result["factor_version"] = factor_version
    result["derived_data_basis"] = DERIVED_BASIS
    result["cash_distributions_included"] = False
    result["cash_dividend_price_gaps_preserved"] = True

    priced = result["split_adjusted_close"].notna()
    if (
        result.loc[priced, "split_adjusted_high"]
        < result.loc[priced, ["split_adjusted_open", "split_adjusted_close", "split_adjusted_low"]].max(axis=1)
    ).any() or (
        result.loc[priced, "split_adjusted_low"]
        > result.loc[priced, ["split_adjusted_open", "split_adjusted_close", "split_adjusted_high"]].min(axis=1)
    ).any():
        raise ValueError("split-adjusted OHLC envelope is inconsistent")
    return result.sort_values(["security_id", "session_date"], kind="mergesort").reset_index(drop=True)


def logical_split_output_hash(frame: pd.DataFrame) -> str:
    return _stable_records_hash(frame, ("security_id", "session_date"))
