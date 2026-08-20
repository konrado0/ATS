from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from ats_contracts.schemas import SCHEMA_VERSION, SEMANTIC_KEYS, schema_for
from ats_contracts.validation import ContractError, validate_table
from ats_data.config import PhaseBConfig
from ats_data.hashing import file_hash, logical_table_hash, object_hash, schema_fingerprint, sorted_table
from ats_data.manifest import DatasetManifest, FileRecord, TableRecord


class PublicationError(RuntimeError):
    pass


class PublishedVersionExists(PublicationError):
    pass


def _git_provenance() -> dict[str, object]:
    repo = Path(__file__).resolve().parents[4]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "status_porcelain": status}


def _environment() -> dict[str, str]:
    import duckdb
    import polars

    return {
        "python": platform.python_version(), "platform": platform.platform(),
        "pyarrow": pa.__version__, "polars": polars.__version__, "duckdb": duckdb.__version__,
    }


def _iso_min_max(table: pa.Table) -> tuple[str | None, str | None]:
    if "event_ts" not in table.column_names or table.num_rows == 0:
        return None, None
    return pc.min(table["event_ts"]).as_py().isoformat(), pc.max(table["event_ts"]).as_py().isoformat()


def _unique_strings(table: pa.Table, column: str) -> list[str]:
    if column not in table.column_names:
        return []
    return sorted(str(value.as_py()) for value in pc.unique(table[column]) if value.as_py() is not None)


def _part_groups(table: pa.Table) -> list[tuple[str | None, str | None, pa.Table]]:
    markets = _unique_strings(table, "market") or [None]
    frequencies = _unique_strings(table, "frequency") or [None]
    result: list[tuple[str | None, str | None, pa.Table]] = []
    for market in markets:
        for frequency in frequencies:
            mask = None
            if market is not None:
                mask = pc.equal(table["market"], market)
            if frequency is not None:
                frequency_mask = pc.equal(table["frequency"], frequency)
                mask = frequency_mask if mask is None else pc.and_(mask, frequency_mask)
            subset = table if mask is None else table.filter(mask)
            if subset.num_rows:
                result.append((market, frequency, subset))
    return result


def _relative_data_path(table_name: str, market: str | None, frequency: str | None, part: int) -> Path:
    path = Path("data") / table_name
    if market is not None:
        path /= f"market={market}"
    if frequency is not None:
        path /= f"frequency={frequency}"
    return path / f"part-{part:03d}.parquet"


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _manifest_hash(value: dict[str, object]) -> str:
    stable = dict(value)
    stable.pop("manifest_hash", None)
    return object_hash(stable)


def _parent_differences(config: PhaseBConfig, parent_id: str | None, tables: dict[str, pa.Table], hashes: dict[str, str]) -> tuple[dict[str, int | None], dict[str, dict[str, str | None]]]:
    if parent_id is None:
        return ({name: table.num_rows for name, table in tables.items()}, {name: {"parent": None, "current": hashes[name]} for name in tables})
    parent_path = config.phase_root / "versions" / parent_id / "manifest.json"
    parent = validate_manifest(parent_path)
    previous = {record.table_name: record for record in parent.tables}
    row_diff: dict[str, int | None] = {}
    content_diff: dict[str, dict[str, str | None]] = {}
    for name, table in tables.items():
        old = previous.get(name)
        row_diff[name] = table.num_rows - old.rows if old else None
        content_diff[name] = {"parent": old.logical_hash if old else None, "current": hashes[name]}
    return row_diff, content_diff


