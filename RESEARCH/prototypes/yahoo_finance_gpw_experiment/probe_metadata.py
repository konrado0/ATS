"""Inspect Yahoo chart metadata for the five target identities."""

from __future__ import annotations

import json
from pathlib import Path

import yfinance as yf


Path(r"D:\Stock\ATS\RESEARCH\.tmp\yfinance-cache").mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(r"D:\Stock\ATS\RESEARCH\.tmp\yfinance-cache")


def main() -> None:
    keys = (
        "currency", "symbol", "exchangeName", "fullExchangeName", "instrumentType",
        "firstTradeDate", "regularMarketTime", "gmtoffset", "timezone",
        "exchangeTimezoneName", "priceHint", "dataGranularity", "range",
    )
    output = {}
    for symbol in ("PLY.WA", "ORB.WA", "BNP.WA", "DVL.WA", "CBF.WA"):
        ticker = yf.Ticker(symbol)
        try:
            ticker.history(
                start="2014-01-01", end="2026-08-26", interval="1d",
                auto_adjust=False, back_adjust=False, repair=False, actions=True,
                keepna=True, timeout=20,
            )
            metadata = ticker.history_metadata
            output[symbol] = {key: metadata.get(key) for key in keys}
        except Exception as exc:
            output[symbol] = {"error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
