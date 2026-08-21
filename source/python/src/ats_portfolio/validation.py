from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow.dataset as ds

from ats_contracts.portfolio import (
    CorporateActionInput,
    LedgerRunManifest,
    RejectionDisposition,
    SecurityEventInput,
    SecurityEventType,
    Side,
    TargetWeightIntent,
    ValuationStatus,
)
from ats_data.publication import validate_manifest as validate_phase_b_manifest
from ats_data.discovery import manifest_files
from ats_portfolio.config import PortfolioConfig, load_config
from ats_portfolio.hashing import file_hash, manifest_hash, object_hash
from ats_portfolio.market import MARKET_FIELD_TIMING_POLICY, modeled_open_timestamp
from ats_portfolio.numeric import (
    NUMERIC_POLICY,
    ONE,
    RECONCILIATION_TOLERANCE,
    WEIGHT_QUANTUM,
    ZERO,
    decimal_value,
    money,
    price,
    quantity,
)
from ats_portfolio.storage import logical_intents_hash, logical_rows_hash, read_intents, read_ledger


class RunValidationError(ValueError):
    pass


LEDGER_NAMES = (
    "intents",
    "orders",
    "fills",
    "cash_movements",
    "position_movements",
    "positions",
    "valuations",
    "portfolio_snapshots",
    "rejections",
    "corporate_action_applications",
)


def _load_manifest(run_dir: Path) -> tuple[dict[str, Any], LedgerRunManifest]:
    path = run_dir / "manifest.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    parsed = LedgerRunManifest.model_validate(raw)
    if manifest_hash(raw) != parsed.manifest_hash:
        raise RunValidationError("run manifest logical hash mismatch")
    return raw, parsed


def _verify_implementation(manifest: LedgerRunManifest) -> None:
    provenance = manifest.implementation_provenance
    repo = Path(__file__).resolve().parents[4]
    commit = str(provenance.get("commit", ""))
    if not commit:
        raise RunValidationError("implementation commit is missing")
    for name, expected in provenance.get("code_file_sha256", {}).items():
        if provenance.get("clean"):
            completed = subprocess.run(
                ["git", "show", f"{commit}:{name}"], cwd=repo, capture_output=True, check=True
            )
            import hashlib

            actual = hashlib.sha256(completed.stdout).hexdigest()
        else:
            path = repo / name
            if not path.is_file():
                raise RunValidationError(f"dirty implementation file unavailable: {name}")
            actual = file_hash(path)
        if actual != expected:
            raise RunValidationError(f"implementation snapshot mismatch: {name}")


def _validate_artifacts(run_dir: Path, manifest: LedgerRunManifest) -> dict[str, list[Any]]:
    declared = {record.path for record in manifest.artifacts}
    actual = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != declared:
        raise RunValidationError(
            f"artifact-set mismatch: missing={sorted(declared-actual)}, unexpected={sorted(actual-declared)}"
        )
    ledgers: dict[str, list[Any]] = {}
    records = {record.path: record for record in manifest.artifacts}
    for relative, record in records.items():
        path = run_dir / relative
        if path.stat().st_size != record.bytes or file_hash(path) != record.physical_sha256:
            raise RunValidationError(f"physical artifact mismatch: {relative}")
        if relative == "ledgers/intents.csv":
            rows = read_intents(path)
            if len(rows) != record.rows or logical_intents_hash(rows) != record.logical_sha256:
                raise RunValidationError("logical intent ledger mismatch")
            if manifest.logical_hashes.get(relative) != record.logical_sha256:
                raise RunValidationError("manifest logical intent hash mismatch")
            ledgers["intents"] = rows
        elif relative.startswith("ledgers/"):
            name = Path(relative).stem
            if name not in LEDGER_NAMES or name == "intents":
                raise RunValidationError(f"unknown ledger artifact: {relative}")
            rows = read_ledger(path, name)
            if len(rows) != record.rows or logical_rows_hash(rows) != record.logical_sha256:
                raise RunValidationError(f"logical ledger mismatch: {relative}")
            if manifest.logical_hashes.get(relative) != record.logical_sha256:
                raise RunValidationError(f"manifest logical hash mismatch: {relative}")
            ledgers[name] = rows
    required = set(LEDGER_NAMES)
    if set(ledgers) != required:
        raise RunValidationError(f"ledger set mismatch: {sorted(set(ledgers)^required)}")
    return ledgers


