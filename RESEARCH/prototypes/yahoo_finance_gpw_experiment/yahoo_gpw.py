"""Small, isolated Yahoo Finance acquisition and normalization helpers.

The module deliberately preserves yfinance's source-native table before creating
an ATS-friendly normalized projection.  It is experimental and is not imported
by accepted Phase A/B/C code paths.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class YahooSettings:
    start: str
    end_exclusive: str
    interval: str = "1d"
    auto_adjust: bool = False
    back_adjust: bool = False
    repair: bool = False
    actions: bool = True
    keepna: bool = True
    rounding: bool = False
    timeout_seconds: int = 30


@dataclass
class FetchResult:
    symbol: str
    native: pd.DataFrame
    normalized: pd.DataFrame
    metadata: dict[str, Any]
    acquired_at_utc: str
    settings: YahooSettings


def configure_cache(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(cache_dir))


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def fetch_history(
    symbol: str,
    security: str,
    isin: str,
    settings: YahooSettings,
) -> FetchResult:
    """Fetch an unmodified yfinance history table and normalized projection."""
    yf.config.debug.hide_exceptions = False
    ticker = yf.Ticker(symbol)
    native = ticker.history(
        start=settings.start,
        end=settings.end_exclusive,
        interval=settings.interval,
        auto_adjust=settings.auto_adjust,
        back_adjust=settings.back_adjust,
        repair=settings.repair,
        actions=settings.actions,
        keepna=settings.keepna,
        rounding=settings.rounding,
        timeout=settings.timeout_seconds,
    )
    metadata: dict[str, Any]
    try:
        metadata = _jsonable(ticker.history_metadata)
    except Exception as exc:
        metadata = {"metadata_error": f"{type(exc).__name__}: {exc}"}
    acquired = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    normalized = normalize_history(native, symbol=symbol, security=security, isin=isin)
    return FetchResult(symbol, native, normalized, metadata, acquired, settings)


def normalize_history(
    native: pd.DataFrame,
    *,
    symbol: str,
    security: str,
    isin: str,
) -> pd.DataFrame:
    """Create a loss-minimizing normalized daily projection.

    The date component is retained exactly as Yahoo presented it.  This matters
    because some delisted `.WA` tables currently carry incorrect New York/YHD
    metadata even though their date labels represent historical GPW sessions.
    """
    columns = [
        "security", "isin", "yahoo_symbol", "session_date", "source_timestamp",
        "open", "high", "low", "close", "adj_close", "volume", "dividend",
        "stock_split", "capital_gain",
    ]
    if native.empty:
        return pd.DataFrame(columns=columns)

    frame = native.copy()
    timestamps = pd.Index(frame.index)
    out = pd.DataFrame(index=range(len(frame)))
    out["security"] = security
    out["isin"] = isin
    out["yahoo_symbol"] = symbol
    out["session_date"] = [timestamp.date().isoformat() for timestamp in timestamps]
    out["source_timestamp"] = [timestamp.isoformat() for timestamp in timestamps]
    source_columns = {
        "Open": "open", "High": "high", "Low": "low", "Close": "close",
        "Adj Close": "adj_close", "Volume": "volume", "Dividends": "dividend",
        "Stock Splits": "stock_split", "Capital Gains": "capital_gain",
    }
    for source, target in source_columns.items():
        out[target] = frame[source].to_numpy() if source in frame else 0.0
    price_complete = out[["open", "high", "low", "close"]].notna().all(axis=1)
    has_action = (
        out[["dividend", "stock_split", "capital_gain"]]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
        .ne(0)
        .any(axis=1)
    )
    return out.loc[price_complete | has_action, columns].reset_index(drop=True)


def validate_normalized(frame: pd.DataFrame) -> dict[str, Any]:
    dates = pd.to_datetime(frame["session_date"], errors="coerce")
    price_columns = ["open", "high", "low", "close", "adj_close"]
    prices = frame[price_columns].apply(pd.to_numeric, errors="coerce")
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    complete_bar = prices[["open", "high", "low", "close"]].notna().all(axis=1)
    positive_prices = (prices.loc[complete_bar, ["open", "high", "low", "close"]] > 0).all(axis=1)
    high_valid = prices.loc[complete_bar, "high"] >= prices.loc[
        complete_bar, ["open", "low", "close"]
    ].max(axis=1)
    low_valid = prices.loc[complete_bar, "low"] <= prices.loc[
        complete_bar, ["open", "high", "close"]
    ].min(axis=1)
    invalid_volume = volume.notna() & (volume < 0)
    return {
        "rows": int(len(frame)),
        "first_session": None if frame.empty else frame["session_date"].min(),
        "last_session": None if frame.empty else frame["session_date"].max(),
        "invalid_dates": int(dates.isna().sum()),
        "duplicate_dates": int(dates.duplicated().sum()),
        "chronological": bool(dates.is_monotonic_increasing),
        "complete_price_bars": int(complete_bar.sum()),
        "incomplete_price_rows": int((~complete_bar).sum()),
        "nonpositive_price_rows": int((~positive_prices).sum()),
        "invalid_high_rows": int((~high_valid).sum()),
        "invalid_low_rows": int((~low_valid).sum()),
        "negative_volume_rows": int(invalid_volume.sum()),
        "valid": bool(
            dates.notna().all()
            and not dates.duplicated().any()
            and dates.is_monotonic_increasing
            and positive_prices.all()
            and high_valid.all()
            and low_valid.all()
            and not invalid_volume.any()
        ),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def save_acquisition(
    result: FetchResult,
    destination: Path,
    *,
    identity_mapping: dict[str, Any],
) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    native_path = destination / "yfinance_native.csv"
    normalized_path = destination / "normalized_daily.csv"
    metadata_path = destination / "yahoo_history_metadata.json"
    provenance_path = destination / "provenance.json"

    result.native.to_csv(native_path, index=True, lineterminator="\n")
    result.normalized.to_csv(normalized_path, index=False, lineterminator="\n")
    metadata_path.write_text(
        json.dumps(result.metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    validation = validate_normalized(result.normalized)
    provenance = {
        "source": "Yahoo Finance via yfinance",
        "status": "experimental_supplemental_source_observation",
        "yahoo_symbol": result.symbol,
        "identity_mapping": identity_mapping,
        "request": asdict(result.settings),
        "actual_first_session": validation["first_session"],
        "actual_last_session": validation["last_session"],
        "rows": validation["rows"],
        "native_rows": int(len(result.native)),
        "native_placeholder_rows_excluded_from_normalized": int(len(result.native) - len(result.normalized)),
        "acquired_at_utc": result.acquired_at_utc,
        "acquisition_mechanism": "yfinance.Ticker.history",
        "yfinance_version": yf.__version__,
        "normalization": {
            "session_date": "date component of Yahoo/yfinance index; source timestamp retained",
            "field_adjustment": "none",
            "timezone_conversion": "none",
            "field_splicing": False,
        },
        "adjustment_semantics": {
            "auto_adjust": False,
            "back_adjust": False,
            "repair": False,
            "source_native_close": "empirically split-adjusted on tested GPW split controls; cash-dividend-unadjusted",
            "adj_close": "empirically split- and cash-dividend-adjusted on tested controls",
            "volume": "generally split-adjusted on tested GPW controls; BLOOBER 2021-03-17 is a retained 10x source anomaly with repair=False",
            "scope_warning": "event semantics are evidence-bounded, not a universal Yahoo guarantee",
        },
        "validation": validation,
        "files": {},
        "api_warning": "Yahoo/yfinance is unofficial and is not treated as a stable production API.",
    }
    for path in (native_path, normalized_path, metadata_path):
        provenance["files"][path.name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    provenance["provenance_path"] = str(provenance_path)
    return provenance
