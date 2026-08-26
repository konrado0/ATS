"""Bounded Yahoo symbol-discovery probe for the GPW experiment."""

from __future__ import annotations

import json
from pathlib import Path

import yfinance as yf


CACHE = Path(r"D:\Stock\ATS\RESEARCH\.tmp\yfinance-cache")
CACHE.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(CACHE))

QUERIES = [
    "PLAY Communications Warsaw",
    "Orbis Warsaw stock",
    "BNP Paribas Bank Polska Warsaw",
    "Develia Warsaw",
    "Cyber_Folks Warsaw",
    "BRE Bank Warsaw",
    "mBank Warsaw",
    "BZ WBK Warsaw",
    "Santander Bank Polska Warsaw",
    "LiveChat Software Warsaw",
    "Text SA Warsaw",
    "Grupa LOTOS Warsaw",
    "PGNiG Warsaw",
    "CIECH Warsaw",
    "Comarch Warsaw",
    "Sunex Warsaw",
    "Bloober Team Warsaw",
    "Caspar Asset Management Warsaw",
]


def main() -> None:
    out: dict[str, object] = {}
    for query in QUERIES:
        try:
            search = yf.Search(query, max_results=20, news_count=0)
            out[query] = [
                {
                    key: quote.get(key)
                    for key in (
                        "symbol",
                        "shortname",
                        "longname",
                        "exchange",
                        "exchDisp",
                        "quoteType",
                    )
                }
                for quote in search.quotes
            ]
        except Exception as exc:  # evidence probe must retain per-query errors
            out[query] = {"error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
