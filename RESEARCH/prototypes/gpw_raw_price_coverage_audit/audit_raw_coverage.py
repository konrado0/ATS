from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ats_research.investing_manual import parse_investing_manual_history


WARMUP_START = pd.Timestamp("2019-01-01")
EXPECTED_EVALUATION_START = pd.Timestamp("2020-11-27")
PRICE_COLUMNS = ("open", "high", "low", "close")


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


def read_bossa(path: Path, expected_ticker: str, endpoint: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.read_csv(path)
    frame.columns = [str(value).strip("<>").lower() for value in frame.columns]
    required = {"ticker", "dtyyyymmdd", *PRICE_COLUMNS, "vol"}
    if not required.issubset(frame.columns) or len(frame.columns) not in (7, 8):
        raise ValueError(f"{path}: unsupported Bossa schema {list(frame.columns)}")
    unexpected = set(frame.columns).difference(required | {"openint"})
    if unexpected:
        raise ValueError(f"{path}: unexpected Bossa columns {sorted(unexpected)}")
    tickers = set(frame["ticker"].astype(str).str.upper().unique())
    if tickers != {expected_ticker}:
        raise ValueError(f"{path}: expected ticker {expected_ticker}, observed {sorted(tickers)}")
    frame["session_date"] = pd.to_datetime(frame["dtyyyymmdd"].astype(str), format="%Y%m%d", errors="raise")
    frame = frame.rename(columns={"vol": "volume"})[["session_date", *PRICE_COLUMNS, "volume"]]
    for column in (*PRICE_COLUMNS, "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.loc[frame["session_date"].between(WARMUP_START, endpoint)].sort_values("session_date").reset_index(drop=True)
    valid = valid_ohlcv(frame)
    invalid = frame.loc[~valid].copy()
    return frame.loc[valid].copy(), invalid


def parse_polish_number(value: str) -> float:
    cleaned = value.strip().replace("\xa0", "").replace(" ", "")
    if cleaned == "-":
        return float("nan")
    return float(cleaned.replace(",", "."))


def read_bossa_session_page(path: Path, session_date: pd.Timestamp) -> pd.DataFrame:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    marker = "Pokaż transakcje "
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if not line.startswith(marker):
            continue
        if index + 7 >= len(lines):
            raise ValueError(f"{path}: truncated company block at line {index + 1}")
        company_name = line[len(marker) :].strip().upper()
        if lines[index + 1].strip().upper() != company_name:
            raise ValueError(f"{path}: company-name mismatch at line {index + 1}")
        chart_match = re.fullmatch(r"(\S+) Wykres (.+)", lines[index + 2].strip())
        if chart_match is None or chart_match.group(2).strip().upper() != company_name:
            raise ValueError(f"{path}: unsupported chart line at {index + 3}")
        ticker = chart_match.group(1).upper()

        def after_prefix(offset: int, prefix: str) -> str:
            value = lines[index + offset].strip()
            if not value.startswith(prefix):
                raise ValueError(f"{path}: expected {prefix!r} at line {index + offset + 1}")
            return value[len(prefix) :]

        high_match = re.search(r"(?:^|\t)Maksimum:([^\t]+)", lines[index + 5])
        volume_match = re.search(
            r"(?:^|\t)Wolumen obrotu \[liczba sztuk\]:([^\t]+)", lines[index + 7]
        )
        if high_match is None or volume_match is None:
            raise ValueError(f"{path}: missing high or volume at company block {company_name}")
        rows.append(
            {
                "session_date": session_date,
                "page_company_name": company_name,
                "page_ticker": ticker,
                "open": parse_polish_number(after_prefix(3, "Otwarcie:")),
                "high": parse_polish_number(high_match.group(1)),
                "low": parse_polish_number(after_prefix(6, "Minimum:")),
                "close": parse_polish_number(after_prefix(4, "Zamknięcie:")),
                "volume": parse_polish_number(volume_match.group(1)),
            }
        )
    if not rows:
        raise ValueError(f"{path}: no Bossa company blocks found")
    frame = pd.DataFrame(rows)
    if frame.duplicated(["session_date", "page_company_name"]).any():
        raise ValueError(f"{path}: duplicate company rows")
    frame["valid_raw_bar"] = ~(
        frame[list(PRICE_COLUMNS)].isna().any(axis=1)
        | frame[list(PRICE_COLUMNS)].le(0).any(axis=1)
        | frame["volume"].isna()
        | frame["volume"].lt(0)
        | frame["high"].lt(frame[["open", "close", "low"]].max(axis=1))
        | frame["low"].gt(frame[["open", "close", "high"]].min(axis=1))
    )
    return frame


def read_stooq(path: Path, expected_symbol: str, endpoint: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.read_csv(path)
    frame.columns = [str(value).strip("<>").lower() for value in frame.columns]
    required = {"ticker", "per", "date", "time", *PRICE_COLUMNS, "vol"}
    if not required.issubset(frame.columns):
        raise ValueError(f"{path}: unsupported Stooq schema {list(frame.columns)}")
    tickers = set(frame["ticker"].astype(str).str.upper().unique())
    periods = set(frame["per"].astype(str).str.upper().unique())
    if tickers != {expected_symbol} or periods != {"D"}:
        raise ValueError(f"{path}: unexpected Stooq symbols/periods {tickers}/{periods}")
    frame["session_date"] = pd.to_datetime(frame["date"].astype(str), format="%Y%m%d", errors="raise")
    frame = frame.rename(columns={"vol": "volume"})[["session_date", *PRICE_COLUMNS, "volume"]]
    for column in (*PRICE_COLUMNS, "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.loc[frame["session_date"].between(WARMUP_START, endpoint)].sort_values("session_date").reset_index(drop=True)
    valid = valid_ohlcv(frame)
    invalid = frame.loc[~valid].copy()
    return frame.loc[valid].copy(), invalid


def choose_bossa_mapping(
    grid: pd.DataFrame, symbol_map: pd.DataFrame, bossa_root: Path
) -> pd.DataFrame:
    files = {path.stem.upper(): path.resolve() for path in bossa_root.glob("*.mst")}
    rows: list[dict[str, Any]] = []
    for isin, group in grid.groupby("isin", sort=True):
        exact_aliases = set(
            symbol_map.loc[
                symbol_map["isin"].eq(isin) & symbol_map["status"].eq("exact"), "company_name"
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
                "security_id": group["security_id"].iloc[0],
                "pit_company_names": "|".join(sorted(member_aliases)),
                "exact_symbol_map_aliases": "|".join(sorted(exact_aliases)),
                "bossa_mapping_state": state,
                "bossa_ticker": selected,
                "bossa_file": str(files[selected]) if selected else None,
            }
        )
    result = pd.DataFrame(rows)
    selected = result["bossa_ticker"].dropna()
    if selected.duplicated().any():
        raise ValueError(f"Bossa files mapped to multiple identities: {selected.loc[selected.duplicated(keep=False)].tolist()}")
    return result


def write_csv(path: Path, frame: pd.DataFrame, sort: list[str]) -> None:
    result = frame.sort_values(sort, kind="mergesort").copy() if not frame.empty else frame.copy()
    for column in result.select_dtypes(include=["datetime64[ns]"]).columns:
        result[column] = result[column].dt.strftime("%Y-%m-%d")
    result.to_csv(path, index=False, lineterminator="\n", float_format="%.12g")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure raw GPW TOP60 coverage without Stooq fallback")
    parser.add_argument("--phase-a-run", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--bossa-root", type=Path, required=True)
    parser.add_argument("--bossa-page-root", type=Path, required=True)
    parser.add_argument("--investing-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {output}")
    output.mkdir(parents=True)

    artifacts = args.phase_a_run.resolve() / "artifacts"
    grid = pd.read_parquet(artifacts / "research_panel.parquet")[
        [
            "isin",
            "security_id",
            "company_name",
            "session_date",
            "stooq_symbol",
            "vendor_resolution_status",
            "price_exclusion_reason",
            "corporate_exit_state",
            "source_index",
        ]
    ].copy()
    grid["session_date"] = pd.to_datetime(grid["session_date"])
    if grid["session_date"].min() != EXPECTED_EVALUATION_START:
        raise ValueError(f"unexpected evaluation start {grid['session_date'].min()}")
    endpoint = grid["session_date"].max()
    if grid.duplicated(["isin", "session_date"]).any():
        raise ValueError("duplicate official member-session rows")
    per_session = grid.groupby("session_date").size()
    if not per_session.eq(60).all():
        raise ValueError(f"official denominator is not 60: {per_session.value_counts().to_dict()}")

    symbol_map_path = args.data_root.resolve() / "reference" / "gpw_indices" / "stooq_symbol_map.csv"
    symbol_map = pd.read_csv(symbol_map_path)
    bossa_map = choose_bossa_mapping(grid, symbol_map, args.bossa_root.resolve())

    bossa_dates: dict[str, set[pd.Timestamp]] = {}
    invalid_bossa_parts = []
    bossa_valid_parts = []
    bossa_inputs = []
    for row in bossa_map.loc[bossa_map["bossa_file"].notna()].itertuples(index=False):
        path = Path(row.bossa_file)
        valid, invalid = read_bossa(path, str(row.bossa_ticker), endpoint)
        bossa_dates[row.isin] = set(valid["session_date"])
        valid_values = valid.copy()
        valid_values.insert(0, "isin", row.isin)
        bossa_valid_parts.append(valid_values)
        if not invalid.empty:
            invalid.insert(0, "bossa_ticker", row.bossa_ticker)
            invalid.insert(0, "isin", row.isin)
            invalid_bossa_parts.append(invalid)
        bossa_inputs.append(
            {
                "isin": row.isin,
                "ticker": row.bossa_ticker,
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "valid_rows_from_warmup": len(valid),
                "invalid_rows_from_warmup": len(invalid),
            }
        )

    bossa_page_manifest_path = args.bossa_page_root.resolve() / "reference_manifest.json"
    bossa_page_manifest = json.loads(bossa_page_manifest_path.read_text(encoding="utf-8"))
    bossa_page_parts = []
    bossa_page_inputs = []
    for item in bossa_page_manifest["files"]:
        path = args.bossa_page_root.resolve() / str(item["filename"])
        actual_hash = sha256(path)
        if path.stat().st_size != int(item["byte_length"]) or actual_hash != str(item["sha256"]):
            raise ValueError(f"Bossa page manifest mismatch: {path}")
        session_date = pd.Timestamp(item["session_date"])
        parsed = read_bossa_session_page(path, session_date)
        parsed.insert(0, "source_filename", path.name)
        bossa_page_parts.append(parsed)
        bossa_page_inputs.append(
            {
                "session_date": session_date.date().isoformat(),
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": actual_hash,
                "parsed_rows": len(parsed),
                "valid_raw_rows": int(parsed["valid_raw_bar"].sum()),
            }
        )
    bossa_page_rows = pd.concat(bossa_page_parts, ignore_index=True)
    if bossa_page_rows.duplicated(["session_date", "page_company_name"]).any():
        raise ValueError("duplicate Bossa page company/session rows across inputs")
    official_page_keys = grid[
        ["session_date", "isin", "security_id", "company_name", "stooq_symbol"]
    ].copy()
    official_page_keys["official_company_name_key"] = (
        official_page_keys["company_name"].astype(str).str.upper()
    )
    official_page_keys["official_stooq_symbol_key"] = (
        official_page_keys["stooq_symbol"].astype(str).str.upper()
    )
    page_session_dates = set(bossa_page_rows["session_date"])
    page_expected = official_page_keys.loc[
        official_page_keys["session_date"].isin(page_session_dates)
    ].copy()
    page_by_name = page_expected.merge(
        bossa_page_rows,
        left_on=["session_date", "official_company_name_key"],
        right_on=["session_date", "page_company_name"],
        how="left",
        validate="one_to_one",
    )
    page_by_ticker = page_expected.merge(
        bossa_page_rows,
        left_on=["session_date", "official_stooq_symbol_key"],
        right_on=["session_date", "page_ticker"],
        how="left",
        validate="one_to_one",
    )
    bossa_page_official = page_by_name.copy()
    name_matched = bossa_page_official["source_filename"].notna()
    ticker_matched = page_by_ticker["source_filename"].notna()
    for column in bossa_page_rows.columns.difference(["session_date"]):
        bossa_page_official.loc[~name_matched, column] = page_by_ticker.loc[~name_matched, column]
    bossa_page_official["page_identity_match_method"] = np.select(
        [name_matched, ~name_matched & ticker_matched],
        ["official_company_name", "official_stooq_symbol"],
        default="unmatched",
    )
    bossa_page_official["valid_raw_bar"] = bossa_page_official["valid_raw_bar"].fillna(False)
    bossa_page_dates = {
        isin: set(group.loc[group["valid_raw_bar"], "session_date"])
        for isin, group in bossa_page_official.groupby("isin", sort=True)
    }

    stooq_dates: dict[str, set[pd.Timestamp]] = {}
    invalid_stooq_parts = []
    stooq_valid_parts = []
    stooq_inputs = []
    stooq_identity = grid[["isin", "stooq_symbol"]].drop_duplicates()
    for row in stooq_identity.loc[stooq_identity["stooq_symbol"].notna()].itertuples(index=False):
        symbol = str(row.stooq_symbol).upper()
        path = args.data_root.resolve() / "daily" / "pl" / "wse stocks" / f"{symbol.lower()}.txt"
        if not path.exists():
            continue
        valid, invalid = read_stooq(path, symbol, endpoint)
        stooq_dates[row.isin] = set(valid["session_date"])
        valid_values = valid.copy()
        valid_values.insert(0, "isin", row.isin)
        stooq_valid_parts.append(valid_values)
        if not invalid.empty:
            invalid.insert(0, "stooq_symbol", symbol)
            invalid.insert(0, "isin", row.isin)
            invalid_stooq_parts.append(invalid)
        stooq_inputs.append(
            {
                "isin": row.isin,
                "symbol": symbol,
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "valid_rows_from_warmup": len(valid),
                "invalid_rows_from_warmup": len(invalid),
            }
        )

    investing_manifest_path = args.investing_root.resolve() / "reference_manifest.json"
    investing_manifest = json.loads(investing_manifest_path.read_text(encoding="utf-8"))
    investing_dates: dict[str, set[pd.Timestamp]] = {}
    investing_inputs = []
    for item in investing_manifest["files"]:
        isin = str(item["isin"])
        path = args.investing_root.resolve() / str(item["filename"])
        parsed = parse_investing_manual_history(
            path,
            allow_missing_display_volume=True,
            allow_dot_thousands_in_prices=True,
        )
        investing_dates[isin] = set(
            parsed.bars.loc[parsed.bars["session_date"].between(WARMUP_START, endpoint), "session_date"]
        )
        investing_inputs.append(
            {
                "isin": isin,
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "rows_from_warmup": len(investing_dates[isin]),
            }
        )

    grid = grid.merge(
        bossa_map[["isin", "bossa_mapping_state", "bossa_ticker", "bossa_file"]],
        on="isin",
        how="left",
        validate="many_to_one",
    )
    grid["stooq_has_valid_bar"] = [date in stooq_dates.get(isin, set()) for isin, date in zip(grid["isin"], grid["session_date"])]
    grid["bossa_mstall_has_valid_raw_bar"] = [
        date in bossa_dates.get(isin, set()) for isin, date in zip(grid["isin"], grid["session_date"])
    ]
    grid["bossa_page_has_valid_raw_bar"] = [
        date in bossa_page_dates.get(isin, set()) for isin, date in zip(grid["isin"], grid["session_date"])
    ]
    grid["bossa_page_supplements_mstall"] = (
        ~grid["bossa_mstall_has_valid_raw_bar"] & grid["bossa_page_has_valid_raw_bar"]
    )
    grid["bossa_has_valid_raw_bar"] = (
        grid["bossa_mstall_has_valid_raw_bar"] | grid["bossa_page_has_valid_raw_bar"]
    )
    grid["investing_has_valid_raw_bar"] = [
        date in investing_dates.get(isin, set()) for isin, date in zip(grid["isin"], grid["session_date"])
    ]
    grid["combined_raw_has_bar"] = grid["bossa_has_valid_raw_bar"] | grid["investing_has_valid_raw_bar"]
    grid["investing_supplements_bossa"] = ~grid["bossa_has_valid_raw_bar"] & grid["investing_has_valid_raw_bar"]

    def classify(row: pd.Series) -> str:
        if row["bossa_has_valid_raw_bar"]:
            return "bossa_available"
        if row["investing_has_valid_raw_bar"]:
            return "bossa_missing_investing_available"
        reason = "" if pd.isna(row["price_exclusion_reason"]) else str(row["price_exclusion_reason"])
        if reason == "suspended_non_tradeable":
            return "legitimate_suspension_non_trading"
        if reason in {"not_yet_listed", "outside_listing_window"}:
            return "not_yet_listed_or_otherwise_not_expected"
        if str(row["bossa_mapping_state"]).startswith("unresolved_"):
            return "unresolved_identity"
        return "both_raw_sources_missing"

    grid["coverage_state"] = grid.apply(classify, axis=1)
    grid["residual_vs_stooq"] = grid["stooq_has_valid_bar"] & ~grid["combined_raw_has_bar"]

    page_flags = grid[
        [
            "session_date",
            "isin",
            "stooq_has_valid_bar",
            "bossa_mstall_has_valid_raw_bar",
            "investing_has_valid_raw_bar",
        ]
    ]
    bossa_page_official = bossa_page_official.merge(
        page_flags, on=["session_date", "isin"], how="left", validate="one_to_one"
    )
    bossa_valid_values = pd.concat(bossa_valid_parts, ignore_index=True).rename(
        columns={column: f"mstall_{column}" for column in (*PRICE_COLUMNS, "volume")}
    )
    stooq_valid_values = pd.concat(stooq_valid_parts, ignore_index=True).rename(
        columns={column: f"stooq_{column}" for column in (*PRICE_COLUMNS, "volume")}
    )
    bossa_page_official = bossa_page_official.merge(
        bossa_valid_values, on=["session_date", "isin"], how="left", validate="one_to_one"
    ).merge(
        stooq_valid_values, on=["session_date", "isin"], how="left", validate="one_to_one"
    )
    for source in ("mstall", "stooq"):
        source_columns = [f"{source}_{column}" for column in (*PRICE_COLUMNS, "volume")]
        available = bossa_page_official[source_columns].notna().all(axis=1)
        matches = np.ones(len(bossa_page_official), dtype=bool)
        for column in (*PRICE_COLUMNS, "volume"):
            matches &= np.isclose(
                bossa_page_official[column].fillna(np.inf),
                bossa_page_official[f"{source}_{column}"].fillna(-np.inf),
                rtol=0,
                atol=1e-12,
            )
        bossa_page_official[f"page_exact_match_{source}_ohlcv"] = available & matches

    security_summary = (
        grid.groupby(
            ["isin", "security_id", "company_name", "bossa_mapping_state", "bossa_ticker"],
            dropna=False,
            as_index=False,
        )
        .agg(
            official_member_sessions=("session_date", "size"),
            stooq_covered_member_sessions=("stooq_has_valid_bar", "sum"),
            bossa_mstall_covered_member_sessions=("bossa_mstall_has_valid_raw_bar", "sum"),
            bossa_page_supplemented_member_sessions=("bossa_page_supplements_mstall", "sum"),
            bossa_covered_member_sessions=("bossa_has_valid_raw_bar", "sum"),
            investing_supplemented_member_sessions=("investing_supplements_bossa", "sum"),
            combined_raw_covered_member_sessions=("combined_raw_has_bar", "sum"),
            residual_vs_stooq_sessions=("residual_vs_stooq", "sum"),
        )
    )
    # Preserve one row per ISIN even when a renamed security has multiple PIT names.
    security_summary = (
        security_summary.groupby(
            ["isin", "security_id", "bossa_mapping_state", "bossa_ticker"], dropna=False, as_index=False
        )
        .agg(
            company_names=("company_name", lambda values: "|".join(sorted(set(map(str, values))))),
            official_member_sessions=("official_member_sessions", "sum"),
            stooq_covered_member_sessions=("stooq_covered_member_sessions", "sum"),
            bossa_mstall_covered_member_sessions=("bossa_mstall_covered_member_sessions", "sum"),
            bossa_page_supplemented_member_sessions=("bossa_page_supplemented_member_sessions", "sum"),
            bossa_covered_member_sessions=("bossa_covered_member_sessions", "sum"),
            investing_supplemented_member_sessions=("investing_supplemented_member_sessions", "sum"),
            combined_raw_covered_member_sessions=("combined_raw_covered_member_sessions", "sum"),
            residual_vs_stooq_sessions=("residual_vs_stooq_sessions", "sum"),
        )
    )

    residual = grid.loc[
        grid["residual_vs_stooq"],
        [
            "session_date",
            "isin",
            "security_id",
            "company_name",
            "source_index",
            "bossa_mapping_state",
            "bossa_ticker",
            "bossa_mstall_has_valid_raw_bar",
            "bossa_page_has_valid_raw_bar",
            "stooq_symbol",
            "coverage_state",
        ],
    ].copy()
    residual_by_session = (
        residual.groupby("session_date", as_index=False)
        .agg(
            residual_missing_count=("isin", "size"),
            residual_isins=("isin", lambda values: "|".join(sorted(set(map(str, values))))),
            residual_company_names=(
                "company_name", lambda values: "|".join(sorted(set(map(str, values))))
            ),
        )
    )
    uncovered = grid.loc[
        ~grid["combined_raw_has_bar"],
        [
            "session_date",
            "isin",
            "security_id",
            "company_name",
            "source_index",
            "stooq_has_valid_bar",
            "bossa_mapping_state",
            "bossa_ticker",
            "bossa_mstall_has_valid_raw_bar",
            "bossa_page_has_valid_raw_bar",
            "stooq_symbol",
            "price_exclusion_reason",
            "coverage_state",
        ],
    ].copy()

    total = len(grid)
    stooq_covered = int(grid["stooq_has_valid_bar"].sum())
    bossa_mstall_covered = int(grid["bossa_mstall_has_valid_raw_bar"].sum())
    bossa_page_supplemented = int(grid["bossa_page_supplements_mstall"].sum())
    bossa_covered = int(grid["bossa_has_valid_raw_bar"].sum())
    investing_supplemented = int(grid["investing_supplements_bossa"].sum())
    combined = int(grid["combined_raw_has_bar"].sum())
    residual_count = int(grid["residual_vs_stooq"].sum())
    bossa_covered_vs_stooq = int(
        (grid["stooq_has_valid_bar"] & grid["bossa_has_valid_raw_bar"]).sum()
    )
    bossa_missing_vs_stooq = stooq_covered - bossa_covered_vs_stooq
    investing_supplemented_vs_stooq = int(
        (grid["stooq_has_valid_bar"] & grid["investing_supplements_bossa"]).sum()
    )
    combined_covered_vs_stooq = stooq_covered - residual_count
    state_counts = {str(key): int(value) for key, value in grid["coverage_state"].value_counts().sort_index().items()}
    metrics = {
        "contract": {
            "warmup_start": WARMUP_START.date().isoformat(),
            "evaluation_start": grid["session_date"].min().date().isoformat(),
            "endpoint": endpoint.date().isoformat(),
            "official_denominator_per_session": 60,
            "stooq_role": "coverage_reference_only_not_raw_fallback",
            "raw_preference": ["bossa_mstall", "bossa_session_pages", "existing_investing_com"],
        },
        "counts": {
            "evaluation_sessions": int(grid["session_date"].nunique()),
            "official_member_sessions": total,
            "stooq_covered_member_sessions": stooq_covered,
            "bossa_mstall_covered_member_sessions": bossa_mstall_covered,
            "bossa_page_official_member_rows": len(bossa_page_official),
            "bossa_page_valid_official_member_bars": int(bossa_page_official["valid_raw_bar"].sum()),
            "bossa_page_supplemented_member_sessions": bossa_page_supplemented,
            "bossa_page_exact_stooq_ohlcv_matches": int(
                bossa_page_official["page_exact_match_stooq_ohlcv"].sum()
            ),
            "bossa_covered_member_sessions": bossa_covered,
            "bossa_covered_stooq_member_sessions": bossa_covered_vs_stooq,
            "bossa_missing_stooq_member_sessions": bossa_missing_vs_stooq,
            "investing_supplemented_member_sessions": investing_supplemented,
            "investing_supplemented_stooq_member_sessions": investing_supplemented_vs_stooq,
            "combined_raw_covered_member_sessions": combined,
            "combined_raw_covered_stooq_member_sessions": combined_covered_vs_stooq,
            "combined_raw_uncovered_member_sessions": total - combined,
            "remaining_unexplained_raw_gaps_vs_stooq": residual_count,
            "bossa_covered_share_of_stooq": bossa_covered_vs_stooq / stooq_covered,
            "combined_raw_covered_share_of_stooq": combined_covered_vs_stooq / stooq_covered,
            "additional_investing_histories_needed": int(security_summary["residual_vs_stooq_sessions"].gt(0).sum()),
        },
        "coverage_state_counts": state_counts,
        "bossa_alone_100pct_of_stooq_covered": bossa_missing_vs_stooq == 0,
        "bossa_plus_existing_investing_100pct_of_stooq_covered": residual_count == 0,
        "securities_using_bossa_page_supplement": security_summary.loc[
            security_summary["bossa_page_supplemented_member_sessions"].gt(0),
            ["isin", "company_names", "bossa_page_supplemented_member_sessions"],
        ].to_dict("records"),
        "securities_using_existing_investing_supplement": security_summary.loc[
            security_summary["investing_supplemented_member_sessions"].gt(0),
            ["isin", "company_names", "investing_supplemented_member_sessions"],
        ].to_dict("records"),
        "securities_needing_additional_investing_history": security_summary.loc[
            security_summary["residual_vs_stooq_sessions"].gt(0),
            ["isin", "company_names", "residual_vs_stooq_sessions"],
        ].to_dict("records"),
    }

    invalid_bossa = (
        pd.concat(invalid_bossa_parts, ignore_index=True)
        if invalid_bossa_parts
        else pd.DataFrame(columns=["isin", "bossa_ticker", "session_date", *PRICE_COLUMNS, "volume"])
    )
    invalid_stooq = (
        pd.concat(invalid_stooq_parts, ignore_index=True)
        if invalid_stooq_parts
        else pd.DataFrame(columns=["isin", "stooq_symbol", "session_date", *PRICE_COLUMNS, "volume"])
    )
    invalid_bossa_page = bossa_page_rows.loc[~bossa_page_rows["valid_raw_bar"]].copy()
    write_csv(output / "bossa_identity_map.csv", bossa_map, ["isin"])
    write_csv(
        output / "bossa_page_parsed_rows.csv",
        bossa_page_rows,
        ["session_date", "page_company_name"],
    )
    write_csv(
        output / "bossa_page_official_reconciliation.csv",
        bossa_page_official,
        ["session_date", "isin"],
    )
    write_csv(output / "security_coverage_summary.csv", security_summary, ["isin"])
    write_csv(output / "residual_missing_sessions.csv", residual, ["isin", "session_date"])
    write_csv(output / "residual_by_session_date.csv", residual_by_session, ["session_date"])
    write_csv(output / "all_uncovered_member_sessions.csv", uncovered, ["isin", "session_date"])
    write_csv(output / "invalid_bossa_rows.csv", invalid_bossa, ["isin", "session_date"])
    write_csv(
        output / "invalid_bossa_page_rows.csv",
        invalid_bossa_page,
        ["session_date", "page_company_name"],
    )
    write_csv(output / "invalid_stooq_rows.csv", invalid_stooq, ["isin", "session_date"])
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    script_path = Path(__file__).resolve()
    produced = sorted(path for path in output.iterdir() if path.name != "manifest.json")
    manifest = {
        "script": {"path": str(script_path), "sha256": sha256(script_path)},
        "phase_a_run": {
            "path": str(args.phase_a_run.resolve()),
            "manifest_sha256": sha256(args.phase_a_run.resolve() / "manifest.json"),
            "research_panel_sha256": sha256(artifacts / "research_panel.parquet"),
        },
        "identity_map": {"path": str(symbol_map_path), "sha256": sha256(symbol_map_path)},
        "bossa_page_reference_manifest": {
            "path": str(bossa_page_manifest_path),
            "sha256": sha256(bossa_page_manifest_path),
        },
        "investing_reference_manifest": {
            "path": str(investing_manifest_path),
            "sha256": sha256(investing_manifest_path),
        },
        "bossa_inputs": bossa_inputs,
        "bossa_page_inputs": bossa_page_inputs,
        "stooq_inputs": stooq_inputs,
        "investing_inputs": investing_inputs,
        "outputs": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in produced},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
