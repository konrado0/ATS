from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import date, datetime, timezone
from pathlib import Path

import psutil
import pyarrow as pa
import pyarrow.parquet as pq

from ats_data.config import load_config
from ats_data.discovery import create_duckdb_catalog, scan_table
from ats_data.hashing import file_hash
from ats_data.ingest import gpw_tables, stage_us_tables
from ats_data.publication import Publisher, recover_valid_staging, validate_manifest
from ats_data.reconciliation import reconcile_gpw
from ats_contracts.schemas import SCHEMA_VERSION, schema_for
from ats_contracts.validation import ContractError
from ats_data.manifest import DatasetManifest


def _write_report(config, name: str, value: object) -> Path:
    path = config.phase_root / "reports" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def _phase_a_sources(config) -> tuple[dict[str, str], list[dict[str, object]]]:
    files = [
        config.trusted_phase_a_run / "manifest.json",
        config.trusted_phase_a_run / "artifacts" / "validated_daily_bars.parquet",
        config.trusted_phase_a_run / "artifacts" / "wig_daily.parquet",
        config.trusted_phase_a_run / "artifacts" / "security_master.parquet",
        config.trusted_phase_a_run / "artifacts" / "security_aliases.parquet",
        config.trusted_phase_a_run / "artifacts" / "vendor_resolution.parquet",
        config.trusted_phase_a_run / "artifacts" / "membership_intervals.parquet",
    ]
    hashes = {path.relative_to(config.trusted_phase_a_run).as_posix(): file_hash(path) for path in files}
    return hashes, [{"kind": "trusted_phase_a_archive", "run": config.trusted_phase_a_run.as_posix(), "files": len(files)}]


def _publish_gpw(config) -> dict[str, object]:
    started = time.perf_counter(); process = psutil.Process(); before = process.memory_info().rss
    tables, ingest_report = gpw_tables(config)
    source_hashes, provenance = _phase_a_sources(config)
    manifest_path = Publisher(config).publish("gpw_phase_a_scope", tables, source_hashes, provenance, "initial GPW Phase B publication")
    elapsed = time.perf_counter() - started
    reconciliation = reconcile_gpw(config.trusted_phase_a_run, manifest_path)
    catalog = create_duckdb_catalog(manifest_path, config.phase_root / "catalogs" / f"{manifest_path.parent.name}.duckdb")
    query_started = time.perf_counter()
    query = scan_table(manifest_path, "bars").filter((__import__("polars").col("market") == "GPW") & (__import__("polars").col("session_date") >= __import__("polars").lit("2025-01-01").str.to_date())).select(["security_id", "session_date", "close"]).collect()
    report = {
        "manifest": manifest_path.as_posix(), "dataset_version_id": manifest_path.parent.name,
        "ingestion": ingest_report, "reconciliation": reconciliation, "duckdb": catalog,
        "measurements": {"rebuild_seconds": elapsed, "rss_before_bytes": before, "rss_after_bytes": process.memory_info().rss, "representative_polars_rows": query.height, "representative_polars_seconds": time.perf_counter() - query_started},
    }
    _write_report(config, "gpw_reference.json", report)
    _write_report(config, "gpw_reconciliation.json", reconciliation)
    return report


def _publish_us(config, parent_version_id: str | None = None, reason: str = "U.S. daily bounded rebuild; separate filename/header evidence and unresolved validity") -> dict[str, object]:
    started = time.perf_counter(); process = psutil.Process(); before = process.memory_info().rss
    publisher = Publisher(config); stage = publisher.create_stage()
    try:
        staged, ingest_report, paths = stage_us_tables(config, stage)
        hash_started = time.perf_counter()
        hashes = {path.relative_to(config.source_data_root).as_posix(): file_hash(path) for path in paths}
        hash_seconds = time.perf_counter() - hash_started
        manifest_path = publisher.finalize_stage(
            stage, "us_daily", staged, hashes,
            [{"kind": "immutable_local_raw_archive", "root": (config.source_data_root / "daily" / "us").as_posix(), "files": len(paths)}],
            reason, parent_version_id,
        )
    except Exception:
        if stage.exists(): shutil.rmtree(stage)
        raise
    catalog = create_duckdb_catalog(manifest_path, config.phase_root / "catalogs" / f"{manifest_path.parent.name}.duckdb")
    query_started = time.perf_counter()
    pl = __import__("polars")
    query = scan_table(manifest_path, "bars").filter((pl.col("venue_mic") == "XNAS") & (pl.col("session_date") >= pl.lit("2025-01-01").str.to_date())).select(["security_id", "session_date", "close"]).collect()
    report = {
        "manifest": manifest_path.as_posix(), "dataset_version_id": manifest_path.parent.name,
        "ingestion": ingest_report, "duckdb": catalog, "parent_version_id": parent_version_id, "correction_reason": reason,
        "measurements": {"rebuild_seconds": time.perf_counter() - started, "source_hash_seconds": hash_seconds, "rss_before_bytes": before,
                         "rss_after_bytes": process.memory_info().rss, "process_peak_working_set_bytes": getattr(process.memory_info(), "peak_wset", None),
                         "process_peak_private_bytes": getattr(process.memory_info(), "peak_pagefile", None),
                         "representative_polars_rows": query.height, "representative_polars_seconds": time.perf_counter() - query_started},
    }
    _write_report(config, "us_reference.json", report)
    return report


