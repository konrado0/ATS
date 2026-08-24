from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PARSER_VERSION = "investing_com_manual_tsv_v1"
SOURCE_NAME = "investing_com_manual_history"
EXPECTED_HEADER = ("Data", "Ostatnio", "Otwarcie", "Max.", "Min.", "Wol.", "Zmiana%")
_DECIMAL = re.compile(r"^[0-9]+(?:,[0-9]+)?$")
_DECIMAL_WITH_DOT_THOUSANDS = re.compile(r"^[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]+)?$")
_VOLUME = re.compile(r"^(?P<value>[0-9]+(?:,[0-9]+)?)(?P<suffix>[KM])$")
_PERCENT = re.compile(r"^[+-]?[0-9]+(?:[.,][0-9]+)?%$")


class InvestingManualValidationError(ValueError):
    pass


@dataclass(frozen=True)
class InvestingManualHistory:
    bars: pd.DataFrame
    inspection: dict[str, Any]


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_supplemental_mapping(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("source") != SOURCE_NAME:
        raise InvestingManualValidationError("supplemental mapping has incorrect source")
    if payload.get("parser_version") != PARSER_VERSION:
        raise InvestingManualValidationError("supplemental mapping has unsupported parser version")
    mappings = payload.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        raise InvestingManualValidationError("supplemental mapping must contain mappings")
    isins = [str(row.get("isin", "")) for row in mappings]
    files = [str(row.get("source_file", "")) for row in mappings]
    if any(not value for value in isins + files) or len(isins) != len(set(isins)) or len(files) != len(set(files)):
        raise InvestingManualValidationError("supplemental mappings require unique non-empty ISINs and files")
    return payload


def listing_state(session_date: str | pd.Timestamp, listing_date: str | pd.Timestamp) -> str:
    return "not_yet_listed" if pd.Timestamp(session_date) < pd.Timestamp(listing_date) else "listed"


def _decimal(value: str, field: str, line_number: int, *, allow_dot_thousands: bool = False) -> float:
    standard = _DECIMAL.fullmatch(value)
    dot_thousands = allow_dot_thousands and _DECIMAL_WITH_DOT_THOUSANDS.fullmatch(value)
    if not standard and not dot_thousands:
        raise InvestingManualValidationError(f"line {line_number}: malformed {field} value {value!r}")
    try:
        normalized = value.replace(".", "") if dot_thousands else value
        return float(Decimal(normalized.replace(",", ".")))
    except InvalidOperation as error:
        raise InvestingManualValidationError(f"line {line_number}: malformed {field} value {value!r}") from error


def _volume(value: str, line_number: int) -> tuple[float, str, float]:
    match = _VOLUME.fullmatch(value)
    if match is None:
        raise InvestingManualValidationError(f"line {line_number}: unsupported volume form {value!r}")
    base = Decimal(match.group("value").replace(",", "."))
    suffix = match.group("suffix")
    multiplier = Decimal(1_000 if suffix == "K" else 1_000_000)
    uncertainty = 5.0 if suffix == "K" else 5_000.0
    return float(base * multiplier), suffix, uncertainty


def _percent(value: str, line_number: int) -> float:
    if not _PERCENT.fullmatch(value):
        raise InvestingManualValidationError(f"line {line_number}: malformed percentage value {value!r}")
    return float(Decimal(value[:-1].replace(",", ".")))


def parse_investing_manual_history(
    path: Path,
    *,
    allow_missing_display_volume: bool = False,
    allow_dot_thousands_in_prices: bool = False,
) -> InvestingManualHistory:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise InvestingManualValidationError(f"{path}: expected strict UTF-8/ASCII-compatible text") from error
    lines = [(number, line.strip()) for number, line in enumerate(text.splitlines(), start=1) if line.strip()]
    header = tuple(line for _number, line in lines[: len(EXPECTED_HEADER)])
    if header != EXPECTED_HEADER:
        raise InvestingManualValidationError(f"{path}: unexpected header {header!r}")
    rows: list[dict[str, object]] = []
    displayed_changes: list[float] = []
    for line_number, line in lines[len(EXPECTED_HEADER) :]:
        fields = line.split("\t")
        if len(fields) != 7:
            raise InvestingManualValidationError(f"line {line_number}: expected 7 tab-separated fields, got {len(fields)}")
        date_raw, close_raw, open_raw, high_raw, low_raw, volume_raw, change_raw = fields
        try:
            session_date = pd.to_datetime(date_raw, format="%d.%m.%Y", errors="raise")
        except (TypeError, ValueError) as error:
            raise InvestingManualValidationError(f"line {line_number}: invalid date {date_raw!r}") from error
        close = _decimal(close_raw, "close", line_number, allow_dot_thousands=allow_dot_thousands_in_prices)
        open_ = _decimal(open_raw, "open", line_number, allow_dot_thousands=allow_dot_thousands_in_prices)
        high = _decimal(high_raw, "high", line_number, allow_dot_thousands=allow_dot_thousands_in_prices)
        low = _decimal(low_raw, "low", line_number, allow_dot_thousands=allow_dot_thousands_in_prices)
        if not volume_raw and allow_missing_display_volume:
            volume, suffix, uncertainty = np.nan, pd.NA, np.nan
        else:
            volume, suffix, uncertainty = _volume(volume_raw, line_number)
        displayed_change = _percent(change_raw, line_number)
        if min(open_, high, low, close) <= 0 or volume < 0 or high < max(open_, close, low) or low > min(open_, close, high):
            raise InvestingManualValidationError(
                f"line {line_number}: invalid OHLCV open={open_} high={high} low={low} close={close} volume={volume}"
            )
        rows.append(
            {
                "session_date": session_date,
                "raw_vendor_symbol": pd.NA,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "volume_display_suffix": suffix,
                "volume_rounding_uncertainty_shares": uncertainty,
                "display_rounded_volume": True,
            }
        )
        displayed_changes.append(displayed_change)
    if not rows:
        raise InvestingManualValidationError(f"{path}: no observations")
    frame = pd.DataFrame(rows)
    input_dates = frame["session_date"].copy()
    if input_dates.duplicated().any():
        dates = input_dates.loc[input_dates.duplicated(keep=False)].dt.strftime("%Y-%m-%d").unique().tolist()
        raise InvestingManualValidationError(f"{path}: duplicate dates {dates[:5]}")
    input_order = "descending" if input_dates.is_monotonic_decreasing else "ascending" if input_dates.is_monotonic_increasing else "unsorted"
    frame["_displayed_change_pct"] = displayed_changes
    frame = frame.sort_values("session_date", kind="mergesort").reset_index(drop=True)
    expected_change = frame["close"].pct_change() * 100.0
    change_error = (frame["_displayed_change_pct"] - expected_change).abs()
    close_jump = frame["close"].pct_change().abs()
    volume_ratio = frame["volume"].replace(0, np.nan).pct_change().abs()
    inspection = {
        "parser_version": PARSER_VERSION,
        "encoding": "utf-8-strict-ascii-compatible",
        "delimiter": "tab",
        "header": list(EXPECTED_HEADER),
        "raw_line_count": len(text.splitlines()),
        "nonempty_line_count": len(lines),
        "row_count": len(frame),
        "column_count": 7,
        "first_date": frame["session_date"].min().date().isoformat(),
        "last_date": frame["session_date"].max().date().isoformat(),
        "input_order": input_order,
        "duplicate_dates": 0,
        "malformed_rows": 0,
        "volume_forms": sorted(frame["volume_display_suffix"].dropna().unique().tolist()),
        "missing_display_volume_rows": int(frame["volume"].isna().sum()),
        "dot_thousands_price_rows": int(
            sum(any("." in value for value in fields[1:5]) for fields in (line.split("\t") for _number, line in lines[len(EXPECTED_HEADER) :]))
        ),
        "change_pct_max_abs_error_pp": float(change_error.dropna().max()) if change_error.notna().any() else None,
        "change_pct_rows_over_0_15pp_error": int(change_error.gt(0.15).sum()),
        "absolute_close_jumps_over_25pct": int(close_jump.gt(0.25).sum()),
        "absolute_volume_changes_over_100x": int(volume_ratio.gt(100).sum()),
    }
    return InvestingManualHistory(frame.drop(columns="_displayed_change_pct"), inspection)
