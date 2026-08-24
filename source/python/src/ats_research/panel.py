from __future__ import annotations

import numpy as np
import pandas as pd

from ats_research.bars import BarData, localized_timestamp, validate_feature_availability
from ats_research.config import PhaseAConfig
from ats_research.features.definitions import (
    compute_pandas_reference,
    compute_polars,
    feature_columns,
    regime_feature_column,
)
from ats_research.labels.forward_returns import compute_forward_returns
from ats_research.identity import RESOLVED_VENDOR_STATUSES


class PanelValidationError(ValueError):
    pass


def feature_key(column: str) -> str:
    return column.removeprefix("feature__")


def feature_eligibility_column(column: str) -> str:
    return f"is_feature_eligible__{feature_key(column)}"


def feature_exclusion_column(column: str) -> str:
    return f"feature_exclusion_reason__{feature_key(column)}"


def feature_count_column(column: str) -> str:
    return f"feature_usable_member_count__{feature_key(column)}"


def feature_coverage_column(column: str) -> str:
    return f"feature_coverage_ratio__{feature_key(column)}"


def _max_timestamp(left: pd.Series, right: pd.Series) -> pd.Series:
    result = left.copy()
    take_right = result.isna() | (right.notna() & right.gt(result))
    result.loc[take_right] = right.loc[take_right]
    return result


