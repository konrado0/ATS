from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from ats_contracts.portfolio import TargetWeightIntent
from ats_portfolio.config import PortfolioConfig
from ats_portfolio.engine import DailyPortfolioEngine
from ats_portfolio.market import MarketBar
from ats_portfolio.storage import logical_rows_hash


TZ = ZoneInfo("Europe/Warsaw")
DAY = date(2025, 7, 1)
MANIFEST = "D:/Stock/data/ATS/phase_b/versions/phaseb-pinned/manifest.json"
MANIFEST_HASH = "b" * 64


def stamp(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=TZ)


def config(**updates: object) -> PortfolioConfig:
    values: dict[str, object] = {
        "phase_root": Path("D:/Stock/data/ATS/phase_c"),
        "phase_b_manifest": Path(MANIFEST),
        "intents_file": Path("D:/Stock/data/ATS/phase_c/fixture-intents.json"),
        "account_id": "contract-account",
        "initial_cash": Decimal("1000"),
    }
    values.update(updates)
    return PortfolioConfig.model_validate(values)


def intent(
    security_id: str = "A",
    target_weight: str = "0.5",
    *,
    intent_id: str | None = None,
    batch_id: str = "batch",
    decision: datetime | None = None,
    information: datetime | None = None,
    eligible_day: date = DAY,
) -> TargetWeightIntent:
    decision_ts = decision or stamp(DAY, 8)
    return TargetWeightIntent(
        intent_id=intent_id or f"intent-{security_id}",
        batch_id=batch_id,
        account_id="contract-account",
        security_id=security_id,
        decision_ts=decision_ts,
        information_available_ts=information or decision_ts,
        earliest_eligible_execution_ts=stamp(eligible_day, 9),
        earliest_eligible_session=eligible_day,
        target_weight=Decimal(target_weight),
        currency="PLN",
        source_run_id="frozen-source",
        signal_version="frozen-v1",
        data_manifest_id="phaseb-pinned",
        data_manifest_path=MANIFEST,
        data_manifest_sha256=MANIFEST_HASH,
        official_universe_denominator=1,
        usable_price_count=1,
        feature_eligible_count=1,
        reason="contract fixture",
        provenance={"fixture": True},
    )


def bar(security_id: str = "A", *, open_: str = "10", close: str = "10") -> MarketBar:
    return MarketBar(
        security_id=security_id,
        session_date=DAY,
        event_ts=stamp(DAY, 17),
        available_ts=datetime(2025, 7, 1, 17, 5, tzinfo=TZ),
        open=Decimal(open_),
        close=Decimal(close),
        currency="PLN",
    )


def engine(bars: list[MarketBar], intents: list[TargetWeightIntent], run_id: str = "contract-run") -> DailyPortfolioEngine:
    return DailyPortfolioEngine(
        config(),
        run_id,
        bars,
        intents,
        {row.security_id for row in bars},
        "phaseb-pinned",
        MANIFEST,
        MANIFEST_HASH,
    )


def test_contracts_fail_closed_on_temporal_counts_mutable_manifest_and_forbidden_config() -> None:
    with pytest.raises(ValidationError, match="information_available_ts is after decision_ts"):
        intent(information=stamp(DAY, 9))
    payload = intent().model_dump()
    payload.update(official_universe_denominator=60, usable_price_count=57, feature_eligible_count=57)
    with pytest.raises(ValidationError, match="excluded member states"):
        TargetWeightIntent.model_validate(payload)
    payload = intent().model_dump()
    payload["data_manifest_path"] = "D:/Stock/data/ATS/phase_b/catalogs/current.json"
    with pytest.raises(ValidationError, match="explicit manifest.json|mutable"):
        TargetWeightIntent.model_validate(payload)
    payload = intent().model_dump()
    payload["exclusion_artifact_sha256"] = "c" * 64
    with pytest.raises(ValidationError, match="exclusion artifact mode is not supported"):
        TargetWeightIntent.model_validate(payload)
    with pytest.raises(ValidationError):
        config(allow_shorting=True)


def test_batch_weight_and_unknown_identity_fail_closed() -> None:
    with pytest.raises(ValueError, match="target weights exceed one"):
        engine([bar("A"), bar("B")], [intent("A", "0.6"), intent("B", "0.5")])
    with pytest.raises(ValueError, match="unknown intent security identity"):
        engine([bar("A")], [intent("B")])


def test_no_eligible_future_session_is_explicit_and_ordered() -> None:
    later = date(2025, 7, 2)
    result = engine([bar()], [intent(eligible_day=later)]).run()
    assert not result.fills
    assert result.rejections[-1].reason_code == "no_eligible_future_session"
    assert result.rejections[-1].timestamp >= result.portfolio_snapshots[-1].timestamp
    events = result.all_events()
    assert [row.timestamp for row in events] == sorted(row.timestamp for row in events)


