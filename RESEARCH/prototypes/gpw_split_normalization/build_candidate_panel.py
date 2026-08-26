from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import polars as pl
import pyarrow.parquet as pq

from ats_research.gpw_split_adjustment import (
    NATIVE_BASIS,
    logical_split_output_hash,
    select_whole_bars,
    transform_split_adjusted,
)
from ats_research.investing_manual import parse_investing_manual_history


PRICE = ("open", "high", "low", "close")
ACCEPTED_YAHOO = {
    "PLBGZ0000010": "PLBGZ0000010_BNPPPL_BNP_WA",
    "PLLCCRP00017": "PLLCCRP00017_DEVELIA_DVL_WA",
    "PLR220000018": "PLR220000018_CYBERFLKS_CBF_WA",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def series_version(source: str, isin: str, digest: str) -> str:
    return f"{source}:{isin}:{digest}"


def native_frame(
    frame: pd.DataFrame,
    *,
    isin: str,
    source: str,
    priority: int,
    source_path: Path,
    digest: str,
    volume_basis: str,
    precision: str,
) -> pd.DataFrame:
    result = frame[["session_date", *PRICE, "volume"]].copy()
    result["security_id"] = f"isin:{isin}"
    result["isin"] = isin
    result["selected_source"] = source
    result["source_priority"] = priority
    result["source_series_version"] = series_version(source, isin, digest)
    result["data_basis"] = NATIVE_BASIS
    for column in PRICE:
        result[f"native_{column}"] = pd.to_numeric(result.pop(column), errors="raise")
    result["native_volume"] = pd.to_numeric(result.pop("volume"), errors="coerce")
    result["volume_basis"] = volume_basis
    result["volume_precision_state"] = precision
    result.loc[result["native_volume"].isna(), "volume_basis"] = "missing"
    result.loc[result["native_volume"].isna(), "volume_precision_state"] = "missing_volume"
    result["volume_usable_for_relative_volume"] = result["native_volume"].notna() & result[
        "volume_precision_state"
    ].isin(["exact_source_reported_shares", "vendor_displayed_rounded_volume"])
    result["volume_ineligibility_reason"] = ""
    result.loc[result["native_volume"].isna(), "volume_ineligibility_reason"] = "missing_volume"
    result.loc[result["volume_precision_state"].eq("unknown_precision"), "volume_ineligibility_reason"] = (
        "unknown_volume_precision"
    )
    result["source_lineage"] = str(source_path.resolve())
    result["source_hash"] = digest
    return result


def load_bossa(path: Path, isin: str) -> pd.DataFrame:
    digest = sha256(path)
    frame = pd.read_csv(path)
    frame.columns = [str(value).strip("<>").lower() for value in frame.columns]
    frame["session_date"] = pd.to_datetime(frame["dtyyyymmdd"].astype(str), format="%Y%m%d")
    frame = frame.rename(columns={"vol": "volume"})
    return native_frame(
        frame,
        isin=isin,
        source="bossa_mstall",
        priority=1,
        source_path=path,
        digest=digest,
        volume_basis="shares",
        precision="exact_source_reported_shares",
    )


def load_page_supplements(
    root: Path, identities: pd.DataFrame, symbol_map: pd.DataFrame
) -> tuple[list[pd.DataFrame], list[dict[str, Any]]]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    page_frames: list[pd.DataFrame] = []
    inputs: list[dict[str, Any]] = []
    for item in manifest["outputs"]:
        if not str(item["filename"]).endswith(".mst"):
            continue
        path = root / str(item["filename"])
        digest = sha256(path)
        if digest != item["sha256"]:
            raise ValueError("Bossa session supplement hash mismatch")
        frame = pd.read_csv(path)
        frame.columns = [str(value).strip("<>").lower() for value in frame.columns]
        frame["session_date"] = pd.to_datetime(frame["dtyyyymmdd"].astype(str), format="%Y%m%d")
        frame["page_ticker"] = frame["ticker"].astype(str).str.upper()
        frame = frame.rename(columns={"vol": "volume"})
        page_frames.append(frame)
        inputs.append({"path": str(path.resolve()), "sha256": digest, "bytes": path.stat().st_size})
    pages = pd.concat(page_frames, ignore_index=True)

    source_manifest_path = Path(manifest["source_manifest"]["path"])
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    identity_rows: list[dict[str, Any]] = []
    marker = "Pokaż transakcje "
    for item in source_manifest["files"]:
        path = source_manifest_path.parent / item["filename"]
        for position, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines()):
            if line.startswith(marker):
                company = line[len(marker) :].strip().upper()
                chart = re.fullmatch(r"(\S+) Wykres (.+)", path.read_text(encoding="utf-8-sig").splitlines()[position + 2].strip())
                if chart:
                    identity_rows.append({"session_date": pd.Timestamp(item["session_date"]), "page_company_name": company, "page_ticker": chart.group(1).upper()})
    identity_pages = pd.DataFrame(identity_rows)
    aliases = (
        symbol_map.loc[symbol_map["status"].isin(["exact", "mapped_renamed", "mapped_successor"])]
        .dropna(subset=["stooq_symbol"])
        .groupby("isin")["stooq_symbol"]
        .agg(lambda values: set(str(value).upper() for value in values))
        .to_dict()
    )
    outputs: list[pd.DataFrame] = []
    for row in identities.itertuples(index=False):
        names = set(str(row.company_names).upper().split("|")) | aliases.get(str(row.isin), set())
        matches = identity_pages.loc[
            identity_pages["page_ticker"].isin(names) | identity_pages["page_company_name"].isin(names)
        ]
        if matches.empty:
            continue
        matched = pages.merge(matches[["session_date", "page_ticker"]], on=["session_date", "page_ticker"], how="inner")
        for digest, group in matched.groupby(matched["session_date"].astype(str), sort=True):
            source_item = next(item for item in inputs if digest.replace("-", "") in Path(item["path"]).stem)
            outputs.append(
                native_frame(
                    group,
                    isin=str(row.isin),
                    source="bossa_session_page",
                    priority=2,
                    source_path=Path(source_item["path"]),
                    digest=source_item["sha256"],
                    volume_basis="shares",
                    precision="exact_source_reported_shares",
                )
            )
    return outputs, inputs