def build_panel(
    config: PhaseAConfig,
    official_membership: pd.DataFrame,
    bar_data: BarData,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if config.feature_engine != "polars":
        raise PanelValidationError("the real Phase A run is pinned to the validated Polars feature engine")
    features = compute_polars(bar_data.session_grid, bar_data.wig)
    reference = compute_pandas_reference(bar_data.session_grid, bar_data.wig)
    columns = feature_columns()
    merged_check = features[["security_id", "session_date", *columns]].merge(
        reference[["security_id", "session_date", *columns]],
        on=["security_id", "session_date"], suffixes=("_polars", "_pandas"), validate="one_to_one",
    )
    for column in columns:
        left = merged_check[f"{column}_polars"].to_numpy(dtype=float)
        right = merged_check[f"{column}_pandas"].to_numpy(dtype=float)
        if not np.allclose(left, right, rtol=1e-11, atol=1e-12, equal_nan=True):
            delta = np.nanmax(np.abs(left - right))
            raise PanelValidationError(f"Polars/reference mismatch for {column}: max abs delta {delta}")

    sessions = bar_data.sessions.to_frame(name="session_date")
    sessions["feature_session_date"] = sessions["session_date"].shift(1)
    decision_sessions = sessions.loc[
        sessions["session_date"].between(pd.Timestamp(config.start_date), pd.Timestamp(config.end_date))
    ].copy()
    panel = official_membership.merge(decision_sessions, on="session_date", how="inner", validate="many_to_one")
    feature_projection = features.rename(
        columns={
            "session_date": "feature_session_date", "close": "feature_input_close",
            "volume": "feature_input_volume", "event_ts": "feature_event_ts",
            "available_ts": "security_feature_available_ts",
        }
    )
    keep = [
        "security_id", "feature_session_date", "feature_input_close", "feature_input_volume",
        "feature_event_ts", "security_feature_available_ts", "wig_event_ts", "wig_available_ts", *columns,
    ]
    panel = panel.merge(feature_projection[keep], on=["security_id", "feature_session_date"], how="left", validate="many_to_one")
    panel["feature_available_ts"] = _max_timestamp(panel["security_feature_available_ts"], panel["wig_available_ts"])
    panel["decision_ts"] = localized_timestamp(panel["session_date"], config.decision_time, config.timezone)
    panel["decision_semantics"] = "pre-open decision; features use only the immediately preceding WIG session close"

    labels = compute_forward_returns(bar_data.session_grid, config.label_horizons)
    panel = panel.merge(labels, on=["security_id", "session_date"], how="left", validate="many_to_one")
    current_prices = bar_data.session_grid[["security_id", "session_date", "close"]].rename(columns={"close": "label_start_close"})
    panel = panel.merge(current_prices, on=["security_id", "session_date"], how="left", validate="many_to_one")

    securities_with_files = set(bar_data.bars["security_id"].dropna().astype(str))
    panel["source_file_available"] = panel["security_id"].astype(str).isin(securities_with_files)
    missing_identity = panel["security_id"].isna()
    missing_vendor = ~panel["vendor_resolution_status"].isin(RESOLVED_VENDOR_STATUSES)
    source_missing = ~missing_vendor & ~panel["source_file_available"]
    suspended = panel["trading_suspension_from"].notna() & panel["session_date"].ge(panel["trading_suspension_from"])
    missing_prior_price = panel["feature_input_close"].isna()

    panel["price_exclusion_reason"] = pd.Series(pd.NA, index=panel.index, dtype="string")
    assigned = pd.Series(False, index=panel.index)
    for mask, reason in [
        (missing_identity, "unresolved_identity"),
        (missing_vendor, "unresolved_vendor_alias"),
        (source_missing, "source_file_missing"),
        (suspended, "suspended_non_tradeable"),
        (missing_prior_price, "missing_prior_session_price"),
    ]:
        apply = mask & ~assigned
        panel.loc[apply, "price_exclusion_reason"] = reason
        assigned |= apply
    panel["price_eligibility_state"] = panel["price_exclusion_reason"].fillna("eligible")
    panel["is_price_usable_member"] = ~assigned
    official = panel.groupby("session_date")["security_id"].transform("size").astype("int64")
    price_usable = panel.groupby("session_date")["is_price_usable_member"].transform("sum").astype("int64")
    panel["official_member_count"] = official
    panel["price_usable_member_count"] = price_usable
    panel["price_coverage_ratio"] = price_usable / official
    # Compatibility fields now mean price/member usability only.
    panel["member_eligibility_state"] = panel["price_eligibility_state"]
    panel["exclusion_reason"] = panel["price_exclusion_reason"]
    panel["is_usable_member"] = panel["is_price_usable_member"]
    panel["usable_member_count"] = panel["price_usable_member_count"]
    panel["coverage_ratio"] = panel["price_coverage_ratio"]

    complete = panel["is_price_usable_member"].copy()
    for column in columns:
        eligibility = panel["is_price_usable_member"] & panel[column].notna()
        reason = panel["price_exclusion_reason"].copy()
        reason.loc[panel["is_price_usable_member"] & panel[column].isna()] = "insufficient_lookback"
        panel[feature_eligibility_column(column)] = eligibility
        panel[feature_exclusion_column(column)] = reason
        count = eligibility.groupby(panel["session_date"]).transform("sum").astype("int64")
        panel[feature_count_column(column)] = count
        panel[feature_coverage_column(column)] = count / official
        complete &= eligibility
    panel["is_complete_feature_matrix"] = complete
    panel["complete_matrix_exclusion_reason"] = panel["price_exclusion_reason"].copy()
    panel.loc[panel["is_price_usable_member"] & ~complete, "complete_matrix_exclusion_reason"] = "incomplete_feature_matrix"
    complete_count = complete.groupby(panel["session_date"]).transform("sum").astype("int64")
    panel["complete_matrix_member_count"] = complete_count
    panel["complete_matrix_coverage_ratio"] = complete_count / official

    regime_column = regime_feature_column()
    panel["wig_trend_regime"] = np.select(
        [panel[regime_column].gt(0), panel[regime_column].le(0)],
        ["positive", "non_positive"], default="unavailable",
    )
    benign_exit_isins = ["PLLOTOS00025", "PLPGNIG00014", "PLSTSHL00012", "PLCIECH00018", "PLTIM0000016"]
    panel["is_unresolved_exit_member"] = panel["isin"].isin(benign_exit_isins) & missing_vendor
    panel["unresolved_exit_member_count"] = panel.groupby("session_date")["is_unresolved_exit_member"].transform("sum").astype("int64")

    if not panel["official_member_count"].eq(60).all():
        raise PanelValidationError("official denominator was not preserved as 60")
    validate_feature_availability(panel)
    if panel.duplicated(["session_date", "security_id"]).any():
        raise PanelValidationError("duplicate member/session semantic keys")
    panel = panel.sort_values(["session_date", "universe_component", "security_id"]).reset_index(drop=True)
    return panel, features, reference
