from __future__ import annotations

import pyarrow as pa


SCHEMA_VERSION = "ats.canonical.v2"
LEGACY_SCHEMA_VERSION = "ats.canonical.v1"
UTC_US = pa.timestamp("us", tz="UTC")


def _field(name: str, dtype: pa.DataType, nullable: bool = False) -> pa.Field:
    return pa.field(name, dtype, nullable=nullable)


_V1_SCHEMAS: dict[str, pa.Schema] = {
    "security_master": pa.schema([
        _field("security_id", pa.string()),
        _field("issuer_id", pa.string(), True),
        _field("market", pa.string()),
        _field("venue_mic", pa.string()),
        _field("instrument_type", pa.string()),
        _field("base_currency", pa.string()),
        _field("valid_from", pa.date32()),
        _field("valid_to", pa.date32(), True),
        _field("identity_status", pa.string()),
        _field("status", pa.string()),
        _field("source", pa.string()),
        _field("schema_version", pa.string()),
    ]),
    "security_aliases": pa.schema([
        _field("security_id", pa.string(), True),
        _field("identifier_type", pa.string()),
        _field("identifier_value", pa.string(), True),
        _field("raw_identifier", pa.string()),
        _field("market", pa.string()),
        _field("venue_mic", pa.string(), True),
        _field("vendor", pa.string(), True),
        _field("valid_from", pa.date32()),
        _field("valid_to", pa.date32(), True),
        _field("source", pa.string()),
        _field("provenance", pa.string()),
        _field("resolution_status", pa.string()),
        _field("schema_version", pa.string()),
    ]),
    "bars": pa.schema([
        _field("security_id", pa.string()),
        _field("market", pa.string()),
        _field("venue_mic", pa.string()),
        _field("frequency", pa.string()),
        _field("event_ts", UTC_US),
        _field("session_date", pa.date32()),
        _field("available_ts", UTC_US),
        _field("open", pa.float64()),
        _field("high", pa.float64()),
        _field("low", pa.float64()),
        _field("close", pa.float64()),
        _field("volume", pa.float64()),
        _field("turnover", pa.float64(), True),
        _field("currency", pa.string()),
        _field("source", pa.string()),
        _field("source_record_id", pa.string()),
        _field("adjustment_state", pa.string()),
        _field("adjustment_version", pa.string()),
        _field("ingest_batch_id", pa.string()),
        _field("ingested_at", UTC_US),
        _field("quality_state", pa.string()),
        _field("quality_flags", pa.string()),
        _field("resolution_state", pa.string()),
        _field("schema_version", pa.string()),
    ]),
    "universe_membership": pa.schema([
        _field("universe_id", pa.string()),
        _field("universe_component", pa.string()),
        _field("security_id", pa.string(), True),
        _field("raw_identifier", pa.string()),
        _field("valid_from", pa.date32()),
        _field("valid_to", pa.date32(), True),
        _field("announced_at", UTC_US, True),
        _field("available_ts", UTC_US, True),
        _field("source", pa.string()),
        _field("source_record_id", pa.string()),
        _field("provenance", pa.string()),
        _field("resolution_status", pa.string()),
        _field("member_state", pa.string()),
        _field("official_denominator", pa.int32()),
        _field("schema_version", pa.string()),
    ]),
    "security_events": pa.schema([
        _field("event_id", pa.string()),
        _field("security_id", pa.string(), True),
        _field("related_security_id", pa.string(), True),
        _field("market", pa.string()),
        _field("event_type", pa.string()),
        _field("event_ts", UTC_US),
        _field("available_ts", UTC_US),
        _field("effective_date", pa.date32(), True),
        _field("terms_json", pa.string()),
        _field("source", pa.string()),
        _field("source_record_id", pa.string()),
        _field("revision", pa.int32()),
        _field("resolution_status", pa.string()),
        _field("schema_version", pa.string()),
    ]),
    "corporate_actions": pa.schema([
        _field("action_id", pa.string()),
        _field("security_id", pa.string(), True),
        _field("related_security_id", pa.string(), True),
        _field("market", pa.string()),
        _field("action_type", pa.string()),
        _field("event_ts", UTC_US),
        _field("available_ts", UTC_US),
        _field("ex_date", pa.date32(), True),
        _field("pay_date", pa.date32(), True),
        _field("ratio", pa.float64(), True),
        _field("cash_amount", pa.float64(), True),
        _field("currency", pa.string(), True),
        _field("terms_json", pa.string()),
        _field("source", pa.string()),
        _field("source_record_id", pa.string()),
        _field("revision", pa.int32()),
        _field("resolution_status", pa.string()),
        _field("schema_version", pa.string()),
    ]),
    "macro_series": pa.schema([
        _field("series_id", pa.string()),
        _field("market", pa.string(), True),
        _field("event_ts", UTC_US),
        _field("available_ts", UTC_US),
        _field("value", pa.float64()),
        _field("unit", pa.string()),
        _field("frequency", pa.string()),
        _field("source", pa.string()),
        _field("source_record_id", pa.string()),
        _field("revision", pa.int32()),
        _field("vintage", pa.string()),
        _field("quality_state", pa.string()),
        _field("schema_version", pa.string()),
    ]),
    "lineage_records": pa.schema([
        _field("dataset_version_id", pa.string()),
        _field("parent_version_id", pa.string(), True),
        _field("reason", pa.string()),
        _field("source_hashes_json", pa.string()),
        _field("configuration_hash", pa.string()),
        _field("schema_versions_json", pa.string()),
        _field("row_differences_json", pa.string()),
        _field("content_differences_json", pa.string()),
        _field("git_commit", pa.string()),
        _field("environment_json", pa.string()),
        _field("created_at", UTC_US),
        _field("schema_version", pa.string()),
    ]),
    "dataset_manifests": pa.schema([
        _field("dataset_version_id", pa.string()),
        _field("manifest_hash", pa.string()),
        _field("table_name", pa.string()),
        _field("file_path", pa.string()),
        _field("file_size", pa.int64()),
        _field("physical_hash", pa.string()),
        _field("logical_hash", pa.string()),
        _field("row_count", pa.int64()),
        _field("semantic_key_json", pa.string()),
        _field("schema_fingerprint", pa.string()),
        _field("table_schema_version", pa.string()),
        _field("min_event_ts", UTC_US, True),
        _field("max_event_ts", UTC_US, True),
        _field("market", pa.string(), True),
        _field("frequency", pa.string(), True),
        _field("schema_version", pa.string()),
    ]),
    "ingestion_issues": pa.schema([
        _field("source", pa.string()),
        _field("source_record_id", pa.string()),
        _field("market", pa.string()),
        _field("raw_identifier", pa.string()),
        _field("issue_code", pa.string()),
        _field("raw_payload_json", pa.string()),
        _field("detected_at", UTC_US),
        _field("resolution_state", pa.string()),
        _field("schema_version", pa.string()),
    ]),
}


