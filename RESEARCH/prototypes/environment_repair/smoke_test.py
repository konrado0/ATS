from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()

    import catboost
    import lightgbm
    import matplotlib
    import numba
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    import scipy
    import scipy.linalg as scipy_linalg
    import scipy.stats as scipy_stats
    import torch
    import vectorbt
    import xgboost
    from sklearn.linear_model import LinearRegression

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = np.arange(20.0)
    matrix = np.array([[2.0, 1.0], [1.0, 3.0]])
    target = np.array([1.0, 2.0])

    numpy_solve = np.linalg.solve(matrix, target)
    numpy_svd = np.linalg.svd(matrix)[1]
    polyfit = np.polyfit(x, x * x, 2)
    corrcoef = float(np.corrcoef(x, x * x)[0, 1])
    scipy_solve = scipy_linalg.solve(matrix, target)
    spearman = float(scipy_stats.spearmanr(x, x * x).statistic)
    pandas_corr = float(pd.Series(x).corr(pd.Series(x * x)))
    sklearn_slope = float(LinearRegression().fit(x.reshape(-1, 1), x * x).coef_[0])

    compiled_sum = numba.njit(lambda values: (values * values).sum())(x)
    torch_dot = float(torch.tensor([1.0, 2.0]) @ torch.tensor([3.0, 4.0]))

    parquet_path = output_dir / "smoke.parquet"
    pq.write_table(pa.table({"x": [1, 2, 3]}), parquet_path)
    arrow_rows = pq.read_table(parquet_path).num_rows

    figure_path = output_dir / "smoke.png"
    figure, axis = plt.subplots()
    axis.plot(x, x * x)
    figure.savefig(figure_path)
    plt.close(figure)

    checks = {
        "numpy_solve": bool(np.allclose(numpy_solve, [0.2, 0.6])),
        "numpy_svd": bool(np.all(numpy_svd > 0)),
        "numpy_polyfit": bool(np.allclose(polyfit, [1.0, 0.0, 0.0], atol=1e-10)),
        "numpy_corrcoef": bool(0.9 < corrcoef < 1.0),
        "scipy_solve": bool(np.allclose(scipy_solve, [0.2, 0.6])),
        "scipy_spearman": spearman == 1.0,
        "pandas_corr": bool(np.isclose(pandas_corr, corrcoef)),
        "sklearn_fit": sklearn_slope == 19.0,
        "numba_compile": float(compiled_sum) == 2470.0,
        "torch_compute": torch_dot == 11.0,
        "pyarrow_roundtrip": arrow_rows == 3,
        "matplotlib_render": figure_path.stat().st_size > 0,
        # The Codex command runner intentionally sanitizes child PATH values.
        # Availability plus successful native-library imports above is the
        # portable check when Python is invoked directly from the clone.
        "conda_library_bin_available": (Path(sys.prefix) / "Library" / "bin").is_dir(),
    }

    results = {
        "passed": all(checks.values()),
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "python": {
            "executable": sys.executable,
            "prefix": sys.prefix,
            "version": platform.python_version(),
        },
        "versions": {
            "catboost": catboost.__version__,
            "lightgbm": lightgbm.__version__,
            "matplotlib": matplotlib.__version__,
            "numba": numba.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyarrow": pa.__version__,
            "scipy": scipy.__version__,
            "torch": torch.__version__,
            "vectorbt": vectorbt.__version__,
            "xgboost": xgboost.__version__,
        },
        "checks": checks,
        "outputs": {
            "figure": str(figure_path),
            "figure_bytes": figure_path.stat().st_size,
            "parquet": str(parquet_path),
            "parquet_bytes": parquet_path.stat().st_size,
        },
    }

    (output_dir / "smoke_results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
