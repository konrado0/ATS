from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import numpy as np

from ats_contracts.schemas import SORT_ORDERS


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def object_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sorted_table(table_name: str, table: pa.Table) -> pa.Table:
    declared = (table.schema.metadata or {}).get(b"ats.sorted_by")
    expected = json.dumps(list(SORT_ORDERS[table_name]), separators=(",", ":")).encode("utf-8")
    if declared == expected:
        return table.replace_schema_metadata(None)
    keys = [(name, "ascending") for name in SORT_ORDERS[table_name]]
    return table.take(pc.sort_indices(table, sort_keys=keys)) if table.num_rows else table


def mark_sorted(table_name: str, table: pa.Table) -> pa.Table:
    metadata = dict(table.schema.metadata or {})
    metadata[b"ats.sorted_by"] = json.dumps(list(SORT_ORDERS[table_name]), separators=(",", ":")).encode("utf-8")
    return table.replace_schema_metadata(metadata)


def logical_table_hash(table_name: str, table: pa.Table, *, assume_sorted: bool = False, algorithm: str = "arrow_ipc_v1") -> str:
    normalized = (table if assume_sorted else sorted_table(table_name, table)).replace_schema_metadata(None)
    if algorithm == "arrow_ipc_v1":
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, normalized.schema) as writer:
            writer.write_table(normalized)
        return hashlib.sha256(sink.getvalue().to_pybytes()).hexdigest()
    if algorithm != "arrow_ipc_stream_batches_v2":
        raise ValueError(f"unknown logical hash algorithm: {algorithm}")
    digest = hashlib.sha256(normalized.schema.serialize().to_pybytes())
    batch_size = 65_536
    for offset in range(0, normalized.num_rows, batch_size):
        length = min(batch_size, normalized.num_rows - offset)
        sliced = normalized.slice(offset, length)
        batch = sliced.take(pa.array(np.arange(length, dtype=np.int32)))
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, normalized.schema) as writer:
            writer.write_table(batch)
        digest.update(sink.getvalue().to_pybytes())
    return digest.hexdigest()


def schema_fingerprint(schema: pa.Schema) -> str:
    return hashlib.sha256(schema.remove_metadata().serialize().to_pybytes()).hexdigest()
