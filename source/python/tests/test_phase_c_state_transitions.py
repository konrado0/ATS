from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ats_contracts.portfolio import (
    CorporateActionInput,
    CorporateActionType,
    RejectionDisposition,
    SecurityEventInput,
    SecurityEventType,
    TargetWeightIntent,
    ValuationStatus,
)
from ats_portfolio.config import PortfolioConfig
from ats_portfolio.engine import DailyPortfolioEngine
from ats_portfolio.market import MarketBar
from ats_portfolio.validation import _validate_events


TZ = ZoneInfo("Europe/Warsaw")
MANIFEST_PATH = "D:/Stock/data/phase_b/runs/pinned/manifest.json"
MANIFEST_ID = "phase-b-pinned"
MANIFEST_HASH = "a" * 64
ACCOUNT_ID = "phase-c-state-test"


def stamp(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


def config(*, adjustment_policy: str = "adjusted_without_actions") -> PortfolioConfig:
    return PortfolioConfig(
        phase_root=Path("D:/Stock/data/phase_c"),
        phase_b_manifest=Path(MANIFEST_PATH),
        intents_file=Path("D:/Stock/data/phase_c/intents.jsonl"),
        account_id=ACCOUNT_ID,
        initial_cash=Decimal("1000"),
        commission_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        adjustment_policy=adjustment_policy,
    )


def bar(security_id: str, session: date, *, open: str | None = "10", close: str | None = "10", adjustment_state: str = "raw") -> MarketBar:
    return MarketBar(
        security_id=security_id,
        session_date=session,
        event_ts=stamp(session, 17),
        available_ts=stamp(session, 17, 1),
        open=Decimal(open) if open is not None else None,
        close=Decimal(close) if close is not None else None,
        currency="PLN",
        adjustment_state=adjustment_state,
    )


def intent(intent_id: str, batch_id: str, security_id: str, session: date, weight: str) -> TargetWeightIntent:
    return TargetWeightIntent(
        intent_id=intent_id,
        batch_id=batch_id,
        account_id=ACCOUNT_ID,
        security_id=security_id,
        decision_ts=stamp(session, 8),
        information_available_ts=stamp(session, 8),
        earliest_eligible_execution_ts=stamp(session, 9),
        earliest_eligible_session=session,
        target_weight=Decimal(weight),
        currency="PLN",
        source_run_id="phase-b-source",
        signal_version="frozen-intent-v1",
        data_manifest_id=MANIFEST_ID,
        data_manifest_path=MANIFEST_PATH,
        data_manifest_sha256=MANIFEST_HASH,
        official_universe_denominator=1,
        usable_price_count=1,
        feature_eligible_count=1,
        reason="state-transition test",
        provenance={"fixture": "phase-c-state-transitions"},
    )


def security_event(
    event_id: str,
    revision: int,
    security_id: str,
    event_type: SecurityEventType,
    effective_session: date,
    *,
    available_session: date | None = None,
    new_identifier: str | None = None,
) -> SecurityEventInput:
    available = available_session or effective_session
    return SecurityEventInput(
        event_id=event_id,
        revision=revision,
        security_id=security_id,
        event_type=event_type,
        event_ts=stamp(min(effective_session, available), 8),
        available_ts=stamp(available, 8),
        effective_session=effective_session,
        new_identifier=new_identifier,
        reason="state-transition test",
        provenance={"fixture": "phase-c-state-transitions"},
    )


def action(
    action_id: str,
    revision: int,
    security_id: str,
    action_type: CorporateActionType,
    effective_session: date,
    *,
    available_session: date | None = None,
    ratio: str | None = None,
    successor: str | None = None,
    cash_per_share: str | None = None,
) -> CorporateActionInput:
    available = available_session or effective_session
    return CorporateActionInput(
        action_id=action_id,
        revision=revision,
        security_id=security_id,
        action_type=action_type,
        event_ts=stamp(min(effective_session, available), 8),
        available_ts=stamp(available, 8),
        effective_session=effective_session,
        related_security_id=successor,
        ratio=Decimal(ratio) if ratio is not None else None,
        cash_amount_per_share=Decimal(cash_per_share) if cash_per_share is not None else None,
        currency="PLN" if cash_per_share is not None else None,
        reason="state-transition test",
        provenance={"fixture": "phase-c-state-transitions"},
    )


def run(
    bars: list[MarketBar],
    intents: list[TargetWeightIntent],
    *,
    security_events: list[SecurityEventInput] | None = None,
    corporate_actions: list[CorporateActionInput] | None = None,
    adjustment_policy: str = "adjusted_without_actions",
) -> object:
    known = {item.security_id for item in bars}
    return DailyPortfolioEngine(
        config(adjustment_policy=adjustment_policy),
        "phase-c-state-transition-run",
        bars,
        intents,
        known,
        MANIFEST_ID,
        MANIFEST_PATH,
        MANIFEST_HASH,
        security_events=security_events or [],
        corporate_actions=corporate_actions or [],
    ).run()


def test_suspension_defers_existing_position_until_known_resumption() -> None:
    day_one, day_two, day_three = date(2025, 1, 6), date(2025, 1, 7), date(2025, 1, 8)
    result = run(
        [bar("AAA", day_one), bar("AAA", day_two), bar("AAA", day_three)],
        [
            intent("buy", "buy-batch", "AAA", day_one, "1"),
            intent("suspended-exit", "suspended-exit-batch", "AAA", day_two, "0"),
            intent("resumed-exit", "resumed-exit-batch", "AAA", day_three, "0"),
        ],
        security_events=[
            security_event("suspension", 0, "AAA", SecurityEventType.SUSPENSION, day_two),
            security_event("resumption", 0, "AAA", SecurityEventType.RESUMPTION, day_three),
        ],
    )

    deferred = next(item for item in result.rejections if item.intent_id == "suspended-exit")
    assert deferred.disposition == RejectionDisposition.DEFERRED
    assert deferred.reason_code == "suspended"
    assert [item.intent_id for item in result.fills] == ["buy", "resumed-exit"]
    assert result.portfolio_snapshots[-1].market_value == Decimal("0")


@pytest.mark.parametrize(
    ("action_type", "ratio", "expected_quantity"),
    [
        (CorporateActionType.SPLIT, "2", Decimal("200")),
        (CorporateActionType.REVERSE_SPLIT, "0.2", Decimal("20")),
    ],
)
def test_split_actions_change_quantity_at_the_open(
    action_type: CorporateActionType, ratio: str, expected_quantity: Decimal
) -> None:
    day_one, day_two = date(2025, 1, 6), date(2025, 1, 7)
    result = run(
        [bar("AAA", day_one), bar("AAA", day_two, open="5", close="5")],
        [intent("buy", "buy-batch", "AAA", day_one, "1")],
        corporate_actions=[action("split", 0, "AAA", action_type, day_two, ratio=ratio)],
        adjustment_policy="raw_with_explicit_actions",
    )

    application = result.corporate_action_applications[0]
    assert application.source_quantity_before == Decimal("100")
    assert application.source_quantity_after == expected_quantity
    assert application.timestamp == stamp(day_two, 9)
    assert result.positions[-1].quantity == expected_quantity


def test_merger_removes_source_and_credits_successor_shares() -> None:
    day_one, day_two = date(2025, 1, 6), date(2025, 1, 7)
    result = run(
        [bar("AAA", day_one), bar("AAA", day_two), bar("BBB", day_two, open="20", close="20")],
        [intent("buy", "buy-batch", "AAA", day_one, "1")],
        corporate_actions=[
            action("merger", 0, "AAA", CorporateActionType.MERGER, day_two, ratio="0.5", successor="BBB")
        ],
        adjustment_policy="raw_with_explicit_actions",
    )

    application = result.corporate_action_applications[0]
    assert (application.source_quantity_after, application.related_quantity_after) == (Decimal("0E-12"), Decimal("50"))
    assert [(item.security_id, item.quantity) for item in result.positions[-1:]] == [("BBB", Decimal("50"))]
    assert {item.movement_type.value for item in result.position_movements[-2:]} == {"merger_remove", "merger_receive"}


def test_cash_takeover_removes_shares_and_credits_cash() -> None:
    day_one, day_two = date(2025, 1, 6), date(2025, 1, 7)
    result = run(
        [bar("AAA", day_one), bar("AAA", day_two)],
        [intent("buy", "buy-batch", "AAA", day_one, "1")],
        corporate_actions=[
            action("takeover", 0, "AAA", CorporateActionType.CASH_TAKEOVER, day_two, cash_per_share="12")
        ],
        adjustment_policy="raw_with_explicit_actions",
    )

    application = result.corporate_action_applications[0]
    snapshot = result.portfolio_snapshots[-1]
    assert application.cash_delta == Decimal("1200")
    assert snapshot.cash == Decimal("1200")
    assert snapshot.market_value == Decimal("0")
    assert snapshot.equity == Decimal("1200")


def test_delisting_without_terms_keeps_shares_and_leaves_value_unresolved() -> None:
    day_one, day_two = date(2025, 1, 6), date(2025, 1, 7)
    result = run(
        [bar("AAA", day_one), bar("AAA", day_two)],
        [intent("buy", "buy-batch", "AAA", day_one, "1")],
        security_events=[security_event("delisting", 0, "AAA", SecurityEventType.DELISTING, day_two)],
    )

    valuation = result.valuations[-1]
    snapshot = result.portfolio_snapshots[-1]
    assert valuation.quantity == Decimal("100")
    assert valuation.status == ValuationStatus.UNRESOLVED
    assert valuation.market_value is None
    assert snapshot.valuation_status == ValuationStatus.UNRESOLVED
    assert snapshot.unvalued_security_ids == ("AAA",)


def test_identifier_change_preserves_position_under_stable_security_id() -> None:
    day_one, day_two = date(2025, 1, 6), date(2025, 1, 7)
    result = run(
        [bar("AAA", day_one), bar("AAA", day_two)],
        [intent("buy", "buy-batch", "AAA", day_one, "1")],
        security_events=[
            security_event("rename", 0, "AAA", SecurityEventType.IDENTIFIER_CHANGE, day_two, new_identifier="NEW")
        ],
    )

    position = result.positions[-1]
    assert (position.security_id, position.quantity, position.identifier) == ("AAA", Decimal("100"), "NEW")
    assert len(result.position_movements) == 1


@pytest.mark.parametrize(
    ("policy", "adjustment_state", "message"),
    [
        ("adjusted_without_actions", "raw", "explicit actions are prohibited"),
        ("raw_with_explicit_actions", "adjusted", "ambiguous adjusted bars"),
    ],
)
def test_adjusted_bar_and_explicit_action_combinations_fail_closed(
    policy: str, adjustment_state: str, message: str
) -> None:
    day = date(2025, 1, 6)
    with pytest.raises(ValueError, match=message):
        run(
            [bar("AAA", day, adjustment_state=adjustment_state)],
            [intent("buy", "buy-batch", "AAA", day, "1")],
            corporate_actions=[action("split", 0, "AAA", CorporateActionType.SPLIT, day, ratio="2")],
            adjustment_policy=policy,
        )


def test_highest_action_revision_known_before_effectiveness_replaces_earlier_revision() -> None:
    day_one, day_two = date(2025, 1, 6), date(2025, 1, 7)
    result = run(
        [bar("AAA", day_one), bar("AAA", day_two)],
        [intent("buy", "buy-batch", "AAA", day_one, "1")],
        corporate_actions=[
            action("split", 0, "AAA", CorporateActionType.SPLIT, day_two, available_session=day_one, ratio="2"),
            action("split", 1, "AAA", CorporateActionType.SPLIT, day_two, available_session=day_one, ratio="3"),
        ],
        adjustment_policy="raw_with_explicit_actions",
    )

    assert [(item.revision, item.source_quantity_after) for item in result.corporate_action_applications] == [
        (1, Decimal("300"))
    ]
    assert not result.rejections


def test_later_action_revision_requires_replay_without_double_application() -> None:
    day_one, day_two, day_three = date(2025, 1, 6), date(2025, 1, 7), date(2025, 1, 8)
    result = run(
        [bar("AAA", day_one), bar("AAA", day_two), bar("AAA", day_three)],
        [intent("buy", "buy-batch", "AAA", day_one, "1")],
        corporate_actions=[
            action("split", 0, "AAA", CorporateActionType.SPLIT, day_two, ratio="2"),
            action("split", 1, "AAA", CorporateActionType.SPLIT, day_two, available_session=day_three, ratio="3"),
        ],
        adjustment_policy="raw_with_explicit_actions",
    )

    assert len(result.corporate_action_applications) == 1
    assert result.positions[-1].quantity == Decimal("200")
    replay = result.rejections[-1]
    assert (replay.disposition, replay.reason_code) == (
        RejectionDisposition.REPLAY_REQUIRED,
        "later_revision_requires_replay",
    )


def test_later_security_event_revision_requires_replay_without_changing_applied_state() -> None:
    day_one, day_two, day_three = date(2025, 1, 6), date(2025, 1, 7), date(2025, 1, 8)
    result = run(
        [bar("AAA", day_one), bar("AAA", day_two), bar("AAA", day_three)],
        [intent("buy", "buy-batch", "AAA", day_one, "1")],
        security_events=[
            security_event("listing-status", 0, "AAA", SecurityEventType.SUSPENSION, day_two),
            security_event(
                "listing-status", 1, "AAA", SecurityEventType.RESUMPTION, day_two, available_session=day_three
            ),
        ],
    )

    assert result.positions[-1].tradeability_state == "suspended"
    assert result.rejections[-1].disposition == RejectionDisposition.REPLAY_REQUIRED


def test_duplicate_intent_and_event_revisions_are_rejected() -> None:
    day = date(2025, 1, 6)
    duplicated = intent("duplicate", "first", "AAA", day, "1")
    with pytest.raises(ValueError, match="duplicate intent ID or semantic key"):
        run([bar("AAA", day)], [duplicated, duplicated])

    event = security_event("duplicate-event", 0, "AAA", SecurityEventType.SUSPENSION, day)
    with pytest.raises(ValueError, match="duplicate event/action revision"):
        run([bar("AAA", day)], [intent("buy", "buy-batch", "AAA", day, "1")], security_events=[event, event])

    corporate = action("duplicate-action", 0, "AAA", CorporateActionType.SPLIT, day, ratio="2")
    with pytest.raises(ValueError, match="duplicate event/action revision"):
        run(
            [bar("AAA", day)],
            [intent("buy", "buy-batch", "AAA", day, "1")],
            corporate_actions=[corporate, corporate],
            adjustment_policy="raw_with_explicit_actions",
        )


def test_independent_validator_replays_security_event_state() -> None:
    day_one, day_two, day_three = date(2025, 2, 3), date(2025, 2, 4), date(2025, 2, 5)
    intents = [
        intent("buy", "buy-batch", "AAA", day_one, "1"),
        intent("exit", "exit-batch", "AAA", day_three, "0"),
    ]
    events = [
        security_event("suspend", 0, "AAA", SecurityEventType.SUSPENSION, day_two),
        security_event("resume", 0, "AAA", SecurityEventType.RESUMPTION, day_three),
    ]
    result = run(
        [bar("AAA", day_one), bar("AAA", day_two), bar("AAA", day_three)],
        intents,
        security_events=events,
    )
    ledgers = result.ledgers()
    ledgers["intents"] = sorted(intents, key=lambda row: (row.batch_id, row.security_id, row.intent_id))
    report = _validate_events(ledgers, intents, events, [], config())
    assert report["fills"] == 2


def test_independent_validator_matches_corporate_action_terms_and_movements() -> None:
    day_one, day_two = date(2025, 2, 3), date(2025, 2, 4)
    intents = [intent("buy", "buy-batch", "AAA", day_one, "1")]
    actions = [action("merger", 0, "AAA", CorporateActionType.MERGER, day_two, ratio="0.5", successor="BBB")]
    result = run(
        [bar("AAA", day_one), bar("AAA", day_two), bar("BBB", day_two, open="20", close="20")],
        intents,
        corporate_actions=actions,
        adjustment_policy="raw_with_explicit_actions",
    )
    ledgers = result.ledgers()
    ledgers["intents"] = intents
    report = _validate_events(
        ledgers,
        intents,
        [],
        actions,
        config(adjustment_policy="raw_with_explicit_actions"),
    )
    assert report["events"] == len(result.all_events())