def _validate_identity(
    run_dir: Path, manifest: LedgerRunManifest, require_directory_identity: bool
) -> tuple[list[TargetWeightIntent], list[SecurityEventInput], list[CorporateActionInput], PortfolioConfig]:
    config = load_config(run_dir / "config.yaml")
    if file_hash(run_dir / "config.yaml") != manifest.config_sha256:
        raise RunValidationError("config hash mismatch")
    if file_hash(run_dir / "inputs" / "phase_b_manifest.json") != manifest.phase_b_manifest_sha256:
        raise RunValidationError("retained Phase B manifest hash mismatch")
    original = Path(manifest.phase_b_manifest_path)
    if not original.is_file() or file_hash(original) != manifest.phase_b_manifest_sha256:
        raise RunValidationError("pinned external Phase B manifest is missing or changed")
    phase_b = validate_phase_b_manifest(original)
    if phase_b.dataset_version_id != manifest.phase_b_manifest_id:
        raise RunValidationError("Phase B manifest identity mismatch")
    intents_path = run_dir / "inputs" / "intents.json"
    if file_hash(intents_path) != manifest.input_hashes.get("intents"):
        raise RunValidationError("intent input hash mismatch")
    intents_raw = json.loads(intents_path.read_text(encoding="utf-8"))
    intents = [TargetWeightIntent.model_validate(row) for row in intents_raw]
    retained_security_events: list[SecurityEventInput] = []
    retained_actions: list[CorporateActionInput] = []
    for key, filename in (("security_events", "security_events.json"), ("corporate_actions", "corporate_actions.json")):
        path = run_dir / "inputs" / filename
        if (key in manifest.event_hashes) != path.is_file():
            raise RunValidationError(f"event artifact presence mismatch: {key}")
        if path.is_file() and file_hash(path) != manifest.event_hashes[key]:
            raise RunValidationError(f"event input hash mismatch: {key}")
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            model = SecurityEventInput if key == "security_events" else CorporateActionInput
            parsed = [model.model_validate(row) for row in raw]
            if key == "security_events":
                retained_security_events = parsed
            else:
                retained_actions = parsed
    lock = json.loads((run_dir / "environment_lock.json").read_text(encoding="utf-8"))
    if object_hash(lock) != manifest.environment_lock_hash:
        raise RunValidationError("environment lock mismatch")
    if manifest.numeric_policy != NUMERIC_POLICY or manifest.market_field_timing_policy != MARKET_FIELD_TIMING_POLICY:
        raise RunValidationError("numeric or market timing policy mismatch")
    payload = {
        "config": config.identity_dict(),
        "config_sha256": manifest.config_sha256,
        "phase_b_manifest_id": manifest.phase_b_manifest_id,
        "phase_b_manifest_sha256": manifest.phase_b_manifest_sha256,
        "input_hashes": manifest.input_hashes,
        "event_hashes": manifest.event_hashes,
        "contract_versions": manifest.contract_versions,
        "implementation_provenance": manifest.implementation_provenance,
        "environment_lock_hash": manifest.environment_lock_hash,
        "numeric_policy": manifest.numeric_policy,
        "market_field_timing_policy": manifest.market_field_timing_policy,
        "calendar": manifest.calendar,
        "cost_model": manifest.cost_model,
        "seed": manifest.seed,
    }
    expected_id = f"phasec-{object_hash(payload)[:20]}"
    if expected_id != manifest.run_id:
        raise RunValidationError("content-derived run identity mismatch")
    if require_directory_identity and run_dir.name != manifest.run_id:
        raise RunValidationError("run directory is not the immutable content-derived identity")
    _verify_implementation(manifest)
    event_keys = [(row.event_id, row.revision) for row in retained_security_events]
    action_keys = [(row.action_id, row.revision) for row in retained_actions]
    if len(event_keys) != len(set(event_keys)) or len(action_keys) != len(set(action_keys)):
        raise RunValidationError("duplicate retained event/action revision")
    return intents, retained_security_events, retained_actions, config


