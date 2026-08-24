from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from ats_research.config import PhaseAConfig
from ats_research.investing_manual import (
    SOURCE_NAME as INVESTING_SOURCE_NAME,
    load_supplemental_mapping,
    parse_investing_manual_history,
    sha256_path,
)


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
    source_inspection: pd.DataFrame
    source_overlaps: pd.DataFrame


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


def _decorate_bars(
    frame: pd.DataFrame,
    config: PhaseAConfig,
    source_path: Path,
    *,
    source_name: str | None = None,
    source_version: str | None = None,
    adjustment_version: str | None = None,
    metadata: dict[str, object] | None = None,
) -> pd.DataFrame:
    result = frame.copy()
    result["event_ts"] = localized_timestamp(result["session_date"], config.event_time, config.timezone)
    result["available_ts"] = localized_timestamp(result["session_date"], config.available_time, config.timezone)
    if not result["available_ts"].ge(result["event_ts"]).all():
        raise BarValidationError("bar availability precedes event timestamp")
    result["market"] = config.market
    result["venue_mic"] = config.venue_mic
    result["frequency"] = "daily"
    result["currency"] = "PLN"
    result["source"] = source_name or config.source_name
    result["data_version"] = source_version or config.source_version
    result["adjustment_state"] = "vendor_adjusted_semantics_unverified"
    result["adjustment_version"] = adjustment_version or config.source_version
    result["source_file"] = source_path.relative_to(config.source_data_root).as_posix()
    result["source_file_sha256"] = sha256_path(source_path)
    result["schema_version"] = "phase_a.bar.v1"
    for column, value in (metadata or {}).items():
        result[column] = value
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
    inspection_rows: list[dict[str, object]] = []
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
    supplemental = load_supplemental_mapping(config.supplemental_bar_mapping_path)
    if supplemental is not None:
        archive_manifest = config.source_data_root / str(supplemental["archive_manifest"])
        archive_source = archive_manifest.parent / "SOURCE.md"
        for provenance_path in (archive_manifest, archive_source):
            if not provenance_path.is_file():
                raise BarValidationError(f"supplemental provenance file is missing: {provenance_path}")
            input_files.append(provenance_path)
        quality_flags = "|".join(str(value) for value in supplemental["quality_flags"])
        for mapping in sorted(supplemental["mappings"], key=lambda value: str(value["isin"])):
            path = config.source_data_root / str(mapping["source_file"])
            if not path.is_file() or path.stat().st_size == 0:
                missing_files.append(path.relative_to(config.source_data_root).as_posix())
                continue
            actual_hash = sha256_path(path)
            if actual_hash.lower() != str(mapping["expected_sha256"]).lower():
                raise BarValidationError(f"supplemental source hash mismatch: {path}")
            parsed = parse_investing_manual_history(path)
            expected_security_id = vendor_resolution.loc[
                vendor_resolution["isin"].eq(str(mapping["isin"])), "security_id"
            ]
            if len(expected_security_id) != 1 or str(expected_security_id.iloc[0]) != str(mapping["security_id"]):
                raise BarValidationError(f"supplemental identity mapping mismatch for {mapping['isin']}")
            if parsed.bars["session_date"].min() < pd.Timestamp(str(mapping["listing_date"])):
                raise BarValidationError(f"supplemental observations precede listing for {mapping['isin']}")
            if parsed.bars["session_date"].max() != pd.Timestamp(str(mapping["last_trade_date"])):
                raise BarValidationError(f"supplemental terminal date mismatch for {mapping['isin']}")
            frame = parsed.bars.loc[
                parsed.bars["session_date"].between(pd.Timestamp(config.warmup_start), pd.Timestamp(config.end_date))
            ].copy()
            frame = _decorate_bars(
                frame,
                config,
                path,
                source_name=str(supplemental["source"]),
                source_version=str(supplemental["source_version"]),
                adjustment_version="investing_com_semantics_unverified",
                metadata={
                    "quality_flags": quality_flags,
                    "acquisition_method": str(supplemental["acquisition_method"]),
                    "observed_acquisition_date": str(supplemental["observed_acquisition_date"]),
                    "source_url": "unknown",
                    "source_instrument_id": "unknown",
                    "volume_semantics": "display_rounded_not_exact_share_volume",
                    "source_local_filename": path.name,
                },
            )
            frame["security_id"] = str(mapping["security_id"])
            frame["isin"] = str(mapping["isin"])
            frame["vendor_symbol"] = pd.NA
            frames.append(frame)
            input_files.append(path)
            inspection_rows.append(
                {
                    "company": str(mapping["company"]),
                    "isin": str(mapping["isin"]),
                    "security_id": str(mapping["security_id"]),
                    "source_file": path.relative_to(config.source_data_root).as_posix(),
                    "sha256": actual_hash,
                    "byte_length": path.stat().st_size,
                    **parsed.inspection,
                }
            )
    if not frames:
        raise BarValidationError("no resolved TOP60 price files were loaded")
    bars = pd.concat(frames, ignore_index=True)
    bars["source_priority"] = np.where(bars["source"].eq(INVESTING_SOURCE_NAME), 0, 1)
    overlap_mask = bars.duplicated(["security_id", "session_date"], keep=False)
    overlaps = bars.loc[overlap_mask, ["security_id", "isin", "session_date", "source", "source_file", "close"]].copy()
    if not overlaps.empty:
        overlaps["selection_rule"] = "whole Investing.com bar preferred; fields are never combined across vendors"
    bars = (
        bars.sort_values(["security_id", "session_date", "source_priority", "source_file"], kind="mergesort")
        .drop_duplicates(["security_id", "session_date"], keep="first")
        .reset_index(drop=True)
    )
    bars["source_selection_rule"] = "one whole bar per security/session; Investing.com supplemental priority, no field splicing"
    bars = bars.drop(columns="source_priority")
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
        bars[[
            "security_id", "session_date", "open", "high", "low", "close", "volume", "event_ts", "available_ts",
            "source", "source_file", "source_file_sha256", "adjustment_state", "adjustment_version", "quality_flags",
            "display_rounded_volume", "volume_rounding_uncertainty_shares", "volume_semantics", "observed_acquisition_date",
        ]],
        on=["security_id", "session_date"], how="left", validate="one_to_one",
    )
    grid = grid.sort_values(["security_id", "session_date"]).reset_index(drop=True)
    return BarData(
        bars,
        grid,
        wig.sort_values("session_date").reset_index(drop=True),
        sessions,
        tuple(input_files),
        tuple(sorted(missing_files)),
        pd.DataFrame(inspection_rows),
        overlaps.reset_index(drop=True),
    )


def validate_feature_availability(frame: pd.DataFrame) -> None:
    present = frame["feature_available_ts"].notna()
    invalid = present & frame["feature_available_ts"].gt(frame["decision_ts"])
    if invalid.any():
        sample = frame.loc[invalid, ["security_id", "session_date", "feature_available_ts", "decision_ts"]].head().to_dict("records")
        raise BarValidationError(f"feature availability exceeds decision timestamp: {sample}")
