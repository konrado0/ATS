from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ats_research.bars import BarValidationError, validate_feature_availability
from ats_research.diagnostics import add_cross_sectional_ranks
from ats_research.features.definitions import cross_sectional_feature_columns, feature_columns
from ats_research.panel import feature_count_column, feature_coverage_column, feature_eligibility_column


def _coverage_fixture() -> pd.DataFrame:
    rows = []
    features = feature_columns()
    for index in range(60):
        usable = index < 57
        row = {
            "session_date": pd.Timestamp("2024-01-02"),
            "security_id": f"s{index:02}",
            "official_member_count": 60,
            "usable_member_count": 57,
            "coverage_ratio": 57 / 60,
            "is_usable_member": usable,
            "is_price_usable_member": usable,
            "price_usable_member_count": 57,
            "price_coverage_ratio": 57 / 60,
            "member_eligibility_state": "eligible" if usable else "missing_prior_session_price",
            "exclusion_reason": pd.NA if usable else "missing_prior_session_price",
        }
        for feature in features:
            row[feature] = float(index) if usable else np.nan
            row[feature_eligibility_column(feature)] = usable
            row[feature_count_column(feature)] = 57
            row[feature_coverage_column(feature)] = 57 / 60
        rows.append(row)
    return pd.DataFrame(rows)


def test_57_of_60_denominator_and_exclusion_retention() -> None:
    ranked = add_cross_sectional_ranks(_coverage_fixture(), 5)
    rank_column = "rank__momentum_12_1__v1"
    assert len(ranked) == 60
    assert ranked["official_member_count"].eq(60).all()
    assert ranked["usable_member_count"].eq(57).all()
    assert np.isclose(ranked["coverage_ratio"].iloc[0], 57 / 60)
    assert ranked[rank_column].notna().sum() == 57
    excluded = ranked.loc[~ranked["is_usable_member"]]
    assert len(excluded) == 3
    assert excluded["exclusion_reason"].eq("missing_prior_session_price").all()


def test_feature_specific_eligibility_does_not_apply_global_mask() -> None:
    frame = _coverage_fixture()
    momentum = "feature__momentum_12_1__v1"
    short_return = "feature__return_5__v1"
    frame.loc[0, momentum] = np.nan
    frame.loc[0, feature_eligibility_column(momentum)] = False
    frame[feature_count_column(momentum)] = 56
    frame[feature_coverage_column(momentum)] = 56 / 60
    ranked = add_cross_sectional_ranks(frame, 5)
    assert pd.isna(ranked.loc[0, "rank__momentum_12_1__v1"])
    assert pd.notna(ranked.loc[0, "rank__return_5__v1"])
    assert ranked["rank__momentum_12_1__v1"].notna().sum() == 56
    assert ranked["rank__return_5__v1"].notna().sum() == 57


def test_wig_trend_is_not_cross_sectionally_ranked() -> None:
    ranked = add_cross_sectional_ranks(_coverage_fixture(), 5)
    assert "feature__wig_trend_200__v1" not in cross_sectional_feature_columns()
    assert "rank__wig_trend_200__v1" not in ranked.columns
    assert "quantile__wig_trend_200__v1" not in ranked.columns


def test_availability_must_not_exceed_decision() -> None:
    frame = pd.DataFrame(
        {
            "security_id": ["one"],
            "session_date": [pd.Timestamp("2024-01-02")],
            "feature_available_ts": [pd.Timestamp("2024-01-02 17:05", tz="Europe/Warsaw")],
            "decision_ts": [pd.Timestamp("2024-01-02 08:45", tz="Europe/Warsaw")],
        }
    )
    with pytest.raises(BarValidationError):
        validate_feature_availability(frame)


def test_availability_previous_close_is_valid_for_next_decision() -> None:
    frame = pd.DataFrame(
        {
            "security_id": ["one"],
            "session_date": [pd.Timestamp("2024-01-03")],
            "feature_available_ts": [pd.Timestamp("2024-01-02 17:05", tz="Europe/Warsaw")],
            "decision_ts": [pd.Timestamp("2024-01-03 08:45", tz="Europe/Warsaw")],
        }
    )
    validate_feature_availability(frame)
