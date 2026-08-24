from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PhaseAConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_data_root: Path
    output_root: Path
    phase_name: str = "phase_a"
    start_date: date
    end_date: date
    warmup_start: date
    market: str = "GPW"
    venue_mic: str = "XWAR"
    timezone: str = "Europe/Warsaw"
    event_time: str = "17:00:00"
    available_time: str = "17:05:00"
    decision_time: str = "08:45:00"
    source_name: str
    source_version: str
    schema_version: str
    universe_id: str
    universe_version: str
    logical_dataset_name: str
    seed: int = 0
    compression: str = "zstd"
    compression_level: int = 3
    row_group_size: int = 122_880
    quantiles: int = Field(default=5, ge=2, le=20)
    feature_engine: str = "polars"
    label_horizons: tuple[int, ...] = (3, 5, 10, 20)
    bootstrap_samples: int = Field(default=1_000, ge=100, le=100_000)
    bootstrap_block_sessions: int = Field(default=20, ge=2, le=252)
    confidence_level: float = Field(default=0.95, gt=0.5, lt=1.0)
    supplemental_bar_mapping_path: Path | None = None

    @field_validator("source_data_root", "output_root", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> Path:
        return Path(str(value)).resolve()

    @field_validator("supplemental_bar_mapping_path", mode="before")
    @classmethod
    def normalize_optional_path(cls, value: object) -> Path | None:
        return None if value is None else Path(str(value)).resolve()

    @model_validator(mode="after")
    def validate_contract(self) -> "PhaseAConfig":
        if self.warmup_start >= self.start_date:
            raise ValueError("warmup_start must precede start_date")
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        expected = (self.source_data_root / "ATS").resolve()
        if self.output_root != expected:
            raise ValueError(f"output_root must be exactly {expected}")
        if self.phase_name != "phase_a":
            raise ValueError("Phase A writes only beneath the phase_a namespace")
        if tuple(sorted(set(self.label_horizons))) != self.label_horizons:
            raise ValueError("label_horizons must be sorted and unique")
        if any(h <= 0 for h in self.label_horizons):
            raise ValueError("label horizons must be positive")
        return self

    @property
    def phase_root(self) -> Path:
        return self.output_root / self.phase_name

    def portable_dict(self) -> dict[str, object]:
        data = self.model_dump(mode="json")
        data["source_data_root"] = self.source_data_root.as_posix()
        data["output_root"] = self.output_root.as_posix()
        data["label_horizons"] = list(self.label_horizons)
        if self.supplemental_bar_mapping_path is not None:
            data["supplemental_bar_mapping_path"] = self.supplemental_bar_mapping_path.as_posix()
        return data


def load_config(path: Path) -> PhaseAConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("configuration must be a YAML mapping")
    return PhaseAConfig.model_validate(raw)


def dump_config(config: PhaseAConfig) -> str:
    return yaml.safe_dump(config.portable_dict(), sort_keys=True, allow_unicode=True)
