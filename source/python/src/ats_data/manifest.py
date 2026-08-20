from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    bytes: int
    physical_sha256: str
    logical_hash: str
    logical_hash_algorithm: str = "arrow_ipc_v1"
    rows: int
    row_groups: int
    semantic_key: list[str]
    schema_fingerprint: str
    schema_version: str
    min_event_ts: str | None = None
    max_event_ts: str | None = None
    market: str | None = None
    frequency: str | None = None


class TableRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    table_name: str
    rows: int
    files: list[FileRecord]
    logical_hash: str
    logical_hash_algorithm: str = "arrow_ipc_v1"
    semantic_key: list[str]
    schema_fingerprint: str
    schema_version: str
    min_event_ts: str | None = None
    max_event_ts: str | None = None
    markets: list[str]
    frequencies: list[str]

    @model_validator(mode="after")
    def totals_match(self) -> "TableRecord":
        if sum(item.rows for item in self.files) != self.rows:
            raise ValueError(f"file rows do not sum to table rows: {self.table_name}")
        if len({item.path for item in self.files}) != len(self.files):
            raise ValueError(f"duplicate manifest file paths: {self.table_name}")
        return self


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_schema_version: str = "ats.dataset_manifest.v1"
    dataset_version_id: str
    dataset_name: str
    created_at: str
    tables: list[TableRecord]
    source_provenance: list[dict[str, Any]]
    source_hashes: dict[str, str]
    writer_settings: dict[str, Any]
    parent_version_id: str | None = None
    correction_reason: str
    row_differences: dict[str, int | None]
    content_differences: dict[str, dict[str, str | None]]
    configuration: dict[str, Any]
    configuration_hash: str
    git_provenance: dict[str, Any]
    environment: dict[str, str]
    implementation_provenance: dict[str, Any] | None = None
    environment_lock: dict[str, str] | None = None
    environment_lock_hash: str | None = None
    manifest_hash: str

    @model_validator(mode="after")
    def unique_tables(self) -> "DatasetManifest":
        names = [table.table_name for table in self.tables]
        if len(names) != len(set(names)):
            raise ValueError("duplicate table records in manifest")
        return self
