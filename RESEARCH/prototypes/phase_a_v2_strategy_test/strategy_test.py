from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import uuid
from collections import defaultdict
from datetime import datetime, time, timezone
from decimal import Decimal, ROUND_DOWN, getcontext
from importlib import metadata
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ats_contracts.portfolio import (
    CorporateActionInput,
    CorporateActionType,
    ExcludedMemberState,
    SecurityEventInput,
    SecurityEventType,
    TargetWeightIntent,
)
from ats_portfolio.config import PortfolioConfig
from ats_portfolio.engine import DailyPortfolioEngine, EngineResult
from ats_portfolio.market import MarketBar
from ats_portfolio.numeric import money


getcontext().prec = 38
ROOT = Path(__file__).resolve().parent
WARSAW = ZoneInfo("Europe/Warsaw")
LINEAGE = {
    "isin:PLLOTOS00025": "ORLEN_MERGER_LINEAGE",
    "isin:PLPGNIG00014": "ORLEN_MERGER_LINEAGE",
    "isin:PLPKN0000018": "ORLEN_MERGER_LINEAGE",
}
EXIT_ACTIONS = {
    "LU1642887738": {"kind": "cash_takeover", "effective": "2020-12-23", "cash": "39.00"},
    "PLLOTOS00025": {"kind": "merger", "effective": "2022-08-12", "related": "PLPKN0000018", "ratio": "1.075"},
    "PLPGNIG00014": {"kind": "merger", "effective": "2022-11-18", "related": "PLPKN0000018", "ratio": "0.0925"},
    "PLSTSHL00012": {"kind": "cash_takeover", "effective": "2023-10-10", "cash": "24.80"},
    "PLCIECH00018": {"kind": "cash_takeover", "effective": "2023-11-17", "cash": "54.25"},
    "PLTIM0000016": {"kind": "cash_takeover", "effective": "2024-03-07", "cash": "50.69"},
}


def load_effective_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "base_config" not in raw:
        return raw
    base_path = Path(raw["base_config"])
    actual = sha256_file(base_path)
    if actual != raw["base_config_sha256"]:
        raise RuntimeError(f"base config hash mismatch: expected {raw['base_config_sha256']}, got {actual}")
    base = json.loads(base_path.read_text(encoding="utf-8"))
    base.update(raw["overrides"])
    base["config_correction"] = {
        "overlay_path": path.resolve().as_posix(),
        "overlay_sha256": sha256_file(path),
        "base_config_path": base_path.resolve().as_posix(),
        "base_config_sha256": actual,
        "correction_scope": raw["correction_scope"],
    }
    return base


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def object_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stable_frame_hash(frame: pd.DataFrame) -> str:
    work = frame.copy()
    for column in work.columns:
        if pd.api.types.is_datetime64_any_dtype(work[column]):
            work[column] = work[column].dt.strftime("%Y-%m-%dT%H:%M:%S")
    work = work.fillna("").astype(str)
    rows = work.to_dict("records")
    return object_hash(rows)


def validate_pins(config: dict[str, Any]) -> dict[str, str]:
    paths = {
        "candidate_manifest": Path(config["candidate_run"]) / "manifest.json",
        "candidate_panel": Path(config["candidate_run"]) / "candidate_panel.parquet",
        "phase_a_v2_panel": Path(config["phase_a_v2_run"]) / "adapted_new_panel.parquet",
        "exit_evidence": Path(config["accepted_exit_evidence"]),
        "dino_manifest": Path(config["dino_correction_run"]) / "manifest.json",
    }
    expected = {
        "candidate_manifest": config["candidate_manifest_sha256"],
        "candidate_panel": config["candidate_panel_physical_sha256"],
        "phase_a_v2_panel": config["phase_a_v2_adapted_panel_sha256"],
        "exit_evidence": config["accepted_exit_evidence_sha256"],
    }
    if config.get("play_exit_supplement"):
        paths["play_exit_supplement"] = Path(config["play_exit_supplement"])
        expected["play_exit_supplement"] = config["play_exit_supplement_sha256"]
    actual = {key: sha256_file(path) for key, path in paths.items()}
    failures = {key: {"expected": expected[key], "actual": actual[key]} for key in expected if actual[key] != expected[key]}
    dino_summary = json.loads((Path(config["dino_correction_run"]) / "summary.json").read_text(encoding="utf-8"))
    if dino_summary["dino_correction"] != "PASS":
        failures["dino_correction"] = {"expected": "PASS", "actual": dino_summary["dino_correction"]}
    if failures:
        raise RuntimeError(f"pinned strategy inputs failed: {failures}")
    return actual


def matrix(frame: pd.DataFrame, value: str, calendar: pd.DatetimeIndex, securities: pd.Index) -> pd.DataFrame:
    return frame.pivot(index="session_date", columns="security_id", values=value).reindex(index=calendar, columns=securities)


def lookup(mat: pd.DataFrame, base: pd.DataFrame) -> np.ndarray:
    stacked = mat.stack(future_stack=True)
    index = pd.MultiIndex.from_frame(base[["session_date", "security_id"]])
    return stacked.reindex(index).to_numpy()


