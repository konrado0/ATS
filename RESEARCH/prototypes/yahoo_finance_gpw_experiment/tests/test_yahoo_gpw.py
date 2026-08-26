from __future__ import annotations

import pandas as pd

from yahoo_gpw import normalize_history, validate_normalized


def sample_native() -> pd.DataFrame:
    index = pd.DatetimeIndex(
        ["2021-03-17 00:00:00+01:00", "2021-03-18 00:00:00+01:00"],
        name="Date",
    )
    return pd.DataFrame(
        {
            "Open": [19.0, 19.5],
            "High": [20.0, 20.5],
            "Low": [18.5, 19.0],
            "Close": [19.34, 20.2],
            "Adj Close": [19.34, 20.2],
            "Volume": [22490, 78336],
            "Dividends": [0.0, 0.0],
            "Stock Splits": [0.0, 10.0],
        },
        index=index,
    )


def test_normalization_preserves_identity_dates_and_actions() -> None:
    normalized = normalize_history(
        sample_native(), symbol="BLO.WA", security="BLOOBER", isin="TEST"
    )
    assert normalized["session_date"].tolist() == ["2021-03-17", "2021-03-18"]
    assert normalized["stock_split"].tolist() == [0.0, 10.0]
    assert normalized["security"].unique().tolist() == ["BLOOBER"]
    assert normalized["isin"].unique().tolist() == ["TEST"]


def test_validation_accepts_valid_ohlcv() -> None:
    normalized = normalize_history(
        sample_native(), symbol="BLO.WA", security="BLOOBER", isin="TEST"
    )
    validation = validate_normalized(normalized)
    assert validation["valid"] is True
    assert validation["duplicate_dates"] == 0


def test_validation_rejects_duplicate_and_bad_high() -> None:
    normalized = normalize_history(
        sample_native(), symbol="BLO.WA", security="BLOOBER", isin="TEST"
    )
    normalized.loc[1, "session_date"] = normalized.loc[0, "session_date"]
    normalized.loc[1, "high"] = 18.0
    validation = validate_normalized(normalized)
    assert validation["valid"] is False
    assert validation["duplicate_dates"] == 1
    assert validation["invalid_high_rows"] == 1


def test_normalization_excludes_empty_calendar_placeholders() -> None:
    native = sample_native()
    native.loc[pd.Timestamp("2021-03-19 00:00:00+01:00")] = [
        float("nan"), float("nan"), float("nan"), float("nan"),
        float("nan"), 0, 0.0, 0.0,
    ]
    normalized = normalize_history(
        native, symbol="BLO.WA", security="BLOOBER", isin="TEST"
    )
    assert normalized["session_date"].tolist() == ["2021-03-17", "2021-03-18"]
