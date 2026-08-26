from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from ats_research.gpw_coverage import expected_trading_coverage_counts
from ats_research.gpw_membership import validate_membership_assertion
from ats_research.investing_manual import parse_investing_manual_history


COMPLETE_PIT_START = pd.Timestamp("2019-12-23")
DEFAULT_ENDPOINT = pd.Timestamp("2026-08-18")
LOOKBACK_SESSIONS = 252
PRICE_COLUMNS = ("open", "high", "low", "close")
RESOLVED_STOOQ_STATES = {"exact", "mapped_renamed", "mapped_successor"}
ACCEPTED_YAHOO_SUPPLEMENTS = {
    "PLBGZ0000010": "PLBGZ0000010_BNPPPL_BNP_WA",
    "PLLCCRP00017": "PLLCCRP00017_DEVELIA_DVL_WA",
    "PLR220000018": "PLR220000018_CYBERFLKS_CBF_WA",
}
TARGETED_YAHOO_VALIDATION = {
    "LU1642887738": ("ply.txt", "LU1642887738_PLAY_PLY_WA"),
    "PLORBIS00014": ("orbp.txt", "PLORBIS00014_ORBIS_ORB_WA"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_ohlcv(frame: pd.DataFrame) -> pd.Series:
    return ~(
        frame[list(PRICE_COLUMNS)].isna().any(axis=1)
        | frame[list(PRICE_COLUMNS)].le(0).any(axis=1)
        | frame["volume"].isna()
        | frame["volume"].lt(0)
        | frame["high"].lt(frame[["open", "close", "low"]].max(axis=1))
        | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1))
        | frame["session_date"].duplicated(keep=False)
    )