def _fixture_bars(close: float = 10.5, duplicate: bool = False) -> pa.Table:
    rows = 2 if duplicate else 1; event = datetime(2025, 1, 2, 21, tzinfo=timezone.utc)
    return pa.Table.from_pydict({
        "security_id": ["11111111-1111-4111-8111-111111111111"] * rows, "market": ["US"] * rows,
        "venue_mic": ["XNAS"] * rows, "frequency": ["daily"] * rows, "event_ts": [event] * rows,
        "session_date": [date(2025, 1, 2)] * rows, "available_ts": [event.replace(minute=5)] * rows,
        "open": [10.0] * rows, "high": [max(11.0, close)] * rows, "low": [9.0] * rows, "close": [close] * rows,
        "volume": [100.0] * rows, "turnover": [None] * rows, "currency": ["USD"] * rows,
        "source": ["phase_b_transaction_fixture"] * rows, "source_record_id": [f"fixture-{i}" for i in range(rows)],
        "adjustment_state": ["raw"] * rows, "adjustment_version": ["v1"] * rows,
        "ingest_batch_id": ["fixture"] * rows, "ingested_at": [event] * rows, "quality_state": ["accepted"] * rows,
        "quality_flags": ["[]"] * rows, "resolution_state": ["resolved"] * rows, "schema_version": [SCHEMA_VERSION] * rows,
    }, schema=schema_for("bars"))


def _publication_demo(config) -> dict[str, object]:
    publisher = Publisher(config)
    first = publisher.publish("transaction_fixture", {"bars": _fixture_bars()}, {"fixture": "v1"}, [{"kind": "synthetic_acceptance_fixture"}], "initial fixture")
    pointer = config.phase_root / "catalogs" / "transaction_fixture.current.json"
    pointer_before = pointer.read_bytes(); manifest_before = first.read_bytes()
    failed_error = None
    try:
        publisher.publish("transaction_fixture", {"bars": _fixture_bars(duplicate=True)}, {"fixture": "bad"}, [{"kind": "synthetic_acceptance_fixture"}], "invalid duplicate fixture", first.parent.name)
    except ContractError as exc:
        failed_error = str(exc)
    if failed_error is None or pointer.read_bytes() != pointer_before or first.read_bytes() != manifest_before:
        raise RuntimeError("failed-publication fixture did not preserve the previous publication")
    correction = publisher.publish("transaction_fixture", {"bars": _fixture_bars(close=10.75)}, {"fixture": "v2"}, [{"kind": "synthetic_acceptance_fixture"}], "demonstrated historical correction", first.parent.name)
    corrected = validate_manifest(correction)
    result = {
        "passed": True, "initial_version_id": first.parent.name, "correction_version_id": correction.parent.name,
        "parent_version_id": corrected.parent_version_id, "correction_reason": corrected.correction_reason,
        "row_differences": corrected.row_differences, "content_differences": corrected.content_differences,
        "failed_publish_error": failed_error, "previous_manifest_unchanged": True, "previous_pointer_usable_after_failure": True,
    }
    _write_report(config, "transactional_publication_demo.json", result)
    return result