class Publisher:
    def __init__(self, config: PhaseBConfig):
        self.config = config

    def version_identity(self, dataset_name: str, tables: dict[str, pa.Table], source_hashes: dict[str, str], parent_version_id: str | None, reason: str) -> str:
        for name, table in tables.items():
            validate_table(name, table)
        payload = {
            "dataset_name": dataset_name,
            "tables": {name: logical_table_hash(name, table, algorithm="arrow_ipc_stream_batches_v2") for name, table in sorted(tables.items())},
            "source_hashes": dict(sorted(source_hashes.items())),
            "configuration": self.config.identity_dict(),
            "parent_version_id": parent_version_id,
            "reason": reason,
        }
        return f"phaseb-{object_hash(payload)[:20]}"

    def publish(
        self, dataset_name: str, tables: dict[str, pa.Table], source_hashes: dict[str, str],
        source_provenance: list[dict[str, object]], reason: str, parent_version_id: str | None = None,
    ) -> Path:
        if not tables:
            raise PublicationError("cannot publish an empty logical dataset")
        prepared: dict[str, pa.Table] = {}
        logical_hashes: dict[str, str] = {}
        for name, table in tables.items():
            validate_table(name, table)
            prepared[name] = sorted_table(name, table)
            logical_hashes[name] = logical_table_hash(name, prepared[name], assume_sorted=True, algorithm="arrow_ipc_stream_batches_v2")
        identity_payload = {
            "dataset_name": dataset_name, "tables": dict(sorted(logical_hashes.items())),
            "source_hashes": dict(sorted(source_hashes.items())), "configuration": self.config.identity_dict(),
            "parent_version_id": parent_version_id, "reason": reason,
        }
        version_id = f"phaseb-{object_hash(identity_payload)[:20]}"
        versions_root = self.config.phase_root / "versions"
        destination = versions_root / version_id
        if destination.exists():
            raise PublishedVersionExists(f"published version already exists and cannot be overwritten: {version_id}")
        row_diff, content_diff = _parent_differences(self.config, parent_version_id, prepared, logical_hashes)
        staging_root = self.config.phase_root / "staging"
        stage = staging_root / f"{version_id}-{uuid.uuid4().hex}"
        stage.mkdir(parents=True, exist_ok=False)
        try:
            table_records: list[TableRecord] = []
            for table_name, table in sorted(prepared.items()):
                files: list[FileRecord] = []
                for market, frequency, group in _part_groups(table):
                    limit = self.config.max_rows_per_file or max(group.num_rows, 1)
                    for part_index, offset in enumerate(range(0, group.num_rows, limit)):
                        part = group.slice(offset, min(limit, group.num_rows - offset))
                        relative = _relative_data_path(table_name, market, frequency, part_index)
                        path = stage / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        pq.write_table(
                            part, path, compression=self.config.compression,
                            compression_level=self.config.compression_level,
                            row_group_size=self.config.row_group_size, version="2.6", write_statistics=True,
                        )
                        metadata = pq.read_metadata(path)
                        minimum, maximum = _iso_min_max(part)
                        files.append(FileRecord(
                            path=relative.as_posix(), bytes=path.stat().st_size, physical_sha256=file_hash(path),
                            logical_hash=logical_table_hash(table_name, part, assume_sorted=True, algorithm="arrow_ipc_stream_batches_v2"),
                            logical_hash_algorithm="arrow_ipc_stream_batches_v2", rows=part.num_rows,
                            row_groups=metadata.num_row_groups, semantic_key=list(SEMANTIC_KEYS[table_name]),
                            schema_fingerprint=schema_fingerprint(part.schema), schema_version=SCHEMA_VERSION,
                            min_event_ts=minimum, max_event_ts=maximum, market=market, frequency=frequency,
                        ))
                minimum, maximum = _iso_min_max(table)
                table_records.append(TableRecord(
                    table_name=table_name, rows=table.num_rows, files=files,
                    logical_hash=logical_hashes[table_name], logical_hash_algorithm="arrow_ipc_stream_batches_v2", semantic_key=list(SEMANTIC_KEYS[table_name]),
                    schema_fingerprint=schema_fingerprint(table.schema), schema_version=SCHEMA_VERSION,
                    min_event_ts=minimum, max_event_ts=maximum,
                    markets=_unique_strings(table, "market"), frequencies=_unique_strings(table, "frequency"),
                ))
            created_at = datetime.now(timezone.utc).isoformat()
            config_value = self.config.identity_dict()
            manifest_value: dict[str, object] = {
                "manifest_schema_version": "ats.dataset_manifest.v1", "dataset_version_id": version_id,
                "dataset_name": dataset_name, "created_at": created_at,
                "tables": [record.model_dump(mode="json") for record in table_records],
                "source_provenance": source_provenance, "source_hashes": dict(sorted(source_hashes.items())),
                "writer_settings": {
                    "compression": self.config.compression.upper(), "compression_level": self.config.compression_level,
                    "row_group_size": self.config.row_group_size, "max_rows_per_file": self.config.max_rows_per_file,
                    "split_size_review_bytes": self.config.split_size_review_bytes,
                    "split_policy": "review only after query/rebuild SLO failure or materially degraded maintenance; not a fixed 2 GiB partition rule",
                    "organization": "one or a few compact files per (table, market, frequency); no security/ticker/time partitions",
                },
                "parent_version_id": parent_version_id, "correction_reason": reason,
                "row_differences": row_diff, "content_differences": content_diff,
                "configuration": config_value, "configuration_hash": object_hash(config_value),
                "git_provenance": _git_provenance(), "environment": _environment(), "manifest_hash": "",
            }
            manifest_value["manifest_hash"] = _manifest_hash(manifest_value)
            _atomic_json(stage / "manifest.json", manifest_value)
            validate_manifest(stage / "manifest.json", expected_root=stage)
            versions_root.mkdir(parents=True, exist_ok=True)
            os.replace(stage, destination)
            _atomic_json(self.config.phase_root / "catalogs" / f"{dataset_name}.current.json", {
                "dataset_name": dataset_name, "dataset_version_id": version_id,
                "manifest": (Path("..") / ".." / "versions" / version_id / "manifest.json").as_posix(),
                "updated_at": created_at, "discovery_only": True,
                "warning": "Experiments must pin the explicit version manifest and must not resolve this pointer during execution.",
            })
            return destination / "manifest.json"
        except Exception:
            if stage.exists():
                try:
                    shutil.rmtree(stage)
                except OSError:
                    pass
            raise


