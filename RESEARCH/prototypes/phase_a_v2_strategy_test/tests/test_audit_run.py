from __future__ import annotations

import numpy as np
import pandas as pd

from audit_run import gate_row_matches, independent_endpoint_audit, unresolved_diagnostics


def test_gate_match_allows_only_machine_scale_float_aggregation_noise() -> None:
    recomputed = {"gate": "single_security_not_necessary", "status": "PASS", "observed": 137_884.096199}
    published = {"gate": "single_security_not_necessary", "status": "PASS", "observed": 137_884.096199 + 2.4e-10}
    materially_different = {"gate": "single_security_not_necessary", "status": "PASS", "observed": 137_884.096200}
    assert gate_row_matches(recomputed, published)
    assert not gate_row_matches(recomputed, materially_different)


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


def test_independent_endpoint_audit_detects_post_horizon_holdings() -> None:
    sessions = pd.bdate_range("2026-01-02", periods=21)
    portfolios = ("q5", "eligible_universe_benchmark", "q1")
    decisions = []
    targets = []
    daily = []
    for portfolio in portfolios:
        decisions.extend(
            [
                {
                    "period": "common", "offset": 0, "portfolio": portfolio,
                    "decision_date": sessions[0], "decision_type": "entry_rebalance",
                    "scheduled_endpoint_date": sessions[-1],
                },
                {
                    "period": "common", "offset": 0, "portfolio": portfolio,
                    "decision_date": sessions[-1], "decision_type": "terminal_liquidation",
                    "scheduled_endpoint_date": sessions[-1],
                },
            ]
        )
        targets.extend(
            [
                {
                    "period": "common", "offset": 0, "portfolio": portfolio,
                    "decision_date": sessions[0], "security_id": "isin:TEST", "target_weight": "1",
                },
                {
                    "period": "common", "offset": 0, "portfolio": portfolio,
                    "decision_date": sessions[-1], "security_id": "isin:TEST", "target_weight": "0",
                },
            ]
        )
        for session in sessions:
            terminal_or_later = session >= sessions[-1]
            daily.append(
                {
                    "period": "common", "offset": 0, "portfolio": portfolio,
                    "session_date": session, "nav": 1_000_000.0,
                    "holdings_count": 0 if terminal_or_later else 1,
                    "cash_weight": 1.0 if terminal_or_later else 0.0,
                }
            )
    tables = {
        "decision_sessions": pd.DataFrame(decisions),
        "target_weights": pd.DataFrame(targets),
        "daily_nav": pd.DataFrame(daily),
        "fills": pd.DataFrame(
            {
                "period": pd.Series(dtype="object"),
                "offset": pd.Series(dtype="int64"),
                "portfolio": pd.Series(dtype="object"),
                "timestamp": pd.Series(dtype="datetime64[ns]"),
            }
        ),
    }
    assert independent_endpoint_audit(tables)["status"] == "PASS"
    bad_tables = dict(tables)
    bad_tables["daily_nav"] = tables["daily_nav"].copy()
    survivor = (
        bad_tables["daily_nav"]["portfolio"].eq("q5")
        & bad_tables["daily_nav"]["session_date"].eq(sessions[-1])
    )
    bad_tables["daily_nav"].loc[survivor, ["holdings_count", "cash_weight"]] = [1, 0.0]
    assert independent_endpoint_audit(bad_tables)["status"] == "FAIL"