def _profile_manifest(config, manifest_path: Path, market: str) -> dict[str, object]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8")); manifest = DatasetManifest.model_validate(raw)
    catalog_path = config.phase_root / "catalogs" / f"{manifest.dataset_version_id}.duckdb"
    catalog = create_duckdb_catalog(manifest_path, catalog_path)
    pl = __import__("polars"); import duckdb
    bars_lazy = scan_table(manifest_path, "bars")
    with duckdb.connect(str(catalog_path), read_only=True) as connection:
        security_id, maximum = connection.execute(
            "select min(security_id), max(session_date) from bars where market = ?", [market],
        ).fetchone()
        cutoff = (maximum - __import__("datetime").timedelta(days=31)).isoformat()
        duck_queries = {
            "one_security_history": ("select session_date, close from bars where security_id = ? order by session_date", [security_id]),
            "recent_cross_section": ("select security_id, close, volume from bars where market = ? and session_date = ?", [market, maximum]),
            "bounded_date_range": ("select security_id, session_date, close from bars where market = ? and session_date >= ? and session_date <= ?", [market, cutoff, maximum]),
            "count_checksum": ("select count(*) as row_count, sum(close) as close_sum, sum(volume) as volume_sum from bars where market = ?", [market]),
        }
        duck_results: dict[str, object] = {}
        for name, (sql, params) in duck_queries.items():
            started = time.perf_counter(); frame = connection.execute(sql, params).to_arrow_table()
            duck_results[name] = {"rows_returned": frame.num_rows, "seconds": time.perf_counter() - started, "values": frame.to_pylist() if name == "count_checksum" else None}
        duck_plan = connection.execute(
            "explain analyze select session_date, close from bars where security_id = ?", [security_id],
        ).fetchall()[0][1]

    polars_queries = {
        "one_security_history": bars_lazy.filter(pl.col("security_id") == security_id).select(["session_date", "close"]).sort("session_date"),
        "recent_cross_section": bars_lazy.filter((pl.col("market") == market) & (pl.col("session_date") == maximum)).select(["security_id", "close", "volume"]),
        "bounded_date_range": bars_lazy.filter((pl.col("market") == market) & (pl.col("session_date") >= pl.lit(cutoff).str.to_date()) & (pl.col("session_date") <= maximum)).select(["security_id", "session_date", "close"]),
        "count_checksum": bars_lazy.filter(pl.col("market") == market).select([
            pl.len().alias("row_count"), pl.col("close").sum().alias("close_sum"), pl.col("volume").sum().alias("volume_sum"),
        ]),
    }
    polars_results: dict[str, object] = {}
    for name, lazy in polars_queries.items():
        started = time.perf_counter(); frame = lazy.collect()
        polars_results[name] = {"rows_returned": frame.height, "seconds": time.perf_counter() - started, "values": frame.to_dicts() if name == "count_checksum" else None}
    plan = polars_queries["one_security_history"].explain(optimized=True)

    pruning = {"total_row_groups": 0, "one_security_candidate_row_groups": 0, "method": "Parquet security_id min/max statistics"}
    bars_record = next(record for record in manifest.tables if record.table_name == "bars")
    for file_record in bars_record.files:
        parquet = pq.ParquetFile(manifest_path.parent / file_record.path)
        index = parquet.schema_arrow.names.index("security_id")
        for group in range(parquet.metadata.num_row_groups):
            stats = parquet.metadata.row_group(group).column(index).statistics
            pruning["total_row_groups"] += 1
            if stats is None or stats.min <= security_id <= stats.max:
                pruning["one_security_candidate_row_groups"] += 1
        parquet.close()
    table_stats = {table.table_name: {"rows": table.rows, "files": len(table.files), "bytes": sum(item.bytes for item in table.files), "row_groups": sum(item.row_groups for item in table.files)} for table in manifest.tables}
    duck_checksum = duck_results["count_checksum"]["values"][0]
    polars_checksum = polars_results["count_checksum"]["values"][0]
    checksum_match = duck_checksum["row_count"] == polars_checksum["row_count"] and all(
        __import__("math").isclose(float(duck_checksum[name]), float(polars_checksum[name]), rel_tol=1e-12, abs_tol=1e-6)
        for name in ("close_sum", "volume_sum")
    )
    result = {
        "passed": True, "dataset_version_id": manifest.dataset_version_id, "manifest": manifest_path.as_posix(),
        "market": market, "tables": table_stats, "writer_settings": manifest.writer_settings,
        "duckdb": {"catalog": catalog, "queries": duck_results, "one_security_explain_analyze": duck_plan},
        "polars": {"queries": polars_results, "one_security_optimized_plan": plan,
                    "projection_pushdown_visible": "PROJECT" in plan, "predicate_pushdown_visible": "SELECTION" in plan},
        "parameters": {"security_id": security_id, "maximum_session": maximum.isoformat(), "bounded_cutoff": cutoff},
        "row_group_pruning_evidence": pruning,
        "engine_checksum_match": checksum_match, "checksum_tolerance": {"relative": 1e-12, "absolute": 1e-6},
    }
    _write_report(config, f"{market.lower()}_profile.json", result)
    return result


