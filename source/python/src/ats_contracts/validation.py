from __future__ import annotations

import math
import uuid

import pyarrow as pa
import pyarrow.compute as pc

from ats_contracts.schemas import SCHEMA_VERSION, SCHEMAS, SEMANTIC_KEYS


class ContractError(ValueError):
    pass


ENUMS: dict[str, dict[str, frozenset[str]]] = {
    "security_master": {
        "identity_status": frozenset({"authoritative", "resolved", "provisional_source_scoped", "unresolved"}),
        "status": frozenset({"active", "inactive", "known_official_member", "provisional_listing", "unresolved"}),
        "instrument_type": frozenset({"common_equity", "etf", "index", "fund", "unknown"}),
    },
    "security_aliases": {
        "identifier_type": frozenset({"ticker", "venue", "venue_mic", "isin", "vendor_symbol", "official_short_name"}),
        "resolution_status": frozenset({"resolved", "exact", "mapped_renamed", "mapped_successor", "provisional_source_scoped", "unresolved", "missing"}),
    },
    "bars": {
        "frequency": frozenset({"daily", "hourly", "minute"}),
        "adjustment_state": frozenset({"raw", "split_adjusted", "total_return_adjusted", "vendor_adjusted_semantics_unverified"}),
        "quality_state": frozenset({"accepted", "provisional", "quarantined"}),
        "resolution_state": frozenset({"resolved", "provisional_source_scoped", "unresolved"}),
    },
    "universe_membership": {
        "resolution_status": frozenset({"official_isin_resolved", "resolved", "provisional_source_scoped", "unresolved"}),
        "member_state": frozenset({"official_resolved", "official_unresolved", "benign_corporate_exit", "inactive"}),
    },
    "security_events": {
        "event_type": frozenset({"listing", "delisting", "suspension", "merger", "cash_takeover", "identifier_change", "other"}),
        "resolution_status": frozenset({"resolved", "provisional_source_scoped", "unresolved"}),
    },
    "corporate_actions": {
        "action_type": frozenset({"split", "reverse_split", "dividend", "rights", "spinoff", "merger", "cash_takeover", "other"}),
        "resolution_status": frozenset({"resolved", "provisional_source_scoped", "unresolved"}),
    },
    "macro_series": {"quality_state": frozenset({"accepted", "provisional", "quarantined"})},
    "ingestion_issues": {"resolution_state": frozenset({"quarantined_visible", "unresolved"})},
}


def _values(table: pa.Table, column: str) -> list[object]:
    return table[column].combine_chunks().to_pylist()


def _validate_exact_schema(table_name: str, table: pa.Table) -> None:
    expected = SCHEMAS[table_name]
    actual = table.schema.remove_metadata()
    if actual != expected:
        raise ContractError(f"unexpected schema for {table_name}: expected {expected}, got {actual}")


def _validate_versions(table_name: str, table: pa.Table) -> None:
    versions = {value.as_py() for value in pc.unique(table["schema_version"])}
    if versions != {SCHEMA_VERSION}:
        raise ContractError(f"incompatible schema versions for {table_name}: {sorted(map(str, versions))}")


def _validate_duplicates(table_name: str, table: pa.Table) -> None:
    key = SEMANTIC_KEYS[table_name]
    unique_rows = table.select(list(key)).group_by(list(key)).aggregate([]).num_rows
    if unique_rows != table.num_rows:
        raise ContractError(f"duplicate semantic key in {table_name}: rows={table.num_rows}, unique_keys={unique_rows}")


def _validate_enums(table_name: str, table: pa.Table) -> None:
    for column, allowed in ENUMS.get(table_name, {}).items():
        actual = {str(value.as_py()) for value in pc.unique(table[column]) if value.as_py() is not None}
        unknown = actual - allowed
        if unknown:
            raise ContractError(f"unknown enum values in {table_name}.{column}: {sorted(unknown)}")


def _validate_uuid_ids(table: pa.Table) -> None:
    if "security_id" not in table.column_names:
        return
    for scalar in pc.unique(table["security_id"]):
        value = scalar.as_py()
        if value is not None:
            try:
                uuid.UUID(str(value))
            except (ValueError, TypeError) as exc:
                raise ContractError(f"invalid security_id UUID: {value}") from exc


