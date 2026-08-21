from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from ats_research.config import PhaseAConfig


class BarValidationError(ValueError):
    pass


@dataclass(frozen=True)
class BarData:
    bars: pd.DataFrame
    session_grid: pd.DataFrame
    wig: pd.DataFrame
    sessions: pd.Series
    input_files: tuple[Path, ...]
    missing_files: tuple[str, ...]


def _clock(value: str) -> time:
    return time.fromisoformat(value)


def localized_timestamp(dates: pd.Series, clock_value: str, timezone: str) -> pd.Series:
    base = pd.to_datetime(dates).dt.normalize()
    parsed = _clock(clock_value)
    delta = pd.Timedelta(hours=parsed.hour, minutes=parsed.minute, seconds=parsed.second)
    return (base + delta).dt.tz_localize(timezone, ambiguous="raise", nonexistent="raise")


def read_stooq(path: Path, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(column).strip("<>").lower() for column in frame.columns]
    required = {"ticker", "per", "date", "open", "high", "low", "close", "vol"}
    if not required.issubset(frame.columns):
        raise BarValidationError(f"schema drift in {path}: missing {sorted(required - set(frame.columns))}")
    frame["session_date"] = pd.to_datetime(frame["date"].astype(str), format="%Y%m%d", errors="raise")
    frame = frame.loc[frame["session_date"].between(start, end)].copy()
    frame = frame.rename(columns={"vol": "volume", "ticker": "raw_vendor_symbol"})
    numeric = ["open", "high", "low", "close", "volume"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="raise")
    if frame["session_date"].duplicated().any():
        raise BarValidationError(f"duplicate session rows in {path}")
    invalid = (
        frame[numeric].isna().any(axis=1)
        | frame["close"].le(0)
        | frame["open"].le(0)
        | frame["high"].lt(frame[["open", "close", "low"]].max(axis=1) - 1e-12)
        | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1) + 1e-12)
        | frame["volume"].lt(0)
    )
    if invalid.any():
        sample = frame.loc[invalid, ["session_date", *numeric]].head().to_dict("records")
        raise BarValidationError(f"invalid OHLCV in {path}: {sample}")
    return frame[["session_date", "raw_vendor_symbol", "open", "high", "low", "close", "volume"]]


def _decorate_bars(frame: pd.DataFrame, config: PhaseAConfig, source_path: Path) -> pd.DataFrame:
    result = frame.copy()
    result["event_ts"] = localized_timestamp(result["session_date"], config.event_time, config.timezone)
    result["available_ts"] = localized_timestamp(result["session_date"], config.available_time, config.timezone)
    if not result["available_ts"].ge(result["event_ts"]).all():
        raise BarValidationError("bar availability precedes event timestamp")
    result["market"] = config.market
    result["venue_mic"] = config.venue_mic
    result["frequency"] = "daily"
    result["currency"] = "PLN"
    result["source"] = config.source_name
    result["data_version"] = config.source_version
    result["adjustment_state"] = "vendor_adjusted_semantics_unverified"
    result["adjustment_version"] = config.source_version
    result["source_file"] = source_path.relative_to(config.source_data_root).as_posix()
    result["schema_version"] = "phase_a.bar.v1"
    return result


def load_bar_data(config: PhaseAConfig, vendor_resolution: pd.DataFrame) -> BarData:
    daily_root = config.source_data_root / "daily" / "pl"
    wig_path = daily_root / "wse indices" / "wig.txt"
    wig_raw = read_stooq(wig_path, pd.Timestamp(config.warmup_start), pd.Timestamp(config.end_date))
    wig = _decorate_bars(wig_raw, config, wig_path)
    sessions = wig["session_date"].drop_duplicates().sort_values().reset_index(drop=True)
    if sessions.empty:
        raise BarValidationError("WIG calendar is empty")

    frames: list[pd.DataFrame] = []
    input_files: list[Path] = [wig_path]
    missing_files: list[str] = []
    resolved = vendor_resolution.loc[vendor_resolution["stooq_symbol"].notna()].copy()
    for row in resolved.sort_values("security_id").itertuples(index=False):
        path = daily_root / "wse stocks" / f"{str(row.stooq_symbol).lower()}.txt"
        if not path.exists() or path.stat().st_size == 0:
            missing_files.append(path.relative_to(config.source_data_root).as_posix())
            continue
        frame = read_stooq(path, pd.Timestamp(config.warmup_start), pd.Timestamp(config.end_date))
        frame = _decorate_bars(frame, config, path)
        frame["security_id"] = row.security_id
        frame["isin"] = row.isin
        frame["vendor_symbol"] = row.stooq_symbol
        frames.append(frame)
        input_files.append(path)
    if not frames:
        raise BarValidationError("no resolved TOP60 price files were loaded")
    bars = pd.concat(frames, ignore_index=True)
    semantic_key = ["security_id", "event_ts", "frequency", "source", "adjustment_version"]
    if bars.duplicated(semantic_key).any():
        raise BarValidationError("duplicate canonical bar semantic keys")
    bars = bars.sort_values(["security_id", "session_date"]).reset_index(drop=True)

    securities = vendor_resolution[["security_id", "isin", "stooq_symbol", "vendor_resolution_status"]].drop_duplicates("security_id")
    grid = pd.MultiIndex.from_product(
        [securities["security_id"].sort_values(), sessions], names=["security_id", "session_date"]
    ).to_frame(index=False)
    grid = grid.merge(securities, on="security_id", how="left", validate="many_to_one")
    grid = grid.merge(
        bars[["security_id", "session_date", "open", "high", "low", "close", "volume", "event_ts", "available_ts", "source_file"]],
        on=["security_id", "session_date"], how="left", validate="one_to_one",
    )
    grid = grid.sort_values(["security_id", "session_date"]).reset_index(drop=True)
    return BarData(bars, grid, wig.sort_values("session_date").reset_index(drop=True), sessions, tuple(input_files), tuple(sorted(missing_files)))


def validate_feature_availability(frame: pd.DataFrame) -> None:
    present = frame["feature_available_ts"].notna()
    invalid = present & frame["feature_available_ts"].gt(frame["decision_ts"])
    if invalid.any():
        sample = frame.loc[invalid, ["security_id", "session_date", "feature_available_ts", "decision_ts"]].head().to_dict("records")
        raise BarValidationError(f"feature availability exceeds decision timestamp: {sample}")

