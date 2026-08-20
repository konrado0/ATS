from __future__ import annotations

import json
import csv
import uuid
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ats_contracts.schemas import SCHEMA_VERSION, schema_for
from ats_contracts.validation import validate_table
from ats_data.config import PhaseBConfig
from ats_data.hashing import mark_sorted


US_LISTING_NAMESPACE = uuid.UUID("2d98bac9-c420-55c5-8c42-3cb70141808c")
WIG_SECURITY_ID = str(uuid.uuid5(uuid.UUID("6398c638-d145-5bee-82c2-1c165adea4df"), "XWAR:INDEX:WIG"))


def _table(schema_name: str, values: dict[str, object]) -> pa.Table:
    table = pa.Table.from_pydict(values, schema=schema_for(schema_name))
    validate_table(schema_name, table)
    return table


def _dates(series: pd.Series) -> list[object]:
    return pd.to_datetime(series, errors="raise").dt.date.where(series.notna(), None).tolist()


def gpw_tables(config: PhaseBConfig) -> tuple[dict[str, pa.Table], dict[str, object]]:
    artifacts = config.trusted_phase_a_run / "artifacts"
    master_a = pd.read_parquet(artifacts / "security_master.parquet")
    master_start = {str(row.security_id): pd.Timestamp(row.valid_from).date() for row in master_a.itertuples(index=False)}
    aliases_a = pd.read_parquet(artifacts / "security_aliases.parquet")
    vendor_a = pd.read_parquet(artifacts / "vendor_resolution.parquet")
    membership_a = pd.read_parquet(artifacts / "membership_intervals.parquet")
    bars_a = pd.read_parquet(artifacts / "validated_daily_bars.parquet")
    wig_a = pd.read_parquet(artifacts / "wig_daily.parquet")

    master_values = {
        "security_id": [*master_a["security_id"].astype(str), WIG_SECURITY_ID],
        "issuer_id": [None] * (len(master_a) + 1),
        "market": ["GPW"] * (len(master_a) + 1),
        "venue_mic": ["XWAR"] * (len(master_a) + 1),
        "instrument_type": [*master_a["instrument_type"].astype(str), "index"],
        "base_currency": [*master_a["base_currency"].astype(str), "PLN"],
        "valid_from": [*_dates(master_a["valid_from"]), wig_a["session_date"].min().date()],
        "valid_to": [*_dates(master_a["valid_to"]), wig_a["session_date"].max().date()],
        "observed_from": [*_dates(master_a["valid_from"]), wig_a["session_date"].min().date()],
        "observed_to": [*_dates(master_a["valid_to"]), wig_a["session_date"].max().date()],
        "identity_status": ["authoritative"] * (len(master_a) + 1),
        "status": [*master_a["status"].astype(str), "active"],
        "source": ["trusted_phase_a_identity"] * len(master_a) + ["trusted_phase_a_wig_calendar"],
        "schema_version": [SCHEMA_VERSION] * (len(master_a) + 1),
    }
    security_master = _table("security_master", master_values)

    alias_values: dict[str, list[object]] = {name: [] for name in schema_for("security_aliases").names}
    for row in aliases_a.itertuples(index=False):
        identifier_type = "venue" if row.identifier_type == "venue_mic" else str(row.identifier_type)
        alias_values["security_id"].append(str(row.security_id) if pd.notna(row.security_id) else None)
        alias_values["identifier_type"].append(identifier_type)
        alias_values["identifier_value"].append(str(row.identifier_value) if pd.notna(row.identifier_value) else None)
        alias_values["raw_identifier"].append(str(row.raw_identifier) if pd.notna(row.raw_identifier) else "")
        alias_values["market"].append("GPW")
        alias_values["venue_mic"].append(str(row.venue_mic) if pd.notna(row.venue_mic) else None)
        alias_values["vendor"].append(str(row.vendor) if pd.notna(row.vendor) else None)
        alias_values["valid_from"].append(pd.Timestamp(row.valid_from).date() if pd.notna(row.valid_from) else master_start[str(row.security_id)])
        alias_values["valid_to"].append(pd.Timestamp(row.valid_to).date() if pd.notna(row.valid_to) else None)
        alias_values["observed_from"].append(pd.Timestamp(row.valid_from).date() if pd.notna(row.valid_from) else master_start[str(row.security_id)])
        alias_values["observed_to"].append(pd.Timestamp(row.valid_to).date() if pd.notna(row.valid_to) else None)
        alias_values["source"].append(str(row.source))
        alias_values["provenance"].append(str(row.provenance))
        alias_values["resolution_status"].append(str(row.resolution_status) if str(row.resolution_status) in {"resolved", "exact", "mapped_renamed", "mapped_successor", "missing"} else "unresolved")
        alias_values["schema_version"].append(SCHEMA_VERSION)
    for identifier_type, value in (("official_short_name", "WIG"), ("vendor_symbol", "WIG"), ("venue", "XWAR")):
        alias_values["security_id"].append(WIG_SECURITY_ID)
        alias_values["identifier_type"].append(identifier_type)
        alias_values["identifier_value"].append(value)
        alias_values["raw_identifier"].append(value)
        alias_values["market"].append("GPW")
        alias_values["venue_mic"].append("XWAR")
        alias_values["vendor"].append("stooq" if identifier_type == "vendor_symbol" else None)
        alias_values["valid_from"].append(wig_a["session_date"].min().date())
        alias_values["valid_to"].append(wig_a["session_date"].max().date())
        alias_values["observed_from"].append(wig_a["session_date"].min().date())
        alias_values["observed_to"].append(wig_a["session_date"].max().date())
        alias_values["source"].append("trusted_phase_a_wig_calendar")
        alias_values["provenance"].append("Phase A wig_daily.parquet")
        alias_values["resolution_status"].append("resolved")
        alias_values["schema_version"].append(SCHEMA_VERSION)
    security_aliases = _table("security_aliases", alias_values)

    isin_to_security = {str(row.isin): str(row.security_id) for row in vendor_a.itertuples(index=False)}
    vendor_status = {str(row.isin): str(row.vendor_resolution_status) for row in vendor_a.itertuples(index=False)}
    benign = {"PLLOTOS00025", "PLPGNIG00014", "PLSTSHL00012", "PLCIECH00018", "PLTIM0000016"}
    membership_values: dict[str, list[object]] = {name: [] for name in schema_for("universe_membership").names}
    for row in membership_a.itertuples(index=False):
        isin = str(row.isin)
        status = vendor_status.get(isin, "unresolved")
        state = "benign_corporate_exit" if isin in benign else ("official_resolved" if status in {"exact", "mapped_renamed", "mapped_successor"} else "official_unresolved")
        membership_values["universe_id"].append(str(row.universe_id))
        membership_values["universe_component"].append(str(row.universe_component))
        membership_values["security_id"].append(isin_to_security.get(isin))
        membership_values["raw_identifier"].append(isin)
        membership_values["valid_from"].append(pd.Timestamp(row.effective_from).date())
        membership_values["valid_to"].append(pd.Timestamp(row.effective_to).date() if pd.notna(row.effective_to) else None)
        membership_values["announced_at"].append(None)
        membership_values["available_ts"].append(None)
        membership_values["source"].append(str(row.source))
        membership_values["source_record_id"].append(f"{row.source_id}:{row.universe_component}:{isin}")
        membership_values["provenance"].append(str(row.source_path) + "; announcement/availability timestamp unavailable and not fabricated")
        membership_values["resolution_status"].append("official_isin_resolved")
        membership_values["member_state"].append(state)
        membership_values["official_denominator"].append(60)
        membership_values["schema_version"].append(SCHEMA_VERSION)
    universe_membership = _table("universe_membership", membership_values)

    all_bars = pd.concat([bars_a.assign(_security_id=bars_a["security_id"]), wig_a.assign(_security_id=WIG_SECURITY_ID)], ignore_index=True)
    bar_values = {
        "security_id": all_bars["_security_id"].astype(str).tolist(), "market": ["GPW"] * len(all_bars),
        "venue_mic": all_bars["venue_mic"].astype(str).tolist(), "frequency": all_bars["frequency"].astype(str).tolist(),
        "event_ts": pd.to_datetime(all_bars["event_ts"], utc=True).tolist(), "session_date": pd.to_datetime(all_bars["session_date"]).dt.date.tolist(),
        "available_ts": pd.to_datetime(all_bars["available_ts"], utc=True).tolist(),
        "open": all_bars["open"].astype(float).tolist(), "high": all_bars["high"].astype(float).tolist(),
        "low": all_bars["low"].astype(float).tolist(), "close": all_bars["close"].astype(float).tolist(),
        "volume": all_bars["volume"].astype(float).tolist(), "turnover": [None] * len(all_bars),
        "currency": all_bars["currency"].astype(str).tolist(), "source": all_bars["source"].astype(str).tolist(),
        "source_record_id": (all_bars["source_file"].astype(str) + "#" + all_bars["raw_vendor_symbol"].astype(str) + "#" + pd.to_datetime(all_bars["session_date"]).dt.strftime("%Y%m%d")).tolist(),
        "adjustment_state": all_bars["adjustment_state"].astype(str).tolist(),
        "adjustment_version": all_bars["adjustment_version"].astype(str).tolist(),
        "ingest_batch_id": ["trusted-phase-a-phasea-2a2b3898aba37814"] * len(all_bars),
        "ingested_at": [config.ingestion_timestamp] * len(all_bars), "quality_state": ["accepted"] * len(all_bars),
        "quality_flags": ["[]"] * len(all_bars), "resolution_state": ["resolved"] * len(all_bars),
        "schema_version": [SCHEMA_VERSION] * len(all_bars),
    }
    bars = _table("bars", bar_values)
    report = {
        "phase_a_validated_bar_rows": len(bars_a), "wig_rows": len(wig_a), "canonical_bar_rows": bars.num_rows,
        "membership_rows": universe_membership.num_rows,
        "official_unresolved_intervals": sum(value == "official_unresolved" for value in membership_values["member_state"]),
        "benign_exit_intervals": sum(value == "benign_corporate_exit" for value in membership_values["member_state"]),
        "event_availability_semantics": "daily bar event_ts is modeled Phase A session close and available_ts is five minutes later; membership announcement/availability is null because unavailable",
    }
    return {"security_master": security_master, "security_aliases": security_aliases, "universe_membership": universe_membership, "bars": bars}, report


