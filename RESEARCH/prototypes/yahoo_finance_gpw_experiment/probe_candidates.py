"""Probe bounded Yahoo ticker candidates without retaining histories."""

from __future__ import annotations

import json
from pathlib import Path

import yfinance as yf


CACHE = Path(r"D:\Stock\ATS\RESEARCH\.tmp\yfinance-cache")
CACHE.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(CACHE))

CANDIDATES = [
    "PLY.WA", "PLAY.WA", "ORB.WA", "ORBIS.WA",
    "BNP.WA", "BNPP.WA", "BGZ.WA",
    "DVL.WA", "LCC.WA", "CBF.WA", "R22.WA",
    "MBK.WA", "BRE.WA", "SPL.WA", "BZW.WA",
    "TXT.WA", "LVC.WA", "LTS.WA", "LOTOS.WA",
    "PGN.WA", "PGNIG.WA", "CIE.WA", "CMR.WA",
    "SNX.WA", "BLO.WA", "CSR.WA",
]


def main() -> None:
    yf.config.debug.hide_exceptions = False
    results: list[dict[str, object]] = []
    for symbol in CANDIDATES:
        row: dict[str, object] = {"symbol": symbol}
        try:
            history = yf.Ticker(symbol).history(
                start="2014-01-01",
                end="2026-08-27",
                interval="1d",
                auto_adjust=False,
                back_adjust=False,
                repair=False,
                actions=True,
                keepna=False,
                timeout=20,
            )
            row.update(
                rows=len(history),
                first=None if history.empty else str(history.index.min()),
                last=None if history.empty else str(history.index.max()),
                columns=list(history.columns),
                dividend_rows=(
                    0 if "Dividends" not in history else int((history["Dividends"] != 0).sum())
                ),
                split_rows=(
                    0 if "Stock Splits" not in history else int((history["Stock Splits"] != 0).sum())
                ),
            )
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        results.append(row)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
