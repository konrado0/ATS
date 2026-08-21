from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable, Sequence, TypeVar

from pydantic import BaseModel

from ats_contracts.portfolio import (
    CashMovement,
    CashMovementType,
    CorporateActionApplication,
    CorporateActionInput,
    CorporateActionType,
    Fill,
    GeneratedOrder,
    LedgerEvent,
    PortfolioSnapshot,
    PositionMovement,
    PositionMovementType,
    PositionSnapshot,
    RejectionDisposition,
    RejectionOrDeferredAction,
    SecurityEventInput,
    SecurityEventType,
    Side,
    TargetWeightIntent,
    Valuation,
    ValuationStatus,
)
from ats_portfolio.config import PortfolioConfig
from ats_portfolio.market import MARKET_FIELD_TIMING_POLICY, MarketBar, modeled_open_timestamp
from ats_portfolio.numeric import (
    ONE,
    RECONCILIATION_TOLERANCE,
    ZERO,
    money,
    price,
    quantity,
    weight,
)


class LedgerInvariantError(ValueError):
    pass


TEvent = TypeVar("TEvent", bound=LedgerEvent)


@dataclass
class EngineResult:
    orders: list[GeneratedOrder] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    cash_movements: list[CashMovement] = field(default_factory=list)
    position_movements: list[PositionMovement] = field(default_factory=list)
    positions: list[PositionSnapshot] = field(default_factory=list)
    valuations: list[Valuation] = field(default_factory=list)
    portfolio_snapshots: list[PortfolioSnapshot] = field(default_factory=list)
    rejections: list[RejectionOrDeferredAction] = field(default_factory=list)
    corporate_action_applications: list[CorporateActionApplication] = field(default_factory=list)

    def ledgers(self) -> dict[str, list[LedgerEvent]]:
        return {
            "orders": list(self.orders),
            "fills": list(self.fills),
            "cash_movements": list(self.cash_movements),
            "position_movements": list(self.position_movements),
            "positions": list(self.positions),
            "valuations": list(self.valuations),
            "portfolio_snapshots": list(self.portfolio_snapshots),
            "rejections": list(self.rejections),
            "corporate_action_applications": list(self.corporate_action_applications),
        }

    def all_events(self) -> list[LedgerEvent]:
        return sorted(
            [event for rows in self.ledgers().values() for event in rows],
            key=lambda event: event.sequence,
        )