def validate_manifest(manifest_path: Path, expected_root: Path | None = None) -> DatasetManifest:
    manifest_path = manifest_path.resolve()
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = DatasetManifest.model_validate(raw)
    if _manifest_hash(raw) != manifest.manifest_hash:
        raise PublicationError("manifest logical hash mismatch")
    root = expected_root.resolve() if expected_root else manifest_path.parent
    if expected_root is None and manifest_path.parent.name != manifest.dataset_version_id:
        raise PublicationError("manifest is not pinned beneath its explicit version directory")
    declared: set[str] = set()
    for table_record in manifest.tables:
        pieces: list[pa.Table] = []
        for record in table_record.files:
            if record.path in declared:
                raise PublicationError(f"file declared more than once: {record.path}")
            declared.add(record.path)
            path = (root / record.path).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise PublicationError(f"missing or escaped manifest file: {record.path}")
            if path.stat().st_size != record.bytes or file_hash(path) != record.physical_sha256:
                raise PublicationError(f"physical file validation failed: {record.path}")
            parquet = pq.ParquetFile(path)
            if parquet.schema_arrow.remove_metadata() != schema_for(table_record.table_name):
                raise PublicationError(f"Parquet schema drift: {record.path}")
            if parquet.metadata.num_rows != record.rows or parquet.metadata.num_row_groups != record.row_groups:
                raise PublicationError(f"Parquet statistics mismatch: {record.path}")
            part = parquet.read()
            parquet.close()
            if logical_table_hash(table_record.table_name, part, assume_sorted=True, algorithm=record.logical_hash_algorithm) != record.logical_hash:
                raise PublicationError(f"logical file hash mismatch: {record.path}")
            pieces.append(part)
        combined = pa.concat_tables(pieces) if pieces else pa.Table.from_batches([], schema=schema_for(table_record.table_name))
        validate_table(table_record.table_name, combined)
        if combined.num_rows != table_record.rows or logical_table_hash(table_record.table_name, combined, assume_sorted=True, algorithm=table_record.logical_hash_algorithm) != table_record.logical_hash:
            raise PublicationError(f"logical table validation failed: {table_record.table_name}")
    actual = {path.relative_to(root).as_posix() for path in (root / "data").rglob("*.parquet")} if (root / "data").exists() else set()
    if actual != declared:
        raise PublicationError(f"manifest/data file set mismatch: missing={sorted(declared-actual)}, unexpected={sorted(actual-declared)}")
    return manifest


def recover_valid_staging(config: PhaseBConfig, stage: Path) -> Path:
    """Re-hash and publish a complete failed stage after a hash-algorithm fix.

    Recovery never trusts partial output: every listed Parquet file is re-read, all
    tables pass the current contracts, and the complete stage passes manifest
    validation before the atomic rename and pointer update.
    """
    stage = stage.resolve()
    staging_root = (config.phase_root / "staging").resolve()
    if not stage.is_relative_to(staging_root) or stage == staging_root:
        raise PublicationError("recovery target must be a concrete child of phase_b/staging")
    raw = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    tables: dict[str, pa.Table] = {}
    hashes: dict[str, str] = {}
    for table_record in raw["tables"]:
        name = table_record["table_name"]
        pieces: list[pa.Table] = []
        for file_record in table_record["files"]:
            path = stage / file_record["path"]
            part = pq.read_table(path)
            digest = logical_table_hash(name, part, assume_sorted=True, algorithm="arrow_ipc_stream_batches_v2")
            file_record["logical_hash"] = digest
            file_record["logical_hash_algorithm"] = "arrow_ipc_stream_batches_v2"
            pieces.append(part)
        combined = pa.concat_tables(pieces)
        validate_table(name, combined)
        digest = logical_table_hash(name, combined, assume_sorted=True, algorithm="arrow_ipc_stream_batches_v2")
        table_record["logical_hash"] = digest
        table_record["logical_hash_algorithm"] = "arrow_ipc_stream_batches_v2"
        tables[name] = combined
        hashes[name] = digest
    identity_payload = {
        "dataset_name": raw["dataset_name"], "tables": dict(sorted(hashes.items())),
        "source_hashes": dict(sorted(raw["source_hashes"].items())), "configuration": raw["configuration"],
        "parent_version_id": raw["parent_version_id"], "reason": raw["correction_reason"],
    }
    version_id = f"phaseb-{object_hash(identity_payload)[:20]}"
    destination = config.phase_root / "versions" / version_id
    if destination.exists():
        raise PublishedVersionExists(f"published version already exists and cannot be overwritten: {version_id}")
    raw["dataset_version_id"] = version_id
    for name, digest in hashes.items():
        raw["content_differences"][name]["current"] = digest
    raw["manifest_hash"] = _manifest_hash(raw)
    _atomic_json(stage / "manifest.json", raw)
    validate_manifest(stage / "manifest.json", expected_root=stage)
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(stage, destination)
    _atomic_json(config.phase_root / "catalogs" / f"{raw['dataset_name']}.current.json", {
        "dataset_name": raw["dataset_name"], "dataset_version_id": version_id,
        "manifest": (Path("..") / ".." / "versions" / version_id / "manifest.json").as_posix(),
        "updated_at": raw["created_at"], "discovery_only": True,
        "warning": "Experiments must pin the explicit version manifest and must not resolve this pointer during execution.",
    })
    return destination / "manifest.json"
