from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import duckdb
import numba
import numpy as np
import pandas as pd
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common.benchmark_utils import append_rows, benchmark_repeated, measure, stable_checksum, tree_stats


def eligible_prices(cache: Path) -> pd.DataFrame:
    prices = (cache / "top60_prices.parquet").resolve().as_posix()
    membership = (cache / "top60_membership.parquet").resolve().as_posix()
    connection = duckdb.connect()
    return connection.execute(
        f"""
        SELECT DISTINCT p.*
        FROM read_parquet('{prices}') p
        JOIN read_parquet('{membership}') m
          ON p.security_id=m.security_id
         AND p.timestamp BETWEEN m.effective_from AND m.effective_to
        WHERE p.timestamp >= DATE '2020-11-27'
        ORDER BY p.security_id, p.timestamp
        """
    ).fetchdf()


def pandas_features(prices: pd.DataFrame, wig: pd.DataFrame) -> pd.DataFrame:
    frame = prices.sort_values(["security_id", "timestamp"]).copy()
    grouped = frame.groupby("security_id", sort=False)
    frame["ret_5"] = grouped["close"].pct_change(5, fill_method=None)
    frame["momentum_12_1"] = grouped["close"].shift(21) / grouped["close"].shift(252) - 1
    frame["ret_1"] = grouped["close"].pct_change(fill_method=None)
    frame["volatility_20"] = grouped["ret_1"].rolling(20).std().reset_index(level=0, drop=True)
    volume_mean = grouped["volume"].rolling(20).mean().reset_index(level=0, drop=True)
    frame["relative_volume_20"] = frame["volume"] / volume_mean
    for horizon in (3, 5, 10, 20):
        frame[f"forward_return_{horizon}"] = grouped["close"].shift(-horizon) / frame["close"] - 1
    frame["momentum_rank"] = frame.groupby("timestamp")["momentum_12_1"].rank(pct=True)
    wig = wig.sort_values("timestamp").copy()
    wig["wig_trend_200"] = wig["close"] / wig["close"].rolling(200).mean() - 1
    return frame.merge(wig[["timestamp", "wig_trend_200"]], on="timestamp", how="left")


def polars_features(prices: pl.DataFrame, wig: pl.DataFrame) -> pl.DataFrame:
    frame = prices.sort(["security_id", "timestamp"]).with_columns(
        (pl.col("close") / pl.col("close").shift(5).over("security_id") - 1).alias("ret_5"),
        (pl.col("close").shift(21).over("security_id") / pl.col("close").shift(252).over("security_id") - 1).alias("momentum_12_1"),
        (pl.col("close") / pl.col("close").shift(1).over("security_id") - 1).alias("ret_1"),
        (pl.col("volume") / pl.col("volume").rolling_mean(20).over("security_id")).alias("relative_volume_20"),
    ).with_columns(
        pl.col("ret_1").rolling_std(20).over("security_id").alias("volatility_20"),
        *[
            (pl.col("close").shift(-horizon).over("security_id") / pl.col("close") - 1).alias(f"forward_return_{horizon}")
            for horizon in (3, 5, 10, 20)
        ],
        pl.col("momentum_12_1").rank(method="average").over("timestamp").alias("momentum_rank_raw"),
        pl.len().over("timestamp").alias("cross_section_count"),
    ).with_columns(
        (pl.col("momentum_rank_raw") / pl.col("cross_section_count")).alias("momentum_rank")
    )
    wig_features = wig.sort("timestamp").with_columns(
        (pl.col("close") / pl.col("close").rolling_mean(200) - 1).alias("wig_trend_200")
    )
    return frame.join(wig_features.select("timestamp", "wig_trend_200"), on="timestamp", how="left")


