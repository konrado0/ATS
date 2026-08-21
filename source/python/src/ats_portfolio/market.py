from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from ats_portfolio.numeric import decimal_value


@dataclass(frozen=True)
class MarketBar:
    security_id: str
    session_date: date
    event_ts: datetime
    available_ts: datetime
    open: Decimal | None
    close: Decimal | None
    currency: str
    market: str = "GPW"
    source: str = "fixture"
    source_record_id: str = "fixture"
    adjustment_state: str = "raw"
    adjustment_version: str = "raw-v1"

    def __post_init__(self) -> None:
        for name in ("open", "close"):
            value = getattr(self, name)
            if value is not None:
                converted = decimal_value(value)
                if converted <= 0:
                    raise ValueError(f"{name} must be positive when present")
                object.__setattr__(self, name, converted)
        if self.available_ts < self.event_ts:
            raise ValueError("bar availability precedes its completed-bar event")

    @property
    def source_bar_id(self) -> str:
        return "|".join(
            [self.security_id, self.event_ts.isoformat(), self.source, self.adjustment_version]
        )


def modeled_open_timestamp(session: date, timezone: str, value: str) -> datetime:
    hour, minute, second = [int(part) for part in value.split(":")]
    return datetime.combine(session, time(hour, minute, second), ZoneInfo(timezone))


MARKET_FIELD_TIMING_POLICY = {
    "before_open": "no current-session OHLCV visible",
    "at_open": "open only",
    "at_bar_completion": "high low close volume",
    "fill_price_field": "open",
    "phase_b_available_ts_interpretation": "completed-bar availability only",
}
