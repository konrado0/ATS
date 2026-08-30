from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from ats_contracts.portfolio import TargetWeightIntent
from strategy_test import (
    action_inputs,
    build_decisions,
    build_event_preflight,
    load_effective_config,
    performance_metrics,
    rank_quantile,
    stable_frame_hash,
)


def test_rank_ties_match_frozen_phase_a_convention() -> None:
    frame = pd.DataFrame({"session_date": pd.to_datetime(["2026-01-02"] * 5), "feature": [1, 2, 2, 4, 5]})
    ranks, percentile, quantile = rank_quantile(frame, "feature", pd.Series(True, index=frame.index))
    assert ranks.tolist() == [1.0, 2.5, 2.5, 4.0, 5.0]
    assert quantile.tolist() == [1, 3, 3, 4, 5]
    assert percentile.iloc[-1] == 1.0


def test_first_session_cost_is_included_in_return_metrics() -> None:
    nav = pd.DataFrame(
        {
            "nav": [990_000.0, 1_000_000.0], "daily_return": [-0.01, 1_000_000 / 990_000 - 1],
            "cash_weight": [0.1, 0.1], "holdings_count": [10, 10], "max_single_name_weight": [0.1, 0.1],
            "valuation_status": ["complete", "complete"], "rejected_target_weight": [0.0, 0.0], "deferred_target_weight": [0.0, 0.0],
        }
    )
    metrics = performance_metrics(nav, 1_000_000.0, 1, 1, 1.0, 100.0, 150.0)
    assert metrics["cumulative_return"] == 0.0
    assert metrics["commission_drag_initial"] == 0.0001


def test_cagr_uses_elapsed_sessions_not_only_resolved_nav_rows() -> None:
    nav = pd.DataFrame(
        {
            "nav": [1_000_000.0, float("nan"), 1_005_000.0, 1_010_000.0],
            "daily_return": [0.0, float("nan"), 0.005, 1_010_000 / 1_005_000 - 1],
            "cash_weight": [1.0, float("nan"), 1.0, 1.0],
            "holdings_count": [0, 0, 0, 0],
            "max_single_name_weight": [0.0, 0.0, 0.0, 0.0],
            "valuation_status": ["complete", "unresolved", "complete", "complete"],
            "rejected_target_weight": [0.0] * 4,
            "deferred_target_weight": [0.0] * 4,
        }
    )
    metrics = performance_metrics(nav, 1_000_000.0, 0, 0, 0.0, 0.0, 0.0)
    assert metrics["sessions"] == 4
    assert metrics["resolved_sessions"] == 3
    assert metrics["cagr"] == (1.01 ** (252.0 / 4.0)) - 1.0


def test_stable_hash_is_row_and_value_sensitive() -> None:
    first = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    second = pd.DataFrame({"a": [1, 3], "b": ["x", "y"]})
    assert stable_frame_hash(first) != stable_frame_hash(second)


def test_target_contract_requires_next_open_after_information() -> None:
    tz = ZoneInfo("Europe/Warsaw")
    value = TargetWeightIntent(
        intent_id="i", batch_id="b", account_id="a", security_id="s",
        decision_ts=datetime(2026, 1, 2, 17, 10, tzinfo=tz),
        information_available_ts=datetime(2026, 1, 2, 17, 5, tzinfo=tz),
        earliest_eligible_execution_ts=datetime(2026, 1, 5, 9, 0, tzinfo=tz),
        earliest_eligible_session=pd.Timestamp("2026-01-05").date(), target_weight=Decimal("1"), currency="PLN",
        source_run_id="r", signal_version="v", data_manifest_id="m", data_manifest_path="D:/x/manifest.json",
        data_manifest_sha256="a" * 64, official_universe_denominator=1, usable_price_count=1, feature_eligible_count=1,
        reason="test", provenance={},
    )
    assert value.information_available_ts < value.decision_ts < value.earliest_eligible_execution_ts