# Version 2 separates observed source coverage from asserted identifier/listing
# validity.  The latter is intentionally nullable: a bar file is evidence that a
# symbol was observed, not evidence of issuer continuity or an authoritative
# listing interval.
SCHEMAS: dict[str, pa.Schema] = dict(_V1_SCHEMAS)
SCHEMAS["security_master"] = pa.schema([
    _field("security_id", pa.string()),
    _field("issuer_id", pa.string(), True),
    _field("market", pa.string()),
    _field("venue_mic", pa.string()),
    _field("instrument_type", pa.string()),
    _field("base_currency", pa.string()),
    _field("valid_from", pa.date32(), True),
    _field("valid_to", pa.date32(), True),
    _field("observed_from", pa.date32(), True),
    _field("observed_to", pa.date32(), True),
    _field("identity_status", pa.string()),
    _field("status", pa.string()),
    _field("source", pa.string()),
    _field("schema_version", pa.string()),
])
SCHEMAS["security_aliases"] = pa.schema([
    _field("security_id", pa.string(), True),
    _field("identifier_type", pa.string()),
    _field("identifier_value", pa.string(), True),
    _field("raw_identifier", pa.string()),
    _field("market", pa.string()),
    _field("venue_mic", pa.string(), True),
    _field("vendor", pa.string(), True),
    _field("valid_from", pa.date32(), True),
    _field("valid_to", pa.date32(), True),
    _field("observed_from", pa.date32(), True),
    _field("observed_to", pa.date32(), True),
    _field("source", pa.string()),
    _field("provenance", pa.string()),
    _field("resolution_status", pa.string()),
    _field("schema_version", pa.string()),
])

SCHEMA_REGISTRY: dict[str, dict[str, pa.Schema]] = {
    LEGACY_SCHEMA_VERSION: _V1_SCHEMAS,
    SCHEMA_VERSION: SCHEMAS,
}


SEMANTIC_KEYS: dict[str, tuple[str, ...]] = {
    "security_master": ("security_id",),
    "security_aliases": ("security_id", "identifier_type", "identifier_value", "venue_mic", "vendor", "valid_from"),
    "bars": ("security_id", "event_ts", "frequency", "source", "adjustment_version"),
    "universe_membership": ("universe_id", "universe_component", "raw_identifier", "valid_from"),
    "security_events": ("event_id", "revision"),
    "corporate_actions": ("action_id", "revision"),
    "macro_series": ("series_id", "event_ts", "source", "revision", "vintage"),
    "lineage_records": ("dataset_version_id",),
    "dataset_manifests": ("dataset_version_id", "table_name", "file_path"),
    "ingestion_issues": ("source", "source_record_id", "issue_code"),
}


SORT_ORDERS: dict[str, tuple[str, ...]] = {
    "security_master": ("security_id",),
    "security_aliases": ("security_id", "identifier_type", "valid_from", "identifier_value"),
    "bars": ("security_id", "event_ts", "source", "adjustment_version"),
    "universe_membership": ("universe_id", "valid_from", "universe_component", "raw_identifier"),
    "security_events": ("security_id", "event_ts", "available_ts", "event_id", "revision"),
    "corporate_actions": ("security_id", "event_ts", "available_ts", "action_id", "revision"),
    "macro_series": ("series_id", "event_ts", "available_ts", "revision"),
    "lineage_records": ("dataset_version_id",),
    "dataset_manifests": ("table_name", "file_path"),
    "ingestion_issues": ("market", "raw_identifier", "source_record_id", "issue_code"),
}


def schema_for(table_name: str, version: str = SCHEMA_VERSION) -> pa.Schema:
    try:
        return SCHEMA_REGISTRY[version][table_name]
    except KeyError as exc:
        raise KeyError(f"unknown canonical table/version: {table_name}/{version}") from exc


def semantic_key_for(table_name: str) -> tuple[str, ...]:
    return SEMANTIC_KEYS[table_name]
