from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ats_research.config import PhaseAConfig
from ats_research.hashing import content_hash, logical_frame_hash, sha256_file


@dataclass(frozen=True)
class ArtifactRecord:
    path: str
    format: str
    rows: int | None
    bytes: int
    sha256: str
    logical_hash: str
    sort_by: tuple[str, ...] | None = None

    def to_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


class ArtifactWriter:
    def __init__(self, run_dir: Path, config: PhaseAConfig):
        self.run_dir = run_dir.resolve()
        self.config = config
        self.records: dict[str, ArtifactRecord] = {}

    def _path(self, relative: str) -> Path:
        path = (self.run_dir / relative).resolve()
        if not path.is_relative_to(self.run_dir):
            raise ValueError(f"artifact path escapes run directory: {relative}")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def parquet(self, relative: str, frame: pd.DataFrame, sort_by: list[str]) -> ArtifactRecord:
        path = self._path(relative)
        ordered = frame.sort_values([key for key in sort_by if key in frame.columns], kind="mergesort", na_position="last").reset_index(drop=True)
        table = pa.Table.from_pandas(ordered, preserve_index=False)
        pq.write_table(
            table, path, compression=self.config.compression, compression_level=self.config.compression_level,
            row_group_size=self.config.row_group_size, version="2.6", data_page_version="1.0",
            use_dictionary=True, write_statistics=True,
        )
        round_tripped = pd.read_parquet(path)
        record = ArtifactRecord(
            relative, "parquet", len(ordered), path.stat().st_size,
            sha256_file(path), logical_frame_hash(round_tripped, sort_by), tuple(sort_by),
        )
        self.records[relative] = record
        return record

    def csv(self, relative: str, frame: pd.DataFrame, sort_by: list[str]) -> ArtifactRecord:
        path = self._path(relative)
        ordered = frame.sort_values([key for key in sort_by if key in frame.columns], kind="mergesort", na_position="last").reset_index(drop=True)
        ordered.to_csv(path, index=False, encoding="utf-8", lineterminator="\n", date_format="%Y-%m-%dT%H:%M:%S%z")
        text = path.read_text(encoding="utf-8")
        record = ArtifactRecord(relative, "csv", len(ordered), path.stat().st_size, sha256_file(path), content_hash(text), tuple(sort_by))
        self.records[relative] = record
        return record

    def json(self, relative: str, value: Any, track: bool = True) -> ArtifactRecord:
        path = self._path(relative)
        text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
        path.write_text(text, encoding="utf-8", newline="\n")
        record = ArtifactRecord(relative, "json", None, path.stat().st_size, sha256_file(path), content_hash(value))
        if track:
            self.records[relative] = record
        return record

    def text(self, relative: str, value: str, format_name: str) -> ArtifactRecord:
        path = self._path(relative)
        path.write_text(value, encoding="utf-8", newline="\n")
        record = ArtifactRecord(relative, format_name, None, path.stat().st_size, sha256_file(path), content_hash(value))
        self.records[relative] = record
        return record

    def bytes(self, relative: str, value: bytes, format_name: str) -> ArtifactRecord:
        path = self._path(relative)
        path.write_bytes(value)
        digest = hashlib.sha256(value).hexdigest()
        record = ArtifactRecord(relative, format_name, None, len(value), digest, digest)
        self.records[relative] = record
        return record