class DailyPortfolioEngine:
    def __init__(
        self,
        config: PortfolioConfig,
        run_id: str,
        bars: Sequence[MarketBar],
        intents: Sequence[TargetWeightIntent],
        known_security_ids: set[str],
        data_manifest_id: str,
        data_manifest_path: str,
        data_manifest_sha256: str,
        security_events: Sequence[SecurityEventInput] = (),
        corporate_actions: Sequence[CorporateActionInput] = (),
    ) -> None:
        self.config = config
        self.run_id = run_id
        self.bars = list(bars)
        self.intents = list(intents)
        self.known_security_ids = set(known_security_ids)
        self.data_manifest_id = data_manifest_id
        self.data_manifest_path = data_manifest_path
        self.data_manifest_sha256 = data_manifest_sha256
        self.security_events = list(security_events)
        self.corporate_actions = list(corporate_actions)
        self.result = EngineResult()
        self.sequence = 0
        self.cash = money(config.initial_cash)
        self.holdings: dict[str, Decimal] = {}
        self.last_close: dict[str, tuple[Decimal, datetime, int, str, str]] = {}
        self.tradeability: dict[str, str] = defaultdict(lambda: "tradeable")
        self.identifiers: dict[str, str] = {}
        self.applied_actions: dict[str, int] = {}
        self.applied_security_events: dict[str, int] = {}
        self.commission_rate = config.commission_bps / Decimal("10000")
        self.slippage_rate = config.slippage_bps / Decimal("10000")
        self._validate_inputs()

    def _validate_inputs(self) -> None:
        if not self.bars:
            raise ValueError("at least one market bar is required")
        bar_keys = [(bar.security_id, bar.session_date, bar.source, bar.adjustment_version) for bar in self.bars]
        if len(bar_keys) != len(set(bar_keys)):
            raise ValueError("duplicate market bar semantic key")
        unknown_bars = {bar.security_id for bar in self.bars} - self.known_security_ids
        if unknown_bars:
            raise ValueError(f"unknown bar security identity: {sorted(unknown_bars)}")
        intent_ids = [intent.intent_id for intent in self.intents]
        semantic_keys = [(intent.batch_id, intent.security_id) for intent in self.intents]
        if len(intent_ids) != len(set(intent_ids)) or len(semantic_keys) != len(set(semantic_keys)):
            raise ValueError("duplicate intent ID or semantic key")
        unknown_intents = {intent.security_id for intent in self.intents} - self.known_security_ids
        if unknown_intents:
            raise ValueError(f"unknown intent security identity: {sorted(unknown_intents)}")
        for intent in self.intents:
            if intent.account_id != self.config.account_id or intent.currency != self.config.account_currency:
                raise ValueError("intent account or currency is inconsistent with the shared account")
            if (
                intent.data_manifest_id != self.data_manifest_id
                or intent.data_manifest_sha256 != self.data_manifest_sha256
                or intent.data_manifest_path.replace("\\", "/") != self.data_manifest_path.replace("\\", "/")
            ):
                raise ValueError("intent does not pin the run's exact data manifest")
        for batch_id, rows in self._group_intents().items():
            if sum((row.target_weight for row in rows), ZERO) > ONE:
                raise ValueError(f"target weights exceed one in batch {batch_id}")
            fields = {
                (
                    row.decision_ts,
                    row.information_available_ts,
                    row.earliest_eligible_execution_ts,
                    row.earliest_eligible_session,
                    row.official_universe_denominator,
                    row.usable_price_count,
                    row.feature_eligible_count,
                    tuple(row.excluded_member_states),
                )
                for row in rows
            }
            if len(fields) != 1:
                raise ValueError(f"inconsistent metadata within intent batch {batch_id}")
        event_keys = [(event.event_id, event.revision) for event in self.security_events]
        action_keys = [(event.action_id, event.revision) for event in self.corporate_actions]
        if len(event_keys) != len(set(event_keys)) or len(action_keys) != len(set(action_keys)):
            raise ValueError("duplicate event/action revision")
        referenced = {event.security_id for event in self.security_events}
        referenced |= {event.security_id for event in self.corporate_actions}
        referenced |= {event.related_security_id for event in self.corporate_actions if event.related_security_id}
        if referenced - self.known_security_ids:
            raise ValueError(f"unknown event security identity: {sorted(referenced - self.known_security_ids)}")
        if self.corporate_actions and self.config.adjustment_policy == "adjusted_without_actions":
            raise ValueError("explicit actions are prohibited with adjusted_without_actions")
        if self.corporate_actions and any(bar.adjustment_state != "raw" for bar in self.bars):
            raise ValueError("ambiguous adjusted bars with explicit corporate actions")
        for action in self.corporate_actions:
            if action.currency is not None and action.currency != self.config.account_currency:
                raise ValueError("corporate action currency is inconsistent with the shared account")

    def _group_intents(self) -> dict[str, list[TargetWeightIntent]]:
        groups: dict[str, list[TargetWeightIntent]] = defaultdict(list)
        for intent in self.intents:
            groups[intent.batch_id].append(intent)
        return {key: sorted(value, key=lambda row: (row.security_id, row.intent_id)) for key, value in groups.items()}

    def _event_id(self, kind: str, cause_id: str, security_id: str | None) -> str:
        payload = f"{self.run_id}|{self.sequence}|{kind}|{cause_id}|{security_id or ''}"
        return f"{kind}-{hashlib.sha256(payload.encode()).hexdigest()[:24]}"

    def _emit(self, collection: list[TEvent], model: type[TEvent], **values: object) -> TEvent:
        kind = model.__name__.lower()
        event = model(
            event_id=self._event_id(kind, str(values["cause_id"]), values.get("security_id")),
            run_id=self.run_id,
            sequence=self.sequence,
            account_id=self.config.account_id,
            **values,
        )
        self.sequence += 1
        collection.append(event)
        return event

    def _bar_map(self) -> dict[tuple[date, str], MarketBar]:
        return {(bar.session_date, bar.security_id): bar for bar in self.bars}

    def run(self) -> EngineResult:
        sessions = sorted({bar.session_date for bar in self.bars})
        bar_map = self._bar_map()
        first_open = modeled_open_timestamp(sessions[0], self.config.market_timezone, self.config.market_open_time)
        self._emit(
            self.result.cash_movements,
            CashMovement,
            timestamp=first_open - timedelta(microseconds=1),
            security_id=None,
            cause_id="initial-capital",
            movement_type=CashMovementType.INITIAL_CAPITAL,
            amount=self.cash,
            balance_after=self.cash,
            currency=self.config.account_currency,
        )
        scheduled, unscheduled = self._schedule_intents(sessions)
        overlapping = {session: rows for session, rows in scheduled.items() if len(rows) > 1}
        if overlapping:
            raise ValueError(
                "multiple intent batches resolve to the same execution session; combine them explicitly: "
                + ", ".join(
                    f"{session}={sorted(batch_id for batch_id, _batch in rows)}"
                    for session, rows in overlapping.items()
                )
            )
        for session_index, session in enumerate(sessions):
            open_ts = modeled_open_timestamp(session, self.config.market_timezone, self.config.market_open_time)
            self._process_known_events(session, open_ts)
            batch_metrics: dict[str, object] | None = None
            for batch_id, batch in scheduled.get(session, []):
                batch_metrics = self._process_batch(batch_id, batch, session, session_index, open_ts, bar_map)
            self._value_session(session, session_index, open_ts, bar_map, batch_metrics)
        last_timestamp = self.result.portfolio_snapshots[-1].timestamp
        for intent in sorted(unscheduled, key=lambda row: (row.earliest_eligible_execution_ts, row.intent_id)):
            self._reject(
                timestamp=max(last_timestamp, intent.earliest_eligible_execution_ts),
                security_id=intent.security_id,
                cause_id=intent.intent_id,
                disposition=RejectionDisposition.REJECTED,
                reason_code="no_eligible_future_session",
                detail="pinned calendar contains no eligible future session",
                batch_id=intent.batch_id,
                intent_id=intent.intent_id,
                target_weight=intent.target_weight,
            )
        self._validate_final_invariants()
        return self.result

    def _schedule_intents(
        self, sessions: list[date]
    ) -> tuple[dict[date, list[tuple[str, list[TargetWeightIntent]]]], list[TargetWeightIntent]]:
        scheduled: dict[date, list[tuple[str, list[TargetWeightIntent]]]] = defaultdict(list)
        unscheduled: list[TargetWeightIntent] = []
        for batch_id, batch in sorted(self._group_intents().items()):
            representative = batch[0]
            eligible = [
                session
                for session in sessions
                if session >= representative.earliest_eligible_session
                and modeled_open_timestamp(session, self.config.market_timezone, self.config.market_open_time)
                >= representative.earliest_eligible_execution_ts
            ]
            if not eligible:
                unscheduled.extend(batch)
            else:
                scheduled[eligible[0]].append((batch_id, batch))
        return scheduled, unscheduled

    def _known_revision(self, rows: Iterable[BaseModel], key_name: str, open_ts: datetime) -> dict[str, BaseModel]:
        selected: dict[str, BaseModel] = {}
        for row in rows:
            if getattr(row, "available_ts") > open_ts:
                continue
            key = str(getattr(row, key_name))
            prior = selected.get(key)
            if prior is None or getattr(row, "revision") > getattr(prior, "revision"):
                selected[key] = row
        return selected

    def _process_known_events(self, session: date, open_ts: datetime) -> None:
        known_events = self._known_revision(self.security_events, "event_id", open_ts)
        known_actions = self._known_revision(self.corporate_actions, "action_id", open_ts)
        combined: list[tuple[datetime, str, str, BaseModel]] = []
        for key, event in known_events.items():
            if event.effective_session <= session:
                combined.append((event.event_ts, "security", key, event))
        for key, action in known_actions.items():
            if action.effective_session <= session:
                combined.append((action.event_ts, "corporate", key, action))
        for _event_ts, kind, key, item in sorted(combined, key=lambda row: (row[0], row[1], row[2], row[3].revision)):
            applied = self.applied_security_events if kind == "security" else self.applied_actions
            if key in applied:
                if item.revision > applied[key]:
                    self._reject(
                        timestamp=open_ts,
                        security_id=item.security_id,
                        cause_id=key,
                        disposition=RejectionDisposition.REPLAY_REQUIRED,
                        reason_code="later_revision_requires_replay",
                        detail=f"revision {item.revision} became known after revision {applied[key]} was applied",
                    )
                    applied[key] = item.revision
                continue
            if item.effective_session < session and item.available_ts > modeled_open_timestamp(
                item.effective_session, self.config.market_timezone, self.config.market_open_time
            ):
                self._reject(
                    timestamp=open_ts,
                    security_id=item.security_id,
                    cause_id=key,
                    disposition=RejectionDisposition.REPLAY_REQUIRED,
                    reason_code="event_known_after_effective_session",
                    detail="event was unavailable at effectiveness and requires corrected replay",
                )
                applied[key] = item.revision
                continue
            if kind == "security":
                self._apply_security_event(item, open_ts)
            else:
                self._apply_corporate_action(item, open_ts)
            applied[key] = item.revision

    def _apply_security_event(self, event: SecurityEventInput, timestamp: datetime) -> None:
        if event.event_type == SecurityEventType.SUSPENSION:
            self.tradeability[event.security_id] = "suspended"
        elif event.event_type == SecurityEventType.RESUMPTION:
            self.tradeability[event.security_id] = "tradeable"
        elif event.event_type == SecurityEventType.DELISTING:
            self.tradeability[event.security_id] = "terminal_delisted"
        elif event.event_type == SecurityEventType.IDENTIFIER_CHANGE:
            self.identifiers[event.security_id] = str(event.new_identifier)

    def _apply_corporate_action(self, action: CorporateActionInput, timestamp: datetime) -> None:
        before = self.holdings.get(action.security_id, ZERO)
        source_after = before
        related_before: Decimal | None = None
        related_after: Decimal | None = None
        cash_delta = ZERO
        if action.action_type in {CorporateActionType.SPLIT, CorporateActionType.REVERSE_SPLIT}:
            source_after = quantity(before * action.ratio)
        elif action.action_type == CorporateActionType.MERGER:
            source_after = ZERO
            related_before = self.holdings.get(str(action.related_security_id), ZERO)
            related_after = quantity(related_before + before * action.ratio)
        elif action.action_type == CorporateActionType.CASH_TAKEOVER:
            source_after = ZERO
            cash_delta = money(before * action.cash_amount_per_share)
        application = self._emit(
            self.result.corporate_action_applications,
            CorporateActionApplication,
            timestamp=timestamp,
            security_id=action.security_id,
            cause_id=action.action_id,
            action_id=action.action_id,
            revision=action.revision,
            action_type=action.action_type,
            related_security_id=action.related_security_id,
            source_quantity_before=before,
            source_quantity_after=source_after,
            related_quantity_before=related_before,
            related_quantity_after=related_after,
            cash_delta=cash_delta,
            ratio=action.ratio,
            cash_amount_per_share=action.cash_amount_per_share,
            adjustment_policy=self.config.adjustment_policy,
        )
        if source_after != before:
            movement_type = {
                CorporateActionType.SPLIT: PositionMovementType.SPLIT,
                CorporateActionType.REVERSE_SPLIT: PositionMovementType.SPLIT,
                CorporateActionType.MERGER: PositionMovementType.MERGER_REMOVE,
                CorporateActionType.CASH_TAKEOVER: PositionMovementType.CASH_TAKEOVER_REMOVE,
            }[action.action_type]
            self.holdings[action.security_id] = source_after
            if source_after == ZERO:
                self.holdings.pop(action.security_id, None)
            self._emit(
                self.result.position_movements,
                PositionMovement,
                timestamp=timestamp,
                security_id=action.security_id,
                cause_id=application.event_id,
                movement_type=movement_type,
                quantity_delta=quantity(source_after - before),
                quantity_after=source_after,
                corporate_action_application_id=application.event_id,
                related_security_id=action.related_security_id,
            )
        if related_after is not None and related_before is not None:
            successor = str(action.related_security_id)
            self.holdings[successor] = related_after
            self._emit(
                self.result.position_movements,
                PositionMovement,
                timestamp=timestamp,
                security_id=successor,
                cause_id=application.event_id,
                movement_type=PositionMovementType.MERGER_RECEIVE,
                quantity_delta=quantity(related_after - related_before),
                quantity_after=related_after,
                corporate_action_application_id=application.event_id,
                related_security_id=action.security_id,
            )
            self.tradeability[action.security_id] = "terminal_merged"
        if cash_delta:
            self.cash = money(self.cash + cash_delta)
            self._emit(
                self.result.cash_movements,
                CashMovement,
                timestamp=timestamp,
                security_id=action.security_id,
                cause_id=application.event_id,
                movement_type=CashMovementType.CASH_TAKEOVER,
                amount=cash_delta,
                balance_after=self.cash,
                currency=self.config.account_currency,
                corporate_action_application_id=application.event_id,
            )
            self.tradeability[action.security_id] = "terminal_taken_over"

    def _execution_mark(
        self, security_id: str, session: date, session_index: int, bar_map: dict[tuple[date, str], MarketBar]
    ) -> Decimal | None:
        bar = bar_map.get((session, security_id))
        if (
            bar
            and bar.open is not None
            and bar.currency == self.config.account_currency
            and bar.source
            and bar.source_record_id
        ):
            return bar.open
        stale = self.last_close.get(security_id)
        maximum = self.config.max_stale_valuation_sessions
        if stale and maximum is not None and session_index - stale[2] <= maximum:
            return stale[0]
        return None

    def _process_batch(
        self,
        batch_id: str,
        batch: list[TargetWeightIntent],
        session: date,
        session_index: int,
        open_ts: datetime,
        bar_map: dict[tuple[date, str], MarketBar],
    ) -> dict[str, object]:
        for intent in batch:
            if intent.information_available_ts > intent.decision_ts or open_ts < intent.earliest_eligible_execution_ts:
                raise LedgerInvariantError("intent temporal eligibility violated")
        held_marks = {
            security_id: self._execution_mark(security_id, session, session_index, bar_map)
            for security_id in self.holdings
        }
        unresolved_held = sorted(key for key, value in held_marks.items() if value is None)
        gross = weight(sum((intent.target_weight for intent in batch), ZERO))
        rejected_weight = ZERO
        deferred_weight = ZERO
        if unresolved_held:
            for intent in batch:
                deferred_weight += intent.target_weight
                self._reject(
                    timestamp=open_ts,
                    security_id=intent.security_id,
                    cause_id=intent.intent_id,
                    disposition=RejectionDisposition.DEFERRED,
                    reason_code="unresolved_execution_equity",
                    detail=f"held positions lack admissible execution marks: {unresolved_held}",
                    batch_id=batch_id,
                    intent_id=intent.intent_id,
                    target_weight=intent.target_weight,
                )
            return self._batch_metrics(batch, gross, rejected_weight, deferred_weight)
        execution_equity = money(self.cash + sum(self.holdings[key] * held_marks[key] for key in self.holdings))
        unavailable: dict[str, str] = {}
        for intent in batch:
            bar = bar_map.get((session, intent.security_id))
            state = self.tradeability[intent.security_id]
            if state != "tradeable":
                unavailable[intent.intent_id] = state
            elif bar is None or bar.open is None:
                unavailable[intent.intent_id] = "missing_next_session_open"
            elif not bar.currency:
                unavailable[intent.intent_id] = "missing_currency"
            elif not bar.source or not bar.source_record_id:
                unavailable[intent.intent_id] = "missing_price_provenance"
            elif bar.currency != self.config.account_currency:
                unavailable[intent.intent_id] = "inconsistent_currency"
        if unavailable and self.config.unavailable_target_policy == "fail_batch":
            for intent in batch:
                rejected_weight += intent.target_weight
                self._reject(
                    timestamp=open_ts,
                    security_id=intent.security_id,
                    cause_id=intent.intent_id,
                    disposition=RejectionDisposition.REJECTED,
                    reason_code="batch_failed_unavailable_target",
                    detail=json.dumps(unavailable, sort_keys=True),
                    batch_id=batch_id,
                    intent_id=intent.intent_id,
                    target_weight=intent.target_weight,
                )
            return self._batch_metrics(batch, gross, rejected_weight, deferred_weight)
        candidates: list[tuple[TargetWeightIntent, MarketBar, Decimal]] = []
        for intent in batch:
            if intent.intent_id in unavailable:
                disposition = RejectionDisposition.DEFERRED if self.holdings.get(intent.security_id, ZERO) else RejectionDisposition.REJECTED
                if disposition == RejectionDisposition.DEFERRED:
                    deferred_weight += intent.target_weight
                else:
                    rejected_weight += intent.target_weight
                self._reject(
                    timestamp=open_ts,
                    security_id=intent.security_id,
                    cause_id=intent.intent_id,
                    disposition=disposition,
                    reason_code=unavailable[intent.intent_id],
                    detail="target retained as cash; existing untradeable quantity, if any, is unchanged",
                    batch_id=batch_id,
                    intent_id=intent.intent_id,
                    target_weight=intent.target_weight,
                )
                continue
            bar = bar_map[(session, intent.security_id)]
            desired = quantity(execution_equity * intent.target_weight / bar.open)
            delta = quantity(desired - self.holdings.get(intent.security_id, ZERO))
            if self.holdings.get(intent.security_id, ZERO) + delta < ZERO:
                raise LedgerInvariantError("translated order would create a short position")
            if delta:
                candidates.append((intent, bar, delta))
        sells = sorted((row for row in candidates if row[2] < ZERO), key=lambda row: row[0].security_id)
        buys = sorted((row for row in candidates if row[2] > ZERO), key=lambda row: row[0].security_id)
        for intent, bar, delta in sells:
            self._execute_order(intent, bar, delta, delta, ONE, execution_equity, open_ts)
        required = sum((self._buy_cash_required(bar.open, delta) for _intent, bar, delta in buys), ZERO)
        scale = ONE if required <= self.cash or required == ZERO else self.cash / required
        if scale < ONE:
            self._reject(
                timestamp=open_ts,
                security_id=None,
                cause_id=batch_id,
                disposition=RejectionDisposition.DEFERRED,
                reason_code="insufficient_cash_buy_scale",
                detail=f"all batch buys scaled proportionally by {scale}",
                batch_id=batch_id,
            )
        for intent, bar, delta in buys:
            generated = quantity(delta * scale)
            if generated:
                self._execute_order(intent, bar, delta, generated, scale, execution_equity, open_ts)
        return self._batch_metrics(batch, gross, rejected_weight, deferred_weight)

    def _batch_metrics(
        self,
        batch: list[TargetWeightIntent],
        gross: Decimal,
        rejected_weight: Decimal,
        deferred_weight: Decimal,
    ) -> dict[str, object]:
        accepted = max(ZERO, gross - rejected_weight - deferred_weight)
        representative = batch[0]
        return {
            "gross": weight(gross),
            "rejected": weight(rejected_weight),
            "deferred": weight(deferred_weight),
            "unallocated": weight(max(ZERO, ONE - accepted)),
            "official": representative.official_universe_denominator,
            "usable": representative.usable_price_count,
            "eligible": representative.feature_eligible_count,
            "excluded": representative.excluded_member_states,
        }

    def _buy_cash_required(self, raw_open: Decimal, requested_quantity: Decimal) -> Decimal:
        fill_price = price(raw_open * (ONE + self.slippage_rate))
        notional = money(requested_quantity * fill_price)
        return money(notional + abs(notional) * self.commission_rate)

    def _execute_order(
        self,
        intent: TargetWeightIntent,
        bar: MarketBar,
        requested_delta: Decimal,
        generated_delta: Decimal,
        scale: Decimal,
        execution_equity: Decimal,
        timestamp: datetime,
    ) -> None:
        side = Side.BUY if generated_delta > ZERO else Side.SELL
        current = self.holdings.get(intent.security_id, ZERO)
        order = self._emit(
            self.result.orders,
            GeneratedOrder,
            timestamp=timestamp,
            security_id=intent.security_id,
            cause_id=intent.intent_id,
            batch_id=intent.batch_id,
            intent_id=intent.intent_id,
            side=side,
            target_weight=intent.target_weight,
            execution_equity=execution_equity,
            current_quantity=current,
            requested_quantity=requested_delta,
            generated_quantity=generated_delta,
            cash_scale=weight(scale),
            raw_open_price=price(bar.open),
            currency=bar.currency,
        )
        fill_price = price(bar.open * (ONE + self.slippage_rate if side == Side.BUY else ONE - self.slippage_rate))
        notional = money(generated_delta * fill_price)
        commission = money(abs(notional) * self.commission_rate)
        slippage_amount = money((fill_price - price(bar.open)) * generated_delta)
        fill = self._emit(
            self.result.fills,
            Fill,
            timestamp=timestamp,
            security_id=intent.security_id,
            cause_id=order.event_id,
            order_id=order.event_id,
            intent_id=intent.intent_id,
            side=side,
            quantity=generated_delta,
            raw_open_price=price(bar.open),
            fill_price=fill_price,
            notional=notional,
            commission=commission,
            slippage_amount=slippage_amount,
            currency=bar.currency,
            source_bar_id=bar.source_bar_id,
            source_bar_event_ts=bar.event_ts,
            source_bar_available_ts=bar.available_ts,
            modeled_market_event_ts=timestamp,
            calendar=self.config.calendar,
            adjustment_state=bar.adjustment_state,
            adjustment_version=bar.adjustment_version,
        )
        trade_cash = money(-notional)
        self.cash = money(self.cash + trade_cash)
        self._emit(
            self.result.cash_movements,
            CashMovement,
            timestamp=timestamp,
            security_id=intent.security_id,
            cause_id=fill.event_id,
            movement_type=CashMovementType.TRADE,
            amount=trade_cash,
            balance_after=self.cash,
            currency=bar.currency,
            fill_id=fill.event_id,
        )
        self.cash = money(self.cash - commission)
        self._emit(
            self.result.cash_movements,
            CashMovement,
            timestamp=timestamp,
            security_id=intent.security_id,
            cause_id=fill.event_id,
            movement_type=CashMovementType.COMMISSION,
            amount=-commission,
            balance_after=self.cash,
            currency=bar.currency,
            fill_id=fill.event_id,
        )
        new_quantity = quantity(current + generated_delta)
        if new_quantity < ZERO:
            raise LedgerInvariantError("fill created a short position")
        if new_quantity:
            self.holdings[intent.security_id] = new_quantity
        else:
            self.holdings.pop(intent.security_id, None)
        self._emit(
            self.result.position_movements,
            PositionMovement,
            timestamp=timestamp,
            security_id=intent.security_id,
            cause_id=fill.event_id,
            movement_type=PositionMovementType.TRADE,
            quantity_delta=generated_delta,
            quantity_after=new_quantity,
            fill_id=fill.event_id,
        )
        if self.cash < -RECONCILIATION_TOLERANCE:
            raise LedgerInvariantError(f"negative cash after fill: {self.cash}")
        if self.cash < ZERO:
            self.cash = ZERO

    def _value_session(
        self,
        session: date,
        session_index: int,
        open_ts: datetime,
        bar_map: dict[tuple[date, str], MarketBar],
        metrics: dict[str, object] | None,
    ) -> None:
        close_candidates = [bar.event_ts for (bar_session, _security), bar in bar_map.items() if bar_session == session]
        close_ts = max(close_candidates) if close_candidates else open_ts
        values: list[Decimal] = []
        unvalued: list[str] = []
        any_stale = False
        for security_id, held_quantity in sorted(self.holdings.items()):
            bar = bar_map.get((session, security_id))
            terminal = self.tradeability[security_id].startswith("terminal")
            mark: Decimal | None = None
            status = ValuationStatus.UNRESOLVED
            source_ts: datetime | None = None
            source_bar_id: str | None = None
            source_name: str | None = None
            age: int | None = None
            reason = "missing_close_no_admissible_stale_mark"
            if (
                not terminal
                and bar
                and bar.close is not None
                and bar.currency == self.config.account_currency
                and bar.source
                and bar.source_record_id
            ):
                mark = price(bar.close)
                status = ValuationStatus.COMPLETE
                source_ts = bar.event_ts
                source_bar_id = bar.source_bar_id
                source_name = bar.source
                age = 0
                reason = "current_session_close"
                self.last_close[security_id] = (mark, bar.event_ts, session_index, bar.source, bar.source_bar_id)
            elif not terminal and security_id in self.last_close and self.config.max_stale_valuation_sessions is not None:
                prior, prior_ts, prior_index, prior_source, prior_bar_id = self.last_close[security_id]
                candidate_age = session_index - prior_index
                if candidate_age <= self.config.max_stale_valuation_sessions:
                    mark = prior
                    status = ValuationStatus.STALE
                    source_ts = prior_ts
                    source_bar_id = prior_bar_id
                    source_name = prior_source
                    age = candidate_age
                    reason = "explicit_stale_close_policy"
                    any_stale = True
            if terminal:
                reason = f"{self.tradeability[security_id]}_without_value_terms"
            elif bar and bar.close is not None and not bar.currency:
                reason = "missing_currency"
            elif bar and bar.close is not None and (not bar.source or not bar.source_record_id):
                reason = "missing_price_provenance"
            elif bar and bar.close is not None and bar.currency != self.config.account_currency:
                reason = "inconsistent_currency"
            market_value = money(held_quantity * mark) if mark is not None else None
            if market_value is None:
                unvalued.append(security_id)
            else:
                values.append(market_value)
            self._emit(
                self.result.valuations,
                Valuation,
                timestamp=close_ts,
                security_id=security_id,
                cause_id=f"valuation:{session.isoformat()}",
                session_date=session,
                quantity=held_quantity,
                price=mark,
                market_value=market_value,
                currency=self.config.account_currency,
                status=status,
                price_field="close" if mark is not None else None,
                price_source=source_name,
                source_bar_id=source_bar_id,
                source_timestamp=source_ts,
                stale_age_sessions=age,
                reason=reason,
            )
            self._emit(
                self.result.positions,
                PositionSnapshot,
                timestamp=close_ts,
                security_id=security_id,
                cause_id=f"position:{session.isoformat()}",
                session_date=session,
                quantity=held_quantity,
                identifier=self.identifiers.get(security_id),
                tradeability_state=self.tradeability[security_id],
            )
        if unvalued:
            market_value_total = None
            equity = None
            portfolio_status = ValuationStatus.UNRESOLVED
        else:
            market_value_total = money(sum(values, ZERO))
            equity = money(self.cash + market_value_total)
            portfolio_status = ValuationStatus.STALE if any_stale else ValuationStatus.COMPLETE
            if abs(equity - (self.cash + market_value_total)) > RECONCILIATION_TOLERANCE:
                raise LedgerInvariantError("portfolio valuation does not reconcile")
        defaults: dict[str, object] = {
            "gross": ZERO,
            "rejected": ZERO,
            "deferred": ZERO,
            "unallocated": ONE,
            "official": None,
            "usable": None,
            "eligible": None,
            "excluded": (),
        }
        values_by_key = metrics or defaults
        self._emit(
            self.result.portfolio_snapshots,
            PortfolioSnapshot,
            timestamp=close_ts,
            security_id=None,
            cause_id=f"session:{session.isoformat()}",
            session_date=session,
            cash=self.cash,
            market_value=market_value_total,
            equity=equity,
            valuation_status=portfolio_status,
            unvalued_security_ids=tuple(unvalued),
            gross_target_weight=values_by_key["gross"],
            rejected_target_weight=values_by_key["rejected"],
            deferred_target_weight=values_by_key["deferred"],
            unallocated_weight=values_by_key["unallocated"],
            official_universe_denominator=values_by_key["official"],
            usable_price_count=values_by_key["usable"],
            feature_eligible_count=values_by_key["eligible"],
            excluded_member_states=values_by_key["excluded"],
        )
        if unvalued and not self.config.continue_on_unresolved_valuation:
            raise LedgerInvariantError(f"unresolved portfolio valuation: {unvalued}")

    def _reject(self, **values: object) -> RejectionOrDeferredAction:
        return self._emit(self.result.rejections, RejectionOrDeferredAction, **values)

    def _validate_final_invariants(self) -> None:
        events = self.result.all_events()
        sequences = [event.sequence for event in events]
        if sequences != list(range(len(sequences))):
            raise LedgerInvariantError("event sequences are not contiguous and deterministic")
        ids = [event.event_id for event in events]
        if len(ids) != len(set(ids)):
            raise LedgerInvariantError("duplicate ledger event ID")
        fill_movements = {movement.fill_id: movement for movement in self.result.position_movements if movement.fill_id}
        cash_by_fill: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for movement in self.result.cash_movements:
            if movement.fill_id:
                cash_by_fill[movement.fill_id] += movement.amount
        for fill in self.result.fills:
            movement = fill_movements.get(fill.event_id)
            if movement is None or movement.quantity_delta != fill.quantity:
                raise LedgerInvariantError(f"fill/position movement mismatch: {fill.event_id}")
            expected_cash = money(-fill.notional - fill.commission)
            if money(cash_by_fill[fill.event_id]) != expected_cash:
                raise LedgerInvariantError(f"fill/cash movement mismatch: {fill.event_id}")
            if fill.timestamp < fill.modeled_market_event_ts or fill.price_field != "open":
                raise LedgerInvariantError("fill market-field timing mismatch")