@numba.njit(cache=True)
def parameter_sweep(close: np.ndarray, windows: np.ndarray) -> np.ndarray:
    rows, columns = close.shape
    result = np.empty((len(windows), columns), dtype=np.float64)
    for parameter in range(len(windows)):
        window = windows[parameter]
        for column in range(columns):
            newest = close[rows - 1, column]
            oldest = close[max(0, rows - 1 - window), column]
            result[parameter, column] = newest / oldest - 1 if newest > 0 and oldest > 0 else np.nan
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--results", type=Path, default=ROOT.parent / "benchmark_results.csv")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    prices_pd = eligible_prices(args.cache)
    wig_pd = pd.read_parquet(args.cache / "wig.parquet")
    prices_pl = pl.from_pandas(prices_pd)
    wig_pl = pl.from_pandas(wig_pd)
    files, size = tree_stats(args.cache)

    rows = []
    pandas_rows = benchmark_repeated(
        layer="research_backtester", name="feature_matrix", engine="pandas", dataset="gpw_top60",
        layout="normalized_top60", function=lambda: pandas_features(prices_pd, wig_pd), repeats=args.repeats,
        rows=len(prices_pd), bytes_on_disk=size, file_count=files,
    )
    rows.extend(pandas_rows)
    rows.extend(benchmark_repeated(
        layer="research_backtester", name="feature_matrix", engine="polars", dataset="gpw_top60",
        layout="normalized_top60", function=lambda: polars_features(prices_pl, wig_pl), repeats=args.repeats,
        rows=len(prices_pd), bytes_on_disk=size, file_count=files,
    ))
    append_rows(args.results, rows)
    rows = []

    features = pandas_features(prices_pd, wig_pd)
    features.to_parquet(args.cache / "top60_features.parquet", index=False, compression="zstd")
    close = prices_pd.pivot(index="timestamp", columns="security_id", values="close").to_numpy(dtype=np.float64)
    windows = (np.arange(1000, dtype=np.int64) % 230) + 20
    parameter_sweep(close, windows)
    rows.extend(benchmark_repeated(
        layer="research_backtester", name="parameter_sweep_1000", engine="numba", dataset="gpw_top60",
        layout="wide_numpy", function=lambda: parameter_sweep(close, windows), repeats=args.repeats,
        rows=close.shape[0] * close.shape[1], bytes_on_disk=size, file_count=files,
        notes=f"shape={close.shape}; variants=1000",
    ))
    append_rows(args.results, rows)
    rows = []

    try:
        benchmark_script = f"""
import pandas as pd
import vectorbt as vbt
p=pd.read_parquet(r'{(args.cache / 'top60_prices.parquet').resolve()}')
c=p.pivot(index='timestamp',columns='security_id',values='close').sort_index()
r=vbt.MA.run(c,window=[20,50,100,200]).ma
print(vbt.__version__,r.shape,float(r.iloc[-1].sum()))
"""
        started = time.perf_counter()
        completed = subprocess.run([sys.executable, "-c", benchmark_script], capture_output=True, text=True, timeout=120, check=True)
        elapsed = time.perf_counter() - started
        rows.append({
            "benchmark_layer": "research_backtester", "benchmark_name": "cold_import_and_ma_grid", "engine": "vectorbt",
            "dataset": "gpw_top60", "layout": "wide_pandas", "run_kind": "first", "run_index": 0,
            "elapsed_seconds": round(elapsed, 6), "peak_rss_mb": "", "rows": len(prices_pd),
            "bytes_on_disk": size, "file_count": files, "checksum": stable_checksum(completed.stdout),
            "notes": completed.stdout.strip(),
        })
    except subprocess.TimeoutExpired:
        rows.append({
            "benchmark_layer": "research_backtester", "benchmark_name": "cold_import_and_ma_grid", "engine": "vectorbt",
            "dataset": "gpw_top60", "layout": "wide_pandas", "run_kind": "compatibility_failed", "run_index": 0,
            "elapsed_seconds": 120, "peak_rss_mb": "", "rows": len(prices_pd), "bytes_on_disk": size,
            "file_count": files, "checksum": "", "notes": "FAILED: cold import and MA grid exceeded 120 seconds",
        })
    except Exception as error:
        rows.append({
            "benchmark_layer": "research_backtester", "benchmark_name": "vectorbt_import", "engine": "vectorbt",
            "dataset": "gpw_top60", "layout": "wide_pandas", "run_kind": "compatibility", "run_index": 0,
            "elapsed_seconds": 0, "peak_rss_mb": 0, "rows": len(prices_pd), "bytes_on_disk": size,
            "file_count": files, "checksum": "", "notes": f"FAILED: {error}",
        })
    append_rows(args.results, rows)
    print({"eligible_rows": len(prices_pd), "features_rows": len(features), "checksum": stable_checksum(features.tail(100))})


if __name__ == "__main__":
    main()
