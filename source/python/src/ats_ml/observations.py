from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable

import numpy as np
import pandas as pd

from ats_ml.contracts import FrozenD0Contract
from ats_ml.features import FROZEN_EXCLUSION_CODES, _reject_predictive_columns, attach_information_session_features, compute_x_features
from ats_ml.guard import D1ExecutionGuard, ExecutionContext, Operation
from ats_ml.labels import LabelFrame


class ObservationContractError(ValueError):
    pass


CORE_SCORE_FEATURES = (
    "proximity_to_max_high_252",
    "momentum_12_1",
    "realized_volatility_20",
    "return_5",
)


def _row_state(row: pd.Series) -> str:
    text = "|".join(
        str(row.get(column, ""))
        for column in ("missing_state", "nontrading_reason", "coverage_result", "volume_ineligibility_reason")
        if pd.notna(row.get(column, ""))
    ).lower()
    if "prelist" in text or "not_yet" in text:
        return "PRELISTING"
    if "nontrading" in text or "non_trading" in text or "suspend" in text:
        return "DOCUMENTED_NON_TRADING"
    if "identity" in text or "unresolved" in text:
        return "UNRESOLVED_IDENTITY"
    return "MISSING_PRICE"


def build_observation_matrix(
    official_membership: pd.DataFrame,
    stock_history: pd.DataFrame,
    market_features: pd.DataFrame,
    calendar: Iterable[object],
    contract: FrozenD0Contract,
    *,
    stock_blocks: tuple[str, ...] = ("C", "P"),
) -> pd.DataFrame:
    _reject_predictive_columns(official_membership, "observation membership input")
    _reject_predictive_columns(stock_history, "observation stock-feature input")
    _reject_predictive_columns(market_features, "observation market-feature input")
    stock_names = [name for block in stock_blocks for name in contract.feature_blocks[block]]
    observations = attach_information_session_features(official_membership, stock_history, calendar, stock_names)
    if "C" in stock_blocks:
        observations = compute_x_features(observations, contract.config["observation_contract"]["cross_section_minimum_eligible_members"])
    market = market_features.copy()
    market["decision_session"] = pd.to_datetime(market["decision_session"]).dt.normalize()
    m_names = list(contract.feature_blocks["M"])
    if set(m_names) - set(market.columns):
        raise ObservationContractError(f"market features missing: {sorted(set(m_names) - set(market.columns))}")
    market_proof_columns = [
        column for column in market.columns
        if column.startswith(("eligible_count__", "eligible_count_current__", "eligible_count_lag10__", "official_expected_count__", "excluded_count__", "excluded_count_current__", "excluded_count_lag10__", "exclusion_reason_counts__", "exclusion_reason_counts_current__", "exclusion_reason_counts_lag10__", "aggregation_state__"))
    ]
    observations = observations.merge(
        market[["decision_session", "information_session", *m_names, *market_proof_columns]].rename(columns={"information_session": "market_information_session"}),
        on="decision_session",
        how="left",
        validate="many_to_one",
    )
    if not observations["market_information_session"].eq(observations["information_session"]).all():
        raise ObservationContractError("stock and market information sessions differ")
    observations["decision_ts"] = (
        observations["decision_session"].dt.tz_localize(contract.config["observation_contract"]["market_timezone"])
        + pd.Timedelta(hours=8, minutes=45)
    )
    observations["official_expected_count"] = 60
    for name in m_names:
        observations[f"eligible__{name}"] = observations[name].notna() & np.isfinite(observations[name])
    for name in contract.registry_order:
        if f"eligible__{name}" in observations.columns:
            aggregation_count = f"eligible_count__{name}"
            if name in m_names and aggregation_count in observations.columns:
                observations[f"feature_eligible_count__{name}"] = observations[aggregation_count].astype("Int64")
            else:
                observations[f"feature_eligible_count__{name}"] = (
                    observations[f"eligible__{name}"].fillna(False).groupby(observations["decision_session"]).transform("sum").astype("int64")
                )
    score_mask = pd.Series(True, index=observations.index)
    for name in CORE_SCORE_FEATURES:
        score_mask &= observations[f"eligible__{name}"].fillna(False)
    observations["model_score_eligible"] = score_mask
    observations["scored"] = score_mask
    observations["model_eligible_count"] = score_mask.groupby(observations["decision_session"]).transform("sum").astype("int64")
    observations["scored_count"] = observations["model_eligible_count"]
    observations["excluded_count"] = 60 - observations["model_eligible_count"]
    observations["feature_eligible_counts"] = observations.apply(
        lambda row: json.dumps(
            {name: int(row[f"feature_eligible_count__{name}"]) for name in contract.registry_order if f"feature_eligible_count__{name}" in observations.columns},
            sort_keys=True,
            separators=(",", ":"),
        ),
        axis=1,
    )
    observations["model_exclusion_reason"] = ""
    for index in observations.index[~score_mask]:
        row = observations.loc[index]
        failed = [name for name in CORE_SCORE_FEATURES if not bool(row.get(f"eligible__{name}", False))]
        feature_states = [str(row.get(f"missing_state__{name}", "")) for name in failed]
        closed_state = next((state for state in feature_states if state in FROZEN_EXCLUSION_CODES), None)
        observations.at[index, "model_exclusion_reason"] = closed_state or _row_state(row)
    reason_by_session: dict[pd.Timestamp, str] = {}
    for session, group in observations.groupby("decision_session", sort=True):
        counter = Counter(group.loc[~group["model_score_eligible"], "model_exclusion_reason"])
        reason_by_session[session] = json.dumps(dict(sorted(counter.items())), sort_keys=True, separators=(",", ":"))
    observations["exclusion_reason_counts"] = observations["decision_session"].map(reason_by_session)
    observations["outcome_evaluable_count"] = pd.array([pd.NA] * len(observations), dtype="Int64")
    observations["outcome_unavailable_count"] = pd.array([pd.NA] * len(observations), dtype="Int64")
    observations["candidate_run_id"] = contract.config["input"]["candidate_run_id"]
    observations["contract_version"] = contract.config["contract_version"]
    if observations.duplicated(["security_id", "decision_session"]).any():
        raise ObservationContractError("observation matrix has duplicate semantic keys")
    counts = observations.groupby("decision_session")["security_id"].nunique()
    row_counts = observations.groupby("decision_session").size()
    if not counts.eq(60).all() or not row_counts.eq(60).all():
        raise ObservationContractError("observation matrix lost the official denominator 60")
    return observations.sort_values(["decision_session", "security_id"], kind="mergesort").reset_index(drop=True)


def attach_outcome_availability(
    observations: pd.DataFrame,
    labels: LabelFrame,
    guard: D1ExecutionGuard,
    context: ExecutionContext,
) -> pd.DataFrame:
    if not isinstance(labels, LabelFrame) or labels.context != context:
        raise ObservationContractError("outcome attachment requires an aligned sealed synthetic label frame")
    guard.require(Operation.BUILD_LABEL_VALUES, context)
    label_values = labels.frame
    result = observations.merge(
        label_values[["security_id", "decision_session", "label_endpoint_session", "label_endpoint_ts", "label__open_to_open__20", "label_state"]],
        on=["security_id", "decision_session"],
        how="left",
        validate="one_to_one",
    )
    result["outcome_evaluable"] = result["model_score_eligible"] & result["label__open_to_open__20"].notna()
    count = result["outcome_evaluable"].groupby(result["decision_session"]).transform("sum").astype("int64")
    result["outcome_evaluable_count"] = count
    result["outcome_unavailable_count"] = result["scored_count"] - count
    return result
