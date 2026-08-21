from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


FIELDS = [
    "benchmark_layer", "benchmark_name", "engine", "dataset", "layout", "run_kind", "run_index",
    "elapsed_seconds", "peak_rss_mb", "rows", "bytes_on_disk", "file_count", "checksum", "notes", "timestamp_utc",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    candidates = {
        "pybroker": "pybroker",
        "zipline_reloaded": "zipline",
        "backtrader": "backtrader",
    }
    rows = []
    for engine, module in candidates.items():
        started = time.perf_counter()
        try:
            code = f"import {module} as m; print(getattr(m, '__version__', 'unknown'))"
            completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=90, check=True)
            elapsed = time.perf_counter() - started
            version = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else "unknown"
            note = f"import_ok; version={version}; python={sys.version.split()[0]}"
            kind = "compatibility"
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - started
            note = f"FAILED: cold import exceeded 90 seconds; python={sys.version.split()[0]}"
            kind = "compatibility_failed"
        except Exception as error:
            elapsed = time.perf_counter() - started
            note = f"FAILED: {type(error).__name__}: {error}; python={sys.version.split()[0]}"
            kind = "compatibility_failed"
        rows.append({
            "benchmark_layer": "event_engine", "benchmark_name": "import_smoke", "engine": engine,
            "dataset": "none", "layout": "none", "run_kind": kind, "run_index": 0,
            "elapsed_seconds": round(elapsed, 6), "peak_rss_mb": "", "rows": 0,
            "bytes_on_disk": 0, "file_count": 0, "checksum": "", "notes": note,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        })
    args.results.parent.mkdir(parents=True, exist_ok=True)
    exists = args.results.exists() and args.results.stat().st_size > 0
    with args.results.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(row["engine"], row["notes"])


if __name__ == "__main__":
    main()
