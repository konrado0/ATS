from __future__ import annotations

from decimal import Decimal
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PortfolioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    config_schema_version: Literal["ats.portfolio_config.v1"] = "ats.portfolio_config.v1"
    phase_root: Path
    phase_b_manifest: Path
    intents_file: Path
    security_events_file: Path | None = None
    corporate_actions_file: Path | None = None
    account_id: str = "reference-account"
    account_currency: str = "PLN"
    calendar: str = "XWAR"
    market_timezone: str = "Europe/Warsaw"
    market_open_time: str = "09:00:00"
    initial_cash: Decimal = Decimal("1000000")
    commission_bps: Decimal = Decimal("10")
    slippage_bps: Decimal = Decimal("15")
    max_stale_valuation_sessions: int | None = Field(default=None, ge=0)
    continue_on_unresolved_valuation: bool = True
    unavailable_target_policy: Literal["retain_as_cash", "fail_batch"] = "retain_as_cash"
    adjustment_policy: Literal["raw_with_explicit_actions", "adjusted_without_actions"] = (
        "adjusted_without_actions"
    )
    allow_borrowing: Literal[False] = False
    allow_negative_cash: Literal[False] = False
    allow_shorting: Literal[False] = False
    seed: int = 0
    run_label: str = "phase-c"
    start_session: date | None = None
    end_session: date | None = None

    @field_validator("initial_cash", "commission_bps", "slippage_bps")
    @classmethod
    def finite_nonnegative(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0:
            raise ValueError("numeric configuration must be finite and nonnegative")
        return value

    @model_validator(mode="after")
    def constraints(self) -> "PortfolioConfig":
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if self.commission_bps >= 10_000 or self.slippage_bps >= 10_000:
            raise ValueError("cost rates must be less than 10000 bps")
        lowered = self.phase_b_manifest.as_posix().lower()
        if self.phase_b_manifest.name != "manifest.json" or "current" in lowered or "latest" in lowered:
            raise ValueError("phase_b_manifest must be an explicit pinned manifest.json")
        if len(self.market_open_time.split(":")) != 3:
            raise ValueError("market_open_time must be HH:MM:SS")
        if self.start_session and self.end_session and self.end_session < self.start_session:
            raise ValueError("end_session precedes start_session")
        return self

    def identity_dict(self) -> dict[str, object]:
        value = self.model_dump(mode="json")
        value["phase_root"] = self.phase_root.resolve().as_posix()
        value["phase_b_manifest"] = self.phase_b_manifest.resolve().as_posix()
        value["intents_file"] = self.intents_file.resolve().as_posix()
        if self.security_events_file:
            value["security_events_file"] = self.security_events_file.resolve().as_posix()
        if self.corporate_actions_file:
            value["corporate_actions_file"] = self.corporate_actions_file.resolve().as_posix()
        return value


def load_config(path: Path) -> PortfolioConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("configuration must be a YAML mapping")
    return PortfolioConfig.model_validate(raw)