def _validate_events(
    ledgers: dict[str, list[Any]],
    intents: list[TargetWeightIntent],
    security_events: list[SecurityEventInput],
    corporate_actions: list[CorporateActionInput],
    config: PortfolioConfig,
    canonical_bars: dict[tuple[Any, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    retained_intents = ledgers["intents"]
    if [row.model_dump(mode="json") for row in retained_intents] != [
        row.model_dump(mode="json") for row in sorted(intents, key=lambda value: (value.batch_id, value.security_id, value.intent_id))
    ]:
        raise RunValidationError("intent ledger differs from retained input")
    semantic_keys = [(row.batch_id, row.security_id) for row in retained_intents]
    if len(semantic_keys) != len(set(semantic_keys)):
        raise RunValidationError("duplicate intent semantic key")
    events = sorted([row for name, rows in ledgers.items() if name != "intents" for row in rows], key=lambda row: row.sequence)
    if [row.sequence for row in events] != list(range(len(events))):
        raise RunValidationError("ledger sequence is not contiguous")
    if len({row.event_id for row in events}) != len(events):
        raise RunValidationError("duplicate output event ID")
    timestamps = [row.timestamp for row in events]
    if timestamps != sorted(timestamps):
        raise RunValidationError("out-of-order ledger timestamps")
    intent_by_id = {row.intent_id: row for row in intents}
    if len(intent_by_id) != len(intents):
        raise RunValidationError("duplicate retained intent ID")
    orders = {row.event_id: row for row in ledgers["orders"]}
    fills = {row.event_id: row for row in ledgers["fills"]}
    position_by_fill = {row.fill_id: row for row in ledgers["position_movements"] if row.fill_id}
    cash_by_fill: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for movement in ledgers["cash_movements"]:
        if movement.fill_id:
            cash_by_fill[movement.fill_id] += movement.amount
    for fill in fills.values():
        order = orders.get(fill.order_id)
        intent = intent_by_id.get(fill.intent_id)
        movement = position_by_fill.get(fill.event_id)
        if order is None or intent is None or movement is None:
            raise RunValidationError(f"fill lineage is incomplete: {fill.event_id}")
        if fill.quantity != movement.quantity_delta or fill.quantity != order.generated_quantity:
            raise RunValidationError(f"fill/order/position quantity mismatch: {fill.event_id}")
        if (
            fill.intent_id != order.intent_id
            or fill.security_id != order.security_id
            or fill.side != order.side
            or fill.raw_open_price != order.raw_open_price
            or fill.currency != order.currency
        ):
            raise RunValidationError(f"fill differs from generated order: {fill.event_id}")
        if fill.timestamp < intent.earliest_eligible_execution_ts or fill.timestamp <= intent.decision_ts:
            raise RunValidationError(f"fill precedes intent eligibility: {fill.event_id}")
        if intent.information_available_ts > intent.decision_ts:
            raise RunValidationError(f"intent uses unavailable information: {intent.intent_id}")
        if fill.price_field != "open" or fill.timestamp != fill.modeled_market_event_ts:
            raise RunValidationError(f"fill violates field-level timing: {fill.event_id}")
        if money(cash_by_fill[fill.event_id]) != money(-fill.notional - fill.commission):
            raise RunValidationError(f"fill cash does not reconcile: {fill.event_id}")
        expected_price = price(
            fill.raw_open_price
            * (Decimal("1") + config.slippage_bps / Decimal("10000") if fill.side == Side.BUY else Decimal("1") - config.slippage_bps / Decimal("10000"))
        )
        expected_notional = money(fill.quantity * expected_price)
        expected_commission = money(abs(expected_notional) * config.commission_bps / Decimal("10000"))
        expected_slippage = money((expected_price - fill.raw_open_price) * fill.quantity)
        if (
            fill.fill_price != expected_price
            or fill.notional != expected_notional
            or fill.commission != expected_commission
            or fill.slippage_amount != expected_slippage
        ):
            raise RunValidationError(f"fill cost model mismatch: {fill.event_id}")
    running_cash = ZERO
    running_positions: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for event in events:
        if event in ledgers["cash_movements"]:
            running_cash = money(running_cash + event.amount)
            if event.balance_after != running_cash:
                raise RunValidationError(f"event-order cash mismatch: {event.event_id}")
        elif event in ledgers["position_movements"]:
            running_positions[str(event.security_id)] += event.quantity_delta
            if running_positions[str(event.security_id)] != event.quantity_after:
                raise RunValidationError(f"event-order position mismatch: {event.event_id}")
        elif event in ledgers["positions"]:
            if running_positions[str(event.security_id)] != event.quantity:
                raise RunValidationError(f"position snapshot differs from ledger state: {event.event_id}")
        elif event in ledgers["valuations"]:
            if running_positions[str(event.security_id)] != event.quantity:
                raise RunValidationError(f"valuation quantity differs from ledger state: {event.event_id}")
            if event.price is not None and event.market_value != money(event.quantity * event.price):
                raise RunValidationError(f"valuation arithmetic mismatch: {event.event_id}")
        elif event in ledgers["portfolio_snapshots"] and event.cash != running_cash:
            raise RunValidationError(f"portfolio snapshot cash differs from ledger state: {event.event_id}")
    cash = ZERO
    for movement in ledgers["cash_movements"]:
        cash = money(cash + movement.amount)
        if movement.balance_after != cash or cash < ZERO:
            raise RunValidationError(f"cash balance mismatch: {movement.event_id}")
    positions: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for movement in ledgers["position_movements"]:
        positions[str(movement.security_id)] += movement.quantity_delta
        if positions[str(movement.security_id)] != movement.quantity_after or movement.quantity_after < ZERO:
            raise RunValidationError(f"position conservation mismatch: {movement.event_id}")
    applications = {row.event_id: row for row in ledgers["corporate_action_applications"]}
    if len(applications) != len(ledgers["corporate_action_applications"]):
        raise RunValidationError("duplicate corporate-action application event ID")
    if len({row.action_id for row in applications.values()}) != len(applications):
        raise RunValidationError("corporate action applied more than once")
    retained_action_keys = {(row.action_id, row.revision): row for row in corporate_actions}
    action_position: dict[str, list[Any]] = defaultdict(list)
    action_cash: dict[str, list[Any]] = defaultdict(list)
    for movement in ledgers["position_movements"]:
        if movement.corporate_action_application_id:
            action_position[movement.corporate_action_application_id].append(movement)
    for movement in ledgers["cash_movements"]:
        if movement.corporate_action_application_id:
            action_cash[movement.corporate_action_application_id].append(movement)
    unknown_action_refs = (set(action_position) | set(action_cash)) - set(applications)
    if unknown_action_refs:
        raise RunValidationError(f"movement references unknown corporate action: {sorted(unknown_action_refs)}")
    for application_id, application in applications.items():
        action = retained_action_keys.get((application.action_id, application.revision))
        if action is None:
            raise RunValidationError(f"corporate action application has no retained input: {application_id}")
        known_revisions = [
            row.revision
            for row in corporate_actions
            if row.action_id == action.action_id and row.available_ts <= application.timestamp
        ]
        if not known_revisions or application.revision != max(known_revisions):
            raise RunValidationError(f"corporate action application uses a non-current revision: {application_id}")
        if application.timestamp < action.available_ts or application.timestamp.date() < action.effective_session:
            raise RunValidationError(f"corporate action applied before availability/effectiveness: {application_id}")
        expected_open = modeled_open_timestamp(
            application.timestamp.astimezone(ZoneInfo(config.market_timezone)).date(),
            config.market_timezone,
            config.market_open_time,
        )
        if application.timestamp != expected_open:
            raise RunValidationError(f"corporate action was not applied at modeled open: {application_id}")
        if (
            application.cause_id != action.action_id
            or application.security_id != action.security_id
            or application.action_type != action.action_type
            or application.related_security_id != action.related_security_id
            or application.ratio != action.ratio
            or application.cash_amount_per_share != action.cash_amount_per_share
            or application.adjustment_policy != config.adjustment_policy
        ):
            raise RunValidationError(f"corporate action terms differ from retained input: {application_id}")
        source = [row for row in action_position[application_id] if row.security_id == application.security_id]
        source_delta = application.source_quantity_after - application.source_quantity_before
        if source_delta and (len(source) != 1 or source[0].quantity_delta != source_delta):
            raise RunValidationError(f"corporate action source shares do not balance: {application_id}")
        if application.related_security_id:
            related = [row for row in action_position[application_id] if row.security_id == application.related_security_id]
            related_delta = application.related_quantity_after - application.related_quantity_before
            if related_delta and (len(related) != 1 or related[0].quantity_delta != related_delta):
                raise RunValidationError(f"corporate action successor shares do not balance: {application_id}")
        cash_delta = money(sum((row.amount for row in action_cash[application_id]), ZERO))
        if cash_delta != application.cash_delta:
            raise RunValidationError(f"corporate action cash does not balance: {application_id}")
    sessions = [row.session_date for row in ledgers["portfolio_snapshots"]]
    rejections_by_cause = {row.cause_id for row in ledgers["rejections"] if row.disposition == RejectionDisposition.REPLAY_REQUIRED}
    for action_id, revisions in _group_actions(corporate_actions).items():
        if not sessions:
            continue
        effective = min(row.effective_session for row in revisions)
        eligible_sessions = [session for session in sessions if session >= effective]
        if not eligible_sessions:
            continue
        first_session = eligible_sessions[0]
        open_ts = modeled_open_timestamp(first_session, config.market_timezone, config.market_open_time)
        known = [row for row in revisions if row.available_ts <= open_ts]
        if known:
            chosen = max(known, key=lambda row: row.revision)
            applied = [row for row in applications.values() if row.action_id == action_id]
            if chosen.effective_session == first_session and not applied and action_id not in rejections_by_cause:
                raise RunValidationError(f"eligible corporate action was omitted: {action_id}")
    _validate_security_event_states(ledgers, security_events, config)
    valuations_by_session: dict[Any, list[Any]] = defaultdict(list)
    for valuation in ledgers["valuations"]:
        valuations_by_session[valuation.session_date].append(valuation)
        if valuation.status == ValuationStatus.UNRESOLVED and (valuation.price is not None or valuation.market_value is not None):
            raise RunValidationError("unresolved valuation contains a fabricated value")
    for snapshot in ledgers["portfolio_snapshots"]:
        rows = valuations_by_session[snapshot.session_date]
        unresolved = sorted(str(row.security_id) for row in rows if row.status == ValuationStatus.UNRESOLVED)
        if unresolved:
            if snapshot.equity is not None or snapshot.market_value is not None or list(snapshot.unvalued_security_ids) != unresolved:
                raise RunValidationError(f"unresolved portfolio aggregate mismatch: {snapshot.session_date}")
        else:
            value = money(sum((row.market_value for row in rows), ZERO))
            if snapshot.market_value != value or snapshot.equity != money(snapshot.cash + value):
                raise RunValidationError(f"portfolio snapshot does not reconcile: {snapshot.session_date}")
    translated = _validate_order_translation(ledgers, intents, config, canonical_bars)
    return {
        "events": len(events),
        "fills": len(fills),
        "sessions": len(ledgers["portfolio_snapshots"]),
        "ending_cash": str(cash),
        "event_sequence_hash": object_hash([row.event_id for row in events]),
        "orders_independently_reconstructed": translated,
    }


def _independent_buy_cost(raw_open: Decimal, requested: Decimal, config: PortfolioConfig) -> Decimal:
    fill_price = price(raw_open * (ONE + config.slippage_bps / Decimal("10000")))
    notional = money(requested * fill_price)
    return money(notional + abs(notional) * config.commission_bps / Decimal("10000"))


def _independent_affordable_scale(
    buys: list[tuple[Decimal, Decimal]], available_cash: Decimal, config: PortfolioConfig
) -> Decimal:
    def total(scale: Decimal) -> Decimal:
        return sum(
            (
                _independent_buy_cost(raw_open, generated, config)
                for raw_open, requested in buys
                if (generated := quantity(requested * scale))
            ),
            ZERO,
        )

    if not buys or total(ONE) <= available_cash:
        return ONE
    low = 0
    high = int(ONE / WEIGHT_QUANTUM)
    while low < high:
        midpoint = (low + high + 1) // 2
        candidate = Decimal(midpoint) * WEIGHT_QUANTUM
        if total(candidate) <= available_cash:
            low = midpoint
        else:
            high = midpoint - 1
    return Decimal(low) * WEIGHT_QUANTUM


def _validate_order_translation(
    ledgers: dict[str, list[Any]],
    intents: list[TargetWeightIntent],
    config: PortfolioConfig,
    canonical_bars: dict[tuple[Any, str], dict[str, Any]] | None,
) -> int:
    """Rebuild target-to-order translation without calling portfolio-engine code."""
    intent_by_id = {row.intent_id: row for row in intents}
    orders = ledgers["orders"]
    order_by_intent: dict[str, Any] = {}
    for order in orders:
        if order.intent_id in order_by_intent:
            raise RunValidationError(f"intent generated more than one order: {order.intent_id}")
        intent = intent_by_id.get(order.intent_id)
        if intent is None:
            raise RunValidationError(f"order has no retained intent: {order.event_id}")
        if (
            order.cause_id != intent.intent_id
            or order.batch_id != intent.batch_id
            or order.security_id != intent.security_id
            or order.target_weight != intent.target_weight
        ):
            raise RunValidationError(f"order differs from retained intent: {order.event_id}")
        expected_requested = quantity(
            order.execution_equity * intent.target_weight / order.raw_open_price - order.current_quantity
        )
        if order.requested_quantity != expected_requested:
            raise RunValidationError(f"order target translation mismatch: {order.event_id}")
        if (
            (order.side == Side.BUY and (order.requested_quantity <= ZERO or order.generated_quantity <= ZERO))
            or (order.side == Side.SELL and (order.requested_quantity >= ZERO or order.generated_quantity >= ZERO))
            or order.cash_scale < ZERO
            or order.cash_scale > ONE
        ):
            raise RunValidationError(f"order side or cash scale is invalid: {order.event_id}")
        order_by_intent[order.intent_id] = order

    all_events = sorted(
        [row for name, rows in ledgers.items() if name != "intents" for row in rows],
        key=lambda row: row.sequence,
    )
    cash = ZERO
    positions: dict[str, Decimal] = defaultdict(lambda: ZERO)
    state_before: dict[int, tuple[Decimal, dict[str, Decimal]]] = {}
    cash_ids = {row.event_id for row in ledgers["cash_movements"]}
    position_ids = {row.event_id for row in ledgers["position_movements"]}
    for event in all_events:
        state_before[event.sequence] = (cash, dict(positions))
        if event.event_id in cash_ids:
            cash = money(cash + event.amount)
        elif event.event_id in position_ids:
            positions[str(event.security_id)] = event.quantity_after
    for order in orders:
        _cash, before_positions = state_before[order.sequence]
        if order.current_quantity != before_positions.get(str(order.security_id), ZERO):
            raise RunValidationError(f"order current quantity differs from ledger state: {order.event_id}")

    batches: dict[str, list[TargetWeightIntent]] = defaultdict(list)
    for intent in intents:
        batches[intent.batch_id].append(intent)
    valuation_history: dict[str, list[Any]] = defaultdict(list)
    for valuation in ledgers["valuations"]:
        if valuation.price is not None:
            valuation_history[str(valuation.security_id)].append(valuation)
    rejection_causes = {row.intent_id for row in ledgers["rejections"] if row.intent_id}
    snapshot_sessions = sorted(row.session_date for row in ledgers["portfolio_snapshots"])
    reconstructed = 0
    for batch_id, batch in batches.items():
        actual = sorted(
            [row for row in orders if row.batch_id == batch_id], key=lambda row: row.sequence
        )
        eligible_sessions = [
            session
            for session in snapshot_sessions
            if all(
                modeled_open_timestamp(session, config.market_timezone, config.market_open_time)
                >= intent.earliest_eligible_execution_ts
                for intent in batch
            )
        ]
        if not eligible_sessions:
            continue
        expected_timestamp = modeled_open_timestamp(
            eligible_sessions[0], config.market_timezone, config.market_open_time
        )
        timestamps = {row.timestamp for row in actual}
        if len(timestamps) > 1 or (timestamps and timestamps != {expected_timestamp}):
            raise RunValidationError(f"batch orders have different execution timestamps: {batch_id}")
        timestamp = expected_timestamp
        session = timestamp.astimezone(ZoneInfo(config.market_timezone)).date()
        batch_rejections = [row for row in ledgers["rejections"] if row.batch_id == batch_id]
        anchors = actual + batch_rejections
        if anchors:
            anchor = min(anchors, key=lambda row: row.sequence)
            starting_cash, starting_positions = state_before[anchor.sequence]
        else:
            starting_cash = ZERO
            starting_positions = {}
            for event in all_events:
                if event.timestamp >= timestamp:
                    break
                if event.event_id in cash_ids:
                    starting_cash = money(starting_cash + event.amount)
                elif event.event_id in position_ids:
                    starting_positions[str(event.security_id)] = event.quantity_after
        marks: dict[str, Decimal] = {}
        for security_id, held in starting_positions.items():
            if not held:
                continue
            canonical = canonical_bars.get((session, security_id)) if canonical_bars is not None else None
            if canonical is not None and canonical.get("open") is not None and str(canonical.get("currency")) == config.account_currency:
                marks[security_id] = price(decimal_value(canonical["open"]))
                continue
            same_security = next((row for row in actual if str(row.security_id) == security_id), None)
            if same_security is not None:
                marks[security_id] = same_security.raw_open_price
                continue
            previous = [row for row in valuation_history[security_id] if row.timestamp < timestamp]
            if previous:
                marks[security_id] = previous[-1].price
        if set(marks) != {key for key, held in starting_positions.items() if held}:
            raise RunValidationError(f"cannot independently reconstruct execution equity: {batch_id}")
        expected_equity = money(
            starting_cash + sum((starting_positions[key] * marks[key] for key in marks), ZERO)
        )
        if any(row.execution_equity != expected_equity for row in actual):
            raise RunValidationError(f"order execution equity mismatch: {batch_id}")

        expected: dict[str, tuple[Decimal, Decimal]] = {}
        for intent in batch:
            order = order_by_intent.get(intent.intent_id)
            canonical = canonical_bars.get((session, intent.security_id)) if canonical_bars is not None else None
            if canonical_bars is not None:
                if (
                    canonical is None
                    or canonical.get("open") is None
                    or str(canonical.get("currency")) != config.account_currency
                    or intent.intent_id in rejection_causes
                ):
                    continue
                raw_open = price(decimal_value(canonical["open"]))
                if order is not None and (
                    order.raw_open_price != raw_open
                    or order.currency != str(canonical.get("currency"))
                ):
                    raise RunValidationError(f"order open/currency differs from canonical source: {order.event_id}")
            elif order is not None:
                raw_open = order.raw_open_price
            else:
                continue
            current = starting_positions.get(intent.security_id, ZERO)
            requested = quantity(expected_equity * intent.target_weight / raw_open - current)
            if requested:
                expected[intent.intent_id] = (raw_open, requested)
        sells = sorted(
            [(intent_id, raw, requested) for intent_id, (raw, requested) in expected.items() if requested < ZERO],
            key=lambda row: intent_by_id[row[0]].security_id,
        )
        buys = sorted(
            [(intent_id, raw, requested) for intent_id, (raw, requested) in expected.items() if requested > ZERO],
            key=lambda row: intent_by_id[row[0]].security_id,
        )
        cash_after_sells = starting_cash
        for intent_id, raw_open, requested in sells:
            fill_price = price(raw_open * (ONE - config.slippage_bps / Decimal("10000")))
            notional = money(requested * fill_price)
            commission = money(abs(notional) * config.commission_bps / Decimal("10000"))
            cash_after_sells = money(cash_after_sells - notional - commission)
            order = order_by_intent.get(intent_id)
            if order is None or order.requested_quantity != requested or order.generated_quantity != requested or order.cash_scale != ONE:
                raise RunValidationError(f"sell order reconstruction mismatch: {intent_id}")
            reconstructed += 1
        scale = _independent_affordable_scale(
            [(raw, requested) for _intent_id, raw, requested in buys], cash_after_sells, config
        )
        for intent_id, _raw_open, requested in buys:
            generated = quantity(requested * scale)
            order = order_by_intent.get(intent_id)
            if generated:
                if order is None or order.requested_quantity != requested or order.generated_quantity != generated or order.cash_scale != scale:
                    raise RunValidationError(f"buy order reconstruction mismatch: {intent_id}")
                reconstructed += 1
            elif order is not None:
                raise RunValidationError(f"zero-sized buy unexpectedly generated an order: {intent_id}")
        expected_ids = {intent_id for intent_id, _raw, _requested in sells + buys if quantity(_requested * (scale if _requested > ZERO else ONE))}
        if {row.intent_id for row in actual} != expected_ids:
            raise RunValidationError(f"batch order set differs from reconstructed targets: {batch_id}")
    return reconstructed


def _group_actions(actions: list[CorporateActionInput]) -> dict[str, list[CorporateActionInput]]:
    grouped: dict[str, list[CorporateActionInput]] = defaultdict(list)
    for action in actions:
        grouped[action.action_id].append(action)
    return grouped


def _validate_security_event_states(
    ledgers: dict[str, list[Any]], events: list[SecurityEventInput], config: PortfolioConfig
) -> None:
    grouped: dict[str, list[SecurityEventInput]] = defaultdict(list)
    for event in events:
        grouped[event.event_id].append(event)
    applied: dict[str, int] = {}
    states: dict[str, str] = defaultdict(lambda: "tradeable")
    identifiers: dict[str, str] = {}
    replay_causes = {
        row.cause_id for row in ledgers["rejections"] if row.disposition == RejectionDisposition.REPLAY_REQUIRED
    }
    positions_by_session: dict[Any, list[Any]] = defaultdict(list)
    fills_by_session: dict[Any, list[Any]] = defaultdict(list)
    for row in ledgers["positions"]:
        positions_by_session[row.session_date].append(row)
    for row in ledgers["fills"]:
        local_session = row.timestamp.astimezone(ZoneInfo(config.market_timezone)).date()
        fills_by_session[local_session].append(row)
    for snapshot in ledgers["portfolio_snapshots"]:
        session = snapshot.session_date
        open_ts = modeled_open_timestamp(session, config.market_timezone, config.market_open_time)
        for event_id, revisions in sorted(grouped.items()):
            known = [row for row in revisions if row.available_ts <= open_ts and row.effective_session <= session]
            if not known:
                continue
            chosen = max(known, key=lambda row: row.revision)
            if event_id in applied:
                if chosen.revision > applied[event_id]:
                    if event_id not in replay_causes:
                        raise RunValidationError(f"later security-event revision lacks replay requirement: {event_id}")
                    applied[event_id] = chosen.revision
                continue
            effective_open = modeled_open_timestamp(
                chosen.effective_session, config.market_timezone, config.market_open_time
            )
            if chosen.effective_session < session and chosen.available_ts > effective_open:
                if event_id not in replay_causes:
                    raise RunValidationError(f"late security event lacks replay requirement: {event_id}")
                applied[event_id] = chosen.revision
                continue
            if chosen.event_type == SecurityEventType.SUSPENSION:
                states[chosen.security_id] = "suspended"
            elif chosen.event_type == SecurityEventType.RESUMPTION:
                states[chosen.security_id] = "tradeable"
            elif chosen.event_type == SecurityEventType.DELISTING:
                states[chosen.security_id] = "terminal_delisted"
            elif chosen.event_type == SecurityEventType.IDENTIFIER_CHANGE:
                identifiers[chosen.security_id] = str(chosen.new_identifier)
            applied[event_id] = chosen.revision
        for fill in fills_by_session[session]:
            if states[str(fill.security_id)] != "tradeable":
                raise RunValidationError(f"fill occurred while security was not tradeable: {fill.event_id}")
        for position in positions_by_session[session]:
            security_id = str(position.security_id)
            if position.tradeability_state != states[security_id]:
                raise RunValidationError(f"position tradeability differs from retained events: {position.event_id}")
            if position.identifier != identifiers.get(security_id):
                raise RunValidationError(f"position identifier differs from retained events: {position.event_id}")


def _validate_market_sources(
    ledgers: dict[str, list[Any]], manifest: LedgerRunManifest, config: PortfolioConfig
) -> tuple[dict[str, int], dict[tuple[Any, str], dict[str, Any]]]:
    fills = ledgers["fills"]
    resolved_valuations = [row for row in ledgers["valuations"] if row.source_bar_id is not None]
    snapshots = ledgers["portfolio_snapshots"]
    if not fills and not resolved_valuations and not snapshots:
        return {"fills": 0, "valuations": 0}, {}
    manifest_path = Path(manifest.phase_b_manifest_path)
    files = manifest_files(manifest_path, "bars")
    security_ids = sorted(
        {str(fill.security_id) for fill in fills}
        | {str(valuation.security_id) for valuation in resolved_valuations}
        | {str(intent.security_id) for intent in ledgers["intents"]}
        | {str(position.security_id) for position in ledgers["positions"]}
    )
    source_timestamps = [fill.source_bar_event_ts for fill in fills] + [
        valuation.source_timestamp for valuation in resolved_valuations
    ]
    if not source_timestamps:
        source_timestamps = [row.timestamp for row in snapshots]
    minimum = min(source_timestamps)
    maximum = max(source_timestamps)
    dataset = ds.dataset([str(path) for path in files], format="parquet")
    table = dataset.to_table(
        columns=[
            "security_id",
            "event_ts",
            "available_ts",
            "open",
            "close",
            "currency",
            "source",
            "adjustment_state",
            "adjustment_version",
        ],
        filter=(ds.field("security_id").isin(security_ids))
        & (ds.field("event_ts") >= minimum)
        & (ds.field("event_ts") <= maximum),
    )
    rows = table.to_pylist()
    canonical: dict[str, dict[str, Any]] = {}
    canonical_by_session: dict[tuple[Any, str], dict[str, Any]] = {}
    for row in rows:
        bar_id = "|".join(
            [str(row["security_id"]), row["event_ts"].isoformat(), str(row["source"]), str(row["adjustment_version"])]
        )
        if bar_id in canonical:
            raise RunValidationError(f"duplicate canonical fill source key: {bar_id}")
        canonical[bar_id] = row
        session_key = (
            row["event_ts"].astimezone(ZoneInfo(config.market_timezone)).date(),
            str(row["security_id"]),
        )
        if session_key in canonical_by_session:
            raise RunValidationError(f"ambiguous canonical session/security row: {session_key}")
        canonical_by_session[session_key] = row
    for fill in fills:
        row = canonical.get(fill.source_bar_id)
        if row is None:
            raise RunValidationError(f"fill source bar is absent from pinned manifest: {fill.event_id}")
        if (
            row["event_ts"] != fill.source_bar_event_ts
            or row["available_ts"] != fill.source_bar_available_ts
            or price(decimal_value(row["open"])) != fill.raw_open_price
            or str(row["currency"]) != fill.currency
            or fill.currency != config.account_currency
            or str(row["adjustment_state"]) != fill.adjustment_state
            or str(row["adjustment_version"]) != fill.adjustment_version
        ):
            raise RunValidationError(f"fill price/provenance differs from pinned canonical source: {fill.event_id}")
        fill_session = fill.timestamp.astimezone(ZoneInfo(config.market_timezone)).date()
        source_session = fill.source_bar_event_ts.astimezone(ZoneInfo(config.market_timezone)).date()
        if source_session != fill_session:
            raise RunValidationError(f"fill source bar is not the execution session: {fill.event_id}")
    session_index = {
        snapshot.session_date: index
        for index, snapshot in enumerate(sorted(ledgers["portfolio_snapshots"], key=lambda row: row.session_date))
    }
    for valuation in resolved_valuations:
        row = canonical.get(valuation.source_bar_id)
        if row is None:
            raise RunValidationError(f"valuation source bar is absent from pinned manifest: {valuation.event_id}")
        if (
            row["event_ts"] != valuation.source_timestamp
            or price(decimal_value(row["close"])) != valuation.price
            or str(row["source"]) != valuation.price_source
            or str(row["currency"]) != valuation.currency
        ):
            raise RunValidationError(f"valuation mark/provenance differs from pinned canonical source: {valuation.event_id}")
        if valuation.source_timestamp > valuation.timestamp:
            raise RunValidationError(f"valuation source is from the future: {valuation.event_id}")
        source_session = valuation.source_timestamp.astimezone(ZoneInfo(config.market_timezone)).date()
        if valuation.status == ValuationStatus.COMPLETE:
            if source_session != valuation.session_date or valuation.stale_age_sessions != 0:
                raise RunValidationError(f"complete valuation does not use its session close: {valuation.event_id}")
        elif valuation.status == ValuationStatus.STALE:
            if (
                source_session not in session_index
                or valuation.session_date not in session_index
                or valuation.stale_age_sessions != session_index[valuation.session_date] - session_index[source_session]
                or valuation.stale_age_sessions <= 0
                or config.max_stale_valuation_sessions is None
                or valuation.stale_age_sessions > config.max_stale_valuation_sessions
            ):
                raise RunValidationError(f"stale valuation age/policy mismatch: {valuation.event_id}")
    return {"fills": len(fills), "valuations": len(resolved_valuations)}, canonical_by_session


def validate_run(run_dir: Path, require_directory_identity: bool = True) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    _raw, manifest = _load_manifest(run_dir)
    intents, security_events, corporate_actions, config = _validate_identity(
        run_dir, manifest, require_directory_identity
    )
    ledgers = _validate_artifacts(run_dir, manifest)
    market_sources, canonical_bars = _validate_market_sources(ledgers, manifest, config)
    accounting = _validate_events(
        ledgers, intents, security_events, corporate_actions, config, canonical_bars
    )
    accounting["canonical_fill_sources_checked"] = market_sources["fills"]
    accounting["canonical_valuation_sources_checked"] = market_sources["valuations"]
    return {
        "passed": True,
        "run_id": manifest.run_id,
        "phase_b_manifest_id": manifest.phase_b_manifest_id,
        "artifact_count": len(manifest.artifacts),
        "logical_hashes": manifest.logical_hashes,
        "accounting": accounting,
        "provenance_clean": bool(manifest.implementation_provenance.get("clean")),
    }


def reconcile_run(run_dir: Path) -> dict[str, Any]:
    validation = validate_run(run_dir)
    _raw, manifest = _load_manifest(run_dir.resolve())
    ledgers = _validate_artifacts(run_dir.resolve(), manifest)
    cash_rows = ledgers["cash_movements"]
    position_rows = ledgers["position_movements"]
    fills = ledgers["fills"]
    intent_by_id = {row.intent_id: row for row in ledgers["intents"]}
    per_fill = []
    for fill in fills:
        cash = [row for row in cash_rows if row.fill_id == fill.event_id]
        positions = [row for row in position_rows if row.fill_id == fill.event_id]
        intent = intent_by_id[fill.intent_id]
        per_fill.append(
            {
                "fill_id": fill.event_id,
                "security_id": fill.security_id,
                "quantity": str(fill.quantity),
                "notional": str(fill.notional),
                "commission": str(fill.commission),
                "cash_movement": str(money(sum((row.amount for row in cash), ZERO))),
                "position_delta": str(sum((row.quantity_delta for row in positions), ZERO)),
                "information_available_ts": intent.information_available_ts.isoformat(),
                "decision_ts": intent.decision_ts.isoformat(),
                "eligible_execution_ts": intent.earliest_eligible_execution_ts.isoformat(),
                "modeled_market_open_ts": fill.modeled_market_event_ts.isoformat(),
                "source_completed_bar_event_ts": fill.source_bar_event_ts.isoformat(),
                "price_field": fill.price_field,
                "field_availability_assumption": fill.field_availability_assumption,
                "causality_passed": intent.information_available_ts <= intent.decision_ts
                and fill.modeled_market_event_ts >= intent.earliest_eligible_execution_ts
                and fill.timestamp == fill.modeled_market_event_ts
                and fill.price_field == "open",
                "passed": len(positions) == 1
                and positions[0].quantity_delta == fill.quantity
                and money(sum((row.amount for row in cash), ZERO)) == money(-fill.notional - fill.commission),
            }
        )
    session_rows = [
        {
            "session_date": row.session_date.isoformat(),
            "cash": str(row.cash),
            "market_value": str(row.market_value) if row.market_value is not None else None,
            "equity": str(row.equity) if row.equity is not None else None,
            "valuation_status": row.valuation_status,
            "unvalued_security_ids": list(row.unvalued_security_ids),
        }
        for row in ledgers["portfolio_snapshots"]
    ]
    payload = {"per_fill": per_fill, "sessions": session_rows}
    return {
        "passed": validation["passed"] and all(row["passed"] for row in per_fill),
        "run_id": manifest.run_id,
        "fills_reconciled": len(per_fill),
        "sessions_reconciled": len(session_rows),
        "reconciliation_hash": object_hash(payload),
        "per_fill": per_fill,
        "sessions": session_rows,
    }
