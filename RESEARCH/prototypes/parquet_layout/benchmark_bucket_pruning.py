from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.benchmark_utils import append_rows
from parquet_layout.benchmark_layout_variants import query_suite


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "cache" / "parquet_layout_variants" / "market_frequency_year_bucket16_zstd3",
    )
    parser.add_argument("--results", type=Path, default=ROOT.parent / "benchmark_results.csv")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    connection = duckdb.connect()
    connection.execute("SET threads=12")
    connection.execute("SET memory_limit='24GB'")
    rows = query_suite(
        connection,
        args.dataset,
        "market_frequency_year_bucket16_zstd3_rg128_pruned",
        args.repeats,
    )
    append_rows(args.results, rows)


if __name__ == "__main__":
    main()
