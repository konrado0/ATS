from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.benchmark_utils import append_rows, benchmark_repeated, measure, stable_checksum, tree_stats


def sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def parquet_relation(path: Path) -> str:
    if path.is_dir():
        return f"read_parquet('{sql_path(path)}/**/*.parquet', hive_partitioning=true)"
    return f"read_parquet('{sql_path(path)}')"


def build(connection: duckdb.DuckDBPyConnection, destination: Path, query: str, options: str) -> dict:
    exists = destination.is_file() or (destination.is_dir() and any(destination.rglob("*.parquet")))
    if exists:
        files, size = tree_stats(destination)
        return {"reused": True, "elapsed_seconds": 0.0, "peak_rss_mb": 0.0, "files": files, "bytes": size}
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.suffix:
        destination.mkdir(parents=True, exist_ok=True)
    statement = f"COPY ({query}) TO '{sql_path(destination)}' ({options})"
    measured = measure(lambda: connection.execute(statement).fetchall())
    files, size = tree_stats(destination)
    return {
        "reused": False,
        "elapsed_seconds": measured.elapsed_seconds,
        "peak_rss_mb": measured.peak_rss_mb,
        "files": files,
        "bytes": size,
    }


def build_result(name: str, layout: str, meta: dict, rows: int) -> dict:
    return {
        "benchmark_layer": "parquet_layout",
        "benchmark_name": name,
        "engine": "duckdb",
        "dataset": "stocks_69m" if "hourly" not in layout else "gpw_hourly_2m",
        "layout": layout,
        "run_kind": "reused" if meta["reused"] else "first",
        "run_index": 0,
        "elapsed_seconds": round(meta["elapsed_seconds"], 6),
        "peak_rss_mb": round(meta["peak_rss_mb"], 3),
        "rows": rows,
        "bytes_on_disk": meta["bytes"],
        "file_count": meta["files"],
        "checksum": stable_checksum({"rows": rows, "files": meta["files"], "bytes": meta["bytes"]}),
        "notes": "initial physical write; reused outputs report zero write time",
    }


