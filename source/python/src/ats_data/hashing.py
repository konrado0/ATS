from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import numpy as np

from ats_contracts.schemas import SORT_ORDERS


class IncrementalArrowHasher:
    """Chunk-boundary-independent logical Arrow hash with bounded buffering."""

    def __init__(self, schema: pa.Schema, batch_size: int = 65_536):
        self.schema = schema.remove_metadata()
        self.batch_size = batch_size
        self._digest = hashlib.sha256(self.schema.serialize().to_pybytes())
        self._pending: list[pa.RecordBatch] = []
        self._pending_rows = 0
        self.rows = 0

    def update(self, value: pa.RecordBatch | pa.Table) -> None:
        table = pa.Table.from_batches([value], schema=value.schema) if isinstance(value, pa.RecordBatch) else value
        table = table.replace_schema_metadata(None).cast(self.schema)
        for batch in table.to_batches(max_chunksize=self.batch_size):
            self._pending.append(batch)
            self._pending_rows += batch.num_rows
            self.rows += batch.num_rows
            self._drain(False)

    def _drain(self, final: bool) -> None:
        while self._pending_rows >= self.batch_size or (final and self._pending_rows):
            take_rows = min(self.batch_size, self._pending_rows)
            combined = pa.Table.from_batches(self._pending, schema=self.schema).combine_chunks()
            chunk = combined.slice(0, take_rows)
            # Preserve the v2 byte contract used by existing Phase B versions.
            chunk = chunk.take(pa.array(np.arange(take_rows, dtype=np.int32)))
            sink = pa.BufferOutputStream()
            with pa.ipc.new_stream(sink, self.schema) as writer:
                writer.write_table(chunk)
            self._digest.update(sink.getvalue().to_pybytes())
            remainder = combined.slice(take_rows)
            self._pending = remainder.to_batches() if remainder.num_rows else []
            self._pending_rows = remainder.num_rows

    def hexdigest(self) -> str:
        self._drain(True)
        return self._digest.hexdigest()


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
