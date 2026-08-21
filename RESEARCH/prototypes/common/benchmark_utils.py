from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import statistics
import threading
import time
from dataclasses import dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import psutil


RESULT_FIELDS = [
    "benchmark_layer",
    "benchmark_name",
    "engine",
    "dataset",
    "layout",
    "run_kind",
    "run_index",
    "elapsed_seconds",
    "peak_rss_mb",
    "rows",
    "bytes_on_disk",
    "file_count",
    "checksum",
    "notes",
    "timestamp_utc",
]


@dataclass
class Measurement:
    elapsed_seconds: float
    peak_rss_mb: float
    value: Any


def measure(function: Callable[[], Any]) -> Measurement:
    """Measure wall time and process peak RSS while a callable runs."""
    process = psutil.Process(os.getpid())
    stop = threading.Event()
    samples: list[int] = [process.memory_info().rss]

    def sample_memory() -> None:
        while not stop.wait(0.02):
            try:
                samples.append(process.memory_info().rss)
            except psutil.Error:
                return

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    started = time.perf_counter()
    try:
        value = function()
    finally:
        elapsed = time.perf_counter() - started
        stop.set()
        sampler.join(timeout=1)
        try:
            samples.append(process.memory_info().rss)
        except psutil.Error:
            pass
    return Measurement(elapsed, max(samples) / 1024**2, value)


def stable_checksum(value: Any) -> str:
    if is_dataclass(value):
        value = {
            key: _sample_for_checksum(item)
            for key, item in value.__dict__.items()
        }
    else:
        value = _sample_for_checksum(value)
    payload = json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _sample_for_checksum(value: Any) -> Any:
    # Parallel floating-point reductions are not bit-reproducible because their
    # summation order can vary. Twelve significant digits keeps the checksum a
    # useful logical-equivalence guard without pretending IEEE sums are exact.
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return float(format(value, ".12g"))
    if isinstance(value, dict):
        return {key: _sample_for_checksum(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sample_for_checksum(item) for item in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return _sample_for_checksum(value.item())
        except (TypeError, ValueError):
            pass
    shape = getattr(value, "shape", None)
    if shape and len(shape) >= 1 and shape[0] > 2_000:
        if hasattr(value, "head") and hasattr(value, "tail"):
            try:
                head = value.head(1000)
                tail = value.tail(1000)
                return {"shape": tuple(shape), "head": _sample_for_checksum(head), "tail": _sample_for_checksum(tail)}
            except Exception:
                pass
    if hasattr(value, "to_dict"):
        try:
            value = value.to_dict(orient="split")
        except TypeError:
            value = value.to_dict()
    elif hasattr(value, "to_pylist"):
        value = value.to_pylist()
    return value


def tree_stats(path: Path) -> tuple[int, int]:
    if path.is_file():
        return 1, path.stat().st_size
    files = [item for item in path.rglob("*") if item.is_file()]
    return len(files), sum(item.stat().st_size for item in files)


def append_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            normalized = {field: row.get(field, "") for field in RESULT_FIELDS}
            normalized["timestamp_utc"] = normalized["timestamp_utc"] or datetime.now(timezone.utc).isoformat()
            writer.writerow(normalized)


def benchmark_repeated(
    *,
    layer: str,
    name: str,
    engine: str,
    dataset: str,
    layout: str,
    function: Callable[[], Any],
    repeats: int,
    rows: int | str,
    bytes_on_disk: int,
    file_count: int,
    notes: str = "",
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index in range(repeats + 1):
        measurement = measure(function)
        results.append(
            {
                "benchmark_layer": layer,
                "benchmark_name": name,
                "engine": engine,
                "dataset": dataset,
                "layout": layout,
                "run_kind": "first" if index == 0 else "warm",
                "run_index": index,
                "elapsed_seconds": round(measurement.elapsed_seconds, 6),
                "peak_rss_mb": round(measurement.peak_rss_mb, 3),
                "rows": rows,
                "bytes_on_disk": bytes_on_disk,
                "file_count": file_count,
                "checksum": stable_checksum(measurement.value),
                "notes": notes,
            }
        )
    return results


def summarize(rows: list[dict[str, Any]]) -> dict[str, float]:
    warm = [float(row["elapsed_seconds"]) for row in rows if row["run_kind"] == "warm"]
    return {
        "warm_median_seconds": statistics.median(warm),
        "warm_min_seconds": min(warm),
        "warm_max_seconds": max(warm),
    }
