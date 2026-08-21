from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PORTFOLIO_CONTRACT_VERSION = "ats.portfolio.v1"
LEDGER_MANIFEST_VERSION = "ats.ledger_run_manifest.v1"
DecimalValue = Decimal


class PortfolioContractError(ValueError):
    pass


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class RejectionDisposition(StrEnum):
    REJECTED = "rejected"
    DEFERRED = "deferred"
    REPLAY_REQUIRED = "replay_required"


class ValuationStatus(StrEnum):
    COMPLETE = "complete"
    STALE = "stale"
    UNRESOLVED = "unresolved"


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class CashMovementType(StrEnum):
    INITIAL_CAPITAL = "initial_capital"
    TRADE = "trade"
    COMMISSION = "commission"
    CASH_TAKEOVER = "cash_takeover"


class PositionMovementType(StrEnum):
    TRADE = "trade"
    SPLIT = "split"
    MERGER_REMOVE = "merger_remove"
    MERGER_RECEIVE = "merger_receive"
    CASH_TAKEOVER_REMOVE = "cash_takeover_remove"


class SecurityEventType(StrEnum):
    SUSPENSION = "suspension"
    RESUMPTION = "resumption"
    DELISTING = "delisting"
    IDENTIFIER_CHANGE = "identifier_change"


class CorporateActionType(StrEnum):
    SPLIT = "split"
    REVERSE_SPLIT = "reverse_split"
    MERGER = "merger"
    CASH_TAKEOVER = "cash_takeover"


class ExcludedMemberState(FrozenModel):
    security_id: str | None = None
    raw_identifier: str
    state: str
    reason: str


