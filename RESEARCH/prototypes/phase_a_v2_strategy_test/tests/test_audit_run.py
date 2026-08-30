from __future__ import annotations

import numpy as np
import pandas as pd

from audit_run import unresolved_diagnostics


def test_terminal_unresolved_sleeve_fails_closed() -> None:
    daily = pd.DataFrame(
        {
            "period": ["expanded"] * 4,
            "offset": [10] * 4,
            "portfolio": ["q5"] * 4,
            "session_date": pd.date_range("2020-12-21", periods=4, freq="D"),
            "nav": [1_000_000.0, np.nan, np.nan, np.nan],
            "valuation_status": ["complete", "unresolved", "unresolved", "unresolved"],
        }
    )
    result = unresolved_diagnostics(daily)
    assert result["status"] == "NOT PROVEN"
    assert not result["all_terminal_navs_resolved"]
    assert result["maximum_consecutive_unresolved_sessions"] == 3


def test_bounded_unresolved_gap_with_resolved_terminal_is_visible_but_passes() -> None:
    daily = pd.DataFrame(
        {
            "period": ["common"] * 4,
            "offset": [0] * 4,
            "portfolio": ["q5"] * 4,
            "session_date": pd.date_range("2024-03-01", periods=4, freq="D"),
            "nav": [1_000_000.0, np.nan, np.nan, 1_010_000.0],
            "valuation_status": ["complete", "unresolved", "unresolved", "complete"],
        }
    )
    result = unresolved_diagnostics(daily)
    assert result["status"] == "PASS"
    assert result["all_terminal_navs_resolved"]
    assert result["maximum_consecutive_unresolved_sessions"] == 2
