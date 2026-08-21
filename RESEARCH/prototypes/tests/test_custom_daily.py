from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from event_engine.custom_daily import simulate


def test_next_session_open_and_costs() -> None:
    prices = pd.DataFrame(
        [
            {"timestamp": pd.Timestamp("2024-01-05"), "security_id": "A", "open": 10.0, "close": 10.0},
            {"timestamp": pd.Timestamp("2024-01-08"), "security_id": "A", "open": 11.0, "close": 12.0},
        ]
    )
    result = simulate(prices, {pd.Timestamp("2024-01-05"): ["A"]}, initial_cash=1_000.0)
    assert len(result.trades) == 1
    assert result.trades.iloc[0]["timestamp"] == pd.Timestamp("2024-01-08")
    assert result.trades.iloc[0]["fill_price"] > 11.0
    assert result.trades.iloc[0]["commission"] > 0
    assert result.equity.iloc[-1]["positions"] == 1


def test_empty_target_stays_in_cash() -> None:
    prices = pd.DataFrame(
        [{"timestamp": pd.Timestamp("2024-01-05"), "security_id": "A", "open": 10.0, "close": 10.0}]
    )
    result = simulate(prices, {}, initial_cash=1_000.0)
    assert result.trades.empty
    assert result.equity.iloc[-1]["equity"] == 1_000.0