def _us_listing_rows(config: PhaseBConfig) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    venue_map = {"nasdaq": "XNAS", "nyse": "XNYS", "nysemkt": "XASE"}
    us_root = config.source_data_root / "daily" / "us"
    for path in sorted(us_root.rglob("*.txt"), key=lambda item: item.as_posix().lower()):
        segment = path.relative_to(us_root).parts[0].lower()
        exchange = segment.split()[0]
        venue = venue_map.get(exchange)
        if venue is None:
            continue
        filename_ticker = path.stem.upper()
        if filename_ticker.endswith(".US"):
            filename_ticker = filename_ticker[:-3]
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            first = next(reader, None)
        header_symbol = str(first.get("<TICKER>", "")).strip().upper() if first else ""
        header_ticker = header_symbol[:-3] if header_symbol.endswith(".US") else header_symbol
        instrument = "etf" if segment.endswith("etfs") else "common_equity"
        filename_symbol = filename_ticker + ".US"
        relative = path.relative_to(config.source_data_root).as_posix()
        security_id = str(uuid.uuid5(US_LISTING_NAMESPACE, f"stooq-path:{relative}"))
        rows.append({
            "filename": path.resolve().as_posix(), "relative": relative,
            "security_id": security_id, "filename_ticker": filename_ticker,
            "filename_symbol": filename_symbol, "header_ticker": header_ticker or None,
            "header_symbol": header_symbol or None,
            "ticker_mismatch": bool(header_symbol and header_symbol != filename_symbol),
            "venue_mic": venue, "instrument_type": instrument, "bytes": path.stat().st_size,
        })
    if not rows:
        raise ValueError("no U.S. daily source files found")
    return pd.DataFrame(rows)