def test_multiple_batches_on_one_execution_session_fail_closed() -> None:
    with pytest.raises(ValueError, match="multiple intent batches resolve"):
        engine(
            [bar("A"), bar("B")],
            [intent("A", batch_id="first"), intent("B", batch_id="second")],
        ).run()


def test_foreign_currency_held_mark_cannot_enter_execution_equity() -> None:
    first, second = date(2025, 7, 1), date(2025, 7, 2)
    bars = [
        bar("A"),
        MarketBar(
            security_id="A",
            session_date=second,
            event_ts=stamp(second, 17),
            available_ts=datetime(2025, 7, 2, 17, 5, tzinfo=TZ),
            open=Decimal("10"),
            close=Decimal("10"),
            currency="USD",
        ),
        MarketBar(
            security_id="B",
            session_date=second,
            event_ts=stamp(second, 17),
            available_ts=datetime(2025, 7, 2, 17, 5, tzinfo=TZ),
            open=Decimal("10"),
            close=Decimal("10"),
            currency="PLN",
        ),
    ]
    intents = [
        intent("A", batch_id="buy-a"),
        intent(
            "B",
            batch_id="buy-b",
            decision=stamp(first, 17),
            information=stamp(first, 17),
            eligible_day=second,
        ),
    ]
    result = DailyPortfolioEngine(
        config(),
        "currency-run",
        bars,
        intents,
        {"A", "B"},
        "phaseb-pinned",
        MANIFEST,
        MANIFEST_HASH,
    ).run()
    assert [fill.intent_id for fill in result.fills] == ["intent-A"]
    assert any(row.reason_code == "unresolved_execution_equity" for row in result.rejections)


@pytest.mark.parametrize(
    ("currency", "source", "source_record_id", "reason"),
    [
        ("", "fixture", "fixture", "missing_currency"),
        ("PLN", "", "fixture", "missing_price_provenance"),
        ("EUR", "fixture", "fixture", "inconsistent_currency"),
    ],
)
def test_missing_currency_and_price_provenance_never_fill(
    currency: str, source: str, source_record_id: str, reason: str
) -> None:
    market_bar = MarketBar(
        security_id="A",
        session_date=DAY,
        event_ts=stamp(DAY, 17),
        available_ts=datetime(2025, 7, 1, 17, 5, tzinfo=TZ),
        open=Decimal("10"),
        close=Decimal("10"),
        currency=currency,
        source=source,
        source_record_id=source_record_id,
    )
    result = engine([market_bar], [intent()]).run()
    assert not result.fills
    assert result.rejections[0].reason_code == reason


def test_identical_replay_has_identical_event_and_ledger_hashes() -> None:
    first = engine([bar()], [intent()]).run()
    second = engine([bar()], [intent()]).run()
    assert [row.event_id for row in first.all_events()] == [row.event_id for row in second.all_events()]
    assert {
        name: logical_rows_hash(rows) for name, rows in first.ledgers().items()
    } == {
        name: logical_rows_hash(rows) for name, rows in second.ledgers().items()
    }


@settings(max_examples=30, deadline=None)
@given(
    cash=st.decimals(min_value="10", max_value="100000", places=2, allow_nan=False, allow_infinity=False),
    raw_price=st.decimals(min_value="0.10", max_value="1000", places=2, allow_nan=False, allow_infinity=False),
    target=st.decimals(min_value="0", max_value="1", places=4, allow_nan=False, allow_infinity=False),
)
def test_generated_small_ledgers_preserve_cash_and_complete_equity(
    cash: Decimal, raw_price: Decimal, target: Decimal
) -> None:
    local_config = config(initial_cash=cash)
    market_bar = bar(open_=str(raw_price), close=str(raw_price))
    portfolio = DailyPortfolioEngine(
        local_config,
        "property-run",
        [market_bar],
        [intent(target_weight=str(target))],
        {"A"},
        "phaseb-pinned",
        MANIFEST,
        MANIFEST_HASH,
    ).run()
    snapshot = portfolio.portfolio_snapshots[-1]
    assert snapshot.cash >= 0
    assert snapshot.market_value is not None and snapshot.equity is not None
    assert snapshot.cash + snapshot.market_value == snapshot.equity
    for fill in portfolio.fills:
        movement = next(row for row in portfolio.position_movements if row.fill_id == fill.event_id)
        cash_rows = [row for row in portfolio.cash_movements if row.fill_id == fill.event_id]
        assert movement.quantity_delta == fill.quantity
        assert sum((row.amount for row in cash_rows), Decimal("0")) == -fill.notional - fill.commission
