from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PhaseBConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    phase_root: Path
    trusted_phase_a_run: Path
    source_data_root: Path
    compression: str = "zstd"
    compression_level: int = 3
    row_group_size: int = Field(default=122_880, gt=0)
    split_size_review_bytes: int = Field(default=2 * 1024**3, gt=0)
    max_rows_per_file: int | None = Field(default=None, gt=0)
    ingestion_timestamp: datetime = datetime(2026, 8, 20, tzinfo=timezone.utc)
    source_version: str = "local_snapshot_2025_12_31"
    us_start_date: str | None = None
    us_end_date: str | None = "2025-12-31"

    @field_validator("phase_root", "trusted_phase_a_run", "source_data_root", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> Path:
        return Path(str(value)).resolve()

    @field_validator("ingestion_timestamp")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("ingestion_timestamp must be timezone-aware UTC")
        return value

    @model_validator(mode="after")
    def validate_boundaries(self) -> "PhaseBConfig":
        if self.phase_root.name != "phase_b" or self.phase_root.parent.name != "ATS":
            raise ValueError("phase_root must be a concrete ATS/phase_b subtree")
        if self.compression.lower() != "zstd":
            raise ValueError("Phase B reference publication requires ZSTD")
        if self.max_rows_per_file is not None and self.max_rows_per_file < self.row_group_size:
            raise ValueError("max_rows_per_file cannot be smaller than one row group")
        return self

    def identity_dict(self) -> dict[str, object]:
        data = self.model_dump(mode="json")
        data.pop("phase_root")
        data["trusted_phase_a_run"] = self.trusted_phase_a_run.as_posix()
        data["source_data_root"] = self.source_data_root.as_posix()
        return data


def load_config(path: Path) -> PhaseBConfig:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Phase B configuration must be a YAML mapping")
    return PhaseBConfig.model_validate(value)
