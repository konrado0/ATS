from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.benchmark_utils import append_rows, benchmark_repeated, measure, stable_checksum, tree_stats


def sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def relation(path: Path) -> str:
    if path.is_dir():
        return f"read_parquet('{sql_path(path)}/**/*.parquet', hive_partitioning=true)"
    return f"read_parquet('{sql_path(path)}')"


def build_partitioned(connection: duckdb.DuckDBPyConnection, source: Path, destination: Path) -> dict:
    if any(destination.rglob("*.parquet")):
        files, size = tree_stats(destination)
        return {"reused": True, "elapsed_seconds": 0.0, "files": files, "bytes": size}
    destination.mkdir(parents=True, exist_ok=True)
    source_sql = sql_path(source)
    destination_sql = sql_path(destination)
    connection.execute("SET preserve_insertion_order=false")
    statement = f"""
        COPY (
            SELECT
                CASE
                    WHEN lower(ticker) LIKE '%.us' THEN 'US'
                    WHEN lower(ticker) LIKE '%.pl' THEN 'GPW'
                    ELSE 'UNCLASSIFIED'
                END AS market,
                'daily' AS frequency,
                ticker AS security_id,
                year(date)::INTEGER AS year,
                date AS timestamp,
                open, high, low, close, volume
            FROM read_parquet('{source_sql}')
            ORDER BY market, frequency, year, security_id, timestamp
        ) TO '{destination_sql}' (
            FORMAT PARQUET,
            PARTITION_BY (market, frequency, year),
            COMPRESSION ZSTD,
            ROW_GROUP_SIZE_BYTES '128MB',
            OVERWRITE_OR_IGNORE true
        )
    """
    result = measure(lambda: connection.execute(statement).fetchall())
    files, size = tree_stats(destination)
    return {
        "reused": False,
        "elapsed_seconds": result.elapsed_seconds,
        "peak_rss_mb": result.peak_rss_mb,
        "files": files,
        "bytes": size,
    }


def metadata(connection: duckdb.DuckDBPyConnection, path: Path) -> dict:
    rel = relation(path)
    stats = connection.execute(
        f"SELECT count(*) AS row_count, count(DISTINCT security_id) AS securities, min(timestamp), max(timestamp) FROM {rel}"
        if path.is_dir()
        else f"SELECT count(*) AS row_count, count(DISTINCT ticker) AS securities, min(date), max(date) FROM {rel}"
    ).fetchone()
    return {"rows": stats[0], "securities": stats[1], "min_date": str(stats[2]), "max_date": str(stats[3])}


def benchmark_layout(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
    layout: str,
    repeats: int,
) -> list[dict]:
    rel = relation(path)
    is_partitioned = path.is_dir()
    security_column = "security_id" if is_partitioned else "ticker"
    date_column = "timestamp" if is_partitioned else "date"
    top_security = connection.execute(
        f"SELECT {security_column} FROM {rel} GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT 1"
    ).fetchone()[0]
    maximum_date = connection.execute(f"SELECT max({date_column}) FROM {rel}").fetchone()[0]
    row_count = connection.execute(f"SELECT count(*) FROM {rel}").fetchone()[0]
    file_count, byte_count = tree_stats(path)
    escaped_security = str(top_security).replace("'", "''")
    queries = {
        "broad_scan": f"SELECT count(*), sum(close), avg(volume) FROM {rel}",
        "single_security": f"SELECT count(*), min({date_column}), max({date_column}), sum(close) FROM {rel} WHERE {security_column}='{escaped_security}'",
        "date_range_365d": f"SELECT count(*), sum(close) FROM {rel} WHERE {date_column} > DATE '{maximum_date}' - INTERVAL 365 DAY",
        "security_date_range": f"SELECT count(*), sum(close) FROM {rel} WHERE {security_column}='{escaped_security}' AND {date_column} > DATE '{maximum_date}' - INTERVAL 365 DAY",
        "cross_section_latest": f"SELECT {security_column}, close, volume FROM {rel} WHERE {date_column}=DATE '{maximum_date}' ORDER BY {security_column}",
    }
    rows: list[dict] = []
    for name, query in queries.items():
        rows.extend(
            benchmark_repeated(
                layer="parquet_layout",
                name=name,
                engine="duckdb",
                dataset="stocks_69m",
                layout=layout,
                function=lambda q=query: connection.execute(q).fetchall(),
                repeats=repeats,
                rows=row_count,
                bytes_on_disk=byte_count,
                file_count=file_count,
                notes=f"top_security={top_security}; max_date={maximum_date}",
            )
        )
    return rows


def incremental_update(connection: duckdb.DuckDBPyConnection, partitioned: Path, incremental: Path) -> dict:
    incremental.mkdir(parents=True, exist_ok=True)
    rel = relation(partitioned)
    maximum_date = connection.execute(f"SELECT max(timestamp) FROM {rel}").fetchone()[0]
    target = sql_path(incremental)
    statement = f"""
        COPY (
            SELECT market, frequency, security_id, year, timestamp, open, high, low, close, volume
            FROM {rel} WHERE timestamp=DATE '{maximum_date}'
        ) TO '{target}' (
            FORMAT PARQUET,
            PARTITION_BY (market, frequency, year),
            COMPRESSION ZSTD,
            OVERWRITE_OR_IGNORE true
        )
    """
    result = measure(lambda: connection.execute(statement).fetchall())
    files, size = tree_stats(incremental)
    return {
        "date": str(maximum_date),
        "elapsed_seconds": result.elapsed_seconds,
        "peak_rss_mb": result.peak_rss_mb,
        "files": files,
        "bytes": size,
        "checksum": stable_checksum(connection.execute(f"SELECT count(*),sum(close) FROM {relation(incremental)}").fetchall()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("D:/Stock/data/stocks.parquet"))
    parser.add_argument("--cache", type=Path, default=ROOT / "cache" / "parquet_layout")
    parser.add_argument("--results", type=Path, default=ROOT.parent / "benchmark_results.csv")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    args.cache.mkdir(parents=True, exist_ok=True)
    partitioned = args.cache / "market_frequency_year_zstd"
    incremental = args.cache / "incremental_latest_day"
    connection = duckdb.connect()
    connection.execute("SET threads=12")
    connection.execute("SET memory_limit='24GB'")

    source_meta = connection.execute(
        f"SELECT count(*), count(DISTINCT ticker), min(date), max(date) FROM read_parquet('{sql_path(args.source)}')"
    ).fetchone()
    build = build_partitioned(connection, args.source, partitioned)
    layout_meta = metadata(connection, partitioned)
    if source_meta[0] != layout_meta["rows"]:
        raise RuntimeError(f"row mismatch: source={source_meta[0]} partitioned={layout_meta['rows']}")

    results = benchmark_layout(connection, args.source, "existing_monolithic", args.repeats)
    results.extend(benchmark_layout(connection, partitioned, "market_frequency_year_zstd_128mb", args.repeats))
    append_rows(args.results, results)
    update = incremental_update(connection, partitioned, incremental)
    report = {
        "source": {"path": str(args.source), "rows": source_meta[0], "securities": source_meta[1], "min_date": str(source_meta[2]), "max_date": str(source_meta[3]), "files": tree_stats(args.source)[0], "bytes": tree_stats(args.source)[1]},
        "partitioned": {"path": str(partitioned), **layout_meta, **build},
        "incremental_latest_day": update,
    }
    (args.cache / "layout_metadata.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
