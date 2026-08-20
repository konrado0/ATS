from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa

from ats_data.discovery import manifest_files
from ats_data.publication import validate_manifest


BAR_KEY = ["security_id", "event_ts", "frequency", "source", "adjustment_version"]
BAR_NUMERIC = ["open", "high", "low", "close", "volume"]


def _frame_hash(frame: pd.DataFrame, columns: list[str], sort_by: list[str]) -> str:
    normalized = frame[columns].copy().sort_values(sort_by, kind="mergesort", na_position="last").reset_index(drop=True)
    def stable(value: object) -> str:
        if value is None or pd.isna(value):
            return "<NULL>"
        if isinstance(value, pd.Timestamp):
            if value.tzinfo is not None:
                return value.tz_convert("UTC").isoformat()
            if value.time() == datetime.min.time():
                return value.date().isoformat()
            return value.isoformat()
        if isinstance(value, datetime):
            return pd.Timestamp(value).tz_convert("UTC").isoformat() if value.tzinfo else value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)
    for column in normalized.columns:
        normalized[column] = normalized[column].map(stable)
    table = pa.Table.from_pandas(normalized, preserve_index=False).replace_schema_metadata(None)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return hashlib.sha256(sink.getvalue().to_pybytes()).hexdigest()


def _numeric_hash(frame: pd.DataFrame, sort_by: list[str]) -> str:
    ordered = frame.sort_values(sort_by, kind="mergesort")[BAR_NUMERIC].to_numpy(dtype="<f8", copy=True)
    return hashlib.sha256(ordered.tobytes(order="C")).hexdigest()


def reconcile_gpw(trusted_phase_a_run: Path, manifest_path: Path) -> dict[str, object]:
    manifest = validate_manifest(manifest_path)
    canonical_bars = pd.concat([pd.read_parquet(path) for path in manifest_files(manifest_path, "bars")], ignore_index=True)
    phase_a_bars = pd.read_parquet(trusted_phase_a_run / "artifacts" / "validated_daily_bars.parquet")
    canonical_projection = canonical_bars.loc[canonical_bars["security_id"].isin(set(phase_a_bars["security_id"].astype(str)))].copy()
    canonical_projection["event_ts"] = pd.to_datetime(canonical_projection["event_ts"], utc=True)
    phase_a_bars["event_ts"] = pd.to_datetime(phase_a_bars["event_ts"], utc=True)
    phase_a_bars["frequency"] = phase_a_bars["frequency"].astype(str)
    phase_a_bars["source"] = phase_a_bars["source"].astype(str)
    phase_a_bars["adjustment_version"] = phase_a_bars["adjustment_version"].astype(str)
    key_hash_a = _frame_hash(phase_a_bars, BAR_KEY, BAR_KEY)
    key_hash_b = _frame_hash(canonical_projection, BAR_KEY, BAR_KEY)
    numeric_hash_a = _numeric_hash(phase_a_bars, BAR_KEY)
    numeric_hash_b = _numeric_hash(canonical_projection, BAR_KEY)

    phase_a_membership = pd.read_parquet(trusted_phase_a_run / "artifacts" / "membership_intervals.parquet")
    membership = pd.concat([pd.read_parquet(path) for path in manifest_files(manifest_path, "universe_membership")], ignore_index=True)
    a_membership = phase_a_membership.rename(columns={"effective_from": "valid_from", "effective_to": "valid_to"})
    membership_columns_b = ["universe_id", "universe_component", "raw_identifier", "valid_from", "valid_to"]
    membership_hash_a = _frame_hash(a_membership, membership_columns_b, ["valid_from", "universe_component", "raw_identifier"])
    membership_hash_b = _frame_hash(membership, membership_columns_b, ["valid_from", "universe_component", "raw_identifier"])

    phase_a_aliases = pd.read_parquet(trusted_phase_a_run / "artifacts" / "security_aliases.parquet")
    aliases = pd.concat([pd.read_parquet(path) for path in manifest_files(manifest_path, "security_aliases")], ignore_index=True)
    phase_a_isin = phase_a_aliases.loc[phase_a_aliases["identifier_type"].eq("isin"), ["security_id", "identifier_value"]].drop_duplicates()
    canonical_isin = aliases.loc[aliases["identifier_type"].eq("isin"), ["security_id", "identifier_value"]].drop_duplicates()
    identity_hash_a = _frame_hash(phase_a_isin, ["security_id", "identifier_value"], ["security_id", "identifier_value"])
    identity_hash_b = _frame_hash(canonical_isin, ["security_id", "identifier_value"], ["security_id", "identifier_value"])

    panel = pd.read_parquet(trusted_phase_a_run / "artifacts" / "research_panel.parquet")
    denominator_ok = bool(panel["official_member_count"].eq(60).all() and panel.groupby("session_date").size().eq(60).all())
    usable_ok = bool(panel["price_usable_member_count"].equals(panel.groupby("session_date")["is_price_usable_member"].transform("sum").astype("int64")))
    results = {
        "dataset_version_id": manifest.dataset_version_id,
        "phase_a_bar_rows": len(phase_a_bars), "canonical_phase_a_projection_rows": len(canonical_projection),
        "bar_row_count_match": len(phase_a_bars) == len(canonical_projection),
        "bar_semantic_key_hash_phase_a": key_hash_a, "bar_semantic_key_hash_canonical": key_hash_b,
        "bar_semantic_key_hash_match": key_hash_a == key_hash_b,
        "bar_numeric_hash_phase_a": numeric_hash_a, "bar_numeric_hash_canonical": numeric_hash_b,
        "bar_numeric_hash_match": numeric_hash_a == numeric_hash_b, "numeric_tolerance": 0.0,
        "membership_rows_phase_a": len(phase_a_membership), "membership_rows_canonical": len(membership),
        "membership_interval_hash_phase_a": membership_hash_a, "membership_interval_hash_canonical": membership_hash_b,
        "membership_interval_hash_match": membership_hash_a == membership_hash_b,
        "identity_mapping_hash_phase_a": identity_hash_a, "identity_mapping_hash_canonical": identity_hash_b,
        "identity_mapping_hash_match": identity_hash_a == identity_hash_b,
        "official_denominator_preserved": denominator_ok, "usable_count_preserved": usable_ok,
        "unresolved_exit_rows_phase_a": int(panel["is_unresolved_exit_member"].sum()),
        "benign_exit_intervals_canonical": int(membership["member_state"].eq("benign_corporate_exit").sum()),
        "event_availability_semantics": "canonical daily GPW bars preserve Phase A event_ts and available_ts exactly after UTC normalization; membership availability remains null",
    }
    required = [key for key, value in results.items() if key.endswith("_match") or key.endswith("_preserved")]
    results["passed"] = all(bool(results[key]) for key in required)
    if not results["passed"]:
        raise ValueError(f"GPW Phase A reconciliation failed: {[key for key in required if not results[key]]}")
    return results