def load_sources(args: argparse.Namespace, spans: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, pd.DataFrame]]:
    identity_map = pd.read_csv(args.corrected_audit / "bossa_identity_map.csv")
    frames: list[pd.DataFrame] = []
    inputs: list[dict[str, Any]] = []
    raw_by_source: dict[str, pd.DataFrame] = {}
    for row in identity_map.itertuples(index=False):
        if pd.isna(row.bossa_file):
            continue
        path = Path(str(row.bossa_file))
        loaded = load_bossa(path, str(row.isin))
        frames.append(loaded)
        raw_by_source[f"bossa:{row.isin}"] = loaded
        inputs.append({"source": "bossa_mstall", "isin": str(row.isin), "path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size})

    symbol_map = pd.read_csv(args.data_root / "reference" / "gpw_indices" / "stooq_symbol_map.csv")
    page_frames, page_inputs = load_page_supplements(args.bossa_session_root, identity_map, symbol_map)
    frames.extend(page_frames)
    inputs.extend({"source": "bossa_session_page", **item} for item in page_inputs)

    investing_manifest = json.loads((args.investing_root / "reference_manifest.json").read_text(encoding="utf-8"))
    for item in investing_manifest["files"]:
        path = args.investing_root / item["filename"]
        parsed = parse_investing_manual_history(path, allow_missing_display_volume=True, allow_dot_thousands_in_prices=True)
        loaded = native_frame(
            parsed.bars,
            isin=str(item["isin"]),
            source="investing_com",
            priority=3,
            source_path=path,
            digest=sha256(path),
            volume_basis="vendor_displayed_shares",
            precision="vendor_displayed_rounded_volume",
        )
        frames.append(loaded)
        raw_by_source[f"investing:{item['isin']}"] = loaded
        inputs.append({"source": "investing_com", "isin": item["isin"], "path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size})

    for isin, folder in ACCEPTED_YAHOO.items():
        path = args.yahoo_root / folder / "normalized_daily.csv"
        frame = pd.read_csv(path)
        frame["session_date"] = pd.to_datetime(frame["session_date"])
        loaded = native_frame(
            frame,
            isin=isin,
            source="yahoo_finance_accepted_clean_wse_series",
            priority=4,
            source_path=path,
            digest=sha256(path),
            volume_basis="shares_unknown_vendor_derivation",
            precision="unknown_precision",
        )
        frames.append(loaded)
        raw_by_source[f"yahoo:{isin}"] = loaded
        inputs.append({"source": "yahoo_finance_accepted_clean_wse_series", "isin": isin, "path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size})

    selected = select_whole_bars(frames)
    span_lookup = spans.set_index("isin")[["consumed_start", "consumed_end"]]
    selected = selected.loc[
        [
            isin in span_lookup.index
            and pd.Timestamp(date) >= pd.Timestamp(span_lookup.loc[isin, "consumed_start"])
            and pd.Timestamp(date) <= pd.Timestamp(span_lookup.loc[isin, "consumed_end"])
            for isin, date in zip(selected["isin"], selected["session_date"])
        ]
    ].copy()
    return selected, inputs, raw_by_source


def build_spans(audit: pd.DataFrame, wig_sessions: pd.DatetimeIndex, config: dict[str, Any]) -> pd.DataFrame:
    floor = pd.Timestamp(config["history_floor"])
    endpoint = pd.Timestamp(config["evaluation_end"])
    positions = {pd.Timestamp(value): index for index, value in enumerate(wig_sessions)}
    rows = []
    for isin, group in audit.groupby("isin", sort=True):
        first = pd.Timestamp(group["session_date"].min())
        last = pd.Timestamp(group["session_date"].max())
        start = max(floor, pd.Timestamp(wig_sessions[max(0, positions[first] - 252)]))
        forward_position = positions[last] + int(config["forward_label_horizon_sessions"])
        uncapped = pd.Timestamp(wig_sessions[forward_position]) if forward_position < len(wig_sessions) else pd.NaT
        consumed_end = min(endpoint, uncapped) if pd.notna(uncapped) else endpoint
        rows.append({
            "security_id": f"isin:{isin}", "isin": isin,
            "company_names": "|".join(sorted(set(group["company_name"].astype(str)))),
            "first_official_session": first, "last_official_session": last,
            "consumed_start": start, "consumed_end": consumed_end,
            "feature_lookback_sessions": 252, "forward_label_horizon_sessions": int(config["forward_label_horizon_sessions"]),
            "uncapped_forward_label_end": uncapped,
            "endpoint_censors_forward_window": pd.isna(uncapped) or uncapped > endpoint,
        })
    return pd.DataFrame(rows)


def full_session_panel(selected: pd.DataFrame, spans: pd.DataFrame, wig_sessions: pd.DatetimeIndex) -> pd.DataFrame:
    grids = []
    for row in spans.itertuples(index=False):
        dates = wig_sessions[(wig_sessions >= pd.Timestamp(row.consumed_start)) & (wig_sessions <= pd.Timestamp(row.consumed_end))]
        grids.append(pd.DataFrame({"security_id": row.security_id, "isin": row.isin, "session_date": dates}))
    grid = pd.concat(grids, ignore_index=True)
    panel = grid.merge(selected, on=["security_id", "isin", "session_date"], how="left", validate="one_to_one")
    missing = panel["selected_source"].isna()
    panel.loc[missing, "selected_source"] = "explicit_missing"
    panel.loc[missing, "source_series_version"] = "explicit_missing:v1"
    panel.loc[missing, "data_basis"] = NATIVE_BASIS
    panel.loc[missing, "volume_basis"] = "missing"
    panel.loc[missing, "volume_precision_state"] = "missing_volume"
    panel.loc[missing, "volume_usable_for_relative_volume"] = False
    panel.loc[missing, "volume_ineligibility_reason"] = "missing_volume"
    panel.loc[missing, "source_lineage"] = "explicit_missing"
    panel.loc[missing, "source_hash"] = ""
    panel["missing_state"] = ""
    panel.loc[missing, "missing_state"] = "no_selected_source_observation"
    return panel


def anomaly_scan(panel: pd.DataFrame, data_root: Path) -> pd.DataFrame:
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    observed = panel.loc[panel["native_close"].notna()].sort_values(["isin", "session_date"])
    for isin, group in observed.groupby("isin", sort=True):
        work = group.copy()
        work["native_price_ratio"] = work["native_close"] / work["native_close"].shift()
        work["native_volume_ratio"] = work["native_volume"] / work["native_volume"].shift()
        for row in work.loc[work["native_price_ratio"].le(0.5) | work["native_price_ratio"].ge(2.0)].itertuples(index=False):
            key = (isin, str(pd.Timestamp(row.session_date).date()))
            candidates[key] = {"isin": isin, "candidate_session": key[1], "triggers": "large_native_price_scale_discontinuity", "native_price_ratio": row.native_price_ratio, "native_volume_ratio": row.native_volume_ratio, "selected_source": row.selected_source}

    symbol_map = pd.read_csv(data_root / "reference" / "gpw_indices" / "stooq_symbol_map.csv")
    mappings = symbol_map.loc[symbol_map["status"].isin(["exact", "mapped_renamed", "mapped_successor"])].dropna(subset=["stooq_symbol"])
    for row in mappings.drop_duplicates("isin").itertuples(index=False):
        path = data_root / "daily" / "pl" / "wse stocks" / f"{str(row.stooq_symbol).lower()}.txt"
        if not path.is_file():
            continue
        stooq = pd.read_csv(path)
        stooq.columns = [str(value).strip("<>").lower() for value in stooq.columns]
        stooq["session_date"] = pd.to_datetime(stooq["date"].astype(str), format="%Y%m%d")
        native = observed.loc[observed["isin"].eq(str(row.isin)), ["session_date", "native_close"]]
        joined = native.merge(stooq[["session_date", "close"]], on="session_date", how="inner")
        joined["native_to_stooq"] = joined["native_close"] / joined["close"]
        joined["ratio_regime_change"] = joined["native_to_stooq"] / joined["native_to_stooq"].shift()
        for candidate in joined.loc[joined["ratio_regime_change"].le(0.5) | joined["ratio_regime_change"].ge(2.0)].itertuples(index=False):
            key = (str(row.isin), str(pd.Timestamp(candidate.session_date).date()))
            existing = candidates.setdefault(key, {"isin": key[0], "candidate_session": key[1], "triggers": "", "native_price_ratio": None, "native_volume_ratio": None, "selected_source": ""})
            triggers = set(filter(None, str(existing["triggers"]).split("|"))) | {"stable_cross_source_ratio_regime_change"}
            existing["triggers"] = "|".join(sorted(triggers))
            existing["native_to_stooq_ratio_change"] = candidate.ratio_regime_change
    return pd.DataFrame(sorted(candidates.values(), key=lambda item: (item["isin"], item["candidate_session"])))


def treatments_for_panel(policy: dict[str, Any], events: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for event in events.itertuples(index=False):
        series = panel.loc[panel["security_id"].eq(event.security_id), ["selected_source", "source_series_version", "source_hash"]].drop_duplicates()
        for item in series.itertuples(index=False):
            matches = [entry for entry in policy["event_treatments"] if entry["event_id"] == event.event_id and entry["selected_source"] == item.selected_source]
            if len(matches) != 1:
                raise ValueError(f"missing or duplicate treatment policy for {event.event_id}/{item.selected_source}")
            match = matches[0]
            if match.get("input_file_sha256") and match["input_file_sha256"].lower() != str(item.source_hash).lower():
                raise ValueError("treatment input file hash mismatch")
            rows.append({"event_id": event.event_id, "source_series_version": item.source_series_version, "selected_source": item.selected_source, "source_hash": item.source_hash, "treatment_state": match["treatment_state"]})
    return pd.DataFrame(rows)


def write_csv(path: Path, frame: pd.DataFrame, sort: list[str]) -> None:
    output = frame.sort_values(sort, kind="mergesort").copy()
    for column in output.select_dtypes(include=["datetime64[ns]"]).columns:
        output[column] = output[column].dt.strftime("%Y-%m-%d")
    output.to_csv(path, index=False, lineterminator="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--corrected-audit", type=Path, required=True)
    parser.add_argument("--bossa-session-root", type=Path, required=True)
    parser.add_argument("--investing-root", type=Path, required=True)
    parser.add_argument("--yahoo-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--treatment-policy", type=Path, required=True)
    parser.add_argument("--dispositions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument("--repository-evidence-dir", type=Path)
    args = parser.parse_args()
    args.data_root = args.data_root.resolve()
    args.corrected_audit = args.corrected_audit.resolve()
    args.bossa_session_root = args.bossa_session_root.resolve()
    args.investing_root = args.investing_root.resolve()
    args.yahoo_root = args.yahoo_root.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable output {output}")
    output.mkdir(parents=True)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    audit = pd.read_csv(args.corrected_audit / "member_session_audit.csv", low_memory=False)
    audit["session_date"] = pd.to_datetime(audit["session_date"])
    wig = pd.read_csv(args.data_root / "daily" / "pl" / "wse indices" / "wig.txt")
    wig.columns = [str(value).strip("<>").lower() for value in wig.columns]
    wig_sessions = pd.DatetimeIndex(pd.to_datetime(wig["date"].astype(str), format="%Y%m%d").sort_values().unique())
    spans = build_spans(audit, wig_sessions, config)
    selected, inputs, _ = load_sources(args, spans)
    panel = full_session_panel(selected, spans, wig_sessions)
    candidates = anomaly_scan(panel, args.data_root)
    write_csv(output / "consumed_spans.csv", spans, ["isin"])
    write_csv(output / "numerical_candidates_raw.csv", candidates, ["isin", "candidate_session"])
    if args.scan_only:
        return 0

    if args.dispositions is None:
        raise ValueError("final build requires candidate dispositions")
    dispositions = pd.read_csv(args.dispositions)
    candidate_keys = set(zip(candidates["isin"], candidates["candidate_session"])) if not candidates.empty else set()
    disposition_keys = set(zip(dispositions["isin"], dispositions["candidate_session"]))
    if candidate_keys != disposition_keys:
        raise ValueError(f"candidate disposition mismatch: missing={candidate_keys-disposition_keys}, extra={disposition_keys-candidate_keys}")
    if dispositions["disposition"].eq("unresolved").any():
        raise ValueError("unresolved detected candidate blocks final panel")

    event_payload = json.loads(args.events.read_text(encoding="utf-8"))
    events = pd.DataFrame(event_payload["events"])
    policy = json.loads(args.treatment_policy.read_text(encoding="utf-8"))
    treatments = treatments_for_panel(policy, events, panel)
    transformed = transform_split_adjusted(panel, events, treatments, factor_version=config["transformation_version"])

    member_fields = audit[["isin", "session_date", "source_index", "official_membership", "expected_trading", "nontrading_reason", "nontrading_evidence_reference", "coverage_result", "unresolved_or_missing_state"]]
    transformed = transformed.merge(member_fields, on=["isin", "session_date"], how="left", validate="many_to_one")
    transformed["official_membership"] = transformed["official_membership"].fillna(False).astype(bool)
    transformed["price_usable_for_features"] = transformed["split_adjusted_close"].notna()
    transformed["data_basis_version"] = config["data_basis_version"]

    discovery_rows = []
    candidate_isins = set(candidates["isin"]) if not candidates.empty else set()
    for row in spans.itertuples(index=False):
        targeted = row.isin in candidate_isins
        discovery_rows.append({
            "security_id": row.security_id, "isin": row.isin, "company_names": row.company_names,
            "searched_start": row.consumed_start, "searched_end": row.consumed_end, "date_checked": "2026-08-26",
            "sources_checked": "KDPW Data Portal GET/events and GET/events_2; issuer current reports/ESPI targeted when numerical candidate detected" if targeted else "KDPW Data Portal GET/events and GET/events_2",
            "query_or_retrieval_method": f"ISIN={row.isin}; event types split/reverse split/consolidation",
            "events_returned": "Dino confirmed event" if row.isin == "PLDINPL00011" else "none established",
            "complete_coverage_claim": False,
            "limitations_or_failed_searches": "KDPW corporate-event report is paid package 4 and no entitlement was available; public ESPI/issuer search has no demonstrable exhaustive per-ISIN interval guarantee",
        })
    discovery = pd.DataFrame(discovery_rows)

    official = transformed.loc[transformed["official_membership"]]
    counts = official["selected_source"].value_counts().to_dict()
    expected_counts = {"bossa_mstall": 91415, "bossa_session_page": 85, "investing_com": 8221, "explicit_missing": 59}
    for source, expected in expected_counts.items():
        if int(counts.get(source, 0)) != expected:
            raise ValueError(f"official source count mismatch for {source}: {counts.get(source,0)} != {expected}")
    per_session = official.groupby("session_date").agg(rows=("isin", "size"), identities=("isin", "nunique"))
    if not per_session["rows"].eq(60).all() or not per_session["identities"].eq(60).all():
        raise ValueError("fixed universe denominator failure")

    dino = transformed.loc[transformed["isin"].eq("PLDINPL00011") & transformed["session_date"].isin(pd.to_datetime(["2025-07-30", "2025-07-31"]))]
    dino = dino.sort_values("session_date")
    if list(dino["native_close"]) != [502.0, 49.61] or list(dino["split_adjusted_close"].round(2)) != [50.20, 49.61]:
        raise ValueError("Dino golden transformation mismatch")
    dino_return = float(dino["split_adjusted_close"].iloc[1] / dino["split_adjusted_close"].iloc[0] - 1)
    native_return = float(dino["native_close"].iloc[1] / dino["native_close"].iloc[0] - 1)

    panel_path = output / "candidate_panel.parquet"
    transformed.to_parquet(panel_path, index=False, compression="zstd")
    arrow_rows = pq.read_table(panel_path).num_rows
    polars_rows = pl.scan_parquet(panel_path).select(pl.len()).collect().item()
    duck_rows = duckdb.connect().execute("select count(*) from read_parquet(?)", [str(panel_path)]).fetchone()[0]
    if len(transformed) != arrow_rows or len(transformed) != polars_rows or len(transformed) != duck_rows:
        raise ValueError("cross-engine row count mismatch")

    write_csv(output / "discovery_log.csv", discovery, ["isin"])
    write_csv(output / "numerical_candidate_dispositions.csv", dispositions, ["isin", "candidate_session"])
    write_csv(output / "source_event_treatments.csv", treatments, ["event_id", "source_series_version"])
    (output / "confirmed_event_ledger.json").write_text(json.dumps(event_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validation = {
        "authoritative_event_discovery_coverage": "NOT PROVEN",
        "detected_event_and_anomaly_resolution": "PASS",
        "candidate_count": len(candidates),
        "unresolved_candidate_count": int(dispositions["disposition"].eq("unresolved").sum()),
        "dino": {"native_close": [502.0, 49.61], "split_adjusted_close": [50.2, 49.61], "native_return": native_return, "split_adjusted_price_return": dino_return},
        "native_observations_preserved": transformed[[*['native_'+c for c in PRICE], 'native_volume']].equals(panel[[*['native_'+c for c in PRICE], 'native_volume']]),
        "unaffected_derived_equal_native": bool((transformed.loc[transformed["applied_event_ids"].eq(""), "split_adjusted_close"].fillna(-1) == transformed.loc[transformed["applied_event_ids"].eq(""), "native_close"].fillna(-1)).all()),
        "official_member_sessions": len(official), "expected_trading_member_sessions": int(official["expected_trading"].fillna(False).sum()),
        "covered_expected_trading_member_sessions": int((official["expected_trading"].fillna(False) & official["native_close"].notna()).sum()),
        "official_source_counts": {str(k): int(v) for k,v in counts.items()},
        "cross_engine_rows": {"arrow": arrow_rows, "polars": polars_rows, "duckdb": duck_rows},
        "cash_distributions_included": False, "cash_dividend_price_gaps_preserved": True,
    }
    (output / "validation_results.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    environment = Path("D:/Stock/ATS/RESEARCH/environment/environment.yml")
    produced = sorted(path for path in output.iterdir() if path.name != "manifest.json")
    manifest = {
        "run_id": config["pinned_run_id"],
        "schema_version": "ats.gpw_split_candidate_manifest.v1",
        "checkpoint_1a_evidence_commit": config["checkpoint_1a_evidence_commit"],
        "code_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd="D:/Stock/ATS", text=True, capture_output=True, check=True).stdout.strip(),
        "code_files": {str(Path(__file__).resolve()): sha256(Path(__file__).resolve()), "D:/Stock/ATS/source/python/src/ats_research/gpw_split_adjustment.py": sha256(Path("D:/Stock/ATS/source/python/src/ats_research/gpw_split_adjustment.py"))},
        "configuration": config,
        "configuration_sha256": sha256(args.config),
        "input_hashes": inputs,
        "corrected_audit_manifest_sha256": sha256(args.corrected_audit / "manifest.json"),
        "event_ledger_hash": sha256(args.events),
        "discovery_log_hash": sha256(output / "discovery_log.csv"),
        "environment_lock": {"path": str(environment), "sha256": sha256(environment)},
        "row_counts": {"candidate_panel": len(transformed), "official_member_sessions": len(official)},
        "source_counts": {str(k): int(v) for k,v in transformed["selected_source"].value_counts().to_dict().items()},
        "native_logical_hash": logical_split_output_hash(transformed[["security_id","session_date",*['native_'+c for c in PRICE],"native_volume","selected_source","source_series_version"]]),
        "adjusted_logical_hash": logical_split_output_hash(transformed[["security_id","session_date",*['split_adjusted_'+c for c in PRICE],"split_adjusted_volume","cumulative_price_factor","cumulative_volume_factor","applied_event_ids"]]),
        "physical_file_hashes": {path.name: sha256(path) for path in produced},
        "unresolved_event_count": 0,
        "authoritative_discovery_status": "NOT PROVEN",
        "transformation_version": config["transformation_version"],
        "data_basis_version": config["data_basis_version"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.repository_evidence_dir:
        repo = args.repository_evidence_dir.resolve()
        repo.mkdir(parents=True, exist_ok=False)
        for name in ("consumed_spans.csv", "discovery_log.csv", "confirmed_event_ledger.json", "numerical_candidate_dispositions.csv", "source_event_treatments.csv", "validation_results.json"):
            (repo / name).write_bytes((output / name).read_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