class TargetWeightIntent(FrozenModel):
    schema_version: Literal["ats.portfolio.v1"] = PORTFOLIO_CONTRACT_VERSION
    intent_id: str
    batch_id: str
    account_id: str
    security_id: str
    decision_ts: datetime
    information_available_ts: datetime
    earliest_eligible_execution_ts: datetime
    earliest_eligible_session: date
    target_weight: DecimalValue
    currency: str
    source_run_id: str
    signal_version: str
    data_manifest_id: str
    data_manifest_path: str
    data_manifest_sha256: str
    official_universe_denominator: int = Field(gt=0)
    usable_price_count: int = Field(ge=0)
    feature_eligible_count: int = Field(ge=0)
    excluded_member_states: tuple[ExcludedMemberState, ...] = ()
    exclusion_artifact_sha256: str | None = None
    reason: str
    provenance: dict[str, Any]

    @field_validator("target_weight")
    @classmethod
    def finite_weight(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0 or value > 1:
            raise ValueError("target_weight must be finite and in [0, 1]")
        return value

    @field_validator("data_manifest_sha256")
    @classmethod
    def valid_manifest_hash(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdefABCDEF" for character in value):
            raise ValueError("data_manifest_sha256 must be 64 hexadecimal characters")
        return value.lower()

    @model_validator(mode="after")
    def timing_and_counts(self) -> "TargetWeightIntent":
        if self.information_available_ts > self.decision_ts:
            raise ValueError("information_available_ts is after decision_ts")
        if self.earliest_eligible_execution_ts <= self.decision_ts:
            raise ValueError("eligible execution must be strictly after decision_ts")
        if self.earliest_eligible_execution_ts.date() != self.earliest_eligible_session:
            raise ValueError("eligible execution timestamp/session mismatch")
        if self.feature_eligible_count > self.usable_price_count:
            raise ValueError("feature_eligible_count exceeds usable_price_count")
        if self.usable_price_count > self.official_universe_denominator:
            raise ValueError("usable_price_count exceeds official denominator")
        expected = self.official_universe_denominator - self.feature_eligible_count
        if self.exclusion_artifact_sha256 is not None:
            raise ValueError("exclusion artifact mode is not supported in v1; retain inline excluded member states")
        if len(self.excluded_member_states) != expected:
            raise ValueError("excluded member states do not reconcile to official denominator")
        keys = [(item.security_id, item.raw_identifier) for item in self.excluded_member_states]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate excluded member state")
        if not self.data_manifest_path.lower().endswith("manifest.json"):
            raise ValueError("data manifest reference must be an explicit manifest.json")
        lowered = self.data_manifest_path.replace("\\", "/").lower()
        if "/catalogs/" in lowered or "current.json" in lowered or "latest" in lowered:
            raise ValueError("mutable manifest discovery references are prohibited")
        return self


class LedgerEvent(FrozenModel):
    schema_version: Literal["ats.portfolio.v1"] = PORTFOLIO_CONTRACT_VERSION
    event_id: str
    run_id: str
    sequence: int = Field(ge=0)
    timestamp: datetime
    account_id: str
    security_id: str | None = None
    cause_id: str


class GeneratedOrder(LedgerEvent):
    batch_id: str
    intent_id: str
    side: Side
    target_weight: DecimalValue
    execution_equity: DecimalValue
    current_quantity: DecimalValue
    requested_quantity: DecimalValue
    generated_quantity: DecimalValue
    cash_scale: DecimalValue
    raw_open_price: DecimalValue
    currency: str


class Fill(LedgerEvent):
    order_id: str
    intent_id: str
    side: Side
    quantity: DecimalValue
    raw_open_price: DecimalValue
    fill_price: DecimalValue
    notional: DecimalValue
    commission: DecimalValue
    slippage_amount: DecimalValue
    currency: str
    source_bar_id: str
    source_bar_event_ts: datetime
    source_bar_available_ts: datetime
    price_field: Literal["open"] = "open"
    modeled_market_event_ts: datetime
    calendar: str
    field_availability_assumption: Literal["open_only_at_modeled_exchange_open"] = (
        "open_only_at_modeled_exchange_open"
    )
    adjustment_state: str
    adjustment_version: str


class CashMovement(LedgerEvent):
    movement_type: CashMovementType
    amount: DecimalValue
    balance_after: DecimalValue
    currency: str
    fill_id: str | None = None
    corporate_action_application_id: str | None = None


class PositionMovement(LedgerEvent):
    movement_type: PositionMovementType
    quantity_delta: DecimalValue
    quantity_after: DecimalValue
    fill_id: str | None = None
    corporate_action_application_id: str | None = None
    related_security_id: str | None = None


class PositionSnapshot(LedgerEvent):
    session_date: date
    quantity: DecimalValue
    identifier: str | None = None
    tradeability_state: str


class Valuation(LedgerEvent):
    session_date: date
    quantity: DecimalValue
    price: DecimalValue | None
    market_value: DecimalValue | None
    currency: str
    status: ValuationStatus
    price_field: Literal["close"] | None = None
    price_source: str | None = None
    source_bar_id: str | None = None
    source_timestamp: datetime | None = None
    stale_age_sessions: int | None = Field(default=None, ge=0)
    reason: str

    @model_validator(mode="after")
    def resolved_fields_cohere(self) -> "Valuation":
        resolved = self.status != ValuationStatus.UNRESOLVED
        if resolved != (self.price is not None and self.market_value is not None):
            raise ValueError("valuation price/value do not match status")
        if self.status == ValuationStatus.STALE and (
            self.source_timestamp is None or self.stale_age_sessions is None
        ):
            raise ValueError("stale valuation lacks source timestamp or age")
        return self


class PortfolioSnapshot(LedgerEvent):
    session_date: date
    cash: DecimalValue
    market_value: DecimalValue | None
    equity: DecimalValue | None
    valuation_status: ValuationStatus
    unvalued_security_ids: tuple[str, ...]
    gross_target_weight: DecimalValue
    rejected_target_weight: DecimalValue
    deferred_target_weight: DecimalValue
    unallocated_weight: DecimalValue
    official_universe_denominator: int | None = None
    usable_price_count: int | None = None
    feature_eligible_count: int | None = None
    excluded_member_states: tuple[ExcludedMemberState, ...] = ()

    @model_validator(mode="after")
    def aggregate_coheres(self) -> "PortfolioSnapshot":
        complete = self.valuation_status != ValuationStatus.UNRESOLVED
        if complete != (self.market_value is not None and self.equity is not None):
            raise ValueError("portfolio totals do not match valuation status")
        if complete and self.unvalued_security_ids:
            raise ValueError("complete portfolio lists unvalued securities")
        if not complete and not self.unvalued_security_ids:
            raise ValueError("unresolved portfolio must list unvalued securities")
        return self


class RejectionOrDeferredAction(LedgerEvent):
    disposition: RejectionDisposition
    reason_code: str
    detail: str
    batch_id: str | None = None
    intent_id: str | None = None
    target_weight: DecimalValue | None = None
    requested_quantity: DecimalValue | None = None
    accepted_quantity: DecimalValue | None = None


class CorporateActionApplication(LedgerEvent):
    action_id: str
    revision: int = Field(ge=0)
    action_type: CorporateActionType
    related_security_id: str | None = None
    source_quantity_before: DecimalValue
    source_quantity_after: DecimalValue
    related_quantity_before: DecimalValue | None = None
    related_quantity_after: DecimalValue | None = None
    cash_delta: DecimalValue
    ratio: DecimalValue | None = None
    cash_amount_per_share: DecimalValue | None = None
    adjustment_policy: str


class SecurityEventInput(FrozenModel):
    schema_version: Literal["ats.portfolio.v1"] = PORTFOLIO_CONTRACT_VERSION
    event_id: str
    revision: int = Field(ge=0)
    security_id: str
    event_type: SecurityEventType
    event_ts: datetime
    available_ts: datetime
    effective_session: date
    related_security_id: str | None = None
    new_identifier: str | None = None
    reason: str
    provenance: dict[str, Any]

    @model_validator(mode="after")
    def availability(self) -> "SecurityEventInput":
        if self.available_ts < self.event_ts:
            raise ValueError("security event availability precedes event")
        if self.event_type == SecurityEventType.IDENTIFIER_CHANGE and not self.new_identifier:
            raise ValueError("identifier change requires new_identifier")
        return self


class CorporateActionInput(FrozenModel):
    schema_version: Literal["ats.portfolio.v1"] = PORTFOLIO_CONTRACT_VERSION
    action_id: str
    revision: int = Field(ge=0)
    security_id: str
    action_type: CorporateActionType
    event_ts: datetime
    available_ts: datetime
    effective_session: date
    related_security_id: str | None = None
    ratio: DecimalValue | None = None
    cash_amount_per_share: DecimalValue | None = None
    currency: str | None = None
    reason: str
    provenance: dict[str, Any]

    @model_validator(mode="after")
    def terms(self) -> "CorporateActionInput":
        if self.available_ts < self.event_ts:
            raise ValueError("corporate action availability precedes event")
        if self.action_type in {CorporateActionType.SPLIT, CorporateActionType.REVERSE_SPLIT}:
            if self.ratio is None or not self.ratio.is_finite() or self.ratio <= 0:
                raise ValueError("split requires a positive finite ratio")
        if self.action_type == CorporateActionType.MERGER:
            if not self.related_security_id or self.ratio is None or self.ratio <= 0:
                raise ValueError("merger requires successor and positive ratio")
        if self.action_type == CorporateActionType.CASH_TAKEOVER:
            if self.cash_amount_per_share is None or self.cash_amount_per_share < 0 or not self.currency:
                raise ValueError("cash takeover requires nonnegative cash terms and currency")
        return self


class ArtifactRecord(FrozenModel):
    path: str
    bytes: int = Field(ge=0)
    physical_sha256: str
    logical_sha256: str
    rows: int = Field(ge=0)
    schema_version: str


class LedgerRunManifest(FrozenModel):
    manifest_schema_version: Literal["ats.ledger_run_manifest.v1"] = LEDGER_MANIFEST_VERSION
    run_id: str
    status: Literal["completed", "failed"]
    created_at: datetime
    phase_b_manifest_id: str
    phase_b_manifest_path: str
    phase_b_manifest_sha256: str
    config_sha256: str
    input_hashes: dict[str, str]
    event_hashes: dict[str, str]
    contract_versions: dict[str, str]
    implementation_provenance: dict[str, Any]
    environment_lock_hash: str
    numeric_policy: dict[str, Any]
    market_field_timing_policy: dict[str, Any]
    calendar: str
    cost_model: dict[str, Any]
    seed: int
    artifacts: tuple[ArtifactRecord, ...]
    logical_hashes: dict[str, str]
    manifest_hash: str


LEDGER_MODELS: dict[str, type[LedgerEvent]] = {
    "orders": GeneratedOrder,
    "fills": Fill,
    "cash_movements": CashMovement,
    "position_movements": PositionMovement,
    "positions": PositionSnapshot,
    "valuations": Valuation,
    "portfolio_snapshots": PortfolioSnapshot,
    "rejections": RejectionOrDeferredAction,
    "corporate_action_applications": CorporateActionApplication,
}