def test_equal_weight_grid_never_exceeds_one() -> None:
    from decimal import ROUND_DOWN

    for count in range(1, 61):
        weight = (Decimal(1) / Decimal(count)).quantize(Decimal("0.000000000001"), rounding=ROUND_DOWN)
        assert weight * count <= Decimal(1)
        assert Decimal(1) - weight * count < Decimal("0.000000000060")


def test_v2_overlay_changes_only_declared_accounting_inputs() -> None:
    root = Path(__file__).resolve().parents[1]
    base = load_effective_config(root / "config.json")
    corrected = load_effective_config(root / "config_v2.json")
    assert corrected["run_id"].endswith("-v2")
    assert corrected["signal"] == base["signal"]
    assert corrected["portfolio"] == base["portfolio"]
    assert corrected["economic_gate"] == base["economic_gate"]
    assert corrected["play_exit_supplement_sha256"] == "4405e22431416aaff84bab82d842db699482bc472d03825dcd441130ee852028"


def test_v3_overlay_changes_only_declared_accounting_inputs() -> None:
    root = Path(__file__).resolve().parents[1]
    base = load_effective_config(root / "config.json")
    corrected = load_effective_config(root / "config_v3.json")
    assert corrected["run_id"].endswith("-v3")
    assert corrected["signal"] == base["signal"]
    assert corrected["portfolio"] == base["portfolio"]
    assert corrected["economic_gate"] == base["economic_gate"]
    assert corrected["play_exit_supplement_sha256"] == "a7dd1df9764a32455ddaf49939f606bc650c61267981b3a1ee80961b08ef2d70"


def test_v4_overlay_changes_no_frozen_strategy_or_gate_parameter() -> None:
    root = Path(__file__).resolve().parents[1]
    base = load_effective_config(root / "config.json")
    repaired = load_effective_config(root / "config_v4.json")
    assert repaired["run_id"].endswith("-v4")
    for field in ("periods", "universe", "signal", "portfolio", "timing", "accounting", "concentration", "economic_gate"):
        assert repaired[field] == base[field]
    assert repaired["repair_plan_file"] == "v4_repair_plan.md"
    assert repaired["play_exit_supplement_sha256"] == "a7dd1df9764a32455ddaf49939f606bc650c61267981b3a1ee80961b08ef2d70"


def test_last_valid_cohort_gets_one_exact_terminal_liquidation() -> None:
    sessions = pd.bdate_range("2026-01-02", periods=21)
    rows = []
    for session in sessions:
        for number in range(60):
            rows.append(
                {
                    "session_date": session,
                    "security_id": f"isin:TEST{number:02d}",
                    "isin": f"TEST{number:02d}",
                    "feature_eligible": True,
                    "quantile": number // 12 + 1,
                    "native_open": 100.0,
                    "expected_trading": True,
                    "missing_state": None,
                    "nontrading_reason": None,
                    "unresolved_or_missing_state": None,
                    "prior_price_usable": True,
                    "proximity_to_max_high_252": 0.8 + number / 1000,
                    "rank": float(number + 1),
                    "percentile": (number + 1) / 60,
                }
            )
    config = {
        "periods": {"common": [sessions[0].date().isoformat(), sessions[-1].date().isoformat()]},
    }
    decisions, targets = build_decisions(config, pd.DataFrame(rows))
    for portfolio in ("q5", "eligible_universe_benchmark", "q1"):
        sleeve = decisions.loc[
            decisions["period"].eq("common")
            & decisions["offset"].eq(0)
            & decisions["portfolio"].eq(portfolio)
        ].sort_values("decision_date")
        assert sleeve["decision_type"].tolist() == ["entry_rebalance", "terminal_liquidation"]
        assert sleeve.iloc[0]["scheduled_endpoint_date"] == sessions[-1]
        assert sleeve.iloc[1]["decision_date"] == sessions[-1]
        terminal = targets.loc[
            targets["period"].eq("common")
            & targets["offset"].eq(0)
            & targets["portfolio"].eq(portfolio)
            & targets["decision_date"].eq(sessions[-1])
        ]
        assert len(terminal) > 0
        assert terminal["target_role"].eq("terminal_liquidation").all()
        assert terminal["target_weight"].eq("0").all()
    assert not decisions.loc[decisions["offset"].gt(0)].shape[0]


