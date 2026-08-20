from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd


SECURITY_NAMESPACE = uuid.UUID("6398c638-d145-5bee-82c2-1c165adea4df")
RESOLVED_VENDOR_STATUSES = frozenset({"exact", "mapped_renamed", "mapped_successor"})


class IdentityResolutionError(ValueError):
    pass


def stable_security_id(isin: str | None, venue_mic: str = "XWAR") -> str | None:
    if isin is None or pd.isna(isin) or not str(isin).strip():
        return None
    raw = str(isin).strip().upper()
    return str(uuid.uuid5(SECURITY_NAMESPACE, f"{venue_mic}:{raw}"))


@dataclass(frozen=True)
class IdentityTables:
    security_master: pd.DataFrame
    aliases: pd.DataFrame
    vendor_resolution: pd.DataFrame


def _collapse_vendor_mapping(mapping: pd.DataFrame, isins: set[str]) -> pd.DataFrame:
    selected = mapping.loc[mapping["isin"].isin(isins)].copy()
    rows: list[dict[str, object]] = []
    priority = {"exact": 0, "mapped_renamed": 1, "mapped_successor": 2, "missing": 9, "ambiguous": 10}
    for isin, group in selected.groupby("isin", sort=True):
        symbols = sorted(set(group["stooq_symbol"].dropna().astype(str)))
        resolved = group.loc[group["status"].isin(RESOLVED_VENDOR_STATUSES)]
        if len(symbols) > 1:
            raise IdentityResolutionError(f"multiple vendor symbols for {isin}: {symbols}")
        if not resolved.empty and len(symbols) != 1:
            raise IdentityResolutionError(f"resolved mapping for {isin} has no unique symbol")
        statuses = sorted(set(group["status"].dropna().astype(str)), key=lambda x: priority.get(x, 99))
        status = statuses[0] if statuses else "unresolved"
        if status == "ambiguous":
            raise IdentityResolutionError(f"ambiguous vendor mapping for {isin}")
        rows.append(
            {
                "isin": isin,
                "stooq_symbol": symbols[0] if symbols else None,
                "vendor_resolution_status": status,
                "valid_from": pd.to_datetime(group["valid_from"], errors="coerce").min(),
                "valid_to": pd.to_datetime(group["valid_to"], errors="coerce").max(),
                "mapping_provenance": " | ".join(sorted(set(group["evidence"].dropna().astype(str)))),
                "mapping_confidence": " | ".join(sorted(set(group["confidence"].dropna().astype(str)))),
            }
        )
    missing_isins = isins - set(selected["isin"])
    rows.extend(
        {
            "isin": isin,
            "stooq_symbol": None,
            "vendor_resolution_status": "unresolved",
            "valid_from": pd.NaT,
            "valid_to": pd.NaT,
            "mapping_provenance": "no row in stooq_symbol_map.csv",
            "mapping_confidence": "none",
        }
        for isin in sorted(missing_isins)
    )
    result = pd.DataFrame(rows)
    result["security_id"] = result["isin"].map(stable_security_id)
    return result.sort_values("isin").reset_index(drop=True)


