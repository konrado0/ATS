from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import numpy as np
from sklearn.linear_model import SGDRegressor

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from common.benchmark_utils import append_rows, benchmark_repeated, tree_stats


def load_real_matrix(source: Path, maximum_rows: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    connection = duckdb.connect()
    connection.execute("SET threads=12")
    path = source.resolve().as_posix()
    frame = connection.execute(
        f"""
        WITH raw AS (
            SELECT ticker, date, open, high, low, close, volume
            FROM read_parquet('{path}')
            WHERE date >= DATE '2015-01-01'
            LIMIT {int(maximum_rows + 100_000)}
        ), base AS (
            SELECT s.ticker, s.date, s.open, s.high, s.low, s.close, s.volume,
                   close / lag(close, 1) OVER w - 1 AS r1,
                   close / lag(close, 5) OVER w - 1 AS r5,
                   close / lag(close, 20) OVER w - 1 AS r20,
                   close / lag(close, 60) OVER w - 1 AS r60,
                   close / lag(close, 252) OVER w - 1 AS r252,
                   (high-low)/nullif(close,0) AS range1,
                   volume / nullif(avg(volume) OVER (PARTITION BY s.ticker ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),0) AS relvol20
            FROM raw s
            WINDOW w AS (PARTITION BY s.ticker ORDER BY date)
        ), bars AS (
            SELECT *,
                   stddev_samp(r1) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vol20,
                   lead(close, 5) OVER (PARTITION BY ticker ORDER BY date) / close - 1 AS target
            FROM base
        )
        SELECT * FROM bars
        WHERE r252 IS NOT NULL AND target IS NOT NULL
        ORDER BY date, ticker
        LIMIT {int(maximum_rows)}
        """
    ).fetchdf()
    base_columns = ["r1", "r5", "r20", "r60", "r252", "range1", "relvol20", "vol20"]
    base = frame[base_columns].replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy(dtype=np.float32)
    features = [base]
    for power in (2, 3):
        features.append(np.sign(base) * np.abs(base) ** power)
    for scale in (0.5, 2.0, 5.0, 10.0):
        features.append(np.tanh(base * scale))
    matrix = np.concatenate(features, axis=1)
    target = frame["target"].to_numpy(dtype=np.float32)
    dates = frame["date"].to_numpy()
    return matrix, target, dates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("D:/Stock/data/stocks.parquet"))
    parser.add_argument("--results", type=Path, default=ROOT.parent / "benchmark_results.csv")
    parser.add_argument("--rows", type=int, default=500_000)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    print("building real-data matrix", flush=True)
    x, y, dates = load_real_matrix(args.source, args.rows)
    print(f"matrix ready: {x.shape}", flush=True)
    unique_dates = np.unique(dates)
    split_date = unique_dates[int(len(unique_dates) * 0.8)]
    train_mask = dates < split_date
    test_mask = dates >= split_date
    x_train, x_test, y_train = x[train_mask], x[test_mask], y[train_mask]
    files, size = tree_stats(args.source)
    rows = []

    def linear_baseline() -> np.ndarray:
        model = SGDRegressor(alpha=0.0001, max_iter=100, tol=1e-4, random_state=42)
        model.fit(x_train[:200_000], y_train[:200_000])
        return model.predict(x_test)

    rows.extend(benchmark_repeated(
        layer="ml", name="chronological_fit_predict", engine="sklearn_sgd_cpu", dataset="real_us_equities",
        layout="float32_matrix", function=linear_baseline, repeats=args.repeats, rows=len(x), bytes_on_disk=size,
        file_count=files, notes=f"features={x.shape[1]}; chronological_80_20; train_cap=200000",
    ))
    print("linear baseline complete", flush=True)

    import lightgbm as lgb
    def lightgbm_cpu() -> np.ndarray:
        model = lgb.LGBMRegressor(n_estimators=100, num_leaves=31, learning_rate=0.05, n_jobs=12, verbosity=-1, random_state=42)
        model.fit(x_train, y_train)
        return model.predict(x_test)
    rows.extend(benchmark_repeated(
        layer="ml", name="chronological_fit_predict", engine="lightgbm_cpu", dataset="real_us_equities",
        layout="float32_matrix", function=lightgbm_cpu, repeats=args.repeats, rows=len(x), bytes_on_disk=size,
        file_count=files, notes=f"features={x.shape[1]}; trees=100; chronological_80_20",
    ))
    print("lightgbm complete", flush=True)

    import xgboost as xgb
    def xgboost_cpu() -> np.ndarray:
        model = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.05, tree_method="hist", n_jobs=12, random_state=42)
        model.fit(x_train, y_train)
        return model.predict(x_test)
    rows.extend(benchmark_repeated(
        layer="ml", name="chronological_fit_predict", engine="xgboost_cpu", dataset="real_us_equities",
        layout="float32_matrix", function=xgboost_cpu, repeats=args.repeats, rows=len(x), bytes_on_disk=size,
        file_count=files, notes=f"features={x.shape[1]}; trees=100; chronological_80_20",
    ))
    print("xgboost cpu complete", flush=True)

    def xgboost_gpu() -> np.ndarray:
        model = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.05, tree_method="hist", device="cuda", random_state=42)
        model.fit(x_train, y_train)
        return model.predict(x_test)
    try:
        rows.extend(benchmark_repeated(
            layer="ml", name="chronological_fit_predict", engine="xgboost_gpu", dataset="real_us_equities",
            layout="float32_matrix", function=xgboost_gpu, repeats=args.repeats, rows=len(x), bytes_on_disk=size,
            file_count=files, notes=f"features={x.shape[1]}; trees=100; chronological_80_20",
        ))
        print("xgboost gpu complete", flush=True)
    except Exception as error:
        rows.append({
            "benchmark_layer": "ml", "benchmark_name": "chronological_fit_predict", "engine": "xgboost_gpu",
            "dataset": "real_us_equities", "layout": "float32_matrix", "run_kind": "compatibility", "run_index": 0,
            "elapsed_seconds": 0, "peak_rss_mb": 0, "rows": len(x), "bytes_on_disk": size,
            "file_count": files, "checksum": "", "notes": f"FAILED: {error}",
        })
    append_rows(args.results, rows)
    print({"rows": len(x), "features": x.shape[1], "train_end": str(dates[train_mask][-1]), "test_start": str(dates[test_mask][0]), "split_date": str(split_date)})


if __name__ == "__main__":
    main()