def _validate_intervals(table_name: str, table: pa.Table) -> None:
    if "valid_from" not in table.column_names:
        return
    invalid = pc.and_(pc.is_valid(table["valid_to"]), pc.less(table["valid_to"], table["valid_from"]))
    if pc.any(invalid).as_py():
        raise ContractError(f"invalid validity interval in {table_name}")


def _validate_alias_overlaps(table: pa.Table) -> None:
    groups: dict[tuple[object, ...], list[tuple[object, object, object, object]]] = {}
    columns = {name: _values(table, name) for name in table.column_names}
    for index in range(table.num_rows):
        if columns["identifier_type"][index] not in {"ticker", "isin", "vendor_symbol"}:
            continue
        if columns["identifier_value"][index] is None:
            continue
        namespace = (
            columns["identifier_type"][index], columns["identifier_value"][index],
            columns["market"][index], columns["venue_mic"][index], columns["vendor"][index],
        )
        groups.setdefault(namespace, []).append((columns["valid_from"][index], columns["valid_to"][index], columns["security_id"][index], columns["resolution_status"][index]))
    for namespace, intervals in groups.items():
        if intervals and all(item[3] == "provisional_source_scoped" for item in intervals):
            # Multiple unresolved source-scoped candidates are evidence to retain, not an adjudicated alias mapping.
            continue
        prior_end = None
        prior_security = None
        for start, end, security, _status in sorted(intervals, key=lambda item: item[0]):
            if prior_end is None and prior_security is not None:
                raise ContractError(f"overlapping open-ended alias intervals: {namespace}")
            if prior_end is not None and start <= prior_end:
                raise ContractError(f"overlapping alias intervals: {namespace}")
            prior_end, prior_security = end, security


def _validate_bars(table: pa.Table) -> None:
    numeric = ["open", "high", "low", "close", "volume"]
    finite = pc.is_finite(table[numeric[0]])
    for name in numeric[1:]:
        finite = pc.and_(finite, pc.is_finite(table[name]))
    if not pc.all(finite).as_py():
        raise ContractError("non-finite OHLCV")
    prohibited = pc.or_(pc.less_equal(table["open"], 0), pc.less_equal(table["high"], 0))
    prohibited = pc.or_(prohibited, pc.less_equal(table["low"], 0))
    prohibited = pc.or_(prohibited, pc.less_equal(table["close"], 0))
    prohibited = pc.or_(prohibited, pc.less(table["volume"], 0))
    if pc.any(prohibited).as_py():
        raise ContractError("negative or zero prohibited OHLCV")
    upper = pc.max_element_wise(table["open"], table["close"], table["low"])
    lower = pc.min_element_wise(table["open"], table["close"], table["high"])
    if pc.any(pc.or_(pc.less(table["high"], upper), pc.greater(table["low"], lower))).as_py():
        raise ContractError("inconsistent OHLC")
    if pc.any(pc.less(table["available_ts"], table["event_ts"])).as_py():
        raise ContractError("availability precedes event timestamp")
    daily = pc.equal(table["frequency"], "daily")
    event_dates = pc.cast(table["event_ts"], pa.date32())
    if pc.any(pc.and_(daily, pc.not_equal(table["session_date"], event_dates))).as_py():
        raise ContractError("daily session/event date mismatch")


def _validate_event_timing(table_name: str, table: pa.Table) -> None:
    if "event_ts" not in table.column_names or table_name == "bars":
        return
    if pc.any(pc.less(table["available_ts"], table["event_ts"])).as_py():
        raise ContractError(f"availability precedes event timestamp in {table_name}")


def validate_table(table_name: str, table: pa.Table) -> dict[str, object]:
    if table_name not in SCHEMAS:
        raise ContractError(f"unknown canonical table: {table_name}")
    table.validate(full=True)
    _validate_exact_schema(table_name, table)
    _validate_versions(table_name, table)
    _validate_duplicates(table_name, table)
    _validate_enums(table_name, table)
    _validate_uuid_ids(table)
    _validate_intervals(table_name, table)
    if table_name == "security_aliases":
        _validate_alias_overlaps(table)
    if table_name == "bars":
        _validate_bars(table)
    _validate_event_timing(table_name, table)
    return {"table": table_name, "rows": table.num_rows, "passed": True}