def read_bossa_file(path: Path, expected_ticker: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(value).strip("<>").lower() for value in frame.columns]
    required = {"ticker", "dtyyyymmdd", *PRICE_COLUMNS, "vol"}
    if not required.issubset(frame.columns) or len(frame.columns) not in (7, 8):
        raise ValueError(f"{path}: unsupported Bossa schema {list(frame.columns)}")
    tickers = set(frame["ticker"].astype(str).str.upper().unique())
    if tickers != {expected_ticker}:
        raise ValueError(f"{path}: expected Bossa ticker {expected_ticker}, got {sorted(tickers)}")
    frame["session_date"] = pd.to_datetime(
        frame["dtyyyymmdd"].astype(str), format="%Y%m%d", errors="raise"
    )
    frame = frame.rename(columns={"vol": "volume"})[
        ["session_date", *PRICE_COLUMNS, "volume"]
    ]
    for column in (*PRICE_COLUMNS, "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    valid = valid_ohlcv(frame)
    if (~valid).any():
        sample = frame.loc[~valid].head().to_dict("records")
        raise ValueError(f"{path}: invalid Bossa rows {sample}")
    return frame.sort_values("session_date").reset_index(drop=True)


def read_stooq_file(path: Path, expected_symbol: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(value).strip("<>").lower() for value in frame.columns]
    required = {"ticker", "per", "date", "time", *PRICE_COLUMNS, "vol"}
    if not required.issubset(frame.columns):
        raise ValueError(f"{path}: unsupported Stooq schema {list(frame.columns)}")
    symbols = set(frame["ticker"].astype(str).str.upper().unique())
    periods = set(frame["per"].astype(str).str.upper().unique())
    if symbols != {expected_symbol} or periods != {"D"}:
        raise ValueError(f"{path}: unexpected Stooq identity {symbols}/{periods}")
    frame["session_date"] = pd.to_datetime(
        frame["date"].astype(str), format="%Y%m%d", errors="raise"
    )
    frame = frame.rename(columns={"vol": "volume"})[
        ["session_date", *PRICE_COLUMNS, "volume"]
    ]
    for column in (*PRICE_COLUMNS, "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    valid = valid_ohlcv(frame)
    if (~valid).any():
        sample = frame.loc[~valid].head().to_dict("records")
        raise ValueError(f"{path}: invalid Stooq rows {sample}")
    return frame.sort_values("session_date").reset_index(drop=True)


def load_wig_sessions(data_root: Path, endpoint: pd.Timestamp) -> pd.DatetimeIndex:
    path = data_root / "daily" / "pl" / "wse indices" / "wig.txt"
    frame = pd.read_csv(path)
    frame.columns = [str(value).strip("<>").lower() for value in frame.columns]
    frame["session_date"] = pd.to_datetime(
        frame["date"].astype(str), format="%Y%m%d", errors="raise"
    )
    sessions = pd.DatetimeIndex(
        frame.loc[frame["session_date"].le(endpoint), "session_date"]
        .drop_duplicates()
        .sort_values()
    )
    if COMPLETE_PIT_START not in sessions:
        raise ValueError(f"{COMPLETE_PIT_START.date()} is not a WIG session")
    start_position = int(sessions.get_loc(COMPLETE_PIT_START))
    if start_position < LOOKBACK_SESSIONS:
        raise ValueError("WIG calendar does not contain the required 252 prior sessions")
    return sessions


def membership_intervals(reference_root: Path, endpoint: pd.Timestamp) -> pd.DataFrame:
    manifest = pd.read_csv(reference_root / "manifest.csv")
    manifest["effective_date"] = pd.to_datetime(manifest["effective_date"])
    frames: list[pd.DataFrame] = []
    for component in ("WIG20", "mWIG40"):
        files = sorted((reference_root / "snapshots" / component).glob("*.csv"), key=lambda p: p.stem)
        dated = [(pd.Timestamp(path.stem), path) for path in files]
        for position, (effective_from, path) in enumerate(dated):
            effective_to = (
                dated[position + 1][0] - pd.Timedelta(days=1)
                if position + 1 < len(dated)
                else pd.Timestamp("2262-04-11")
            )
            if effective_to < COMPLETE_PIT_START or effective_from > endpoint:
                continue
            meta = manifest.loc[
                manifest["index"].eq(component)
                & manifest["effective_date"].eq(effective_from)
            ]
            if len(meta) != 1:
                raise ValueError(f"missing or duplicate membership manifest row for {path}")
            frame = pd.read_csv(path)
            if len(frame) != (20 if component == "WIG20" else 40):
                raise ValueError(f"{path}: incomplete official portfolio")
            frame["effective_from"] = effective_from
            frame["effective_to"] = effective_to
            frame["source_index"] = component
            frame["source_id"] = str(meta.iloc[0]["source_id"])
            frame["source_path"] = str(path.resolve())
            frames.append(frame)
    result = pd.concat(frames, ignore_index=True)
    if result.duplicated(["source_index", "effective_from", "isin"]).any():
        raise ValueError("duplicate official membership semantic keys")
    return result.sort_values(["effective_from", "source_index", "isin"]).reset_index(drop=True)


def build_official_grid(
    intervals: pd.DataFrame, sessions: pd.DatetimeIndex, endpoint: pd.Timestamp
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    evaluation_sessions = sessions[
        (sessions >= COMPLETE_PIT_START) & (sessions <= endpoint)
    ]
    for session in evaluation_sessions:
        current = intervals.loc[
            intervals["effective_from"].le(session)
            & intervals["effective_to"].ge(session)
        ].copy()
        if len(current) != 60 or current["isin"].nunique() != 60:
            raise ValueError(
                f"TOP60 denominator failure on {session.date()}: "
                f"rows={len(current)}, unique={current['isin'].nunique()}"
            )
        current["session_date"] = session
        rows.append(current)
    grid = pd.concat(rows, ignore_index=True)
    if grid.duplicated(["isin", "session_date"]).any():
        raise ValueError("duplicate official member-session rows")
    return grid.sort_values(["session_date", "source_index", "isin"]).reset_index(drop=True)


def choose_bossa_mapping(
    grid: pd.DataFrame, symbol_map: pd.DataFrame, bossa_root: Path
) -> pd.DataFrame:
    files = {path.stem.upper(): path.resolve() for path in bossa_root.glob("*.mst")}
    rows: list[dict[str, Any]] = []
    for isin, group in grid.groupby("isin", sort=True):
        exact_aliases = set(
            symbol_map.loc[
                symbol_map["isin"].eq(isin) & symbol_map["status"].eq("exact"),
                "company_name",
            ]
            .dropna()
            .astype(str)
            .str.upper()
        )
        member_aliases = set(group["company_name"].dropna().astype(str).str.upper())
        exact_matches = sorted(exact_aliases.intersection(files))
        member_matches = sorted(member_aliases.intersection(files))
        if len(exact_matches) == 1:
            selected = exact_matches[0]
            state = "exact_symbol_map_alias"
        elif len(exact_matches) > 1:
            selected = None
            state = "unresolved_multiple_exact_alias_files"
        elif len(member_matches) == 1:
            selected = member_matches[0]
            state = "exact_pit_official_short_name"
        elif len(member_matches) > 1:
            selected = None
            state = "unresolved_multiple_pit_alias_files"
        else:
            selected = None
            state = "no_bossa_file_for_resolved_identity"
        rows.append(
            {
                "isin": isin,
                "company_names": "|".join(sorted(member_aliases)),
                "bossa_mapping_state": state,
                "bossa_ticker": selected,
                "bossa_file": str(files[selected]) if selected else None,
            }
        )
    result = pd.DataFrame(rows)
    selected = result["bossa_ticker"].dropna()
    if selected.duplicated().any():
        raise ValueError("one Bossa file maps to multiple identities")
    return result


def load_bossa_dates(
    mapping: pd.DataFrame, history_floor: pd.Timestamp, endpoint: pd.Timestamp
) -> tuple[dict[str, set[pd.Timestamp]], list[dict[str, Any]]]:
    dates: dict[str, set[pd.Timestamp]] = {}
    inputs: list[dict[str, Any]] = []
    for row in mapping.loc[mapping["bossa_file"].notna()].itertuples(index=False):
        path = Path(row.bossa_file)
        frame = read_bossa_file(path, str(row.bossa_ticker))
        frame = frame.loc[frame["session_date"].between(history_floor, endpoint)]
        dates[str(row.isin)] = set(frame["session_date"])
        inputs.append(
            {
                "isin": str(row.isin),
                "ticker": str(row.bossa_ticker),
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "rows_in_contract_window": len(frame),
            }
        )
    return dates, inputs


def load_bossa_session_supplements(
    root: Path, grid: pd.DataFrame, symbol_map: pd.DataFrame
) -> tuple[dict[str, set[pd.Timestamp]], list[dict[str, Any]]]:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[pd.DataFrame] = []
    inputs: list[dict[str, Any]] = []
    for item in manifest["outputs"]:
        if not str(item["filename"]).endswith(".mst"):
            continue
        path = root / str(item["filename"])
        if path.stat().st_size != int(item["byte_length"]) or sha256(path) != str(item["sha256"]):
            raise ValueError(f"Bossa session supplement manifest mismatch: {path}")
        frame = pd.read_csv(path)
        frame.columns = [str(value).strip("<>").lower() for value in frame.columns]
        frame["session_date"] = pd.to_datetime(
            frame["dtyyyymmdd"].astype(str), format="%Y%m%d", errors="raise"
        )
        frame["page_ticker"] = frame["ticker"].astype(str).str.upper()
        rows.append(frame[["session_date", "page_ticker"]])
        inputs.append(
            {
                "path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "rows": len(frame),
            }
        )
    pages = pd.concat(rows, ignore_index=True)
    source_manifest_path = Path(str(manifest["source_manifest"]["path"]))
    if sha256(source_manifest_path) != str(manifest["source_manifest"]["sha256"]):
        raise ValueError("Bossa source-page manifest hash mismatch")
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    identity_rows: list[dict[str, Any]] = []
    marker = "Pokaż transakcje "
    for item in source_manifest["files"]:
        path = source_manifest_path.parent / str(item["filename"])
        if path.stat().st_size != int(item["byte_length"]) or sha256(path) != str(item["sha256"]):
            raise ValueError(f"Bossa source-page hash mismatch: {path}")
        session_date = pd.Timestamp(str(item["session_date"]))
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        for position, line in enumerate(lines):
            if not line.startswith(marker):
                continue
            company_name = line[len(marker) :].strip().upper()
            if position + 2 >= len(lines):
                raise ValueError(f"truncated Bossa source-page identity block: {path}")
            chart = re.fullmatch(r"(\S+) Wykres (.+)", lines[position + 2].strip())
            if chart is None or chart.group(2).strip().upper() != company_name:
                raise ValueError(f"invalid Bossa source-page identity block: {path}")
            identity_rows.append(
                {
                    "session_date": session_date,
                    "page_company_name": company_name,
                    "page_ticker": chart.group(1).upper(),
                }
            )
        inputs.append(
            {
                "path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "role": "source_page_identity_evidence",
            }
        )
    identity_pages = pd.DataFrame(identity_rows)
    if identity_pages.duplicated(["session_date", "page_ticker"]).any():
        raise ValueError("duplicate Bossa source-page ticker/session identities")
    materialized_keys = pages[["session_date", "page_ticker"]].drop_duplicates()
    if not materialized_keys.merge(
        identity_pages[["session_date", "page_ticker"]],
        on=["session_date", "page_ticker"],
        how="left",
        indicator=True,
    )["_merge"].eq("both").all():
        raise ValueError("materialized Bossa session bars do not reconcile to source-page identities")
    # Identity rows for explicit '-' page records are intentionally excluded:
    # only identities that also have a materialized valid bar can supplement.
    identity_pages = identity_pages.merge(
        materialized_keys,
        on=["session_date", "page_ticker"],
        how="inner",
        validate="one_to_one",
    )
    resolved_symbols = symbol_map.loc[
        symbol_map["status"].isin(RESOLVED_STOOQ_STATES),
        ["isin", "stooq_symbol"],
    ].dropna()
    symbol_aliases = (
        resolved_symbols.groupby("isin")["stooq_symbol"]
        .agg(lambda values: set(map(lambda value: str(value).upper(), values)))
        .to_dict()
    )
    result: dict[str, set[pd.Timestamp]] = {}
    # Map the complete session pages to every identity that appears anywhere in
    # the audit interval. A future member can need a page date in its 252-session
    # pre-membership history even when it was not itself an official member on
    # that page date.
    for isin, group in grid.groupby("isin", sort=True):
        candidates = set(group["company_name"].dropna().astype(str).str.upper())
        candidates |= symbol_aliases.get(str(isin), set())
        match = identity_pages.loc[
            identity_pages["page_ticker"].isin(candidates)
            | identity_pages["page_company_name"].isin(candidates)
        ]
        if match["session_date"].duplicated().any():
            raise ValueError(f"multiple Bossa page matches for {isin} on one session")
        if not match.empty:
            result[str(isin)] = set(match["session_date"])
    return result, inputs


def load_investing_dates(
    root: Path, history_floor: pd.Timestamp, endpoint: pd.Timestamp
) -> tuple[
    dict[str, set[pd.Timestamp]],
    dict[str, set[pd.Timestamp]],
    list[dict[str, Any]],
]:
    manifest_path = root / "reference_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dates: dict[str, set[pd.Timestamp]] = {}
    missing_volume_dates: dict[str, set[pd.Timestamp]] = {}
    inputs: list[dict[str, Any]] = []
    for item in manifest["files"]:
        path = root / str(item["filename"])
        actual_hash = sha256(path)
        if path.stat().st_size != int(item["byte_length"]) or actual_hash != str(item["sha256"]):
            raise ValueError(f"Investing manifest mismatch: {path}")
        parsed = parse_investing_manual_history(
            path,
            allow_missing_display_volume=True,
            allow_dot_thousands_in_prices=True,
        )
        valid_dates = set(
            parsed.bars.loc[
                parsed.bars["session_date"].between(history_floor, endpoint),
                "session_date",
            ]
        )
        missing_volume = set(
            parsed.bars.loc[
                parsed.bars["session_date"].between(history_floor, endpoint)
                & parsed.bars["volume"].isna(),
                "session_date",
            ]
        )
        isin = str(item["isin"])
        dates.setdefault(isin, set()).update(valid_dates)
        missing_volume_dates.setdefault(isin, set()).update(missing_volume)
        inputs.append(
            {
                "isin": isin,
                "path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": actual_hash,
                "rows_in_contract_window": len(valid_dates),
                "missing_display_volume_rows_in_contract_window": len(missing_volume),
                "missing_display_volume_dates": sorted(
                    str(value.date()) for value in missing_volume
                ),
                "role": str(item["role"]),
            }
        )
    return dates, missing_volume_dates, inputs


def load_yahoo_dates(
    root: Path, history_floor: pd.Timestamp, endpoint: pd.Timestamp
) -> tuple[dict[str, set[pd.Timestamp]], list[dict[str, Any]]]:
    dates: dict[str, set[pd.Timestamp]] = {}
    inputs: list[dict[str, Any]] = []
    for isin, folder in sorted(ACCEPTED_YAHOO_SUPPLEMENTS.items()):
        target = root / folder
        provenance_path = target / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        identity = provenance["identity_mapping"]
        validation = provenance["validation"]
        if str(identity["isin"]) != isin or not bool(validation["valid"]):
            raise ValueError(f"Yahoo identity or validation mismatch: {target}")
        normalized = target / "normalized_daily.csv"
        expected = provenance["files"]["normalized_daily.csv"]
        if (
            normalized.stat().st_size != int(expected["bytes"])
            or sha256(normalized).upper() != str(expected["sha256"]).upper()
        ):
            raise ValueError(f"Yahoo normalized-history hash mismatch: {normalized}")
        frame = pd.read_csv(normalized)
        frame["session_date"] = pd.to_datetime(frame["session_date"], errors="raise")
        frame = frame.loc[frame["session_date"].between(history_floor, endpoint)].copy()
        for column in (*PRICE_COLUMNS, "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        valid = valid_ohlcv(frame[["session_date", *PRICE_COLUMNS, "volume"]])
        if (~valid).any():
            raise ValueError(f"Yahoo invalid normalized rows: {normalized}")
        dates[isin] = set(frame["session_date"])
        inputs.append(
            {
                "isin": isin,
                "folder": str(target.resolve()),
                "mapping_state": str(identity["mapping_state"]),
                "provenance_path": str(provenance_path.resolve()),
                "provenance_sha256": sha256(provenance_path),
                "normalized_path": str(normalized.resolve()),
                "normalized_bytes": normalized.stat().st_size,
                "normalized_sha256": sha256(normalized),
                "rows_in_contract_window": len(frame),
                "role": "accepted_clean_yahoo_wse_history_supplement",
            }
        )
    return dates, inputs


def validate_targeted_investing_yahoo(
    investing_root: Path,
    yahoo_root: Path,
    wig_sessions: pd.DatetimeIndex,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metrics: dict[str, Any] = {}
    inputs: list[dict[str, Any]] = []
    wig_dates = set(map(pd.Timestamp, wig_sessions))
    for isin, (investing_filename, yahoo_folder) in sorted(
        TARGETED_YAHOO_VALIDATION.items()
    ):
        investing_path = investing_root / investing_filename
        investing = parse_investing_manual_history(
            investing_path,
            allow_missing_display_volume=True,
            allow_dot_thousands_in_prices=True,
        ).bars
        target = yahoo_root / yahoo_folder
        provenance_path = target / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        if str(provenance["identity_mapping"]["isin"]) != isin:
            raise ValueError(f"targeted Yahoo validation identity mismatch: {target}")
        yahoo_path = target / "normalized_daily.csv"
        expected = provenance["files"]["normalized_daily.csv"]
        if (
            yahoo_path.stat().st_size != int(expected["bytes"])
            or sha256(yahoo_path).upper() != str(expected["sha256"]).upper()
        ):
            raise ValueError(f"targeted Yahoo validation hash mismatch: {yahoo_path}")
        yahoo = pd.read_csv(yahoo_path)
        yahoo["session_date"] = pd.to_datetime(yahoo["session_date"], errors="raise")
        for column in (*PRICE_COLUMNS, "volume"):
            yahoo[column] = pd.to_numeric(yahoo[column], errors="coerce")
        first = investing["session_date"].min()
        last = investing["session_date"].max()
        yahoo_span = yahoo.loc[yahoo["session_date"].between(first, last)].copy()
        investing_dates = set(investing["session_date"])
        yahoo_dates = set(yahoo_span["session_date"])
        shared = investing.merge(
            yahoo_span,
            on="session_date",
            how="inner",
            suffixes=("_investing", "_yahoo"),
            validate="one_to_one",
        )
        close_diff = (shared["close_investing"] - shared["close_yahoo"]).abs()
        investing_missing_volume = set(
            investing.loc[investing["volume"].isna(), "session_date"]
        )
        yahoo_complete_dates = set(
            yahoo_span.loc[
                yahoo_span[[*PRICE_COLUMNS, "volume"]].notna().all(axis=1)
                & yahoo_span["volume"].ge(0),
                "session_date",
            ]
        )
        zero_volume_yahoo_only_wig = sorted(
            date
            for date in yahoo_dates - investing_dates
            if date in wig_dates
            and float(
                yahoo_span.loc[yahoo_span["session_date"].eq(date), "volume"].iloc[0]
            )
            == 0.0
        )
        metrics[isin] = {
            "investing_file": investing_filename,
            "yahoo_folder": yahoo_folder,
            "mapping_state": str(provenance["identity_mapping"]["mapping_state"]),
            "comparison_first": str(first.date()),
            "comparison_last": str(last.date()),
            "shared_sessions": len(shared),
            "investing_only_sessions": sorted(
                str(value.date()) for value in investing_dates - yahoo_dates
            ),
            "yahoo_only_sessions": sorted(
                str(value.date()) for value in yahoo_dates - investing_dates
            ),
            "max_abs_close_difference": float(close_diff.max()),
            "median_abs_close_difference": float(close_diff.median()),
            "investing_missing_volume_dates": sorted(
                str(value.date()) for value in investing_missing_volume
            ),
            "yahoo_complete_on_investing_missing_volume_dates": sorted(
                str(value.date())
                for value in investing_missing_volume & yahoo_complete_dates
            ),
            "zero_volume_yahoo_only_wig_sessions": [
                str(value.date()) for value in zero_volume_yahoo_only_wig
            ],
            "selection_decision": "Investing.com remains preferred; retained Yahoo legacy-symbol history is validation evidence only because its metadata/calendar are degraded",
        }
        inputs.extend(
            [
                {
                    "isin": isin,
                    "path": str(investing_path.resolve()),
                    "bytes": investing_path.stat().st_size,
                    "sha256": sha256(investing_path),
                    "role": "targeted_investing_yahoo_overlap_validation",
                },
                {
                    "isin": isin,
                    "path": str(provenance_path.resolve()),
                    "bytes": provenance_path.stat().st_size,
                    "sha256": sha256(provenance_path),
                    "role": "targeted_yahoo_provenance_validation",
                },
                {
                    "isin": isin,
                    "path": str(yahoo_path.resolve()),
                    "bytes": yahoo_path.stat().st_size,
                    "sha256": sha256(yahoo_path),
                    "role": "targeted_yahoo_overlap_validation",
                },
            ]
        )
    return metrics, inputs


def load_targeted_suspensions(
    path: Path,
) -> tuple[dict[str, pd.Timestamp], dict[str, set[pd.Timestamp]], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = payload.get("events", [])
    if not events:
        raise ValueError("targeted non-trading event file contains no events")
    suspension: dict[str, pd.Timestamp] = {}
    nontrading_dates: dict[str, set[pd.Timestamp]] = {}
    for event in events:
        isin = str(event["isin"])
        date = pd.Timestamp(str(event["suspension_from"]))
        if isin in suspension:
            raise ValueError(f"duplicate targeted suspension identity: {isin}")
        suspension[isin] = date
        nontrading_dates[isin] = {
            pd.Timestamp(str(value))
            for value in event.get("nontrading_sessions_before_suspension", [])
        }
    return suspension, nontrading_dates, {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "events": events,
    }


def load_stooq_dates(
    symbol_map: pd.DataFrame,
    required_isins: set[str],
    data_root: Path,
    history_floor: pd.Timestamp,
    endpoint: pd.Timestamp,
) -> tuple[dict[str, set[pd.Timestamp]], list[dict[str, Any]]]:
    dates: dict[str, set[pd.Timestamp]] = {}
    inputs: list[dict[str, Any]] = []
    usable = symbol_map.loc[
        symbol_map["isin"].isin(required_isins)
        & symbol_map["status"].isin(RESOLVED_STOOQ_STATES)
        & symbol_map["stooq_symbol"].notna(),
        ["isin", "stooq_symbol"],
    ].drop_duplicates()
    for row in usable.itertuples(index=False):
        symbol = str(row.stooq_symbol).upper()
        path = data_root / "daily" / "pl" / "wse stocks" / f"{symbol.lower()}.txt"
        if not path.is_file():
            continue
        frame = read_stooq_file(path, symbol)
        frame = frame.loc[frame["session_date"].between(history_floor, endpoint)]
        dates.setdefault(str(row.isin), set()).update(set(frame["session_date"]))
        inputs.append(
            {
                "isin": str(row.isin),
                "symbol": symbol,
                "path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "rows_in_contract_window": len(frame),
            }
        )
    return dates, inputs


def write_csv(path: Path, frame: pd.DataFrame, sort: list[str]) -> None:
    result = frame.sort_values(sort, kind="mergesort").copy() if not frame.empty else frame.copy()
    for column in result.select_dtypes(include=["datetime64[ns]"]).columns:
        result[column] = result[column].dt.strftime("%Y-%m-%d")
    result.to_csv(path, index=False, lineterminator="\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit GPW TOP60 source/native coverage and strict 252-session warm-up from 2019-12-23"
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--bossa-root", type=Path, required=True)
    parser.add_argument("--bossa-session-root", type=Path, required=True)
    parser.add_argument("--investing-root", type=Path, required=True)
    parser.add_argument("--yahoo-root", type=Path, required=True)
    parser.add_argument("--targeted-events", type=Path, required=True)
    parser.add_argument("--membership-assertion", type=Path, required=True)
    parser.add_argument("--endpoint", default=str(DEFAULT_ENDPOINT.date()))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    endpoint = pd.Timestamp(args.endpoint)
    if endpoint != DEFAULT_ENDPOINT:
        raise ValueError(f"endpoint must remain pinned to accepted comparison endpoint {DEFAULT_ENDPOINT.date()}")
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable output {output}")
    output.mkdir(parents=True)

    data_root = args.data_root.resolve()
    reference_root = data_root / "reference" / "gpw_indices"
    sessions = load_wig_sessions(data_root, endpoint)
    start_position = int(sessions.get_loc(COMPLETE_PIT_START))
    history_floor = pd.Timestamp(sessions[start_position - LOOKBACK_SESSIONS])
    intervals = membership_intervals(reference_root, endpoint)
    grid = build_official_grid(intervals, sessions, endpoint)
    membership_validation = validate_membership_assertion(
        args.membership_assertion.resolve(), reference_root, grid
    )
    symbol_map_path = reference_root / "stooq_symbol_map.csv"
    symbol_map = pd.read_csv(symbol_map_path)

    bossa_map = choose_bossa_mapping(grid, symbol_map, args.bossa_root.resolve())
    bossa_dates, bossa_inputs = load_bossa_dates(bossa_map, history_floor, endpoint)
    page_dates, page_inputs = load_bossa_session_supplements(
        args.bossa_session_root.resolve(), grid, symbol_map
    )
    investing_dates, investing_missing_volume_dates, investing_inputs = load_investing_dates(
        args.investing_root.resolve(), history_floor, endpoint
    )
    yahoo_dates, yahoo_inputs = load_yahoo_dates(
        args.yahoo_root.resolve(), history_floor, endpoint
    )
    targeted_overlap, targeted_overlap_inputs = validate_targeted_investing_yahoo(
        args.investing_root.resolve(), args.yahoo_root.resolve(), sessions
    )
    stooq_dates, stooq_inputs = load_stooq_dates(
        symbol_map, set(grid["isin"].astype(str)), data_root, history_floor, endpoint
    )

    combined_dates: dict[str, set[pd.Timestamp]] = {}
    first_raw: dict[str, pd.Timestamp] = {}
    last_raw: dict[str, pd.Timestamp] = {}
    for isin in sorted(set(grid["isin"].astype(str))):
        combined = (
            bossa_dates.get(isin, set())
            | page_dates.get(isin, set())
            | investing_dates.get(isin, set())
            | yahoo_dates.get(isin, set())
        )
        combined_dates[isin] = combined
        if combined:
            first_raw[isin] = min(combined)
            last_raw[isin] = max(combined)

    exits_path = data_root / "analysis" / "top60_exit_event_audit.csv"
    exits = pd.read_csv(exits_path)
    exits["trading_suspension_from"] = pd.to_datetime(
        exits["trading_suspension_from"], errors="coerce"
    )
    suspension = exits.set_index("isin")["trading_suspension_from"].to_dict()
    targeted_suspension, targeted_nontrading_dates, targeted_event_input = load_targeted_suspensions(
        args.targeted_events.resolve()
    )
    for isin, date in targeted_suspension.items():
        existing = suspension.get(isin)
        suspension[isin] = date if pd.isna(existing) else min(pd.Timestamp(existing), date)
    exit_evidence = exits.set_index("isin").to_dict("index")
    targeted_evidence = {
        str(event["isin"]): event for event in targeted_event_input["events"]
    }

    grid = grid.merge(
        bossa_map[["isin", "bossa_mapping_state", "bossa_ticker", "bossa_file"]],
        on="isin",
        how="left",
        validate="many_to_one",
    )
    grid["bossa_mstall_has_bar"] = [
        date in bossa_dates.get(str(isin), set())
        for isin, date in zip(grid["isin"], grid["session_date"])
    ]
    grid["bossa_session_has_bar"] = [
        date in page_dates.get(str(isin), set())
        for isin, date in zip(grid["isin"], grid["session_date"])
    ]
    grid["investing_has_bar"] = [
        date in investing_dates.get(str(isin), set())
        for isin, date in zip(grid["isin"], grid["session_date"])
    ]
    grid["investing_bar_missing_volume"] = [
        date in investing_missing_volume_dates.get(str(isin), set())
        for isin, date in zip(grid["isin"], grid["session_date"])
    ]
    grid["yahoo_has_bar"] = [
        date in yahoo_dates.get(str(isin), set())
        for isin, date in zip(grid["isin"], grid["session_date"])
    ]
    grid["combined_has_bar"] = (
        grid["bossa_mstall_has_bar"]
        | grid["bossa_session_has_bar"]
        | grid["investing_has_bar"]
        | grid["yahoo_has_bar"]
    )
    grid["selected_source"] = "missing"
    grid.loc[grid["yahoo_has_bar"], "selected_source"] = "yahoo_finance"
    grid.loc[grid["investing_has_bar"], "selected_source"] = "investing_com"
    grid.loc[grid["bossa_session_has_bar"], "selected_source"] = "bossa_session_page"
    grid.loc[grid["bossa_mstall_has_bar"], "selected_source"] = "bossa_mstall"
    grid["stooq_has_bar"] = [
        date in stooq_dates.get(str(isin), set())
        for isin, date in zip(grid["isin"], grid["session_date"])
    ]

    grid["official_membership"] = True

    def independently_established_nontrading(row: pd.Series) -> tuple[bool, str, str]:
        isin = str(row["isin"])
        date = pd.Timestamp(row["session_date"])
        targeted = targeted_evidence.get(isin, {})
        if date in targeted_nontrading_dates.get(isin, set()):
            return (
                True,
                "documented_zero_volume_flat_ohlc_nontrading_session",
                f"{targeted.get('authority', 'targeted retained evidence')}|{targeted.get('evidence_url', '')}",
            )
        suspended_from = suspension.get(isin)
        if pd.notna(suspended_from) and date >= pd.Timestamp(suspended_from):
            retained = exit_evidence.get(isin, {})
            authority = targeted.get("authority") or retained.get("event_type") or "retained official exit evidence"
            evidence_url = (
                targeted.get("evidence_url")
                or retained.get("primary_source_url")
                or retained.get("market_source_url")
                or ""
            )
            return True, "officially_established_trading_suspension", f"{authority}|{evidence_url}"
        return False, "", ""

    nontrading = grid.apply(independently_established_nontrading, axis=1)
    grid["independently_established_nontrading"] = [value[0] for value in nontrading]
    grid["nontrading_reason"] = [value[1] for value in nontrading]
    grid["nontrading_evidence_reference"] = [value[2] for value in nontrading]
    grid["expected_trading"] = (
        grid["official_membership"] & ~grid["independently_established_nontrading"]
    )
    grid["selected_source_observation_present"] = grid["combined_has_bar"]
    grid["covered_expected_trading"] = (
        grid["expected_trading"] & grid["selected_source_observation_present"]
    )
    grid["coverage_result"] = "not_expected_nontrading"
    grid.loc[grid["covered_expected_trading"], "coverage_result"] = "covered_expected_trading"
    grid.loc[
        grid["expected_trading"] & ~grid["selected_source_observation_present"],
        "coverage_result",
    ] = "missing_expected_trading"
    grid["unresolved_or_missing_state"] = ""
    grid.loc[
        grid["expected_trading"] & ~grid["selected_source_observation_present"],
        "unresolved_or_missing_state",
    ] = "expected_trading_source_observation_missing"

    def current_gap_state(row: pd.Series) -> str:
        if bool(row["covered_expected_trading"]):
            return "covered_expected_trading"
        if bool(row["independently_established_nontrading"]):
            return "independently_established_nontrading"
        return "unresolved_expected_trading_missing"

    grid["current_coverage_state"] = grid.apply(current_gap_state, axis=1)

    session_positions = {pd.Timestamp(value): position for position, value in enumerate(sessions)}
    warmup_rows: list[dict[str, Any]] = []
    missing_detail_rows: list[dict[str, Any]] = []
    required_dates_by_isin: dict[str, set[pd.Timestamp]] = {
        isin: set() for isin in set(grid["isin"].astype(str))
    }
    for row in grid.itertuples(index=False):
        isin = str(row.isin)
        position = session_positions[pd.Timestamp(row.session_date)]
        required = set(map(pd.Timestamp, sessions[position - LOOKBACK_SESSIONS : position]))
        if len(required) != LOOKBACK_SESSIONS:
            raise ValueError(f"incorrect warm-up length on {row.session_date}")
        required_dates_by_isin[isin].update(required)
        available = combined_dates.get(isin, set())
        missing = sorted(required - available)
        stooq_missing_raw = [date for date in missing if date in stooq_dates.get(isin, set())]
        before_first = [date for date in missing if isin in first_raw and date < first_raw[isin]]
        after_last = [date for date in missing if isin in last_raw and date > last_raw[isin]]
        internal = [
            date
            for date in missing
            if isin in first_raw and first_raw[isin] <= date <= last_raw[isin]
        ]
        fixable_by_identified_history = len(missing) if not available else len(stooq_missing_raw)
        nonhistory_missing = len(missing) - fixable_by_identified_history
        if not missing:
            warmup_state = "ready"
        elif fixable_by_identified_history and not nonhistory_missing:
            warmup_state = "additional_history_only"
        elif fixable_by_identified_history and nonhistory_missing:
            warmup_state = "additional_history_and_no_reference_gaps"
        else:
            warmup_state = "no_reference_gaps_only"
        warmup_rows.append(
            {
                "session_date": row.session_date,
                "isin": isin,
                "company_name": row.company_name,
                "source_index": row.source_index,
                "warmup_start_session": min(required),
                "warmup_end_session": max(required),
                "warmup_required_sessions": LOOKBACK_SESSIONS,
                "warmup_covered_sessions": LOOKBACK_SESSIONS - len(missing),
                "warmup_missing_sessions": len(missing),
                "strict_252_ready": len(missing) == 0,
                "missing_raw_where_stooq_has_bar": len(stooq_missing_raw),
                "missing_before_first_raw": len(before_first),
                "missing_after_last_raw": len(after_last),
                "missing_inside_raw_span": len(internal),
                "no_raw_history": not bool(available),
                "history_fixable_missing_sessions": fixable_by_identified_history,
                "no_reference_missing_sessions": nonhistory_missing,
                "warmup_state": warmup_state,
            }
        )
        for date in missing:
            if date in targeted_nontrading_dates.get(isin, set()):
                state = "known_zero_volume_nontrading"
            elif not available:
                state = "no_raw_history"
            elif date in stooq_dates.get(isin, set()):
                state = "raw_gap_stooq_available"
            elif date < first_raw[isin]:
                state = "before_first_raw_observation"
            elif date > last_raw[isin]:
                state = "after_last_raw_observation"
            else:
                state = "internal_no_bar_without_stooq_reference"
            missing_detail_rows.append(
                {
                    "member_session_date": row.session_date,
                    "isin": isin,
                    "company_name": row.company_name,
                    "required_history_session": date,
                    "stooq_has_bar": date in stooq_dates.get(isin, set()),
                    "missing_state": state,
                }
            )

    warmup = pd.DataFrame(warmup_rows)
    missing_detail = pd.DataFrame(missing_detail_rows)
    grid = grid.merge(
        warmup,
        on=["session_date", "isin", "company_name", "source_index"],
        how="left",
        validate="one_to_one",
    )

    history_need_rows: list[dict[str, Any]] = []
    for isin, group in grid.groupby("isin", sort=True):
        isin = str(isin)
        required = required_dates_by_isin[isin] | set(group["session_date"])
        missing_required = sorted(required - combined_dates.get(isin, set()))
        stooq_evidenced = sorted(
            date for date in missing_required if date in stooq_dates.get(isin, set())
        )
        current_unexplained = group.loc[
            group["current_coverage_state"].eq("unresolved_expected_trading_missing"),
            "session_date",
        ].sort_values()
        no_raw = not bool(combined_dates.get(isin))
        needs_history = no_raw or bool(stooq_evidenced) or not current_unexplained.empty
        if not needs_history:
            continue
        candidate_dates = set(stooq_evidenced) | set(current_unexplained)
        if no_raw:
            candidate_dates |= required
        history_need_rows.append(
            {
                "isin": isin,
                "company_names": "|".join(sorted(set(map(str, group["company_name"])))),
                "first_official_session": group["session_date"].min(),
                "last_official_session": group["session_date"].max(),
                "has_any_raw_history": not no_raw,
                "raw_missing_official_member_sessions": int((~group["combined_has_bar"]).sum()),
                "unexplained_current_member_gaps": len(current_unexplained),
                "unique_required_history_gaps": len(missing_required),
                "unique_stooq_evidenced_raw_history_gaps": len(stooq_evidenced),
                "requested_history_start": min(candidate_dates) if candidate_dates else pd.NaT,
                "requested_history_end": max(candidate_dates) if candidate_dates else pd.NaT,
                "reason": (
                    "no_bossa_or_investing_history"
                    if no_raw
                    else "raw_gaps_with_stooq_or_official_membership_evidence"
                ),
            }
        )
    additional_histories = pd.DataFrame(history_need_rows)

    security_summary = (
        grid.groupby("isin", as_index=False)
        .agg(
            company_names=("company_name", lambda values: "|".join(sorted(set(map(str, values))))),
            first_official_session=("session_date", "min"),
            last_official_session=("session_date", "max"),
            official_member_sessions=("session_date", "size"),
            raw_covered_member_sessions=("combined_has_bar", "sum"),
            strict_252_ready_member_sessions=("strict_252_ready", "sum"),
            first_strict_252_ready_session=(
                "session_date",
                lambda values: pd.NaT,
            ),
        )
    )
    first_ready = (
        grid.loc[grid["strict_252_ready"]]
        .groupby("isin")["session_date"]
        .min()
        .to_dict()
    )
    security_summary["first_strict_252_ready_session"] = security_summary["isin"].map(first_ready)
    security_summary["raw_missing_member_sessions"] = (
        security_summary["official_member_sessions"]
        - security_summary["raw_covered_member_sessions"]
    )
    security_summary["strict_252_not_ready_member_sessions"] = (
        security_summary["official_member_sessions"]
        - security_summary["strict_252_ready_member_sessions"]
    )
    need_isins = set(additional_histories["isin"]) if not additional_histories.empty else set()
    security_summary["additional_history_needed"] = security_summary["isin"].isin(need_isins)
    security_summary["first_raw_session"] = security_summary["isin"].map(first_raw)
    security_summary["last_raw_session"] = security_summary["isin"].map(last_raw)
    unique_missing = (
        missing_detail.drop_duplicates(["isin", "required_history_session", "missing_state"])
        .groupby(["isin", "missing_state"])
        .size()
        .unstack(fill_value=0)
        if not missing_detail.empty
        else pd.DataFrame()
    )
    for state in (
        "no_raw_history",
        "raw_gap_stooq_available",
        "before_first_raw_observation",
        "after_last_raw_observation",
        "internal_no_bar_without_stooq_reference",
        "known_zero_volume_nontrading",
    ):
        values = unique_missing[state] if state in unique_missing.columns else pd.Series(dtype="int64")
        security_summary[f"unique_warmup_missing__{state}"] = (
            security_summary["isin"].map(values).fillna(0).astype("int64")
        )
    security_summary["warmup_limitation_class"] = "complete"
    security_summary.loc[
        security_summary["strict_252_not_ready_member_sessions"].gt(0),
        "warmup_limitation_class",
    ] = "no_reference_gaps_only"
    security_summary.loc[
        security_summary["additional_history_needed"], "warmup_limitation_class"
    ] = "additional_raw_history_needed"

    current_state_counts = {
        str(key): int(value)
        for key, value in grid["current_coverage_state"].value_counts().sort_index().items()
    }
    coverage_counts = expected_trading_coverage_counts(
        grid["expected_trading"], grid["selected_source_observation_present"]
    )
    warmup_missing_state_counts = (
        {
            str(key): int(value)
            for key, value in missing_detail["missing_state"].value_counts().sort_index().items()
        }
        if not missing_detail.empty
        else {}
    )
    first_session = grid.loc[grid["session_date"].eq(COMPLETE_PIT_START)]
    start_readiness = (
        grid.groupby("session_date", as_index=False)
        .agg(
            official_members=("isin", "size"),
            expected_trading_members=("expected_trading", "sum"),
            strict_252_ready_members=("strict_252_ready", "sum"),
        )
    )
    start_readiness["all_60_expected_and_strict_ready"] = (
        start_readiness["official_members"].eq(60)
        & start_readiness["expected_trading_members"].eq(60)
        & start_readiness["strict_252_ready_members"].eq(60)
    )
    first_all_60_strict_ready = start_readiness.loc[
        start_readiness["all_60_expected_and_strict_ready"], "session_date"
    ].min()
    metrics = {
        "contract": {
            "complete_pit_start": str(COMPLETE_PIT_START.date()),
            "endpoint": str(endpoint.date()),
            "official_denominator_per_session": 60,
            "lookback_sessions": LOOKBACK_SESSIONS,
            "lookback_definition": "the immediately preceding 252 WIG sessions, excluding the official member-session",
            "history_floor_session": str(history_floor.date()),
            "source_priority": [
                "bossa_mstall",
                "bossa_session_page",
                "investing_com",
                "yahoo_finance_accepted_clean_wse_series",
                "explicit_missing",
            ],
            "stooq_role": "independent gap and expected-trading reference only; never selected into raw panel",
        },
        "membership_boundary": {
            "wig20_members_on_start": int(first_session["source_index"].eq("WIG20").sum()),
            "mwig40_members_on_start": int(first_session["source_index"].eq("mWIG40").sum()),
            "unique_top60_members_on_start": int(first_session["isin"].nunique()),
            "basis": "first complete December 2019 WIG20 and mWIG40 effective snapshots; extraordinary changes exhaustively layered from this boundary onward",
            "machine_readable_assertion": membership_validation,
        },
        "experiment_start_recommendation": {
            "recommended_start": str(COMPLETE_PIT_START.date()),
            "criterion": "earliest complete-PIT TOP60 session with complete expected-trading source/native price coverage; feature-specific 252-session eligibility remains explicit",
            "complete_pit_start": str(COMPLETE_PIT_START.date()),
            "strict_252_ready_members_on_recommended_start": int(first_session["strict_252_ready"].sum()),
            "strict_252_not_ready_members_on_recommended_start": int((~first_session["strict_252_ready"]).sum()),
            "first_incidental_session_with_all_60_strict_ready": str(first_all_60_strict_ready.date()),
            "why_first_all_60_strict_is_not_recommended": "it discards more than two years and does not guarantee readiness for later newly listed entrants",
            "guarantees_future_new_listing_readiness": False,
        },
        "counts": {
            "evaluation_sessions": int(grid["session_date"].nunique()),
            "official_member_sessions": len(grid),
            "unique_official_members": int(grid["isin"].nunique()),
            "bossa_mstall_member_sessions": int(grid["bossa_mstall_has_bar"].sum()),
            "bossa_session_page_member_sessions": int(
                (~grid["bossa_mstall_has_bar"] & grid["bossa_session_has_bar"]).sum()
            ),
            "investing_supplemented_member_sessions": int(
                (~grid["bossa_mstall_has_bar"] & ~grid["bossa_session_has_bar"] & grid["investing_has_bar"]).sum()
            ),
            "yahoo_supplemented_member_sessions": int(
                (
                    ~grid["bossa_mstall_has_bar"]
                    & ~grid["bossa_session_has_bar"]
                    & ~grid["investing_has_bar"]
                    & grid["yahoo_has_bar"]
                ).sum()
            ),
            "selected_investing_member_sessions_with_missing_display_volume": int(
                (grid["selected_source"].eq("investing_com") & grid["investing_bar_missing_volume"]).sum()
            ),
            "combined_raw_covered_member_sessions": int(grid["combined_has_bar"].sum()),
            "combined_raw_missing_member_sessions": int((~grid["combined_has_bar"]).sum()),
            "expected_trading_member_sessions": coverage_counts["expected_trading_member_sessions"],
            "covered_expected_trading_member_sessions": coverage_counts["covered_expected_trading_member_sessions"],
            "missing_expected_trading_member_sessions": coverage_counts["missing_expected_trading_member_sessions"],
            "expected_trading_price_coverage_share": coverage_counts["coverage_share"],
            "legitimate_suspension_nontrading_member_sessions": int(
                (
                    grid["independently_established_nontrading"]
                    & grid["nontrading_reason"].eq("officially_established_trading_suspension")
                ).sum()
            ),
            "legitimate_zero_volume_nontrading_member_sessions": int(
                grid["nontrading_reason"].eq("documented_zero_volume_flat_ohlc_nontrading_session").sum()
            ),
            "unexplained_or_history_missing_member_sessions": int(
                grid["current_coverage_state"].eq("unresolved_expected_trading_missing").sum()
            ),
            "strict_252_ready_member_sessions": int(grid["strict_252_ready"].sum()),
            "strict_252_not_ready_member_sessions": int((~grid["strict_252_ready"]).sum()),
            "strict_252_ready_share": float(grid["strict_252_ready"].mean()),
            "strict_252_member_sessions_fixable_by_identified_histories_only": int(
                grid["warmup_state"].eq("additional_history_only").sum()
            ),
            "strict_252_member_sessions_with_no_reference_gaps": int(
                grid["warmup_state"].isin(
                    ["no_reference_gaps_only", "additional_history_and_no_reference_gaps"]
                ).sum()
            ),
            "additional_histories_needed": len(additional_histories),
        },
        "current_coverage_state_counts": current_state_counts,
        "warmup_state_counts": {
            str(key): int(value)
            for key, value in grid["warmup_state"].value_counts().sort_index().items()
        },
        "warmup_missing_state_occurrence_counts": warmup_missing_state_counts,
        "targeted_investing_yahoo_validation": targeted_overlap,
        "selected_investing_missing_volume_member_sessions": grid.loc[
            grid["selected_source"].eq("investing_com")
            & grid["investing_bar_missing_volume"],
            ["session_date", "isin", "company_name"],
        ].to_dict("records"),
        "additional_histories": additional_histories.to_dict("records"),
    }

    write_csv(output / "member_session_audit.csv", grid, ["session_date", "source_index", "isin"])
    write_csv(output / "warmup_missing_detail.csv", missing_detail, ["isin", "member_session_date", "required_history_session"])
    write_csv(output / "security_summary.csv", security_summary, ["isin"])
    write_csv(output / "additional_histories_needed.csv", additional_histories, ["isin"])
    write_csv(output / "bossa_identity_map.csv", bossa_map, ["isin"])
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    produced = sorted(path for path in output.iterdir() if path.name != "manifest.json")
    script_path = Path(__file__).resolve()
    membership_inputs = [
        path
        for component in ("WIG20", "mWIG40")
        for path in (reference_root / "snapshots" / component).glob("*.csv")
        if COMPLETE_PIT_START <= pd.Timestamp(path.stem) <= endpoint
    ]
    manifest = {
        "script": {"path": str(script_path), "sha256": sha256(script_path)},
        "contract": metrics["contract"],
        "membership_reference": {
            "manifest_path": str((reference_root / "manifest.csv").resolve()),
            "manifest_sha256": sha256(reference_root / "manifest.csv"),
            "readme_sha256": sha256(reference_root / "README.md"),
            "build_report_sha256": sha256(reference_root / "BUILD_REPORT.md"),
            "snapshots": {
                str(path.resolve()): sha256(path) for path in sorted(membership_inputs)
            },
        },
        "membership_completeness_assertion": {
            "path": str(args.membership_assertion.resolve()),
            "sha256": sha256(args.membership_assertion.resolve()),
            "validation": membership_validation,
        },
        "identity_reference": {"path": str(symbol_map_path), "sha256": sha256(symbol_map_path)},
        "exit_reference": {"path": str(exits_path), "sha256": sha256(exits_path)},
        "targeted_nontrading_event_reference": targeted_event_input,
        "bossa_inputs": bossa_inputs,
        "bossa_session_inputs": page_inputs,
        "investing_inputs": investing_inputs,
        "yahoo_inputs": yahoo_inputs,
        "targeted_investing_yahoo_validation_inputs": targeted_overlap_inputs,
        "stooq_reference_inputs": stooq_inputs,
        "outputs": {
            path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in produced
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