def test_play_unavailable_zero_target_requires_cash_action(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    exits = tmp_path / "exits.csv"
    pd.DataFrame(
        columns=[
            "isin", "event_type", "membership_exit_effective_date", "last_trading_date",
            "trading_suspension_from", "squeeze_out_or_settlement_date", "consideration",
        ]
    ).to_csv(exits, index=False)
    config = {
        "accepted_exit_evidence": str(exits),
        "play_exit_supplement": str(root / "play_exit_supplement_v2.json"),
        "periods": {"expanded": ["2019-12-23", "2026-08-18"]},
    }
    decisions = pd.DataFrame(
        [
            {"period": "expanded", "offset": 10, "portfolio": "q5", "decision_date": pd.Timestamp("2020-11-24"), "decision_type": "entry_rebalance"},
            {"period": "expanded", "offset": 10, "portfolio": "q5", "decision_date": pd.Timestamp("2020-12-22"), "decision_type": "entry_rebalance"},
            {"period": "expanded", "offset": 10, "portfolio": "q5", "decision_date": pd.Timestamp("2021-01-21"), "decision_type": "terminal_liquidation"},
        ]
    )
    targets = pd.DataFrame(
        [
            {"period": "expanded", "offset": 10, "portfolio": "q5", "decision_date": pd.Timestamp("2020-11-24"), "target_role": "selected_entry", "target_weight": "1", "security_id": "isin:LU1642887738", "isin": "LU1642887738"},
            {"period": "expanded", "offset": 10, "portfolio": "q5", "decision_date": pd.Timestamp("2020-12-22"), "target_role": "selected_entry", "target_weight": "1", "security_id": "isin:OTHER", "isin": "OTHER"},
            {"period": "expanded", "offset": 10, "portfolio": "q5", "decision_date": pd.Timestamp("2021-01-21"), "target_role": "terminal_liquidation", "target_weight": "0", "security_id": "isin:LU1642887738", "isin": "LU1642887738"},
            {"period": "expanded", "offset": 10, "portfolio": "q5", "decision_date": pd.Timestamp("2021-01-21"), "target_role": "terminal_liquidation", "target_weight": "0", "security_id": "isin:OTHER", "isin": "OTHER"},
        ]
    )
    candidate = pd.DataFrame(
        [
            {
                "session_date": pd.Timestamp("2021-01-21"), "security_id": "isin:OTHER",
                "native_open": 100.0, "native_close": 100.0, "expected_trading": True,
                "nontrading_reason": None, "missing_state": None,
            },
        ]
    )
    preflight, _ = build_event_preflight(config, decisions, targets, candidate)
    play = preflight.loc[preflight["isin"].eq("LU1642887738")].iloc[0]
    assert play["last_trading_date"] == "2020-12-21"
    assert play["trading_suspension_from"] == "2020-12-22"
    assert bool(play["action_required"])


def test_play_action_uses_announced_cash_terms_once() -> None:
    rows = pd.DataFrame(
        [
            {
                "isin": "LU1642887738",
                "action_required": True,
                "trading_suspension_from": "2020-12-23",
                "consideration": "PLN 39.00 cash per share",
            }
        ]
    )
    events, actions = action_inputs(rows)
    assert len(events) == 1 and len(actions) == 1
    assert actions[0].cash_amount_per_share == Decimal("39.00")
    assert actions[0].available_ts.date().isoformat() == "2020-12-21"
    assert actions[0].effective_session.isoformat() == "2020-12-23"
