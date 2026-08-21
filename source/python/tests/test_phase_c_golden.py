"""Hand-calculated Phase C golden cases.

The expected trade ledger is deliberately a checked-in CSV: its values were
calculated from PHASE_C.md's Decimal, next-open, 15 bps slippage, and 10 bps
commission rules.  These tests must not derive expectations from the engine.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from ats_contracts.portfolio import (
    ExcludedMemberState,
    RejectionDisposition,
    Side,
    TargetWeightIntent,
    ValuationStatus,
)
from ats_portfolio.config import PortfolioConfig
from ats_portfolio.engine import DailyPortfolioEngine
from ats_portfolio.market import MarketBar


D = Decimal
TZ = ZoneInfo("Europe/Warsaw")
FIXTURE = Path(__file__).parent / "fixtures" / "phase_c" / "golden_trade_ledger.csv"
STATE_FIXTURE = Path(__file__).parent / "fixtures" / "phase_c" / "golden_state_ledger.csv"
MANIFEST_ID = "phase-b-pinned-v1"
MANIFEST_PATH = "/pinned/phase_b/manifest.json"
MANIFEST_SHA256 = "a" * 64


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


def bar(day: date, security_id: str, open_: str | None, close: str | None) -> MarketBar:
    return MarketBar(
        security_id=security_id,
        session_date=day,
        event_ts=at(day, 17),
        available_ts=at(day, 17, 1),
        open=D(open_) if open_ is not None else None,
        close=D(close) if close is not None else None,
        currency="PLN",
    )


def intent(
    *,
    batch_id: str,
    security_id: str,
    weight: str,
    decision_day: date,
    eligible_day: date,
    official: int = 1,
    usable: int = 1,
    eligible: int = 1,
    excluded: tuple[ExcludedMemberState, ...] = (),
) -> TargetWeightIntent:
    return TargetWeightIntent(
        intent_id=f"{batch_id}-{security_id}",
        batch_id=batch_id,
        account_id="golden-account",
        security_id=security_id,
        decision_ts=at(decision_day, 17, 2),
        information_available_ts=at(decision_day, 17, 1),
        earliest_eligible_execution_ts=at(eligible_day, 9),
        earliest_eligible_session=eligible_day,
        target_weight=D(weight),
        currency="PLN",
        source_run_id="phase-b-golden-input",
        signal_version="frozen-signal-v1",
        data_manifest_id=MANIFEST_ID,
        data_manifest_path=MANIFEST_PATH,
        data_manifest_sha256=MANIFEST_SHA256,
        official_universe_denominator=official,
        usable_price_count=usable,
        feature_eligible_count=eligible,
        excluded_member_states=excluded,
        reason="hand-calculated golden fixture",
        provenance={"fixture": "phase-c-golden"},
    )


def config(*, initial_cash: str = "1000", stale_sessions: int | None = None) -> PortfolioConfig:
    return PortfolioConfig(
        phase_root=Path("/phase-c"),
        phase_b_manifest=Path(MANIFEST_PATH),
        intents_file=Path("/phase-c/intents.csv"),
        account_id="golden-account",
        initial_cash=D(initial_cash),
        max_stale_valuation_sessions=stale_sessions,
    )


def run(
    bars: list[MarketBar], intents: list[TargetWeightIntent], *, initial_cash: str = "1000", stale_sessions: int | None = None
):
    return DailyPortfolioEngine(
        config=config(initial_cash=initial_cash, stale_sessions=stale_sessions),
        run_id="golden-run",
        bars=bars,
        intents=intents,
        known_security_ids={row.security_id for row in bars} | {row.security_id for row in intents},
        data_manifest_id=MANIFEST_ID,
        data_manifest_path=MANIFEST_PATH,
        data_manifest_sha256=MANIFEST_SHA256,
    ).run()


def golden_rows(scenario: str) -> list[dict[str, str]]:
    with FIXTURE.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row["scenario"] == scenario]


def golden_state(scenario: str) -> dict[str, str]:
    with STATE_FIXTURE.open(newline="", encoding="utf-8") as handle:
        return next(row for row in csv.DictReader(handle) if row["scenario"] == scenario)


def assert_golden_fill(result, expected: dict[str, str]) -> None:
    fill = next(
        row
        for row in result.fills
        if row.security_id == expected["security_id"] and row.side == Side(expected["side"])
    )
    order = next(row for row in result.orders if row.event_id == fill.order_id)
    commission_movement = next(
        row for row in result.cash_movements if row.fill_id == fill.event_id and row.movement_type.value == "commission"
    )
    assert fill.timestamp.date().isoformat() == expected["session_date"]
    assert order.execution_equity == D(expected["execution_equity"])
    assert order.raw_open_price == D(expected["raw_open_price"])
    assert order.requested_quantity == D(expected["requested_quantity"])
    assert order.generated_quantity == D(expected["generated_quantity"])
    assert order.cash_scale == D(expected["cash_scale"])
    assert fill.fill_price == D(expected["fill_price"])
    assert fill.notional == D(expected["notional"])
    assert fill.commission == D(expected["commission"])
    assert commission_movement.balance_after == D(expected["cash_after"])


def test_no_same_close_fill_and_next_open_costed_fill() -> None:
    first, second = date(2025, 1, 6), date(2025, 1, 7)
    result = run(
        [bar(first, "A", "100", "100"), bar(second, "A", "110", "110")],
        [intent(batch_id="timing", security_id="A", weight="0.5", decision_day=first, eligible_day=second)],
    )

    assert len(result.fills) == 1
    assert result.fills[0].timestamp == at(second, 9)
    assert result.fills[0].timestamp.date() != first
    assert result.fills[0].price_field == "open"
    assert result.fills[0].source_bar_event_ts == at(second, 17)
    assert_golden_fill(result, golden_rows("timing_next_open")[0])


def test_fractional_rebalance_sells_first_with_separate_costs() -> None:
    first, second = date(2025, 2, 3), date(2025, 2, 4)
    result = run(
        [
            bar(first, "A", "100", "100"),
            bar(second, "A", "200", "200"),
            bar(second, "B", "50", "50"),
        ],
        [
            intent(batch_id="open-a", security_id="A", weight="0.5", decision_day=date(2025, 2, 2), eligible_day=first),
            intent(batch_id="rebalance", security_id="A", weight="0.25", decision_day=first, eligible_day=second),
            intent(batch_id="rebalance", security_id="B", weight="0.25", decision_day=first, eligible_day=second),
        ],
    )

    assert [fill.side for fill in result.fills] == [Side.BUY, Side.SELL, Side.BUY]
    for scenario in ("fractional_rebalance_initial", "fractional_rebalance_sell", "fractional_rebalance_buy"):
        assert_golden_fill(result, golden_rows(scenario)[0])


def test_insufficient_cash_scales_all_buys_by_one_common_fraction() -> None:
    session = date(2025, 3, 3)
    result = run(
        [bar(session, "A", "100", "100"), bar(session, "B", "100", "100")],
        [
            intent(batch_id="cash-scale", security_id="A", weight="0.5", decision_day=date(2025, 3, 2), eligible_day=session),
            intent(batch_id="cash-scale", security_id="B", weight="0.5", decision_day=date(2025, 3, 2), eligible_day=session),
        ],
        initial_cash="100",
    )

    for scenario in ("insufficient_cash_a", "insufficient_cash_b"):
        assert_golden_fill(result, golden_rows(scenario)[0])
    assert result.orders[0].cash_scale == result.orders[1].cash_scale == D("0.997504741888")
    assert result.rejections[0].disposition == RejectionDisposition.DEFERRED
    assert result.rejections[0].reason_code == "insufficient_cash_buy_scale"
    assert result.portfolio_snapshots[-1].cash == D("0.000000")


def test_missing_new_and_existing_opens_remain_visible_as_rejected_and_deferred() -> None:
    first, second = date(2025, 4, 1), date(2025, 4, 2)
    result = run(
        [
            bar(first, "A", "100", "100"),
            bar(second, "A", None, "100"),
            bar(second, "B", None, "50"),
        ],
        [
            intent(batch_id="buy-a", security_id="A", weight="0.5", decision_day=date(2025, 3, 31), eligible_day=first),
            intent(batch_id="missing-opens", security_id="A", weight="0.2", decision_day=first, eligible_day=second),
            intent(batch_id="missing-opens", security_id="B", weight="0.3", decision_day=first, eligible_day=second),
        ],
        stale_sessions=1,
    )

    missing = {row.security_id: row for row in result.rejections if row.batch_id == "missing-opens"}
    existing_expected = golden_state("missing_existing_open")
    new_expected = golden_state("missing_new_open")
    assert missing["A"].disposition.value == existing_expected["disposition"]
    assert missing["A"].reason_code == existing_expected["reason_code"]
    assert missing["B"].disposition.value == new_expected["disposition"]
    assert missing["B"].reason_code == new_expected["reason_code"]
    assert len(result.fills) == 1  # Only the prior-session purchase of A filled.
    snapshot = result.portfolio_snapshots[-1]
    assert snapshot.rejected_target_weight == D("0.300000000000")
    assert snapshot.deferred_target_weight == D("0.200000000000")
    assert snapshot.unallocated_weight == D("1.000000000000")


def test_missing_close_uses_bounded_stale_mark_then_becomes_unresolved() -> None:
    first, second, third = date(2025, 5, 5), date(2025, 5, 6), date(2025, 5, 7)
    result = run(
        [bar(first, "A", "100", "100"), bar(second, "A", "100", None), bar(third, "A", "100", None)],
        [intent(batch_id="buy-a", security_id="A", weight="0.5", decision_day=date(2025, 5, 2), eligible_day=first)],
        stale_sessions=1,
    )

    stale = next(row for row in result.valuations if row.session_date == second)
    unresolved = next(row for row in result.valuations if row.session_date == third)
    stale_expected = golden_state("stale_close")
    unresolved_expected = golden_state("unresolved_close")
    assert stale.status.value == stale_expected["status"]
    assert stale.price == D(stale_expected["price"])
    assert stale.market_value == D(stale_expected["market_value"])
    assert stale.stale_age_sessions == 1
    assert unresolved.status.value == unresolved_expected["status"]
    assert unresolved.price is None and unresolved.market_value is None
    assert result.portfolio_snapshots[-1].valuation_status == ValuationStatus.UNRESOLVED
    assert result.portfolio_snapshots[-1].unvalued_security_ids == ("A",)


def test_57_of_60_metadata_exclusions_and_cash_weight_are_not_recast() -> None:
    session = date(2025, 6, 2)
    exclusions = (
        ExcludedMemberState(security_id="X", raw_identifier="X", state="missing_price", reason="no usable bar"),
        ExcludedMemberState(security_id="Y", raw_identifier="Y", state="missing_price", reason="no usable bar"),
        ExcludedMemberState(security_id="Z", raw_identifier="Z", state="missing_price", reason="no usable bar"),
    )
    result = run(
        [bar(session, "A", "100", "100")],
        [
            intent(
                batch_id="57-of-60",
                security_id="A",
                weight="0.57",
                decision_day=date(2025, 5, 30),
                eligible_day=session,
                official=60,
                usable=57,
                eligible=57,
                excluded=exclusions,
            )
        ],
    )

    snapshot = result.portfolio_snapshots[-1]
    expected = golden_state("official_57_of_60")
    assert snapshot.official_universe_denominator == int(expected["official_denominator"])
    assert snapshot.usable_price_count == snapshot.feature_eligible_count == int(expected["usable_count"])
    assert snapshot.excluded_member_states == exclusions
    assert snapshot.gross_target_weight == D("0.570000000000")
    assert snapshot.rejected_target_weight == snapshot.deferred_target_weight == D("0")
    assert snapshot.unallocated_weight == D(expected["unallocated_weight"])
