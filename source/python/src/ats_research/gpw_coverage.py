from __future__ import annotations

from typing import Any

import pandas as pd


def expected_trading_coverage_counts(
    expected_trading: pd.Series, source_observation_present: pd.Series
) -> dict[str, Any]:
    """Compute coverage without allowing observation presence to define the denominator."""
    if len(expected_trading) != len(source_observation_present):
        raise ValueError("coverage inputs must have equal lengths")
    expected = expected_trading.astype(bool)
    present = source_observation_present.astype(bool)
    covered = expected & present
    denominator = int(expected.sum())
    numerator = int(covered.sum())
    return {
        "expected_trading_member_sessions": denominator,
        "covered_expected_trading_member_sessions": numerator,
        "missing_expected_trading_member_sessions": denominator - numerator,
        "coverage_share": float(numerator / denominator) if denominator else None,
    }
