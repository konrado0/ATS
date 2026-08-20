from __future__ import annotations

import json
import importlib.metadata
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

from ats_contracts.schemas import SCHEMA_VERSION, SEMANTIC_KEYS, SORT_ORDERS, schema_for
from ats_contracts.validation import ContractError, validate_table
from ats_data.config import PhaseBConfig
from ats_data.hashing import IncrementalArrowHasher, file_hash, logical_table_hash, object_hash, schema_fingerprint, sorted_table
from ats_data.manifest import DatasetManifest, FileRecord, TableRecord


class PublicationError(RuntimeError):
    pass


class PublishedVersionExists(PublicationError):
    pass


IMPLEMENTATION_PATHS = [
    "source/python/src/ats_data", "source/python/src/ats_contracts",
    "source/python/configs/phase_b_reference.yaml", "source/python/PHASE_B.md",
    "source/python/pyproject.toml",
    "source/python/tests/test_phase_b_*.py",
]


def _git_provenance() -> dict[str, object]:
    repo = Path(__file__).resolve().parents[4]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain", "--", *IMPLEMENTATION_PATHS], cwd=repo, capture_output=True, text=True, check=True).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "status_porcelain": status, "scope": IMPLEMENTATION_PATHS}


def _implementation_provenance() -> dict[str, object]:
    repo = Path(__file__).resolve().parents[4]
    git = _git_provenance()
    tracked = subprocess.run(
        ["git", "ls-files", "--", *IMPLEMENTATION_PATHS], cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    if not git["dirty"]:
        hashes = {
            name: __import__("hashlib").sha256(subprocess.run(
                ["git", "show", f"{git['commit']}:{name}"], cwd=repo, capture_output=True, check=True,
            ).stdout).hexdigest()
            for name in sorted(tracked)
        }
    else:
        hashes = {name: file_hash(repo / name) for name in sorted(tracked) if (repo / name).is_file()}
    return {
        "scope": IMPLEMENTATION_PATHS, "commit": git["commit"], "clean": not git["dirty"],
        "status_porcelain": git["status_porcelain"], "code_file_sha256": hashes,
        "reconstruction": "git show <commit>:<path>; unrelated repository paths are outside the Phase B implementation cleanliness scope",
    }


def _environment() -> dict[str, str]:
    import duckdb
    import polars

    return {
        "python": platform.python_version(), "platform": platform.platform(),
        "pyarrow": pa.__version__, "polars": polars.__version__, "duckdb": duckdb.__version__,
    }


def _environment_lock() -> dict[str, str]:
    packages = {
        distribution.metadata.get("Name", "").lower(): distribution.version
        for distribution in importlib.metadata.distributions()
        if distribution.metadata.get("Name")
    }
    return dict(sorted({"python": platform.python_version(), **packages}.items()))


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


def _version_identity(
    dataset_name: str, logical_hashes: dict[str, str], source_hashes: dict[str, str],
    configuration: dict[str, object], parent_version_id: str | None, reason: str,
) -> str:
    payload = {
        "dataset_name": dataset_name, "tables": dict(sorted(logical_hashes.items())),
        "source_hashes": dict(sorted(source_hashes.items())), "configuration": configuration,
        "parent_version_id": parent_version_id, "reason": reason,
    }
    return f"phaseb-{object_hash(payload)[:20]}"


def _batch_table(batch: pa.RecordBatch, schema: pa.Schema) -> pa.Table:
    return pa.Table.from_batches([batch], schema=batch.schema).cast(schema)


def _inspect_files(
    root: Path, table_name: str, relative_paths: list[Path], schema_version: str,
    algorithm: str = "arrow_ipc_stream_batches_v2",
) -> tuple[list[FileRecord], TableRecord]:
    expected = schema_for(table_name, schema_version)
    table_hasher = IncrementalArrowHasher(expected)
    file_records: list[FileRecord] = []
    total_rows = 0
    all_markets: set[str] = set()
    all_frequencies: set[str] = set()
    table_min = table_max = None
    prior_semantic_key: tuple[object, ...] | None = None

    for relative in relative_paths:
        path = root / relative
        parquet = pq.ParquetFile(path)
        file_hasher = IncrementalArrowHasher(expected)
        file_min = file_max = None
        file_markets: set[str] = set()
        file_frequencies: set[str] = set()
        rows = 0
        # Small dimension tables receive whole-table semantic validation. Large
        # facts are validated batchwise with sorted-key boundary checks.
        try:
            if parquet.schema_arrow.remove_metadata() != expected:
                raise PublicationError(f"Parquet schema drift: {relative.as_posix()}")
            small_parts: list[pa.Table] | None = [] if parquet.metadata.num_rows <= 1_000_000 else None
            for batch in parquet.iter_batches(batch_size=122_880):
                part = _batch_table(batch, expected)
                validate_table(table_name, part)
                if not sorted_table(table_name, part).equals(part):
                    raise PublicationError(f"non-deterministic sort order in {table_name}")
                if small_parts is not None:
                    small_parts.append(part)
                semantic = list(SEMANTIC_KEYS[table_name])
                if part.num_rows:
                    first_key = tuple(part[name][0].as_py() for name in semantic)
                    last_key = tuple(part[name][part.num_rows - 1].as_py() for name in semantic)
                    if prior_semantic_key is not None and first_key == prior_semantic_key:
                        raise PublicationError(f"duplicate semantic key across row groups in {table_name}")
                    prior_semantic_key = last_key
                if "event_ts" in part.column_names and part.num_rows:
                    current_min = pc.min(part["event_ts"]).as_py()
                    current_max = pc.max(part["event_ts"]).as_py()
                    file_min = current_min if file_min is None else min(file_min, current_min)
                    file_max = current_max if file_max is None else max(file_max, current_max)
                file_markets.update(_unique_strings(part, "market"))
                file_frequencies.update(_unique_strings(part, "frequency"))
                file_hasher.update(part); table_hasher.update(part)
                rows += part.num_rows
            if small_parts is not None:
                combined = pa.concat_tables(small_parts) if small_parts else pa.Table.from_batches([], schema=expected)
                validate_table(table_name, combined)
        finally:
            parquet.close()
        total_rows += rows
        all_markets.update(file_markets); all_frequencies.update(file_frequencies)
        if file_min is not None:
            table_min = file_min if table_min is None else min(table_min, file_min)
            table_max = file_max if table_max is None else max(table_max, file_max)
        file_records.append(FileRecord(
            path=relative.as_posix(), bytes=path.stat().st_size, physical_sha256=file_hash(path),
            logical_hash=file_hasher.hexdigest(), logical_hash_algorithm=algorithm, rows=rows,
            row_groups=pq.read_metadata(path).num_row_groups, semantic_key=list(SEMANTIC_KEYS[table_name]),
            schema_fingerprint=schema_fingerprint(expected), schema_version=schema_version,
            min_event_ts=file_min.isoformat() if file_min else None,
            max_event_ts=file_max.isoformat() if file_max else None,
            market=next(iter(file_markets)) if len(file_markets) == 1 else None,
            frequency=next(iter(file_frequencies)) if len(file_frequencies) == 1 else None,
        ))
    record = TableRecord(
        table_name=table_name, rows=total_rows, files=file_records,
        logical_hash=table_hasher.hexdigest(), logical_hash_algorithm=algorithm,
        semantic_key=list(SEMANTIC_KEYS[table_name]), schema_fingerprint=schema_fingerprint(expected),
        schema_version=schema_version, min_event_ts=table_min.isoformat() if table_min else None,
        max_event_ts=table_max.isoformat() if table_max else None,
        markets=sorted(all_markets), frequencies=sorted(all_frequencies),
    )
    return file_records, record


def _record_parent_differences(
    config: PhaseBConfig, parent_id: str | None, records: list[TableRecord],
) -> tuple[dict[str, int | None], dict[str, dict[str, str | None]]]:
    if parent_id is None:
        return (
            {record.table_name: record.rows for record in records},
            {record.table_name: {"parent": None, "current": record.logical_hash} for record in records},
        )
    parent = _load_manifest_metadata(config.phase_root / "versions" / parent_id / "manifest.json")
    previous = {record.table_name: record for record in parent.tables}
    return (
        {record.table_name: record.rows - previous[record.table_name].rows if record.table_name in previous else None for record in records},
        {record.table_name: {"parent": previous[record.table_name].logical_hash if record.table_name in previous else None, "current": record.logical_hash} for record in records},
    )


def _load_manifest_metadata(path: Path) -> DatasetManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    manifest = DatasetManifest.model_validate(raw)
    if _manifest_hash(raw) != manifest.manifest_hash or path.parent.name != manifest.dataset_version_id:
        raise PublicationError("parent manifest metadata integrity failed")
    return manifest


class Publisher:
    def __init__(self, config: PhaseBConfig):
        self.config = config

    def version_identity(self, dataset_name: str, tables: dict[str, pa.Table], source_hashes: dict[str, str], parent_version_id: str | None, reason: str) -> str:
        for name, table in tables.items():
            validate_table(name, table)
        hashes = {name: logical_table_hash(name, table, algorithm="arrow_ipc_stream_batches_v2") for name, table in sorted(tables.items())}
        return _version_identity(dataset_name, hashes, source_hashes, self.config.identity_dict(), parent_version_id, reason)

    def create_stage(self) -> Path:
        stage = self.config.phase_root / "staging" / f"build-{uuid.uuid4().hex}"
        stage.mkdir(parents=True, exist_ok=False)
        return stage

    def publish(
        self, dataset_name: str, tables: dict[str, pa.Table], source_hashes: dict[str, str],
        source_provenance: list[dict[str, object]], reason: str, parent_version_id: str | None = None,
    ) -> Path:
        if not tables:
            raise PublicationError("cannot publish an empty logical dataset")
        prepared: dict[str, pa.Table] = {}
        for name, table in tables.items():
            validate_table(name, table)
            prepared[name] = sorted_table(name, table)
        stage = self.create_stage()
        try:
            staged_files: dict[str, list[Path]] = {}
            for table_name, table in sorted(prepared.items()):
                staged_files[table_name] = []
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
                        staged_files[table_name].append(relative)
            return self.finalize_stage(
                stage, dataset_name, staged_files, source_hashes, source_provenance, reason, parent_version_id,
            )
        except Exception:
            if stage.exists():
                try:
                    shutil.rmtree(stage)
                except OSError:
                    pass
            raise

    def finalize_stage(
        self, stage: Path, dataset_name: str, staged_files: dict[str, list[Path]],
        source_hashes: dict[str, str], source_provenance: list[dict[str, object]],
        reason: str, parent_version_id: str | None = None,
    ) -> Path:
        table_records = [
            _inspect_files(stage, name, paths, SCHEMA_VERSION)[1]
            for name, paths in sorted(staged_files.items())
        ]
        hashes = {record.table_name: record.logical_hash for record in table_records}
        config_value = self.config.identity_dict()
        version_id = _version_identity(dataset_name, hashes, source_hashes, config_value, parent_version_id, reason)
        destination = self.config.phase_root / "versions" / version_id
        if destination.exists():
            raise PublishedVersionExists(f"published version already exists and cannot be overwritten: {version_id}")
        row_diff, content_diff = _record_parent_differences(self.config, parent_version_id, table_records)
        implementation = _implementation_provenance()
        if self.config.require_clean_implementation and not implementation["clean"]:
            raise PublicationError(f"implementation scope is dirty: {implementation['status_porcelain']}")
        lock = _environment_lock()
        created_at = datetime.now(timezone.utc).isoformat()
        manifest_value: dict[str, object] = {
            "manifest_schema_version": "ats.dataset_manifest.v2", "dataset_version_id": version_id,
            "dataset_name": dataset_name, "created_at": created_at,
            "tables": [record.model_dump(mode="json") for record in table_records],
            "source_provenance": source_provenance, "source_hashes": dict(sorted(source_hashes.items())),
            "writer_settings": {
                "compression": self.config.compression.upper(), "compression_level": self.config.compression_level,
                "row_group_size": self.config.row_group_size, "max_rows_per_file": self.config.max_rows_per_file,
                "stream_batch_size": self.config.stream_batch_size, "duckdb_memory_limit": self.config.duckdb_memory_limit,
                "split_size_review_bytes": self.config.split_size_review_bytes,
                "split_policy": "review only after query/rebuild SLO failure or materially degraded maintenance; not a fixed 2 GiB partition rule",
                "organization": "one or a few compact files per (table, market, frequency); no security/ticker/time partitions",
            },
            "parent_version_id": parent_version_id, "correction_reason": reason,
            "row_differences": row_diff, "content_differences": content_diff,
            "configuration": config_value, "configuration_hash": object_hash(config_value),
            "git_provenance": _git_provenance(), "environment": _environment(),
            "implementation_provenance": implementation, "environment_lock": lock,
            "environment_lock_hash": object_hash(lock), "manifest_hash": "",
        }
        manifest_value["manifest_hash"] = _manifest_hash(manifest_value)
        _atomic_json(stage / "manifest.json", manifest_value)
        validate_manifest(stage / "manifest.json", expected_root=stage)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage, destination)
        _atomic_json(self.config.phase_root / "catalogs" / f"{dataset_name}.current.json", {
            "dataset_name": dataset_name, "dataset_version_id": version_id,
            "manifest": (Path("..") / ".." / "versions" / version_id / "manifest.json").as_posix(),
            "updated_at": created_at, "discovery_only": True,
            "warning": "Experiments must pin the explicit version manifest and must not resolve this pointer during execution.",
        })
        return destination / "manifest.json"