def build_identity_tables(
    membership_intervals: pd.DataFrame,
    mapping_path: Path,
    venue_mic: str,
) -> IdentityTables:
    membership = membership_intervals.copy()
    membership["security_id"] = membership["isin"].map(lambda value: stable_security_id(value, venue_mic))
    if membership["security_id"].isna().any():
        bad = membership.loc[membership["security_id"].isna(), "raw_identifier"].drop_duplicates().tolist()
        raise IdentityResolutionError(f"official membership rows lack resolvable ISIN identity: {bad}")
    mapping = pd.read_csv(mapping_path)
    vendor = _collapse_vendor_mapping(mapping, set(membership["isin"].astype(str)))
    vendor["security_id"] = vendor["isin"].map(lambda value: stable_security_id(value, venue_mic))

    spans = membership.groupby(["security_id", "isin"], as_index=False).agg(
        valid_from=("effective_from", "min"), valid_to=("effective_to", "max")
    )
    master = spans[["security_id", "valid_from", "valid_to"]].copy()
    master["issuer_id"] = None
    master["instrument_type"] = "common_equity"
    master["base_currency"] = "PLN"
    master["status"] = "known_official_member"
    master = master[["security_id", "issuer_id", "instrument_type", "base_currency", "valid_from", "valid_to", "status"]]

    alias_rows: list[dict[str, object]] = []
    for row in spans.itertuples(index=False):
        for identifier_type, identifier_value in (("isin", row.isin), ("venue_mic", venue_mic)):
            alias_rows.append(
                {
                    "security_id": row.security_id,
                    "identifier_type": identifier_type,
                    "identifier_value": identifier_value,
                    "raw_identifier": identifier_value,
                    "venue_mic": venue_mic,
                    "vendor": None,
                    "valid_from": row.valid_from,
                    "valid_to": row.valid_to,
                    "source": "official_gpwbenchmark_membership",
                    "provenance": "official snapshot ISIN / configured listing venue",
                    "resolution_status": "resolved",
                }
            )
    names = membership[["security_id", "company_name", "effective_from", "effective_to", "source_path"]].drop_duplicates()
    for row in names.itertuples(index=False):
        alias_rows.append(
            {
                "security_id": row.security_id,
                "identifier_type": "official_short_name",
                "identifier_value": row.company_name,
                "raw_identifier": row.company_name,
                "venue_mic": venue_mic,
                "vendor": None,
                "valid_from": row.effective_from,
                "valid_to": row.effective_to,
                "source": "official_gpwbenchmark_membership",
                "provenance": row.source_path,
                "resolution_status": "resolved",
            }
        )
    raw_tickers = membership.loc[membership["historical_ticker"].notna(), ["security_id", "historical_ticker", "effective_from", "effective_to", "source_path"]].drop_duplicates()
    for row in raw_tickers.itertuples(index=False):
        alias_rows.append(
            {
                "security_id": row.security_id,
                "identifier_type": "ticker",
                "identifier_value": row.historical_ticker,
                "raw_identifier": row.historical_ticker,
                "venue_mic": venue_mic,
                "vendor": None,
                "valid_from": row.effective_from,
                "valid_to": row.effective_to,
                "source": "official_gpwbenchmark_membership",
                "provenance": row.source_path,
                "resolution_status": "resolved",
            }
        )
    for row in vendor.itertuples(index=False):
        alias_rows.append(
            {
                "security_id": row.security_id,
                "identifier_type": "vendor_symbol",
                "identifier_value": row.stooq_symbol,
                "raw_identifier": row.stooq_symbol,
                "venue_mic": venue_mic,
                "vendor": "stooq",
                "valid_from": row.valid_from,
                "valid_to": row.valid_to,
                "source": "stooq_symbol_map.csv",
                "provenance": row.mapping_provenance,
                "resolution_status": row.vendor_resolution_status,
            }
        )
    aliases = pd.DataFrame(alias_rows).sort_values(["security_id", "identifier_type", "valid_from"], na_position="last").reset_index(drop=True)
    return IdentityTables(master.reset_index(drop=True), aliases, vendor)


def resolve_alias(aliases: pd.DataFrame, identifier_type: str, value: str, as_of: date) -> str | None:
    date_value = pd.Timestamp(as_of)
    candidates = aliases.loc[
        aliases["identifier_type"].eq(identifier_type)
        & aliases["identifier_value"].eq(value)
        & (aliases["valid_from"].isna() | aliases["valid_from"].le(date_value))
        & (aliases["valid_to"].isna() | aliases["valid_to"].ge(date_value))
        & aliases["resolution_status"].isin(["resolved", *RESOLVED_VENDOR_STATUSES])
    ]
    ids = candidates["security_id"].dropna().unique()
    if len(ids) > 1:
        raise IdentityResolutionError(f"ambiguous alias {identifier_type}:{value} at {as_of}")
    return str(ids[0]) if len(ids) == 1 else None