def _correct_validity(config, manifest_path: Path, market: str) -> dict[str, object]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8")); parent = DatasetManifest.model_validate(raw)
    if market == "GPW":
        tables, detail = gpw_tables(config); source_hashes, provenance = _phase_a_sources(config)
        reason = "replace unresolved-alias placeholder starts with trusted membership starts"
        dataset_name = "gpw_phase_a_scope"
    else:
        reason = "complete bounded correction rebuild demonstrating explicit parent lineage"
        result = _publish_us(config, parent.dataset_version_id, reason)
        result.update({"passed": True, "market": market})
        _write_report(config, f"{market.lower()}_validity_correction.json", result)
        return result
    corrected = Publisher(config).publish(dataset_name, tables, source_hashes, provenance, reason, parent.dataset_version_id)
    result = {"passed": True, "market": market, "parent_version_id": parent.dataset_version_id, "dataset_version_id": corrected.parent.name, "manifest": corrected.as_posix(), "reason": reason, "detail": detail}
    _write_report(config, f"{market.lower()}_validity_correction.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(prog="ats-data")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("publish-gpw", "publish-us"):
        item = sub.add_parser(name); item.add_argument("--config", type=Path, required=True)
    validate = sub.add_parser("validate"); validate.add_argument("--manifest", type=Path, required=True)
    reconcile = sub.add_parser("reconcile-gpw"); reconcile.add_argument("--config", type=Path, required=True); reconcile.add_argument("--manifest", type=Path, required=True)
    catalog = sub.add_parser("build-catalog"); catalog.add_argument("--manifest", type=Path, required=True); catalog.add_argument("--catalog", type=Path, required=True)
    recover = sub.add_parser("recover-stage"); recover.add_argument("--config", type=Path, required=True); recover.add_argument("--stage", type=Path, required=True)
    demo = sub.add_parser("demo-publication"); demo.add_argument("--config", type=Path, required=True)
    profile = sub.add_parser("profile"); profile.add_argument("--config", type=Path, required=True); profile.add_argument("--manifest", type=Path, required=True); profile.add_argument("--market", choices=["GPW", "US"], required=True)
    correct = sub.add_parser("correct-validity"); correct.add_argument("--config", type=Path, required=True); correct.add_argument("--manifest", type=Path, required=True); correct.add_argument("--market", choices=["GPW", "US"], required=True)
    args = parser.parse_args()
    if args.command == "publish-gpw": result = _publish_gpw(load_config(args.config))
    elif args.command == "publish-us": result = _publish_us(load_config(args.config))
    elif args.command == "validate":
        value = validate_manifest(args.manifest); result = {"passed": True, "dataset_version_id": value.dataset_version_id, "tables": {table.table_name: table.rows for table in value.tables}}
    elif args.command == "reconcile-gpw":
        config = load_config(args.config)
        result = reconcile_gpw(config.trusted_phase_a_run, args.manifest)
        _write_report(config, "gpw_reconciliation.json", result)
    elif args.command == "build-catalog": result = create_duckdb_catalog(args.manifest, args.catalog)
    elif args.command == "recover-stage":
        path = recover_valid_staging(load_config(args.config), args.stage)
        result = {"passed": True, "manifest": path.as_posix(), "dataset_version_id": path.parent.name}
    elif args.command == "demo-publication": result = _publication_demo(load_config(args.config))
    elif args.command == "profile": result = _profile_manifest(load_config(args.config), args.manifest, args.market)
    else: result = _correct_validity(load_config(args.config), args.manifest, args.market)
    print(json.dumps(result, indent=2, sort_keys=True))
