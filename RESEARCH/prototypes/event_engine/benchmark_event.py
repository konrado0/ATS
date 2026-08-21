from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common.benchmark_utils import append_rows, benchmark_repeated, tree_stats
from event_engine.custom_daily import simulate, weekly_targets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--results", type=Path, default=ROOT.parent / "benchmark_results.csv")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    prices = pd.read_parquet(args.cache / "top60_prices.parquet")
    features = pd.read_parquet(args.cache / "top60_features.parquet")
    targets = weekly_targets(features)
    files, size = tree_stats(args.cache)
    rows = benchmark_repeated(
        layer="event_engine", name="weekly_top10_next_open", engine="custom_daily", dataset="gpw_top60",
        layout="long_pandas", function=lambda: simulate(prices, targets), repeats=args.repeats,
        rows=len(prices), bytes_on_disk=size, file_count=files,
        notes="10bps commission; 15bps slippage; 99.5% gross target to reserve costs",
    )
    append_rows(args.results, rows)
    result = simulate(prices, targets)
    result.equity.to_parquet(args.cache / "custom_daily_equity.parquet", index=False, compression="zstd")
    result.trades.to_parquet(args.cache / "custom_daily_trades.parquet", index=False, compression="zstd")
    print({"sessions": len(result.equity), "trades": len(result.trades), "ending_equity": float(result.equity.iloc[-1]["equity"])})


if __name__ == "__main__":
    main()