def validate_manifest(manifest_path: Path, expected_root: Path | None = None) -> DatasetManifest:
    manifest_path = manifest_path.resolve()
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = DatasetManifest.model_validate(raw)
    if _manifest_hash(raw) != manifest.manifest_hash:
        raise PublicationError("manifest logical hash mismatch")
    if object_hash(manifest.configuration) != manifest.configuration_hash:
        raise PublicationError("configuration hash mismatch")
    root = expected_root.resolve() if expected_root else manifest_path.parent
    if expected_root is None and manifest_path.parent.name != manifest.dataset_version_id:
        raise PublicationError("manifest is not pinned beneath its explicit version directory")
    declared: set[str] = set()
    inspected_records: list[TableRecord] = []
    for table_record in manifest.tables:
        paths: list[Path] = []
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
            if parquet.schema_arrow.remove_metadata() != schema_for(table_record.table_name, record.schema_version):
                raise PublicationError(f"Parquet schema drift: {record.path}")
            if parquet.metadata.num_rows != record.rows or parquet.metadata.num_row_groups != record.row_groups:
                raise PublicationError(f"Parquet statistics mismatch: {record.path}")
            parquet.close(); paths.append(Path(record.path))
        if table_record.logical_hash_algorithm == "arrow_ipc_stream_batches_v2":
            _files, inspected = _inspect_files(root, table_record.table_name, paths, table_record.schema_version)
            if inspected.model_dump(mode="json") != table_record.model_dump(mode="json"):
                raise PublicationError(f"manifest table metadata mismatch: {table_record.table_name}")
            inspected_records.append(inspected)
        else:
            for path in paths:
                pieces.append(pq.read_table(root / path))
            combined = pa.concat_tables(pieces) if pieces else pa.Table.from_batches([], schema=schema_for(table_record.table_name, table_record.schema_version))
            validate_table(table_record.table_name, combined)
            if combined.num_rows != table_record.rows or logical_table_hash(table_record.table_name, combined, assume_sorted=True, algorithm=table_record.logical_hash_algorithm) != table_record.logical_hash:
                raise PublicationError(f"logical table validation failed: {table_record.table_name}")
    actual = {path.relative_to(root).as_posix() for path in (root / "data").rglob("*.parquet")} if (root / "data").exists() else set()
    if actual != declared:
        raise PublicationError(f"manifest/data file set mismatch: missing={sorted(declared-actual)}, unexpected={sorted(actual-declared)}")
    if manifest.manifest_schema_version == "ats.dataset_manifest.v2":
        hashes = {record.table_name: record.logical_hash for record in manifest.tables}
        expected_id = _version_identity(
            manifest.dataset_name, hashes, manifest.source_hashes, manifest.configuration,
            manifest.parent_version_id, manifest.correction_reason,
        )
        if expected_id != manifest.dataset_version_id:
            raise PublicationError("content-derived dataset version identity mismatch")
        if manifest.environment_lock is None or object_hash(manifest.environment_lock) != manifest.environment_lock_hash:
            raise PublicationError("environment lock hash mismatch")
        implementation = manifest.implementation_provenance
        if not implementation or implementation.get("commit") != manifest.git_provenance.get("commit"):
            raise PublicationError("implementation/Git provenance mismatch")
        if implementation.get("clean"):
            repo = Path(__file__).resolve().parents[4]
            commit = str(implementation["commit"])
            for name, expected_hash in implementation.get("code_file_sha256", {}).items():
                content = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=repo, capture_output=True, check=True).stdout
                if __import__("hashlib").sha256(content).hexdigest() != expected_hash:
                    raise PublicationError(f"implementation snapshot hash mismatch: {name}")
        phase_root = root.parent.parent if root.parent.name in {"versions", "staging"} else root
        if manifest.parent_version_id:
            parent_path = phase_root / "versions" / manifest.parent_version_id / "manifest.json"
            if not parent_path.is_file():
                raise PublicationError("parent version does not exist")
            parent = _load_manifest_metadata(parent_path)
            if parent.dataset_name != manifest.dataset_name:
                raise PublicationError("parent dataset is incompatible")
            previous = {record.table_name: record for record in parent.tables}
            if set(previous) != {record.table_name for record in manifest.tables}:
                raise PublicationError("parent table set is incompatible with complete correction")
            for record in manifest.tables:
                old = previous.get(record.table_name)
                expected_row = record.rows - old.rows if old else None
                expected_content = {"parent": old.logical_hash if old else None, "current": record.logical_hash}
                if manifest.row_differences.get(record.table_name) != expected_row:
                    raise PublicationError(f"row difference mismatch: {record.table_name}")
                if manifest.content_differences.get(record.table_name) != expected_content:
                    raise PublicationError(f"content difference mismatch: {record.table_name}")
        else:
            for record in manifest.tables:
                if manifest.row_differences.get(record.table_name) != record.rows:
                    raise PublicationError(f"initial row difference mismatch: {record.table_name}")
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
