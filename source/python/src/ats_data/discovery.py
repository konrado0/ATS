from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import polars as pl
import pyarrow.parquet as pq

from ats_contracts.schemas import schema_for
from ats_data.hashing import object_hash, schema_fingerprint
from ats_data.manifest import DatasetManifest


def _pinned(manifest_path: Path) -> tuple[Path, object]:
    path = manifest_path.resolve()
    if path.name != "manifest.json" or path.parent.parent.name != "versions":
        raise ValueError("a pinned explicit version manifest is required; current/latest pointers are forbidden")
    raw = json.loads(path.read_text(encoding="utf-8"))
    stable = dict(raw); expected_hash = stable.pop("manifest_hash", None)
    if expected_hash != object_hash(stable):
        raise ValueError("pinned manifest logical hash mismatch")
    manifest = DatasetManifest.model_validate(raw)
    if path.parent.name != manifest.dataset_version_id:
        raise ValueError("pinned manifest/version directory mismatch")
    for table in manifest.tables:
        for record in table.files:
            parquet_path = (path.parent / record.path).resolve()
            if not parquet_path.is_relative_to(path.parent) or not parquet_path.is_file():
                raise ValueError(f"missing or escaped manifest file: {record.path}")
            if parquet_path.stat().st_size != record.bytes:
                raise ValueError(f"manifest file-size mismatch: {record.path}")
            schema = pq.read_schema(parquet_path).remove_metadata()
            if schema != schema_for(table.table_name, record.schema_version) or schema_fingerprint(schema) != record.schema_fingerprint:
                raise ValueError(f"manifest Parquet schema mismatch: {record.path}")
    return path, manifest


def manifest_files(manifest_path: Path, table_name: str) -> list[Path]:
    path, manifest = _pinned(manifest_path)
    record = next((record for record in manifest.tables if record.table_name == table_name), None)
    if record is None:
        raise KeyError(f"table not present in pinned manifest: {table_name}")
    return [(path.parent / item.path).resolve() for item in record.files]


def scan_table(manifest_path: Path, table_name: str) -> pl.LazyFrame:
    files = manifest_files(manifest_path, table_name)
    return pl.scan_parquet([str(path) for path in files], glob=False, missing_columns="raise", extra_columns="raise")


def create_duckdb_catalog(manifest_path: Path, catalog_path: Path) -> dict[str, object]:
    path, manifest = _pinned(manifest_path)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(catalog_path))
    try:
        created: list[str] = []
        for table in manifest.tables:
            files = [(path.parent / item.path).resolve().as_posix().replace("'", "''") for item in table.files]
            literal = "[" + ",".join(f"'{item}'" for item in files) + "]"
            name = table.table_name.replace('"', '""')
            connection.execute(f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM read_parquet({literal}, union_by_name=false)')
            created.append(table.table_name)
        connection.execute("CREATE TABLE IF NOT EXISTS ats_catalog_metadata(dataset_version_id VARCHAR, manifest_path VARCHAR)")
        connection.execute("DELETE FROM ats_catalog_metadata")
        connection.execute("INSERT INTO ats_catalog_metadata VALUES (?, ?)", [manifest.dataset_version_id, path.as_posix()])
    finally:
        connection.close()
    return {"dataset_version_id": manifest.dataset_version_id, "views": created, "catalog": catalog_path.as_posix()}


def cross_sectional_membership_input(manifest_path: Path, universe_id: str, start_date: str, end_date: str) -> pl.LazyFrame:
    membership = scan_table(manifest_path, "universe_membership").filter(
        (pl.col("universe_id") == universe_id)
        & (pl.col("valid_from") <= pl.lit(end_date).str.to_date())
        & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= pl.lit(start_date).str.to_date()))
    )
    return membership.with_columns(
        pl.when(pl.col("security_id").is_not_null() & (pl.col("member_state") == "official_resolved"))
        .then(pl.lit(1)).otherwise(pl.lit(0)).alias("usable_identity_count")
    )


def clear_derived_cache(cache_path: Path, phase_root: Path) -> None:
    target = cache_path.resolve()
    allowed = (phase_root.resolve() / "cache").resolve()
    if target == allowed or not target.is_relative_to(allowed):
        raise ValueError("only a concrete child beneath phase_b/cache may be deleted")
    if target.exists():
        shutil.rmtree(target)
