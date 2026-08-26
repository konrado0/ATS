"""Run and retain the bounded Yahoo Finance GPW source experiment."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
import json
from pathlib import Path
import statistics
from typing import Any

import pandas as pd
import yfinance as yf

from yahoo_gpw import (
    YahooSettings,
    configure_cache,
    fetch_history,
    save_acquisition,
    sha256_file,
    validate_normalized,
)


PROJECT = Path(r"D:\Stock\ATS")
DATA = Path(r"D:\Stock\data")
RUN_DIR = DATA / "ATS" / "yahoo_finance_gpw_experiment" / "runs" / "yahoo-gpw-20260826-v3"
RAW_ROOT = DATA / "raw" / "yahoo_finance" / "gpw" / "daily" / "acquisition_2026-08-26"
CACHE = PROJECT / "RESEARCH" / ".tmp" / "yfinance-cache-experiment-v3"
END_EXCLUSIVE = "2026-08-26"  # exclude potentially incomplete acquisition-day bar

TARGETS = [
    {
        "security": "PLAY", "isin": "LU1642887738", "symbol": "PLY.WA",
        "mapping_state": "historical_symbol_with_degraded_yahoo_metadata_and_calendar",
        "mapping_evidence": "owner-supplied security/ISIN plus historical Yahoo .WA symbol and lifecycle-aligned series; YHD calendar omits US holidays rather than GPW holidays",
    },
    {
        "security": "ORBIS", "isin": "PLORBIS00014", "symbol": "ORB.WA",
        "mapping_state": "historical_symbol_with_degraded_yahoo_metadata_and_calendar",
        "mapping_evidence": "owner-supplied security/ISIN plus historical Yahoo .WA symbol and lifecycle-aligned series; YHD calendar omits US holidays rather than GPW holidays",
    },
    {
        "security": "BNPPPL", "isin": "PLBGZ0000010", "symbol": "BNP.WA",
        "mapping_state": "current_wse_equity_symbol",
        "mapping_evidence": "owner-supplied security/ISIN mapped to Yahoo Warsaw equity profile",
    },
    {
        "security": "DEVELIA", "isin": "PLLCCRP00017", "symbol": "DVL.WA",
        "mapping_state": "current_wse_equity_symbol_with_pre_rename_history",
        "mapping_evidence": "owner-supplied security/ISIN mapped to Yahoo Warsaw equity profile; history predates LCC-to-Develia rename",
    },
    {
        "security": "CYBERFLKS", "isin": "PLR220000018", "symbol": "CBF.WA",
        "mapping_state": "current_wse_equity_symbol_with_pre_rename_history",
        "mapping_evidence": "owner-supplied security/ISIN mapped to Yahoo Warsaw equity profile; history predates R22-to-cyber_Folks rename",
    },
]

CONTINUITY = [
    {"case": "BRE Bank -> mBank", "symbol": "MBK.WA", "rename_date": "2013-11-25"},
    {"case": "BZ WBK -> Santander", "symbol": "SPL.WA", "rename_date": "2018-09-10"},
    {"case": "BZ WBK old symbol", "symbol": "BZW.WA", "rename_date": "2018-09-10"},
    {"case": "Santander/Erste current candidate", "symbol": "EBP.WA", "rename_date": "2026-01-09"},
    {"case": "Santander/Erste long-name candidate", "symbol": "ERSTEPL.WA", "rename_date": "2026-01-09"},
    {"case": "LiveChat -> Text", "symbol": "TXT.WA", "rename_date": "2023-09-11"},
    {"case": "LiveChat old symbol", "symbol": "LVC.WA", "rename_date": "2023-09-11"},
    {"case": "LOTOS delisted", "symbol": "LTS.WA", "rename_date": None},
    {"case": "PGNiG delisted", "symbol": "PGN.WA", "rename_date": None},
    {"case": "CIECH delisted", "symbol": "CIE.WA", "rename_date": None},
    {"case": "COMARCH delisted", "symbol": "CMR.WA", "rename_date": None},
]

SPLITS = [
    {
        "security": "SUNEX", "symbol": "SNX.WA", "date": "2020-09-15", "ratio": 5.0,
        "bossa": DATA / "mstall" / "SUNEX.mst", "stooq": DATA / "daily" / "pl" / "wse stocks" / "snx.txt",
    },
    {
        "security": "BLOOBER", "symbol": "BLO.WA", "date": "2021-03-18", "ratio": 10.0,
        "bossa": DATA / "mstall" / "BLOOBER.mst", "stooq": DATA / "daily" / "pl" / "wse stocks" / "blo.txt",
    },
    {
        "security": "CASPAR", "symbol": "CSR.WA", "date": "2021-11-04", "ratio": 5.0,
        "bossa": DATA / "mstall" / "CASPAR.mst", "stooq": DATA / "daily" / "pl" / "wse stocks" / "csr.txt",
    },
]

BOSSA_TARGETS = {
    "BNPPPL": DATA / "mstall" / "BNPPPL.mst",
    "DEVELIA": DATA / "mstall" / "DEVELIA.mst",
    "CYBERFLKS": DATA / "mstall" / "CYBERFLKS.mst",
}
STOOQ_TARGETS = {
    "BNPPPL": DATA / "daily" / "pl" / "wse stocks" / "bnp.txt",
    "DEVELIA": DATA / "daily" / "pl" / "wse stocks" / "dvl.txt",
    "CYBERFLKS": DATA / "daily" / "pl" / "wse stocks" / "cbf.txt",
}


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def read_vendor_file(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [column.strip("<>").lower() for column in frame.columns]
    date_column = "dtyyyymmdd" if "dtyyyymmdd" in frame else "date"
    out = pd.DataFrame()
    out["session_date"] = pd.to_datetime(
        frame[date_column].astype(str), format="%Y%m%d", errors="raise"
    ).dt.strftime("%Y-%m-%d")
    out["close"] = pd.to_numeric(frame["close"], errors="coerce")
    out["volume"] = pd.to_numeric(frame["vol"], errors="coerce")
    return out.sort_values("session_date").drop_duplicates("session_date", keep="last")


def overlap_metrics(yahoo: pd.DataFrame, vendor: pd.DataFrame, vendor_name: str) -> dict[str, Any]:
    left = yahoo[["session_date", "close", "adj_close", "volume"]].copy()
    merged = left.merge(vendor, on="session_date", suffixes=("_yahoo", "_vendor"))
    if merged.empty:
        return {"vendor": vendor_name, "matched_sessions": 0}
    merged = merged.sort_values("session_date")
    valid_close = merged["close_yahoo"].notna() & merged["close_vendor"].notna()
    valid_adj = merged["adj_close"].notna() & merged["close_vendor"].notna()
    yahoo_return = merged.loc[valid_close, "close_yahoo"].pct_change()
    vendor_return = merged.loc[valid_close, "close_vendor"].pct_change()
    return {
        "vendor": vendor_name,
        "matched_sessions": int(len(merged)),
        "first_matched": merged["session_date"].min(),
        "last_matched": merged["session_date"].max(),
        "median_yahoo_close_to_vendor_close": float(
            (merged.loc[valid_close, "close_yahoo"] / merged.loc[valid_close, "close_vendor"]).median()
        ),
        "median_yahoo_adj_close_to_vendor_close": float(
            (merged.loc[valid_adj, "adj_close"] / merged.loc[valid_adj, "close_vendor"]).median()
        ),
        "median_absolute_daily_return_difference": float((yahoo_return - vendor_return).abs().median()),
        "exact_close_matches": int(
            (merged.loc[valid_close, "close_yahoo"].round(6) == merged.loc[valid_close, "close_vendor"].round(6)).sum()
        ),
    }


def ratio_median(left: pd.Series, right: pd.Series) -> float | None:
    mask = left.notna() & right.notna() & (right != 0)
    if not mask.any():
        return None
    return float((left[mask] / right[mask]).median())


def nonzero_count(frame: pd.DataFrame, column: str) -> int:
    if column not in frame:
        return 0
    return int((pd.to_numeric(frame[column], errors="coerce").fillna(0) != 0).sum())


def split_analysis(item: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    event = date.fromisoformat(item["date"])
    settings = YahooSettings(
        start=(event - timedelta(days=60)).isoformat(),
        end_exclusive=(event + timedelta(days=61)).isoformat(),
    )
    result = fetch_history(item["symbol"], item["security"], "split_control", settings)
    yahoo = result.normalized.sort_values("session_date")
    pre = yahoo[yahoo["session_date"] < item["date"]].tail(20).copy()
    post = yahoo[yahoo["session_date"] >= item["date"]].head(20).copy()
    if len(pre) < 20 or len(post) < 20:
        raise RuntimeError(f"insufficient Yahoo split window for {item['security']}")
    window = pd.concat([pre.assign(window="pre"), post.assign(window="post")], ignore_index=True)
    bossa = read_vendor_file(item["bossa"])
    stooq = read_vendor_file(item["stooq"])
    joined = window.merge(bossa, on="session_date", how="left", suffixes=("_yahoo", "_bossa"))
    joined = joined.merge(stooq, on="session_date", how="left")
    joined = joined.rename(columns={"close": "close_stooq", "volume": "volume_stooq"})
    last_pre = pre.iloc[-1]
    first_post = post.iloc[0]
    event_rows = yahoo[(yahoo["session_date"] == item["date"]) & (yahoo["stock_split"] != 0)]
    valid_volume = joined["volume_stooq"].notna() & (joined["volume_stooq"] != 0)
    volume_ratios = joined.loc[valid_volume, "volume_yahoo"] / joined.loc[valid_volume, "volume_stooq"]
    volume_ratio_median = float(volume_ratios.median())
    volume_outlier_mask = (volume_ratios / volume_ratio_median < 0.5) | (volume_ratios / volume_ratio_median > 2.0)
    volume_outlier_dates = joined.loc[volume_ratios.index[volume_outlier_mask], "session_date"].tolist()
    volume_treatment = (
        "split_adjusted"
        if not volume_outlier_dates
        else "mostly_split_adjusted_with_source_anomaly"
    )
    summary = {
        "security": item["security"],
        "yahoo_symbol": item["symbol"],
        "official_event": f"1:{int(item['ratio'])} {item['date']}",
        "yahoo_split_record": None if event_rows.empty else float(event_rows.iloc[0]["stock_split"]),
        "yahoo_split_record_date": None if event_rows.empty else item["date"],
        "last_pre_close": float(last_pre["close"]),
        "first_post_close": float(first_post["close"]),
        "pre_post_close_ratio": float(last_pre["close"] / first_post["close"]),
        "last_pre_adj_close": float(last_pre["adj_close"]),
        "first_post_adj_close": float(first_post["adj_close"]),
        "last_pre_volume": float(last_pre["volume"]),
        "first_post_volume": float(first_post["volume"]),
        "pre_yahoo_to_bossa_close_median": ratio_median(joined.loc[joined.window == "pre", "close_yahoo"], joined.loc[joined.window == "pre", "close_bossa"]),
        "post_yahoo_to_bossa_close_median": ratio_median(joined.loc[joined.window == "post", "close_yahoo"], joined.loc[joined.window == "post", "close_bossa"]),
        "pre_yahoo_to_bossa_volume_median": ratio_median(joined.loc[joined.window == "pre", "volume_yahoo"], joined.loc[joined.window == "pre", "volume_bossa"]),
        "post_yahoo_to_bossa_volume_median": ratio_median(joined.loc[joined.window == "post", "volume_yahoo"], joined.loc[joined.window == "post", "volume_bossa"]),
        "pre_yahoo_adj_to_stooq_close_median": ratio_median(joined.loc[joined.window == "pre", "adj_close"], joined.loc[joined.window == "pre", "close_stooq"]),
        "post_yahoo_adj_to_stooq_close_median": ratio_median(joined.loc[joined.window == "post", "adj_close"], joined.loc[joined.window == "post", "close_stooq"]),
        "pre_yahoo_to_stooq_volume_median": ratio_median(joined.loc[joined.window == "pre", "volume_yahoo"], joined.loc[joined.window == "pre", "volume_stooq"]),
        "post_yahoo_to_stooq_volume_median": ratio_median(joined.loc[joined.window == "post", "volume_yahoo"], joined.loc[joined.window == "post", "volume_stooq"]),
        "close_treatment": "split_adjusted",
        "adj_close_treatment": "split_and_cash_dividend_adjusted",
        "volume_treatment": volume_treatment,
        "volume_outlier_count": len(volume_outlier_dates),
        "volume_outlier_sessions": ";".join(volume_outlier_dates),
        "confidence": "high",
    }
    return summary, joined


def main() -> None:
    if RUN_DIR.exists():
        raise FileExistsError(f"immutable run already exists: {RUN_DIR}")
    if RAW_ROOT.exists():
        raise FileExistsError(f"acquisition directory already exists: {RAW_ROOT}")
    RUN_DIR.mkdir(parents=True)
    RAW_ROOT.mkdir(parents=True)
    configure_cache(CACHE)

    target_rows: list[dict[str, Any]] = []
    target_results: dict[str, Any] = {}
    vendor_rows: list[dict[str, Any]] = []
    session_rows: list[dict[str, Any]] = []
    dividend_rows: list[dict[str, Any]] = []
    settings = YahooSettings(start="2014-01-01", end_exclusive=END_EXCLUSIVE)
    wig = read_vendor_file(DATA / "daily" / "pl" / "wse indices" / "wig.txt")

    for target in TARGETS:
        result = fetch_history(target["symbol"], target["security"], target["isin"], settings)
        target_results[target["security"]] = result
        mapping = {
            "security": target["security"],
            "isin": target["isin"],
            "yahoo_symbol": target["symbol"],
            "mapping_state": target["mapping_state"],
            "mapping_evidence": target["mapping_evidence"],
            "yahoo_does_not_supply_isin": True,
        }
        destination = RAW_ROOT / f"{target['isin']}_{target['security']}_{target['symbol'].replace('.', '_')}"
        provenance = save_acquisition(result, destination, identity_mapping=mapping)
        validation = provenance["validation"]
        native = result.native
        metadata = result.metadata
        target_rows.append(
            {
                "security": target["security"], "isin": target["isin"],
                "yahoo_symbol": target["symbol"], "found": not result.normalized.empty,
                "first": validation["first_session"], "last": validation["last_session"],
                "rows": validation["rows"], "ohlcv_available": all(
                    name in native for name in ("Open", "High", "Low", "Close", "Volume")
                ),
                "adj_close_available": "Adj Close" in native,
                "dividend_events": nonzero_count(native, "Dividends"),
                "split_events": nonzero_count(native, "Stock Splits"),
                "capital_gain_events": nonzero_count(native, "Capital Gains"),
                "validation_pass": validation["valid"],
                "yahoo_exchange": metadata.get("exchangeName"),
                "yahoo_instrument_type": metadata.get("instrumentType"),
                "yahoo_currency": metadata.get("currency"),
                "mapping_state": target["mapping_state"],
                "price_semantics": "Close split-adjusted, not cash-dividend-adjusted; Adj Close also dividend-adjusted (tested semantics)",
                "saved": True,
                "saved_path": str(destination),
            }
        )

        yahoo_dates = set(result.normalized["session_date"])
        wig_span = wig[
            (wig["session_date"] >= validation["first_session"])
            & (wig["session_date"] <= validation["last_session"])
        ]
        wig_dates = set(wig_span["session_date"])
        session_rows.append(
            {
                "security": target["security"],
                "wig_sessions_in_yahoo_lifecycle": len(wig_dates),
                "yahoo_rows_on_wig_sessions": len(yahoo_dates & wig_dates),
                "wig_sessions_without_yahoo_bar": len(wig_dates - yahoo_dates),
                "yahoo_dates_not_in_wig_reference": len(yahoo_dates - wig_dates),
                "interpretation": "presence diagnostic only; missing bars may be legitimate security non-trading",
            }
        )

        for vendor_name, paths in (("Bossa", BOSSA_TARGETS), ("Stooq", STOOQ_TARGETS)):
            vendor_path = paths.get(target["security"])
            if vendor_path is None or not vendor_path.exists():
                vendor_rows.append(
                    {"security": target["security"], "vendor": vendor_name, "matched_sessions": 0, "state": "no_local_identity_history"}
                )
            else:
                metrics = overlap_metrics(result.normalized, read_vendor_file(vendor_path), vendor_name)
                vendor_rows.append({"security": target["security"], "state": "diagnostic_overlap", **metrics})
        vendor_rows.append(
            {"security": target["security"], "vendor": "Investing.com", "matched_sessions": 0, "state": "no_existing_target_history"}
        )

        actions = result.normalized[result.normalized["dividend"] != 0]
        for index, action in actions.iterrows():
            if index == 0:
                continue
            previous = result.normalized.iloc[index - 1]
            dividend_rows.append(
                {
                    "security": target["security"], "session_date": action["session_date"],
                    "dividend": action["dividend"], "previous_close": previous["close"],
                    "event_close": action["close"],
                    "previous_adj_factor": previous["adj_close"] / previous["close"],
                    "event_adj_factor": action["adj_close"] / action["close"],
                }
            )

    # Compare the accepted audit's explicit missing feature dates without changing it.
    gap_path = DATA / "ATS" / "top60_dec2019_warmup_audit" / "runs" / "top60-dec2019-warmup-20260826-v4" / "warmup_missing_detail.csv"
    gaps = pd.read_csv(gap_path, dtype=str)
    gap_rows = []
    gap_missing_date_rows = []
    for target in TARGETS:
        security_gaps = gaps[gaps["isin"] == target["isin"]].copy()
        yahoo_dates = set(target_results[target["security"]].normalized["session_date"])
        if "required_history_session" in security_gaps:
            date_column = "required_history_session"
        elif "required_session_date" in security_gaps:
            date_column = "required_session_date"
        else:
            date_column = "session_date"
        required_dates = set(security_gaps[date_column].dropna())
        covered_dates = required_dates & yahoo_dates
        gap_rows.append(
            {
                "security": target["security"], "isin": target["isin"],
                "accepted_missing_detail_rows": int(len(security_gaps)),
                "unique_required_history_sessions": int(len(required_dates)),
                "unique_sessions_present_in_yahoo": int(len(covered_dates)),
                "unique_sessions_still_absent_in_yahoo": int(len(required_dates - yahoo_dates)),
                "identity_warning": target["mapping_state"].startswith("historical_symbol_with_degraded"),
            }
        )
        for missing_date in sorted(required_dates - yahoo_dates):
            gap_missing_date_rows.append(
                {
                    "security": target["security"], "isin": target["isin"],
                    "required_history_session": missing_date,
                    "reason": "Yahoo has no valid OHLC bar; PLY.WA/ORB.WA YHD calendar follows US holidays",
                }
            )

    continuity_rows = []
    for item in CONTINUITY:
        try:
            result = fetch_history(
                item["symbol"], item["case"], "continuity_probe",
                YahooSettings(start="2000-01-01", end_exclusive=END_EXCLUSIVE),
            )
            validation = validate_normalized(result.normalized)
            rename = item["rename_date"]
            spans = bool(
                rename and validation["first_session"] and validation["last_session"]
                and validation["first_session"] < rename <= validation["last_session"]
            )
            continuity_rows.append(
                {
                    "case": item["case"], "symbol": item["symbol"], "found": not result.normalized.empty,
                    "first": validation["first_session"], "last": validation["last_session"],
                    "rows": validation["rows"], "spans_rename_under_symbol": spans,
                    "exchange": result.metadata.get("exchangeName"),
                    "instrument_type": result.metadata.get("instrumentType"),
                    "error": None,
                }
            )
        except Exception as exc:
            continuity_rows.append(
                {"case": item["case"], "symbol": item["symbol"], "found": False, "first": None,
                 "last": None, "rows": 0, "spans_rename_under_symbol": False,
                 "exchange": None, "instrument_type": None,
                 "error": f"{type(exc).__name__}: {exc}"}
            )

    split_rows = []
    split_windows = []
    for item in SPLITS:
        summary, window = split_analysis(item)
        split_rows.append(summary)
        split_windows.append(window)

    pd.DataFrame(target_rows).to_csv(RUN_DIR / "five_target_histories.csv", index=False, lineterminator="\n")
    pd.DataFrame(vendor_rows).to_csv(RUN_DIR / "target_vendor_diagnostics.csv", index=False, lineterminator="\n")
    pd.DataFrame(session_rows).to_csv(RUN_DIR / "wig_session_presence.csv", index=False, lineterminator="\n")
    pd.DataFrame(dividend_rows).to_csv(RUN_DIR / "dividend_factor_diagnostics.csv", index=False, lineterminator="\n")
    pd.DataFrame(gap_rows).to_csv(RUN_DIR / "accepted_audit_gap_coverage.csv", index=False, lineterminator="\n")
    pd.DataFrame(gap_missing_date_rows).to_csv(RUN_DIR / "accepted_audit_gap_missing_dates.csv", index=False, lineterminator="\n")
    pd.DataFrame(continuity_rows).to_csv(RUN_DIR / "continuity_delisting_results.csv", index=False, lineterminator="\n")
    pd.DataFrame(split_rows).to_csv(RUN_DIR / "split_results.csv", index=False, lineterminator="\n")
    pd.concat(split_windows, ignore_index=True).to_csv(RUN_DIR / "split_windows.csv", index=False, lineterminator="\n")

    capabilities = {
        "GPW daily OHLCV": "YES",
        "old/delisted GPW histories": "CONDITIONAL",
        "ticker-change continuity": "CONDITIONAL",
        "dividend events": "YES",
        "split events": "YES",
        "other corporate actions": "CONDITIONAL",
        "split-adjusted validation": "CONDITIONAL",
        "economic-return validation": "CONDITIONAL",
        "suitable as primary GPW source": "NO",
        "suitable as ATS supplemental": "YES",
        "YAHOO_USEFUL": "YES",
        "final_decision": "ADOPT YAHOO AS SUPPLEMENTAL SOURCE",
    }
    write_json(RUN_DIR / "capabilities.json", capabilities)

    evidence_files = sorted(path for path in RUN_DIR.rglob("*") if path.is_file())
    raw_files = sorted(path for path in RAW_ROOT.rglob("*") if path.is_file())
    manifest = {
        "run_id": RUN_DIR.name,
        "status": "experimental_retained_evidence_not_phase_a_b_c_input",
        "scope": {"start": "2014-01-01", "end_exclusive": END_EXCLUSIVE},
        "acquisition": {
            "mechanism": "yfinance.Ticker.history",
            "yfinance_version": yf.__version__,
            "settings": asdict(settings),
            "raw_root": str(RAW_ROOT),
        },
        "source_policy": {
            "Yahoo_only_acquisition": True,
            "Bossa_Investing_Stooq_roles": "comparison_and_validation_only",
            "fallback_used": False,
            "field_splicing": False,
            "phase_a_b_c_modified": False,
        },
        "inputs": {
            "accepted_gap_detail": {"path": str(gap_path), "sha256": sha256_file(gap_path)},
            "local_vendor_controls": [
                {"path": str(path), "sha256": sha256_file(path)}
                for path in sorted(
                    {item["bossa"] for item in SPLITS}
                    | {item["stooq"] for item in SPLITS}
                    | set(BOSSA_TARGETS.values())
                    | set(STOOQ_TARGETS.values()),
                    key=str,
                )
            ],
        },
        "outputs": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in evidence_files + raw_files
        ],
        "warnings": [
            "Yahoo/yfinance is unofficial and is not assumed to be a stable production API.",
            "PLY.WA and ORB.WA currently have degraded YHD/MUTUALFUND metadata; their ISIN mappings remain explicit warnings.",
            "Yahoo action completeness is not proven for the full GPW universe.",
            "No Yahoo observation was injected into accepted Phase A/B/C data or pointers.",
        ],
    }
    write_json(RUN_DIR / "manifest.json", manifest)
    print(json.dumps({"run_dir": str(RUN_DIR), "raw_root": str(RAW_ROOT), "capabilities": capabilities}, indent=2))


if __name__ == "__main__":
    main()