def query_suite(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
    layout: str,
    repeats: int,
    date_days: int = 365,
) -> list[dict]:
    rel = parquet_relation(path)
    count, top_security, max_ts = connection.execute(
        f"SELECT count(*), mode(security_id), max(timestamp) FROM {rel}"
    ).fetchone()
    escaped = str(top_security).replace("'", "''")
    bucket_predicate = ""
    if "bucket16" in layout:
        bucket = connection.execute("SELECT (hash(?) % 16)::INTEGER", [str(top_security)]).fetchone()[0]
        bucket_predicate = f"security_bucket={bucket} AND "
    files, size = tree_stats(path)
    queries = {
        "broad_scan": f"SELECT count(*), sum(close), avg(volume) FROM {rel}",
        "single_security": f"SELECT count(*), min(timestamp), max(timestamp), sum(close) FROM {rel} WHERE {bucket_predicate}security_id='{escaped}'",
        "date_range": f"SELECT count(*), sum(close) FROM {rel} WHERE timestamp > TIMESTAMP '{max_ts}' - INTERVAL {date_days} DAY",
        "security_date_range": f"SELECT count(*), sum(close) FROM {rel} WHERE {bucket_predicate}security_id='{escaped}' AND timestamp > TIMESTAMP '{max_ts}' - INTERVAL {date_days} DAY",
        "cross_section_latest": f"SELECT security_id, close, volume FROM {rel} WHERE timestamp=TIMESTAMP '{max_ts}' ORDER BY security_id",
    }
    rows: list[dict] = []
    for name, query in queries.items():
        rows.extend(
            benchmark_repeated(
                layer="parquet_layout",
                name=name,
                engine="duckdb",
                dataset="stocks_69m" if date_days == 365 else "gpw_hourly_2m",
                layout=layout,
                function=lambda q=query: connection.execute(q).fetchall(),
                repeats=repeats,
                rows=count,
                bytes_on_disk=size,
                file_count=files,
                notes=f"top_security={top_security}; max_timestamp={max_ts}",
            )
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("D:/Stock/data/stocks.parquet"))
    parser.add_argument("--hourly-glob", default="D:/Stock/data/hourly/pl/**/*.txt")
    parser.add_argument("--cache", type=Path, default=ROOT / "cache" / "parquet_layout_variants")
    parser.add_argument("--results", type=Path, default=ROOT.parent / "benchmark_results.csv")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    args.cache.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute("SET threads=12")
    connection.execute("SET memory_limit='24GB'")
    connection.execute("SET preserve_insertion_order=false")

    source = sql_path(args.source)
    normalized_query = f"""
        SELECT
            CASE
                WHEN lower(ticker) LIKE '%.us' THEN 'US'
                WHEN lower(ticker) LIKE '%.pl' THEN 'GPW'
                ELSE 'UNCLASSIFIED'
            END AS market,
            'daily' AS frequency,
            ticker AS security_id,
            date AS timestamp,
            open, high, low, close, volume
        FROM read_parquet('{source}')
        ORDER BY market, frequency, security_id, timestamp
    """
    source_rows = connection.execute(f"SELECT count(*) FROM read_parquet('{source}')").fetchone()[0]
    variants = [
        # The control averages about 36 uncompressed bytes/row. Explicit row
        # counts are used because DuckDB's default 122,880-row threshold can
        # otherwise flush before ROW_GROUP_SIZE_BYTES is reached.
        ("normalized_monolith_zstd3_rg64mib", args.cache / "normalized_monolith_zstd3_rg64mib.parquet", "COMPRESSION ZSTD, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE 1860000"),
        ("normalized_monolith_zstd3_rg128mib", args.cache / "normalized_monolith_zstd3_rg128mib.parquet", "COMPRESSION ZSTD, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE 3720000"),
        ("normalized_monolith_zstd3_rg256mib", args.cache / "normalized_monolith_zstd3_rg256mib.parquet", "COMPRESSION ZSTD, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE 7440000"),
        ("normalized_monolith_snappy_rg128mib", args.cache / "normalized_monolith_snappy_rg128mib.parquet", "COMPRESSION SNAPPY, ROW_GROUP_SIZE 3720000"),
    ]

    all_rows: list[dict] = []
    build_meta: dict[str, dict] = {}
    for name, destination, options in variants:
        meta = build(connection, destination, normalized_query, f"FORMAT PARQUET, {options}")
        build_meta[name] = meta
        all_rows.append(build_result("initial_write", name, meta, source_rows))
        all_rows.extend(query_suite(connection, destination, name, args.repeats))

    bucket_path = args.cache / "market_frequency_year_bucket16_zstd3"
    bucket_query = f"""
        SELECT
            CASE
                WHEN lower(ticker) LIKE '%.us' THEN 'US'
                WHEN lower(ticker) LIKE '%.pl' THEN 'GPW'
                ELSE 'UNCLASSIFIED'
            END AS market,
            'daily' AS frequency,
            year(date)::INTEGER AS year,
            (hash(ticker) % 16)::INTEGER AS security_bucket,
            ticker AS security_id,
            date AS timestamp,
            open, high, low, close, volume
        FROM read_parquet('{source}')
        ORDER BY market, frequency, year, security_bucket, security_id, timestamp
    """
    bucket_meta = build(
        connection,
        bucket_path,
        bucket_query,
        "FORMAT PARQUET, PARTITION_BY (market, frequency, year, security_bucket), COMPRESSION ZSTD, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE_BYTES '128MB'",
    )
    all_rows.append(build_result("initial_write", "market_frequency_year_bucket16_zstd3_rg128", bucket_meta, source_rows))
    all_rows.extend(query_suite(connection, bucket_path, "market_frequency_year_bucket16_zstd3_rg128", args.repeats))

    hourly_glob = args.hourly_glob.replace("'", "''")
    hourly_query = f"""
        SELECT
            'GPW' AS market,
            'hourly' AS frequency,
            cast(\"<TICKER>\" AS VARCHAR) AS security_id,
            strptime(cast(\"<DATE>\" AS VARCHAR) || lpad(cast(\"<TIME>\" AS VARCHAR), 6, '0'), '%Y%m%d%H%M%S') AS timestamp,
            cast(\"<OPEN>\" AS DOUBLE) AS open,
            cast(\"<HIGH>\" AS DOUBLE) AS high,
            cast(\"<LOW>\" AS DOUBLE) AS low,
            cast(\"<CLOSE>\" AS DOUBLE) AS close,
            cast(\"<VOL>\" AS BIGINT) AS volume
        FROM read_csv('{hourly_glob}', header=true, union_by_name=true, filename=true, ignore_errors=true)
        WHERE \"<DATE>\" IS NOT NULL AND \"<TIME>\" IS NOT NULL
        ORDER BY market, frequency, security_id, timestamp
    """
    hourly_monolith = args.cache / "gpw_hourly_monolith_zstd3_rg64.parquet"
    hourly_meta = build(
        connection,
        hourly_monolith,
        hourly_query,
        "FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE_BYTES '64MB'",
    )
    hourly_rows = connection.execute(f"SELECT count(*) FROM {parquet_relation(hourly_monolith)}").fetchone()[0]
    all_rows.append(build_result("initial_write", "gpw_hourly_monolith_zstd3_rg64", hourly_meta, hourly_rows))
    all_rows.extend(query_suite(connection, hourly_monolith, "gpw_hourly_monolith_zstd3_rg64", args.repeats, date_days=30))

    hourly_month = args.cache / "gpw_hourly_market_frequency_year_month_zstd3"
    hourly_month_query = f"""
        SELECT *, year(timestamp)::INTEGER AS year, month(timestamp)::INTEGER AS month
        FROM {parquet_relation(hourly_monolith)}
        ORDER BY market, frequency, year, month, security_id, timestamp
    """
    hourly_month_meta = build(
        connection,
        hourly_month,
        hourly_month_query,
        "FORMAT PARQUET, PARTITION_BY (market, frequency, year, month), COMPRESSION ZSTD, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE_BYTES '64MB'",
    )
    all_rows.append(build_result("initial_write", "gpw_hourly_market_frequency_year_month_zstd3_rg64", hourly_month_meta, hourly_rows))
    all_rows.extend(query_suite(connection, hourly_month, "gpw_hourly_market_frequency_year_month_zstd3_rg64", args.repeats, date_days=30))

    append_rows(args.results, all_rows)
    print(json.dumps({"builds": build_meta | {"bucket": bucket_meta, "hourly": hourly_meta, "hourly_month": hourly_month_meta}, "result_rows": len(all_rows)}, indent=2))


if __name__ == "__main__":
    main()
