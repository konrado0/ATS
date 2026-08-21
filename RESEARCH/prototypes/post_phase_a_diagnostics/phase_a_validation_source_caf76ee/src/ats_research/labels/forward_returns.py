from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class LabelDefinition:
    name: str
    version: int
    horizon_sessions: int
    start_price: str = "official decision-session close"
    end_price: str = "close exactly h WIG market sessions after the start session"
    horizon_counting: str = "WIG market sessions; the start session is session 0"
    missing_session_behavior: str = "null when start or exact end-session security close is unavailable; no forward fill"
    interpretation: str = "close-to-close research diagnostic outcome; not an executable portfolio return"

    @property
    def column(self) -> str:
        return f"label__forward_return_{self.horizon_sessions}__v{self.version}"

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["column"] = self.column
        return result


def label_definitions(horizons: tuple[int, ...] = (3, 5, 10, 20)) -> tuple[LabelDefinition, ...]:
    return tuple(LabelDefinition(f"forward_return_{h}", 1, h) for h in horizons)


def compute_forward_returns(session_grid: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    result = session_grid[["security_id", "session_date", "close"]].sort_values(["security_id", "session_date"]).copy()
    grouped = result.groupby("security_id", sort=False)["close"]
    for definition in label_definitions(horizons):
        result[definition.column] = grouped.shift(-definition.horizon_sessions) / result["close"] - 1.0
    return result.drop(columns="close")

