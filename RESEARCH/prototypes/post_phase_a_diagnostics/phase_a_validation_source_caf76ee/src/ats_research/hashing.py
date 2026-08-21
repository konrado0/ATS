from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow as pa


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def hash_files(paths: Iterable[Path], root: Path) -> dict[str, str]:
    unique = sorted({path.resolve() for path in paths}, key=lambda path: path.as_posix().lower())
    return {path.relative_to(root.resolve()).as_posix(): sha256_file(path) for path in unique}


def logical_frame_hash(frame: pd.DataFrame, sort_by: list[str] | None = None) -> str:
    normalized = frame.copy()
    normalized = normalized.reindex(sorted(normalized.columns), axis=1)
    if sort_by:
        keys = [key for key in sort_by if key in normalized.columns]
        normalized = normalized.sort_values(keys, kind="mergesort", na_position="last")
    normalized = normalized.reset_index(drop=True)
    table = pa.Table.from_pandas(normalized, preserve_index=False).replace_schema_metadata(None)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return hashlib.sha256(sink.getvalue().to_pybytes()).hexdigest()


def logical_manifest_hash(manifest: dict[str, Any]) -> str:
    stable = dict(manifest)
    stable.pop("creation_timestamp", None)
    stable.pop("manifest_logical_hash", None)
    return content_hash(stable)