def stage_us_tables(config: PhaseBConfig, stage: Path) -> tuple[dict[str, list[Path]], dict[str, object], list[Path]]:
    """Build U.S. canonical files without materializing the fact table.

    DuckDB may externally sort into the Phase B cache, while Arrow validation,
    coverage accounting and Parquet writing operate one configured batch at a
    time. The result remains a single compact, security/event-sorted bars file.
    """
    listings = _us_listing_rows(config)
    source_paths = [Path(value) for value in listings["filename"]]
    connection = duckdb.connect()
    spill = config.phase_root / "cache" / "duckdb-spill"
    spill.mkdir(parents=True, exist_ok=True)
    connection.execute(f"SET memory_limit='{config.duckdb_memory_limit}'")
    connection.execute(f"SET temp_directory='{spill.as_posix().replace(chr(39), chr(39) * 2)}'")
    connection.register("us_listing", listings)
    glob = (config.source_data_root / "daily" / "us" / "**" / "*.txt").as_posix().replace("'", "''")
    filters = []
    if config.us_start_date:
        filters.append(f"strptime(CAST(\"<DATE>\" AS VARCHAR), '%Y%m%d')::DATE >= DATE '{config.us_start_date}'")
    if config.us_end_date:
        filters.append(f"strptime(CAST(\"<DATE>\" AS VARCHAR), '%Y%m%d')::DATE <= DATE '{config.us_end_date}'")
    where = " AND ".join(filters) if filters else "TRUE"
    raw_relation = f"read_csv('{glob}', header=true, filename=true, union_by_name=false, all_varchar=true, null_padding=false)"
    valid_ohlcv = """
        TRY_CAST(r."<OPEN>" AS DOUBLE) > 0 AND TRY_CAST(r."<HIGH>" AS DOUBLE) > 0
        AND TRY_CAST(r."<LOW>" AS DOUBLE) > 0 AND TRY_CAST(r."<CLOSE>" AS DOUBLE) > 0
        AND TRY_CAST(r."<VOL>" AS DOUBLE) >= 0
        AND TRY_CAST(r."<HIGH>" AS DOUBLE) >= greatest(TRY_CAST(r."<OPEN>" AS DOUBLE), TRY_CAST(r."<CLOSE>" AS DOUBLE), TRY_CAST(r."<LOW>" AS DOUBLE))
        AND TRY_CAST(r."<LOW>" AS DOUBLE) <= least(TRY_CAST(r."<OPEN>" AS DOUBLE), TRY_CAST(r."<CLOSE>" AS DOUBLE), TRY_CAST(r."<HIGH>" AS DOUBLE))
    """
    query = f"""
        SELECT l.security_id, 'US' AS market, l.venue_mic, 'daily' AS frequency,
               timezone('UTC', timezone('America/New_York', strptime(CAST(r.\"<DATE>\" AS VARCHAR) || ' 16:00:00', '%Y%m%d %H:%M:%S'))) AS event_ts,
               strptime(CAST(r.\"<DATE>\" AS VARCHAR), '%Y%m%d')::DATE AS session_date,
               timezone('UTC', timezone('America/New_York', strptime(CAST(r.\"<DATE>\" AS VARCHAR) || ' 16:05:00', '%Y%m%d %H:%M:%S'))) AS available_ts,
               CAST(r.\"<OPEN>\" AS DOUBLE) AS open, CAST(r.\"<HIGH>\" AS DOUBLE) AS high,
               CAST(r.\"<LOW>\" AS DOUBLE) AS low, CAST(r.\"<CLOSE>\" AS DOUBLE) AS close,
               CAST(r.\"<VOL>\" AS DOUBLE) AS volume, NULL::DOUBLE AS turnover, 'USD' AS currency,
               'stooq_local_bulk' AS source,
               l.relative || '#' || CAST(r.\"<DATE>\" AS VARCHAR) || '#' || CAST(r.\"<TIME>\" AS VARCHAR) AS source_record_id,
               'vendor_adjusted_semantics_unverified' AS adjustment_state,
               '{config.source_version}' AS adjustment_version,
               'us-{config.source_version}' AS ingest_batch_id,
               TIMESTAMPTZ '{config.ingestion_timestamp.isoformat()}' AS ingested_at,
               'provisional' AS quality_state,
               CASE
                 WHEN upper(CAST(r."<TICKER>" AS VARCHAR)) <> coalesce(l.header_symbol, '') THEN '[\"identity_provisional_source_scoped\",\"raw_ticker_inconsistent\"]'
                 WHEN l.ticker_mismatch THEN '[\"identity_provisional_source_scoped\",\"ticker_filename_mismatch\"]'
                 ELSE '[\"identity_provisional_source_scoped\"]'
               END AS quality_flags,
               'provisional_source_scoped' AS resolution_state, '{SCHEMA_VERSION}' AS schema_version
        FROM {raw_relation} r
        JOIN us_listing l ON replace(r.filename, '\\', '/') = l.filename
        WHERE {where} AND ({valid_ohlcv})
        ORDER BY l.security_id, event_ts, source, adjustment_version
    """
    staged: dict[str, list[Path]] = {}
    coverage: dict[str, list[object]] = {}
    bars_rows = mismatch_bar_rows = 0
    bars_relative = Path("data/bars/market=US/frequency=daily/part-000.parquet")
    bars_path = stage / bars_relative
    bars_path.parent.mkdir(parents=True, exist_ok=True)
    writer = pq.ParquetWriter(
        bars_path, schema_for("bars"), compression=config.compression,
        compression_level=config.compression_level, version="2.6", write_statistics=True,
    )
    try:
        reader = connection.execute(query).to_arrow_reader(config.stream_batch_size)
        for batch in reader:
            part = pa.Table.from_batches([batch]).cast(schema_for("bars"))
            validate_table("bars", part)
            writer.write_table(part, row_group_size=config.row_group_size)
            bars_rows += part.num_rows
            mismatch_bar_rows += sum("ticker_filename_mismatch" in str(value) for value in part["quality_flags"].to_pylist())
            observed = part.select(["security_id", "session_date"]).group_by("security_id").aggregate([
                ("session_date", "min"), ("session_date", "max"),
            ]).to_pandas()
            for row in observed.itertuples(index=False):
                current = coverage.setdefault(str(row.security_id), [row.session_date_min, row.session_date_max])
                current[0] = min(current[0], row.session_date_min); current[1] = max(current[1], row.session_date_max)
        issue_query = f"""
            SELECT 'stooq_local_bulk' AS source,
                   l.relative || '#' || CAST(r.\"<DATE>\" AS VARCHAR) || '#' || CAST(r.\"<TIME>\" AS VARCHAR) AS source_record_id,
                   'US' AS market, CAST(r.\"<TICKER>\" AS VARCHAR) AS raw_identifier,
                   'invalid_ohlcv' AS issue_code,
                   to_json(struct_pack(open := r.\"<OPEN>\", high := r.\"<HIGH>\", low := r.\"<LOW>\", close := r.\"<CLOSE>\", volume := r.\"<VOL>\")) AS raw_payload_json,
                   TIMESTAMPTZ '{config.ingestion_timestamp.isoformat()}' AS detected_at,
                   'quarantined_visible' AS resolution_state, '{SCHEMA_VERSION}' AS schema_version
            FROM {raw_relation} r
            JOIN us_listing l ON replace(r.filename, '\\', '/') = l.filename
            WHERE {where} AND NOT ({valid_ohlcv})
        """
        issues = connection.execute(issue_query).to_arrow_table().cast(schema_for("ingestion_issues"))
    finally:
        writer.close()
        connection.close()
    staged["bars"] = [bars_relative]
    listings["observed_from"] = listings["security_id"].map(lambda value: coverage.get(str(value), [None, None])[0])
    listings["observed_to"] = listings["security_id"].map(lambda value: coverage.get(str(value), [None, None])[1])

    master = _table("security_master", {
        "security_id": listings["security_id"].astype(str).tolist(), "issuer_id": [None] * len(listings),
        "market": ["US"] * len(listings), "venue_mic": listings["venue_mic"].astype(str).tolist(),
        "instrument_type": listings["instrument_type"].astype(str).tolist(), "base_currency": ["USD"] * len(listings),
        "valid_from": [None] * len(listings), "valid_to": [None] * len(listings),
        "observed_from": listings["observed_from"].tolist(), "observed_to": listings["observed_to"].tolist(),
        "identity_status": ["provisional_source_scoped"] * len(listings), "status": ["provisional_listing"] * len(listings),
        "source": ["stooq_path_scoped_listing"] * len(listings), "schema_version": [SCHEMA_VERSION] * len(listings),
    })
    aliases: dict[str, list[object]] = {name: [] for name in schema_for("security_aliases").names}
    for row in listings.itertuples(index=False):
        header_ticker = None if pd.isna(row.header_ticker) else str(row.header_ticker)
        header_symbol = None if pd.isna(row.header_symbol) else str(row.header_symbol)
        evidence = (
            ("ticker", header_ticker, header_symbol or "", "raw <TICKER> field"),
            ("vendor_symbol", header_symbol, header_symbol or "", "raw <TICKER> field"),
            ("source_filename_ticker", row.filename_ticker, row.filename_ticker, "source filename"),
            ("source_filename_vendor_symbol", row.filename_symbol, row.filename_symbol, "source filename"),
            ("venue", row.venue_mic, row.venue_mic, "source directory"),
        )
        for kind, value, raw_value, evidence_source in evidence:
            aliases["security_id"].append(row.security_id); aliases["identifier_type"].append(kind)
            aliases["identifier_value"].append(value); aliases["raw_identifier"].append(raw_value)
            aliases["market"].append("US"); aliases["venue_mic"].append(row.venue_mic)
            aliases["vendor"].append("stooq" if kind in {"vendor_symbol", "source_filename_vendor_symbol"} else None)
            aliases["valid_from"].append(None); aliases["valid_to"].append(None)
            aliases["observed_from"].append(row.observed_from); aliases["observed_to"].append(row.observed_to)
            aliases["source"].append("stooq_path_scoped_listing")
            aliases["provenance"].append(f"{row.relative}; {evidence_source}; ticker continuity and issuer identity unresolved")
            aliases["resolution_status"].append("provisional_source_scoped")
            aliases["schema_version"].append(SCHEMA_VERSION)
    security_aliases = _table("security_aliases", aliases)

    mismatch_rows: list[dict[str, object]] = []
    for row in listings[listings["ticker_mismatch"]].itertuples(index=False):
        mismatch_rows.append({
            "source": "stooq_local_bulk", "source_record_id": f"{row.relative}#filename_header",
            "market": "US", "raw_identifier": row.header_symbol,
            "issue_code": "ticker_filename_mismatch",
            "raw_payload_json": json.dumps({"filename_ticker": row.filename_symbol, "header_ticker": row.header_symbol}, sort_keys=True),
            "detected_at": config.ingestion_timestamp, "resolution_state": "unresolved", "schema_version": SCHEMA_VERSION,
        })
    if mismatch_rows:
        mismatch = pa.Table.from_pylist(mismatch_rows, schema=schema_for("ingestion_issues"))
        issues = pa.concat_tables([issues, mismatch])
    validate_table("ingestion_issues", issues)

    for table_name, table in {
        "security_master": master, "security_aliases": security_aliases, "ingestion_issues": issues,
    }.items():
        table = mark_sorted(table_name, table)
        relative = Path("data") / table_name / "market=US" / "part-000.parquet"
        path = stage / relative; path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, path, compression=config.compression, compression_level=config.compression_level,
                       row_group_size=config.row_group_size, version="2.6", write_statistics=True)
        staged[table_name] = [relative]
    report = {
        "source_files": len(listings), "source_bytes": int(listings["bytes"].sum()), "bars": bars_rows,
        "provisional_listing_identities": master.num_rows, "unresolved_issuer_ids": master.num_rows,
        "empty_or_no_bar_listings": int(listings["observed_from"].isna().sum()), "visible_ingestion_issues": issues.num_rows,
        "ticker_filename_mismatches": len(mismatch_rows), "ticker_filename_mismatch_bar_rows": mismatch_bar_rows,
        "bounded_build": {"stream_batch_size": config.stream_batch_size, "duckdb_memory_limit": config.duckdb_memory_limit, "single_compact_sorted_bars_file": True},
        "identity_semantics": "UUIDv5 is raw-source-path scoped and provisional; raw-header and filename identifiers are retained separately; valid_from/valid_to stay null absent authority, while observed_from/observed_to record bar coverage",
        "daily_timestamp_semantics": "event_ts models 16:00 America/New_York session close; available_ts models 16:05, converted to UTC; raw TIME is retained in source_record_id",
    }
    return staged, report, source_paths
