from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ats_contracts.validation import ContractError
from ats_data.config import PhaseBConfig
from ats_data.discovery import clear_derived_cache, create_duckdb_catalog, scan_table
from ats_data.manifest import DatasetManifest
from ats_data.publication import PublishedVersionExists, Publisher, validate_manifest
from test_phase_b_contracts import bar_table


def config(tmp_path: Path) -> PhaseBConfig:
    source = tmp_path / "data"
    trusted = source / "ATS" / "phase_a" / "runs" / "trusted"
    trusted.mkdir(parents=True)
    return PhaseBConfig(
        phase_root=source / "ATS" / "phase_b", trusted_phase_a_run=trusted, source_data_root=source,
        ingestion_timestamp=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )


def publish(tmp_path: Path):
    cfg = config(tmp_path)
    manifest = Publisher(cfg).publish("fixture", {"bars": bar_table()}, {"raw/a": "abc"}, [{"kind": "fixture"}], "initial")
    return cfg, manifest


def corrected_bar() -> pa.Table:
    values = bar_table().to_pydict(); values["close"] = [10.75]; values["high"] = [11.25]
    return pa.Table.from_pydict(values, schema=bar_table().schema)


def test_version_identity_is_deterministic_and_publish_is_immutable(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    publisher = Publisher(cfg)
    first = publisher.version_identity("fixture", {"bars": bar_table()}, {"a": "b"}, None, "initial")
    second = publisher.version_identity("fixture", {"bars": bar_table()}, {"a": "b"}, None, "initial")
    assert first == second
    manifest = publisher.publish("fixture", {"bars": bar_table()}, {"a": "b"}, [{"kind": "fixture"}], "initial")
    before = manifest.read_bytes()
    with pytest.raises(PublishedVersionExists):
        publisher.publish("fixture", {"bars": bar_table()}, {"a": "b"}, [{"kind": "fixture"}], "initial")
    assert manifest.read_bytes() == before


def test_failed_publication_leaves_previous_pointer_and_manifest_usable(tmp_path: Path) -> None:
    cfg, manifest = publish(tmp_path)
    pointer = cfg.phase_root / "catalogs" / "fixture.current.json"
    before_pointer, before_manifest = pointer.read_bytes(), manifest.read_bytes()
    with pytest.raises(ContractError):
        Publisher(cfg).publish("fixture", {"bars": bar_table(duplicate=True)}, {"raw/a": "changed"}, [{"kind": "fixture"}], "bad correction", manifest.parent.name)
    assert pointer.read_bytes() == before_pointer
    assert manifest.read_bytes() == before_manifest
    assert validate_manifest(manifest).dataset_version_id == manifest.parent.name


def test_correction_is_complete_distinct_version_with_parent_lineage(tmp_path: Path) -> None:
    cfg, parent = publish(tmp_path)
    correction = Publisher(cfg).publish(
        "fixture", {"bars": corrected_bar()}, {"raw/a": "def"}, [{"kind": "fixture"}],
        "historical vendor correction", parent.parent.name,
    )
    value = validate_manifest(correction)
    assert value.dataset_version_id != parent.parent.name
    assert value.parent_version_id == parent.parent.name
    assert value.correction_reason == "historical vendor correction"
    assert value.row_differences["bars"] == 0
    assert value.content_differences["bars"]["parent"] != value.content_differences["bars"]["current"]
    assert len(value.tables[0].files) == 1


def test_manifest_explicit_files_drive_duckdb_and_polars_requires_pin(tmp_path: Path) -> None:
    cfg, manifest = publish(tmp_path)
    unrelated = cfg.phase_root / "unlisted" / "extra.parquet"
    unrelated.parent.mkdir(parents=True)
    pq.write_table(bar_table(), unrelated)
    catalog = cfg.phase_root / "catalogs" / "fixture.duckdb"
    create_duckdb_catalog(manifest, catalog)
    with duckdb.connect(str(catalog), read_only=True) as connection:
        assert connection.execute("select count(*) from bars").fetchone()[0] == 1
        sql = connection.execute("select sql from duckdb_views() where view_name='bars'").fetchone()[0]
        assert str(unrelated).replace("\\", "/") not in sql
    assert scan_table(manifest, "bars").collect().height == 1
    pointer = cfg.phase_root / "catalogs" / "fixture.current.json"
    with pytest.raises(ValueError, match="pinned"):
        scan_table(pointer, "bars")


def test_no_ticker_security_or_time_partitions_and_cache_boundary(tmp_path: Path) -> None:
    cfg, manifest = publish(tmp_path)
    value = validate_manifest(manifest)
    paths = [item.path for table in value.tables for item in table.files]
    assert all("ticker=" not in path and "security_id=" not in path and "year=" not in path and "month=" not in path for path in paths)
    cache = cfg.phase_root / "cache" / "derived-query"
    cache.mkdir(parents=True); (cache / "value.bin").write_bytes(b"cache")
    clear_derived_cache(cache, cfg.phase_root)
    assert not cache.exists() and manifest.exists()
    with pytest.raises(ValueError):
        clear_derived_cache(manifest.parent, cfg.phase_root)