def rank_quantile(frame: pd.DataFrame, feature: str, eligible: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    values = frame[feature].where(eligible)
    ranks = values.groupby(frame["session_date"]).rank(method="average")
    counts = values.groupby(frame["session_date"]).transform("count")
    percentile = ranks / counts
    quantile = np.ceil(percentile * 5).clip(1, 5).astype("Int64")
    return ranks, percentile, quantile


def prepare_signal(config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DatetimeIndex, dict[str, Any]]:
    candidate = pd.read_parquet(Path(config["candidate_run"]) / "candidate_panel.parquet")
    candidate["session_date"] = pd.to_datetime(candidate["session_date"])
    calendar = pd.DatetimeIndex(sorted(candidate["session_date"].unique()))
    securities = pd.Index(sorted(candidate["security_id"].unique()), name="security_id")
    close = matrix(candidate, "split_adjusted_close", calendar, securities)
    high = matrix(candidate, "split_adjusted_high", calendar, securities)
    price_ok = matrix(candidate, "price_usable_for_features", calendar, securities).fillna(False).astype(bool)
    feature_matrix = close / high.rolling(252, min_periods=252).max()
    official = candidate.loc[candidate["official_membership"].fillna(False)].copy()
    official = official.sort_values(["session_date", "security_id"], kind="mergesort").reset_index(drop=True)
    official["feature_session_date"] = official["session_date"].map(pd.Series(calendar, index=calendar).shift(1))
    official["proximity_to_max_high_252"] = lookup(feature_matrix.shift(1), official)
    official["prior_price_usable"] = pd.array(lookup(price_ok.shift(1).astype("boolean"), official), dtype="boolean")
    official["feature_eligible"] = official["prior_price_usable"].fillna(False) & official["proximity_to_max_high_252"].notna()
    ranks, percentile, quantile = rank_quantile(official, "proximity_to_max_high_252", official["feature_eligible"])
    official["rank"] = ranks
    official["percentile"] = percentile
    official["quantile"] = quantile

    accepted = pd.read_parquet(Path(config["phase_a_v2_run"]) / "adapted_new_panel.parquet")
    accepted["session_date"] = pd.to_datetime(accepted["session_date"])
    accepted = accepted.loc[accepted["session_date"].between(pd.Timestamp("2019-12-23"), pd.Timestamp("2026-08-18"))].copy()
    _, accepted_pct, accepted_q = rank_quantile(
        accepted,
        "proximity_to_max_high_252",
        accepted["eligible__proximity_to_max_high_252"].fillna(False),
    )
    accepted_compare = accepted[["session_date", "security_id", "proximity_to_max_high_252", "eligible__proximity_to_max_high_252"]].copy()
    accepted_compare["accepted_percentile"] = accepted_pct
    accepted_compare["accepted_quantile"] = accepted_q
    compare = official.merge(accepted_compare, on=["session_date", "security_id"], how="inner", validate="one_to_one")
    expected_rows = official["session_date"].between(pd.Timestamp("2019-12-23"), pd.Timestamp("2026-08-18"))
    feature_difference = (compare["proximity_to_max_high_252_x"] - compare["proximity_to_max_high_252_y"]).abs()
    eligible_equal = compare["feature_eligible"].astype(bool).eq(compare["eligible__proximity_to_max_high_252"].astype(bool))
    q_equal = compare["quantile"].fillna(-1).astype(int).eq(compare["accepted_quantile"].fillna(-1).astype(int))
    pct_difference = (compare["percentile"] - compare["accepted_percentile"]).abs()
    counts = official.loc[expected_rows].groupby("session_date").size()
    reconciliation = {
        "official_rows": int(expected_rows.sum()),
        "accepted_join_rows": int(len(compare)),
        "expected_join_rows": int(expected_rows.sum()),
        "official_denominator_min": int(counts.min()),
        "official_denominator_max": int(counts.max()),
        "feature_max_abs_difference": float(feature_difference.max(skipna=True)),
        "eligibility_mismatches": int((~eligible_equal).sum()),
        "percentile_max_abs_difference": float(pct_difference.max(skipna=True)),
        "quantile_mismatches": int((~q_equal).sum()),
    }
    reconciliation["status"] = "PASS" if (
        reconciliation["accepted_join_rows"] == reconciliation["expected_join_rows"]
        and reconciliation["official_denominator_min"] == 60
        and reconciliation["official_denominator_max"] == 60
        and reconciliation["feature_max_abs_difference"] < 1e-12
        and reconciliation["eligibility_mismatches"] == 0
        and reconciliation["percentile_max_abs_difference"] < 1e-12
        and reconciliation["quantile_mismatches"] == 0
    ) else "FAIL"
    return official, candidate, calendar, reconciliation


def exclusion_state(row: pd.Series) -> ExcludedMemberState:
    if pd.notna(row.get("missing_state")) and str(row.get("missing_state")):
        state = str(row["missing_state"])
    elif row.get("expected_trading") is False:
        state = "documented_nontrading"
    elif not bool(row.get("prior_price_usable", False)):
        state = "prior_price_unusable"
    else:
        state = "feature_ineligible_insufficient_252_history"
    reason = str(row.get("nontrading_reason") or row.get("unresolved_or_missing_state") or state)
    return ExcludedMemberState(security_id=str(row["security_id"]), raw_identifier=str(row["isin"]), state=state, reason=reason)


def build_decisions(config: dict[str, Any], official: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    decisions: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for period, (start_text, end_text) in config["periods"].items():
        start, end = pd.Timestamp(start_text), pd.Timestamp(end_text)
        sessions = pd.DatetimeIndex(sorted(official.loc[official["session_date"].between(start, end), "session_date"].unique()))
        for offset in range(20):
            chosen = [sessions[index] for index in range(offset, len(sessions), 20) if index + 20 < len(sessions)]
            for decision_date in chosen:
                group = official.loc[official["session_date"].eq(decision_date)].copy()
                if len(group) != 60:
                    raise RuntimeError(f"official denominator is not 60 on {decision_date.date()}")
                eligible = group.loc[group["feature_eligible"]].copy()
                excluded = [exclusion_state(row).model_dump(mode="json") for _, row in group.loc[~group["feature_eligible"]].iterrows()]
                missing_states = int(group["native_open"].isna().sum())
                nontrading_states = int((~group["expected_trading"].fillna(False)).sum())
                sets = {
                    "q5": eligible.loc[eligible["quantile"].eq(5)],
                    "eligible_universe_benchmark": eligible,
                    "q1": eligible.loc[eligible["quantile"].eq(1)],
                }
                for portfolio, selected in sets.items():
                    selected = selected.sort_values("security_id")
                    count = len(selected)
                    intended_weight = (
                        (Decimal(1) / Decimal(count)).quantize(Decimal("0.000000000001"), rounding=ROUND_DOWN)
                        if count else Decimal(0)
                    )
                    unavailable = int(selected["native_open"].isna().sum())
                    rejected_weight = sum((intended_weight for value in selected["native_open"].isna() if value), Decimal(0))
                    decisions.append(
                        {
                            "period": period,
                            "offset": offset,
                            "portfolio": portfolio,
                            "decision_date": decision_date,
                            "official_expected_members": 60,
                            "feature_eligible_members": len(eligible),
                            "selected_count": count,
                            "missing_states": missing_states,
                            "nontrading_states": nontrading_states,
                            "unavailable_selected_targets": unavailable,
                            "rejected_or_deferred_target_weight_preflight": str(rejected_weight),
                            "intended_invested_weight": str(sum((intended_weight for _ in range(count)), Decimal(0))),
                            "intended_cash_weight": str(Decimal(1) - sum((intended_weight for _ in range(count)), Decimal(0))),
                            "excluded_member_states_json": json.dumps(excluded, sort_keys=True, separators=(",", ":")),
                        }
                    )
                    for row in selected.itertuples(index=False):
                        targets.append(
                            {
                                "period": period,
                                "offset": offset,
                                "portfolio": portfolio,
                                "decision_date": decision_date,
                                "security_id": row.security_id,
                                "isin": row.isin,
                                "target_weight": str(intended_weight),
                                "feature_value": row.proximity_to_max_high_252,
                                "rank": row.rank,
                                "percentile": row.percentile,
                                "quantile": int(row.quantile),
                                "execution_open_available": pd.notna(row.native_open),
                            }
                        )
    decision_frame = pd.DataFrame(decisions).sort_values(["period", "offset", "portfolio", "decision_date"]).reset_index(drop=True)
    target_frame = pd.DataFrame(targets).sort_values(["period", "offset", "portfolio", "decision_date", "security_id"]).reset_index(drop=True)
    return decision_frame, target_frame


def build_event_preflight(config: dict[str, Any], targets: pd.DataFrame, candidate: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    exits = pd.read_csv(config["accepted_exit_evidence"])
    events = exits.loc[exits["isin"].isin(EXIT_ACTIONS)].copy()
    if config.get("play_exit_supplement"):
        play = json.loads(Path(config["play_exit_supplement"]).read_text(encoding="utf-8"))
        events = pd.concat(
            [
                events,
                pd.DataFrame(
                    [
                        {
                            "isin": play["isin"],
                            "event_type": play["event_type"],
                            "membership_exit_effective_date": "2020-11-27",
                            "last_trading_date": play["last_observed_trading_session"],
                            "trading_suspension_from": play["execution_unavailable_from"],
                            "squeeze_out_or_settlement_date": play["payment_date"],
                            "consideration": f"PLN {play['cash_amount_per_share']} cash per share",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    rows: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []
    grouped = targets.groupby(["period", "offset", "portfolio"], sort=True)
    for (period, offset, portfolio), sleeve in grouped:
        decision_dates = pd.DatetimeIndex(sorted(sleeve["decision_date"].unique()))
        for event in events.itertuples(index=False):
            security = f"isin:{event.isin}"
            selected_dates = pd.DatetimeIndex(sorted(sleeve.loc[sleeve["security_id"].eq(security), "decision_date"].unique()))
            suspension = pd.Timestamp(event.trading_suspension_from)
            crossing_dates = []
            for selected_date in selected_dates:
                later = decision_dates[decision_dates > selected_date]
                next_decision = later.min() if len(later) else pd.NaT
                if selected_date < suspension and (pd.isna(next_decision) or next_decision >= suspension):
                    crossing_dates.append(selected_date)
            rows.append(
                {
                    "period": period,
                    "offset": offset,
                    "portfolio": portfolio,
                    "isin": event.isin,
                    "event_type": event.event_type,
                    "membership_exit_effective_date": event.membership_exit_effective_date,
                    "last_trading_date": event.last_trading_date,
                    "trading_suspension_from": event.trading_suspension_from,
                    "settlement_date": event.squeeze_out_or_settlement_date,
                    "consideration": event.consideration,
                    "selected_decisions": len(selected_dates),
                    "crosses_terminal_interval": bool(crossing_dates),
                    "last_crossing_selection": max(crossing_dates).date().isoformat() if crossing_dates else None,
                    "terms_status": "established_official_event_supplement" if event.isin == "LU1642887738" else "established_accepted_evidence",
                    "action_required": bool(crossing_dates),
                }
            )
        dino_dates = pd.DatetimeIndex(sorted(sleeve.loc[sleeve["isin"].eq("PLDINPL00011"), "decision_date"].unique()))
        event_date = pd.Timestamp("2025-07-31")
        dino_cross = []
        for selected_date in dino_dates:
            later = decision_dates[decision_dates > selected_date]
            next_decision = later.min() if len(later) else pd.NaT
            if selected_date < event_date and (pd.isna(next_decision) or next_decision >= event_date):
                dino_cross.append(selected_date)
        rows.append(
            {
                "period": period,
                "offset": offset,
                "portfolio": portfolio,
                "isin": "PLDINPL00011",
                "event_type": "split 1-to-10",
                "membership_exit_effective_date": None,
                "last_trading_date": "2025-07-30 pre-split unit",
                "trading_suspension_from": None,
                "settlement_date": "2025-07-31",
                "consideration": "10 post-split shares per pre-split share",
                "selected_decisions": len(dino_dates),
                "crosses_terminal_interval": False,
                "last_crossing_selection": max(dino_cross).date().isoformat() if dino_cross else None,
                "terms_status": "confirmed_split_evidence",
                "action_required": bool(dino_cross),
            }
        )

        selection_by_date = {
            decision_date: set(group["security_id"])
            for decision_date, group in sleeve.groupby("decision_date", sort=True)
        }
        period_start, period_end = [pd.Timestamp(value) for value in config["periods"][period]]
        missing_candidates = candidate.loc[
            candidate["session_date"].between(period_start, period_end)
            & (candidate["native_open"].isna() | candidate["native_close"].isna())
        ]
        for missing in missing_candidates.itertuples(index=False):
            insertion = decision_dates.searchsorted(missing.session_date, side="right") - 1
            if insertion >= 0:
                holding_decision = decision_dates[insertion]
            else:
                continue
            if missing.security_id in selection_by_date[holding_decision]:
                path_rows.append(
                    {
                        "period": period,
                        "offset": offset,
                        "portfolio": portfolio,
                        "security_id": missing.security_id,
                        "holding_decision_date": holding_decision,
                        "session_date": missing.session_date,
                        "native_open_missing": pd.isna(missing.native_open),
                        "native_close_missing": pd.isna(missing.native_close),
                        "expected_trading": missing.expected_trading,
                        "nontrading_reason": missing.nontrading_reason,
                        "missing_state": missing.missing_state,
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(path_rows)


def market_bars(candidate: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> list[MarketBar]:
    frame = candidate.loc[candidate["session_date"].between(start, end)].copy()
    bars: list[MarketBar] = []
    for row in frame.itertuples(index=False):
        session = row.session_date.date()
        event_ts = datetime.combine(session, time(17, 0), WARSAW)
        available_ts = datetime.combine(session, time(17, 5), WARSAW)
        bars.append(
            MarketBar(
                security_id=str(row.security_id),
                session_date=session,
                event_ts=event_ts,
                available_ts=available_ts,
                open=None if pd.isna(row.native_open) else Decimal(str(row.native_open)),
                close=None if pd.isna(row.native_close) else Decimal(str(row.native_close)),
                currency="PLN",
                market="GPW",
                source=str(row.selected_source or "explicit_missing"),
                source_record_id=str(row.source_hash or f"missing:{row.security_id}:{session}"),
                adjustment_state="raw",
                adjustment_version=f"native:{row.source_series_version or 'missing'}",
            )
        )
    return bars


def action_inputs(event_rows: pd.DataFrame) -> tuple[list[SecurityEventInput], list[CorporateActionInput]]:
    security_events: list[SecurityEventInput] = []
    actions: list[CorporateActionInput] = []
    required = event_rows.loc[event_rows["action_required"]]
    for row in required.itertuples(index=False):
        security_id = f"isin:{row.isin}"
        if row.isin == "PLDINPL00011":
            actions.append(
                CorporateActionInput(
                    action_id="PLDINPL00011-2025-07-31-split-1-to-10-v1",
                    revision=0,
                    security_id=security_id,
                    action_type=CorporateActionType.SPLIT,
                    event_ts=datetime(2025, 7, 28, 0, 0, tzinfo=WARSAW),
                    available_ts=datetime(2025, 7, 28, 0, 0, tzinfo=WARSAW),
                    effective_session=pd.Timestamp("2025-07-31").date(),
                    ratio=Decimal("10"),
                    reason="Confirmed KDPW statement 672/2025; apply quantity once to native execution prices.",
                    provenance={"dino_correction": "phase-a-v2-dino-correction-20260829-v1"},
                )
            )
            continue
        spec = EXIT_ACTIONS[row.isin]
        event_evidence = {"accepted_exit_evidence": "top60_exit_event_audit.csv", "consideration": row.consideration}
        suspension = pd.Timestamp(row.trading_suspension_from).date()
        knowledge_date = pd.Timestamp("2020-12-21").date() if row.isin == "LU1642887738" else suspension
        if row.isin == "LU1642887738":
            event_evidence = {
                "official_event_supplement": "play_exit_supplement.json",
                "consideration": row.consideration,
                "availability": "official Iliad announcement 2020-12-21",
            }
        security_events.append(
            SecurityEventInput(
                event_id=f"{row.isin}-{suspension}-suspension-v1",
                revision=0,
                security_id=security_id,
                event_type=SecurityEventType.SUSPENSION,
                event_ts=datetime.combine(knowledge_date, time(0, 0), WARSAW),
                available_ts=datetime.combine(knowledge_date, time(0, 0), WARSAW),
                effective_session=suspension,
                reason="Accepted terminal-event audit; block fabricated post-last-trade fills.",
                provenance=event_evidence,
            )
        )
        effective = pd.Timestamp(spec["effective"]).date()
        common = dict(
            action_id=f"{row.isin}-{effective}-{spec['kind']}-v1",
            revision=0,
            security_id=security_id,
            event_ts=datetime.combine(knowledge_date, time(0, 0), WARSAW),
            available_ts=datetime.combine(knowledge_date, time(0, 0), WARSAW),
            effective_session=effective,
            reason="Smallest explicit settlement input from accepted TOP60 exit evidence.",
            provenance=event_evidence,
        )
        if spec["kind"] == "merger":
            actions.append(
                CorporateActionInput(
                    **common,
                    action_type=CorporateActionType.MERGER,
                    related_security_id=f"isin:{spec['related']}",
                    ratio=Decimal(spec["ratio"]),
                )
            )
        else:
            actions.append(
                CorporateActionInput(
                    **common,
                    action_type=CorporateActionType.CASH_TAKEOVER,
                    cash_amount_per_share=Decimal(spec["cash"]),
                    currency="PLN",
                )
            )
    unique_events = {(row.event_id, row.revision): row for row in security_events}
    unique_actions = {(row.action_id, row.revision): row for row in actions}
    return list(unique_events.values()), list(unique_actions.values())


def make_intents(
    config: dict[str, Any],
    period: str,
    offset: int,
    portfolio: str,
    decisions: pd.DataFrame,
    targets: pd.DataFrame,
    calendar: pd.DatetimeIndex,
) -> list[TargetWeightIntent]:
    decision_rows = decisions.loc[(decisions["period"].eq(period)) & (decisions["offset"].eq(offset)) & (decisions["portfolio"].eq(portfolio))]
    target_rows = targets.loc[(targets["period"].eq(period)) & (targets["offset"].eq(offset)) & (targets["portfolio"].eq(portfolio))]
    prior_targeted: set[str] = set()
    intents: list[TargetWeightIntent] = []
    manifest_path = (Path(config["candidate_run"]) / "manifest.json").resolve().as_posix()
    calendar_pos = {value: index for index, value in enumerate(calendar)}
    for decision in decision_rows.sort_values("decision_date").itertuples(index=False):
        current = target_rows.loc[target_rows["decision_date"].eq(decision.decision_date)]
        current_weights = {row.security_id: Decimal(row.target_weight) for row in current.itertuples(index=False)}
        names = sorted(set(current_weights) | prior_targeted)
        excluded = tuple(ExcludedMemberState.model_validate(item) for item in json.loads(decision.excluded_member_states_json))
        position = calendar_pos[decision.decision_date]
        prior_session = calendar[position - 1]
        info_ts = datetime.combine(prior_session.date(), time(17, 5), WARSAW)
        decision_ts = datetime.combine(prior_session.date(), time(17, 10), WARSAW)
        execution_ts = datetime.combine(decision.decision_date.date(), time(9, 0), WARSAW)
        batch = f"{period}:{offset}:{portfolio}:{decision.decision_date.date()}"
        for security_id in names:
            target_weight = current_weights.get(security_id, Decimal(0))
            intents.append(
                TargetWeightIntent(
                    intent_id=f"intent-{object_hash([batch, security_id, str(target_weight)])[:24]}",
                    batch_id=batch,
                    account_id=f"{period}-{offset}-{portfolio}",
                    security_id=security_id,
                    decision_ts=decision_ts,
                    information_available_ts=info_ts,
                    earliest_eligible_execution_ts=execution_ts,
                    earliest_eligible_session=decision.decision_date.date(),
                    target_weight=target_weight,
                    currency="PLN",
                    source_run_id=config["phase_a_v2_logical_payload_hash"],
                    signal_version="phase-a-v2-max-high-252-frozen",
                    data_manifest_id=Path(config["candidate_run"]).name,
                    data_manifest_path=manifest_path,
                    data_manifest_sha256=config["candidate_manifest_sha256"],
                    official_universe_denominator=60,
                    usable_price_count=int(decision.feature_eligible_members),
                    feature_eligible_count=int(decision.feature_eligible_members),
                    excluded_member_states=excluded,
                    reason="frozen equal-weight target; zero rows explicitly exit prior targets",
                    provenance={"period": period, "offset": offset, "portfolio": portfolio, "decision_date": str(decision.decision_date.date())},
                )
            )
        prior_targeted |= set(current_weights)
    return intents


def portfolio_config(config: dict[str, Any], period: str, offset: int, portfolio: str) -> PortfolioConfig:
    start, end = config["periods"][period]
    placeholder = ROOT / "config.json"
    return PortfolioConfig(
        phase_root=Path("D:/Stock/data/ATS/phase_a_v2_strategy_test"),
        phase_b_manifest=Path(config["candidate_run"]) / "manifest.json",
        intents_file=placeholder,
        account_id=f"{period}-{offset}-{portfolio}",
        initial_cash=Decimal(str(config["portfolio"]["initial_cash_pln_per_sleeve"])),
        commission_bps=Decimal(str(config["portfolio"]["commission_bps"])),
        slippage_bps=Decimal(str(config["portfolio"]["slippage_bps"])),
        max_stale_valuation_sessions=int(config["accounting"]["max_stale_valuation_sessions"]),
        continue_on_unresolved_valuation=True,
        unavailable_target_policy="retain_as_cash",
        adjustment_policy="raw_with_explicit_actions",
        seed=int(config["seed"]),
        run_label="bounded-research-not-alpha",
        start_session=pd.Timestamp(start).date(),
        end_session=pd.Timestamp(end).date(),
    )


def run_sleeve(
    config: dict[str, Any], period: str, offset: int, portfolio: str,
    decisions: pd.DataFrame, targets: pd.DataFrame, event_preflight: pd.DataFrame,
    bars: list[MarketBar], known: set[str], calendar: pd.DatetimeIndex,
) -> tuple[EngineResult, list[TargetWeightIntent]]:
    intents = make_intents(config, period, offset, portfolio, decisions, targets, calendar)
    event_rows = event_preflight.loc[
        event_preflight["period"].eq(period)
        & event_preflight["offset"].eq(offset)
        & event_preflight["portfolio"].eq(portfolio)
    ]
    security_events, corporate_actions = action_inputs(event_rows)
    engine = DailyPortfolioEngine(
        config=portfolio_config(config, period, offset, portfolio),
        run_id=f"research-{period}-{offset}-{portfolio}",
        bars=bars,
        intents=intents,
        known_security_ids=known,
        data_manifest_id=Path(config["candidate_run"]).name,
        data_manifest_path=(Path(config["candidate_run"]) / "manifest.json").resolve().as_posix(),
        data_manifest_sha256=config["candidate_manifest_sha256"],
        security_events=security_events,
        corporate_actions=corporate_actions,
    )
    return engine.run(), intents


def daily_nav_frame(result: EngineResult, period: str, offset: int, portfolio: str, initial_cash: float) -> pd.DataFrame:
    positions = defaultdict(int)
    for row in result.positions:
        positions[row.session_date] += 1
    valuations = defaultdict(list)
    for row in result.valuations:
        valuations[row.session_date].append(row)
    rows = []
    prior_nav = initial_cash
    for snapshot in result.portfolio_snapshots:
        nav = float(snapshot.equity) if snapshot.equity is not None else np.nan
        cash = float(snapshot.cash)
        weights = [float(value.market_value) / nav for value in valuations[snapshot.session_date] if nav and value.market_value is not None]
        daily_return = nav / prior_nav - 1.0 if np.isfinite(nav) and np.isfinite(prior_nav) else np.nan
        if np.isfinite(nav):
            prior_nav = nav
        rows.append(
            {
                "period": period, "offset": offset, "portfolio": portfolio,
                "session_date": pd.Timestamp(snapshot.session_date), "nav": nav, "cash": cash,
                "daily_return": daily_return, "valuation_status": snapshot.valuation_status.value,
                "cash_weight": cash / nav if np.isfinite(nav) and nav else np.nan,
                "holdings_count": positions[snapshot.session_date],
                "max_single_name_weight": max(weights) if weights else 0.0,
                "rejected_target_weight": float(snapshot.rejected_target_weight),
                "deferred_target_weight": float(snapshot.deferred_target_weight),
                "unallocated_weight": float(snapshot.unallocated_weight),
            }
        )
    return pd.DataFrame(rows)


def performance_metrics(nav: pd.DataFrame, initial_cash: float, fills: int, rebalances: int, turnover: float, commission: float, slippage: float) -> dict[str, Any]:
    clean = nav.dropna(subset=["nav"]).copy()
    returns = clean["daily_return"].dropna()
    sessions = len(clean)
    terminal = float(clean.iloc[-1]["nav"]) if sessions else np.nan
    cumulative = terminal / initial_cash - 1.0 if sessions else np.nan
    years = sessions / 252.0
    cagr = (terminal / initial_cash) ** (1.0 / years) - 1.0 if sessions and terminal > 0 else np.nan
    volatility = returns.std(ddof=1) * math.sqrt(252) if len(returns) > 1 else np.nan
    ratio = cagr / volatility if volatility and np.isfinite(volatility) else np.nan
    drawdown = clean["nav"] / clean["nav"].cummax() - 1.0
    return {
        "sessions": sessions, "terminal_nav": terminal, "cumulative_return": cumulative, "cagr": cagr,
        "annualized_volatility": volatility, "return_volatility_ratio": ratio,
        "maximum_drawdown": float(drawdown.min()), "turnover_cumulative": turnover,
        "turnover_annualized": turnover / years if years else np.nan,
        "commission_pln": commission, "commission_drag_initial": commission / initial_cash,
        "slippage_pln": slippage, "slippage_drag_initial": slippage / initial_cash,
        "total_cost_pln": commission + slippage, "total_cost_drag_initial": (commission + slippage) / initial_cash,
        "fills": fills, "rebalances": rebalances,
        "average_cash_weight": clean["cash_weight"].mean(), "maximum_cash_weight": clean["cash_weight"].max(),
        "average_holdings_count": clean["holdings_count"].mean(), "maximum_single_name_weight": clean["max_single_name_weight"].max(),
        "unresolved_sessions": int(nav["valuation_status"].eq("unresolved").sum()),
        "stale_sessions": int(nav["valuation_status"].eq("stale").sum()),
        "rejected_sessions": int(nav["rejected_target_weight"].gt(0).sum()),
        "deferred_sessions": int(nav["deferred_target_weight"].gt(0).sum()),
    }


def result_costs(result: EngineResult) -> tuple[float, float, float]:
    orders = {row.event_id: row for row in result.orders}
    turnover = 0.0
    for fill in result.fills:
        order = orders[fill.order_id]
        turnover += abs(float(fill.raw_open_price * fill.quantity)) / float(order.execution_equity)
    return turnover, sum(float(row.commission) for row in result.fills), sum(float(row.slippage_amount) for row in result.fills)


def contributions(result: EngineResult, period: str, offset: int, portfolio: str) -> pd.DataFrame:
    values: dict[str, Decimal] = defaultdict(Decimal)
    for fill in result.fills:
        values[LINEAGE.get(fill.security_id, fill.security_id)] += -fill.notional - fill.commission
    for movement in result.cash_movements:
        if movement.corporate_action_application_id and movement.security_id:
            values[LINEAGE.get(movement.security_id, movement.security_id)] += movement.amount
    last = result.portfolio_snapshots[-1].session_date
    for value in result.valuations:
        if value.session_date == last and value.market_value is not None:
            values[LINEAGE.get(value.security_id, value.security_id)] += value.market_value
    return pd.DataFrame(
        [{"period": period, "offset": offset, "portfolio": portfolio, "contribution_group": key, "terminal_pnl_contribution": float(value)} for key, value in sorted(values.items())]
    )


def reconcile_result(result: EngineResult, period: str, offset: int, portfolio: str, candidate_open_keys: set[tuple[str, Any]], initial_cash: Decimal) -> dict[str, Any]:
    final_snapshot = result.portfolio_snapshots[-1]
    cash_total = sum((row.amount for row in result.cash_movements), Decimal(0))
    cash_ok = money(cash_total) == final_snapshot.cash
    equity_ok = all(
        row.equity is None or money(row.cash + row.market_value) == row.equity
        for row in result.portfolio_snapshots
    )
    fill_source_ok = all((row.security_id, row.timestamp.date()) in candidate_open_keys for row in result.fills)
    commission_ok = all(row.commission == money(abs(row.notional) * Decimal("0.001")) for row in result.fills)
    slippage_ok = all(abs(float(row.slippage_amount) - abs(float(row.raw_open_price * row.quantity)) * 0.0015) < 0.02 for row in result.fills)
    action_ids = [row.action_id for row in result.corporate_action_applications]
    action_single = len(action_ids) == len(set(action_ids))
    dino_applications = sum(value.startswith("PLDINPL00011") for value in action_ids)
    no_negative_cash = all(row.balance_after >= 0 for row in result.cash_movements)
    status = "PASS" if all([cash_ok, equity_ok, fill_source_ok, commission_ok, slippage_ok, action_single, dino_applications <= 1, no_negative_cash]) else "FAIL"
    return {
        "period": period, "offset": offset, "portfolio": portfolio, "status": status,
        "cash_conservation": cash_ok, "nav_conservation": equity_ok, "fill_source_native_open": fill_source_ok,
        "commission_exact": commission_ok, "slippage_exact": slippage_ok, "corporate_action_single_application": action_single,
        "dino_applications": dino_applications, "no_negative_cash": no_negative_cash,
        "initial_cash": str(initial_cash), "final_cash": str(final_snapshot.cash), "fills": len(result.fills),
    }


def yearly_metrics(nav: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in nav.groupby(["period", "offset", "portfolio"], sort=True):
        for year, annual in group.groupby(group["session_date"].dt.year, sort=True):
            valid = annual["daily_return"].dropna()
            rows.append({"period": keys[0], "offset": keys[1], "portfolio": keys[2], "year": year, "return": (1.0 + valid).prod() - 1.0, "sessions": len(valid)})
    return pd.DataFrame(rows)


def composite_nav(daily: pd.DataFrame, initial_cash: float) -> pd.DataFrame:
    frames = []
    for (period, portfolio), group in daily.groupby(["period", "portfolio"], sort=True):
        pivot = group.pivot(index="session_date", columns="offset", values="nav").sort_index()
        # Every engine emits cash NAV before its first rebalance. A missing value
        # therefore means unresolved valuation, not an unstarted sleeve, and the
        # composite must remain unresolved rather than conceal it with cash or
        # unaffected offsets.
        composite = pivot.mean(axis=1, skipna=False)
        result = pd.DataFrame({"period": period, "portfolio": portfolio, "session_date": composite.index, "nav": composite.values})
        result["daily_return"] = result["nav"].pct_change()
        result.loc[result.index[0], "daily_return"] = result.loc[result.index[0], "nav"] / initial_cash - 1.0
        frames.append(result)
    return pd.concat(frames, ignore_index=True)


def relative_metrics(metrics: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (period, offset), group in daily.groupby(["period", "offset"], sort=True):
        q5 = group.loc[group["portfolio"].eq("q5")].set_index("session_date")
        benchmark = group.loc[group["portfolio"].eq("eligible_universe_benchmark")].set_index("session_date")
        joined = q5[["nav", "daily_return"]].join(benchmark[["nav", "daily_return"]], lsuffix="_q5", rsuffix="_benchmark")
        relative = joined["nav_q5"] / joined["nav_benchmark"]
        active = joined["daily_return_q5"] - joined["daily_return_benchmark"]
        q5m = metrics.loc[(metrics["period"].eq(period)) & (metrics["offset"].eq(offset)) & (metrics["portfolio"].eq("q5"))].iloc[0]
        bm = metrics.loc[(metrics["period"].eq(period)) & (metrics["offset"].eq(offset)) & (metrics["portfolio"].eq("eligible_universe_benchmark"))].iloc[0]
        tracking = active.std(ddof=1) * math.sqrt(252)
        rows.append(
            {
                "period": period, "offset": offset, "relative_terminal_wealth": relative.iloc[-1],
                "excess_cagr": q5m.cagr - bm.cagr, "tracking_error": tracking,
                "information_ratio": active.mean() * 252 / tracking if tracking else np.nan,
                "relative_drawdown": (relative / relative.cummax() - 1.0).min(),
                "q5_cumulative_return": q5m.cumulative_return, "benchmark_cumulative_return": bm.cumulative_return,
                "positive_absolute": q5m.cumulative_return > 0, "positive_excess": relative.iloc[-1] > 1,
            }
        )
    return pd.DataFrame(rows)


def run_all(config: dict[str, Any], official: pd.DataFrame, candidate: pd.DataFrame, calendar: pd.DatetimeIndex,
            decisions: pd.DataFrame, targets: pd.DataFrame, event_preflight: pd.DataFrame) -> dict[str, pd.DataFrame]:
    daily_frames, metric_rows, fill_rows, contribution_frames, reconciliation_rows = [], [], [], [], []
    initial = float(config["portfolio"]["initial_cash_pln_per_sleeve"])
    candidate_open_keys = set(
        (row.security_id, row.session_date.date())
        for row in candidate.loc[candidate["native_open"].notna(), ["security_id", "session_date"]].itertuples(index=False)
    )
    known = set(candidate["security_id"].astype(str))
    for period, (start, end) in config["periods"].items():
        bars = market_bars(candidate, pd.Timestamp(start), pd.Timestamp(end))
        for offset in range(20):
            for portfolio in ("q5", "eligible_universe_benchmark", "q1"):
                result, intents = run_sleeve(config, period, offset, portfolio, decisions, targets, event_preflight, bars, known, calendar)
                nav = daily_nav_frame(result, period, offset, portfolio, initial)
                daily_frames.append(nav)
                turnover, commission, slippage = result_costs(result)
                rebalances = decisions.loc[
                    decisions["period"].eq(period) & decisions["offset"].eq(offset) & decisions["portfolio"].eq(portfolio)
                ].shape[0]
                metrics = performance_metrics(nav, initial, len(result.fills), rebalances, turnover, commission, slippage)
                metric_rows.append({"period": period, "offset": offset, "portfolio": portfolio, **metrics})
                contribution_frames.append(contributions(result, period, offset, portfolio))
                reconciliation_rows.append(reconcile_result(result, period, offset, portfolio, candidate_open_keys, Decimal(str(initial))))
                for fill in result.fills:
                    fill_rows.append(
                        {"period": period, "offset": offset, "portfolio": portfolio, "timestamp": fill.timestamp,
                         "security_id": fill.security_id, "side": fill.side.value, "quantity": str(fill.quantity),
                         "raw_open_price": str(fill.raw_open_price), "fill_price": str(fill.fill_price),
                         "notional": str(fill.notional), "commission": str(fill.commission), "slippage_amount": str(fill.slippage_amount),
                         "source_bar_id": fill.source_bar_id}
                    )
    daily = pd.concat(daily_frames, ignore_index=True)
    metrics = pd.DataFrame(metric_rows)
    relative = relative_metrics(metrics, daily)
    yearly = yearly_metrics(daily)
    composite = composite_nav(daily, initial)
    composite_yearly = yearly_metrics(composite.assign(offset=-1))
    composite_metrics_rows = []
    for (period, portfolio), nav in composite.groupby(["period", "portfolio"], sort=True):
        composite_metrics_rows.append({"period": period, "portfolio": portfolio, **performance_metrics(
            nav.assign(cash_weight=np.nan, holdings_count=np.nan, max_single_name_weight=np.nan,
                       valuation_status="complete", rejected_target_weight=0.0, deferred_target_weight=0.0),
            initial, 0, 0, np.nan, np.nan, np.nan)})
    composite_metrics = pd.DataFrame(composite_metrics_rows)
    return {
        "daily_nav": daily, "portfolio_metrics": metrics, "offset_relative_metrics": relative,
        "yearly_metrics": yearly, "composite_nav": composite, "composite_yearly_metrics": composite_yearly,
        "composite_metrics": composite_metrics, "fills": pd.DataFrame(fill_rows),
        "contributions": pd.concat(contribution_frames, ignore_index=True), "ledger_reconciliation": pd.DataFrame(reconciliation_rows),
    }


def evaluate_gate(outputs: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, Any]]:
    cm = outputs["composite_metrics"]
    cy = outputs["composite_yearly_metrics"]
    comp = outputs["composite_nav"]
    relative = outputs["offset_relative_metrics"]
    contributions_frame = outputs["contributions"]
    common_q5 = cm.loc[cm["period"].eq("common") & cm["portfolio"].eq("q5")].iloc[0]
    common_bm = cm.loc[cm["period"].eq("common") & cm["portfolio"].eq("eligible_universe_benchmark")].iloc[0]
    expanded_q5 = cm.loc[cm["period"].eq("expanded") & cm["portfolio"].eq("q5")].iloc[0]
    expanded_bm = cm.loc[cm["period"].eq("expanded") & cm["portfolio"].eq("eligible_universe_benchmark")].iloc[0]
    common_offsets = relative.loc[relative["period"].eq("common")]
    yearly_pivot = cy.loc[cy["period"].eq("common")].pivot(index="year", columns="portfolio", values="return")
    yearly_pivot["excess"] = yearly_pivot["q5"] - yearly_pivot["eligible_universe_benchmark"]
    full = yearly_pivot.loc[yearly_pivot.index.isin(range(2021, 2026))]
    strongest_year = int(full["excess"].idxmax())
    no_year = comp.loc[comp["period"].eq("common") & ~comp["session_date"].dt.year.eq(strongest_year)]
    no_year_pivot = no_year.pivot(index="session_date", columns="portfolio", values="daily_return")
    no_year_q5 = (1 + no_year_pivot["q5"]).prod()
    no_year_bm = (1 + no_year_pivot["eligible_universe_benchmark"]).prod()

    contrib = contributions_frame.loc[contributions_frame["period"].eq("common")]
    contrib_composite = contrib.groupby(["portfolio", "contribution_group"])["terminal_pnl_contribution"].mean().unstack(0, fill_value=0.0)
    q5_terminal_excess = common_q5.terminal_nav - common_bm.terminal_nav
    deletion_values = {}
    for group, row in contrib_composite.iterrows():
        deletion_values[group] = q5_terminal_excess - (row.get("q5", 0.0) - row.get("eligible_universe_benchmark", 0.0))
    min_deleted = min(deletion_values.values()) if deletion_values else q5_terminal_excess
    checks = [
        ("q5_positive_after_cost_price_only_cagr", common_q5.cagr > 0, common_q5.cagr),
        ("minimum_excess_cagr_2pp", common_q5.cagr - common_bm.cagr >= 0.02, common_q5.cagr - common_bm.cagr),
        ("q5_return_volatility_ratio_exceeds_benchmark", common_q5.return_volatility_ratio > common_bm.return_volatility_ratio, common_q5.return_volatility_ratio - common_bm.return_volatility_ratio),
        ("maximum_drawdown_disadvantage_at_most_5pp", common_q5.maximum_drawdown >= common_bm.maximum_drawdown - 0.05, common_q5.maximum_drawdown - common_bm.maximum_drawdown),
        ("median_offset_positive_excess", common_offsets["relative_terminal_wealth"].median() > 1, common_offsets["relative_terminal_wealth"].median() - 1),
        ("at_least_12_positive_excess_offsets", int(common_offsets["positive_excess"].sum()) >= 12, int(common_offsets["positive_excess"].sum())),
        ("at_least_3_positive_full_years_2021_2025", int((full["excess"] > 0).sum()) >= 3, int((full["excess"] > 0).sum())),
        ("strongest_year_not_necessary", no_year_q5 / no_year_bm > 1, no_year_q5 / no_year_bm),
        ("single_security_not_necessary", min_deleted > 0, min_deleted),
        ("expanded_same_economic_direction", expanded_q5.cagr > 0 and expanded_q5.cagr > expanded_bm.cagr, expanded_q5.cagr - expanded_bm.cagr),
        ("q5_itself_beats_benchmark", common_q5.terminal_nav > common_bm.terminal_nav, common_q5.terminal_nav / common_bm.terminal_nav),
    ]
    gate = pd.DataFrame([{"gate": name, "status": "PASS" if passed else "FAIL", "observed": value} for name, passed, value in checks])
    overall = "CONTINUE TO ONE BOUNDED VALIDATION STEP" if gate["status"].eq("PASS").all() else "STOP OR DESCOPE PROXIMITY STRATEGY RESEARCH"
    summary = {
        "overall_decision": overall,
        "economic_gate_passes": int(gate["status"].eq("PASS").sum()),
        "economic_gate_total": len(gate),
        "strongest_full_year": strongest_year,
        "relative_wealth_without_strongest_year": no_year_q5 / no_year_bm,
        "minimum_excess_terminal_pln_after_single_group_deletion": min_deleted,
        "q5_common_cagr": common_q5.cagr,
        "benchmark_common_cagr": common_bm.cagr,
        "q5_common_excess_cagr": common_q5.cagr - common_bm.cagr,
        "positive_excess_offsets": int(common_offsets["positive_excess"].sum()),
        "positive_absolute_offsets": int(common_offsets["positive_absolute"].sum()),
        "positive_full_years_2021_2025": int((full["excess"] > 0).sum()),
    }
    return gate, summary


def environment_lock() -> dict[str, str]:
    packages = ["numpy", "pandas", "pyarrow", "pydantic", "pytest"]
    result = {"python": sys.version, "platform": platform.platform()}
    for package in packages:
        try:
            result[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            result[package] = "not-installed"
    return dict(sorted(result.items()))


def provenance(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    repo = ROOT.parents[2]
    freeze_file = ROOT / config.get("plan_freeze_file", "plan_freeze.json")
    files = [ROOT / "strategy_test.py", config_path.resolve(), ROOT / "analysis_plan.md", freeze_file,
             repo / "source/python/src/ats_portfolio/engine.py", repo / "source/python/src/ats_contracts/portfolio.py"]
    if config.get("play_exit_supplement"):
        files.append(Path(config["play_exit_supplement"]))
    return {
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip(),
        "source_hashes": {path.relative_to(repo).as_posix(): sha256_file(path) for path in files},
    }


def write_frame(frame: pd.DataFrame, path: Path) -> None:
    if path.suffix == ".parquet":
        frame.to_parquet(path, index=False, compression="zstd")
    else:
        frame.to_csv(path, index=False, float_format="%.17g", lineterminator="\n")


def publish(config_path: Path, output_root: Path) -> Path:
    config = load_effective_config(config_path)
    destination = output_root.resolve() / config["run_id"]
    if destination.exists():
        raise FileExistsError(f"immutable strategy run already exists: {destination}")
    stage = output_root.resolve().parent / "staging" / f"{config['run_id']}-{uuid.uuid4().hex[:8]}"
    stage.mkdir(parents=True, exist_ok=False)
    try:
        pins = validate_pins(config)
        official, candidate, calendar, signal_reconciliation = prepare_signal(config)
        if signal_reconciliation["status"] != "PASS":
            raise RuntimeError(f"signal reconciliation failed: {signal_reconciliation}")
        decisions, targets = build_decisions(config, official)
        event_preflight, holding_path = build_event_preflight(config, targets, candidate)
        accepted_terms = {"established_accepted_evidence", "established_official_event_supplement", "confirmed_split_evidence"}
        if not set(event_preflight.loc[event_preflight["action_required"], "terms_status"]).issubset(accepted_terms):
            raise RuntimeError("a required corporate exit lacks established terms")
        outputs = run_all(config, official, candidate, calendar, decisions, targets, event_preflight)
        gate, summary = evaluate_gate(outputs)
        if outputs["ledger_reconciliation"]["status"].ne("PASS").any():
            summary["overall_decision"] = "NOT PROVEN — MATERIAL EXECUTION OR DATA BLOCKER"
        summary.update(
            {
                "schema_version": "ats.phase_a_v2_strategy_test.summary.v1",
                "dino_correction": "PASS",
                "signal_and_pit_reconciliation": signal_reconciliation["status"],
                "portfolio_accounting": "PASS" if outputs["ledger_reconciliation"]["status"].eq("PASS").all() else "NOT PROVEN",
                "cash_distributions_included": False,
                "cash_dividend_price_gaps_preserved": True,
                "historical_sample_role": "economic translation/falsification on the same sample that contributed to hypothesis selection; not out-of-sample validation",
            }
        )
        shutil.copyfile(config_path, stage / "config.json")
        freeze_name = config.get("plan_freeze_file", "plan_freeze.json")
        for name in ("analysis_plan.md", freeze_name, "plan_deviations.json"):
            shutil.copyfile(ROOT / name, stage / name)
        (stage / "environment_lock.json").write_text(json.dumps(environment_lock(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (stage / "provenance.json").write_text(json.dumps(provenance(config_path, config), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (stage / "input_validation.json").write_text(json.dumps(pins, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (stage / "signal_reconciliation.json").write_text(json.dumps(signal_reconciliation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (stage / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tables = stage / "tables"
        tables.mkdir()
        write_frame(decisions, tables / "decision_sessions.parquet")
        write_frame(targets, tables / "target_weights.parquet")
        write_frame(event_preflight, tables / "event_preflight.csv")
        write_frame(holding_path, tables / "holding_path_missing_states.csv")
        for name, frame in outputs.items():
            suffix = ".parquet" if name in {"daily_nav", "fills", "contributions"} else ".csv"
            write_frame(frame, tables / f"{name}{suffix}")
        write_frame(gate, tables / "economic_gate.csv")
        checksums = {
            "decision_sessions_logical_sha256": stable_frame_hash(decisions),
            "target_weights_logical_sha256": stable_frame_hash(targets),
            "selected_names_logical_sha256": stable_frame_hash(targets[["period", "offset", "portfolio", "decision_date", "security_id"]]),
        }
        (stage / "selection_checksums.json").write_text(json.dumps(checksums, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        files = {}
        for path in sorted(item for item in stage.rglob("*") if item.is_file()):
            relative = path.relative_to(stage).as_posix()
            files[relative] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        logical_payload = {
            "run_id": config["run_id"], "config_sha256": sha256_file(config_path), "summary": summary,
            "selection_checksums": checksums, "files": {key: value["sha256"] for key, value in files.items() if key != "provenance.json"},
        }
        manifest = {
            "schema_version": "ats.phase_a_v2_strategy_test.manifest.v1", "run_id": config["run_id"],
            "created_utc": datetime.now(timezone.utc).isoformat(), "files": files,
            "logical_payload_hash": object_hash(logical_payload), "selection_checksums": checksums,
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage, destination)
        return destination
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(publish(args.config, args.output_root))


if __name__ == "__main__":
    main()
