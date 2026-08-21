from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import polars as pl
import pyarrow.compute as pc
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common.benchmark_utils import append_rows, benchmark_repeated, tree_stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--results", type=Path, default=ROOT.parent / "benchmark_results.csv")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    glob = f"{args.dataset.resolve().as_posix()}/**/*.parquet"
    files, size = tree_stats(args.dataset)
    connection = duckdb.connect()
    connection.execute("SET threads=12")
    relation = f"read_parquet('{glob}', hive_partitioning=true)"
    count, top_security, max_date = connection.execute(
        f"SELECT count(*), mode(security_id), max(timestamp) FROM {relation}"
    ).fetchone()
    top_security = str(top_security).replace("'", "''")
    arrow_dataset = ds.dataset(args.dataset, format="parquet", partitioning="hive")

    def arrow_broad():
        table = arrow_dataset.to_table(columns=["close", "volume"])
        return [(table.num_rows, pc.sum(table["close"]).as_py(), pc.mean(table["volume"]).as_py())]

    def arrow_single():
        table = arrow_dataset.to_table(filter=ds.field("security_id") == top_security, columns=["security_id", "timestamp", "close", "volume"])
        return [(table.num_rows, pc.min(table["timestamp"]).as_py(), pc.max(table["timestamp"]).as_py(), pc.sum(table["close"]).as_py())]

    date_cutoff = max_date.replace(year=max_date.year - 1)

    def arrow_date_range():
        table = arrow_dataset.to_table(filter=ds.field("timestamp") > date_cutoff, columns=["close"])
        return [(table.num_rows, pc.sum(table["close"]).as_py())]

    tasks = {
        "broad_scan": (
            lambda: connection.execute(f"SELECT count(*),sum(close),avg(volume) FROM {relation}").fetchall(),
            lambda: pl.scan_parquet(glob, hive_partitioning=True).select(pl.len(), pl.col("close").sum(), pl.col("volume").mean()).collect().to_dicts(),
            arrow_broad,
        ),
        "single_security": (
            lambda: connection.execute(f"SELECT * FROM {relation} WHERE security_id='{top_security}' ORDER BY timestamp").fetchall(),
            lambda: pl.scan_parquet(glob, hive_partitioning=True).filter(pl.col("security_id") == top_security).sort("timestamp").collect().to_dicts(),
            arrow_single,
        ),
        "date_range": (
            lambda: connection.execute(f"SELECT count(*),sum(close) FROM {relation} WHERE timestamp > DATE '{max_date}' - INTERVAL 365 DAY").fetchall(),
            lambda: pl.scan_parquet(glob, hive_partitioning=True).filter(pl.col("timestamp") > pl.lit(max_date) - pl.duration(days=365)).select(pl.len(), pl.col("close").sum()).collect().to_dicts(),
            arrow_date_range,
        ),
    }

    rows = []
    for name, functions in tasks.items():
        for engine, function in zip(("duckdb", "polars", "pyarrow"), functions):
            rows.extend(
                benchmark_repeated(
                    layer="data_engine",
                    name=name,
                    engine=engine,
                    dataset="stocks_69m_partitioned",
                    layout="market_frequency_year_zstd_128mb",
                    function=function,
                    repeats=args.repeats,
                    rows=count,
                    bytes_on_disk=size,
                    file_count=files,
                )
            )
    append_rows(args.results, rows)


if __name__ == "__main__":
    main()
