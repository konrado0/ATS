from __future__ import annotations

import numpy as np
import pandas as pd

from ats_ml.contracts import FrozenD0Contract, load_frozen_d0_contract
from ats_ml.guard import D1ExecutionGuard, ExecutionContext, synthetic_fixture_context


def d1_contract_guard_context(fixture_id: str = "phase-d1-fixture-core") -> tuple[FrozenD0Contract, D1ExecutionGuard, ExecutionContext]:
    contract = load_frozen_d0_contract()
    guard = D1ExecutionGuard(contract)
    context = synthetic_fixture_context(contract, guard, fixture_id)
    return contract, guard, context


def stock_bars(
    dates: pd.DatetimeIndex,
    securities: int = 1,
    *,
    close_paths: dict[str, np.ndarray] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for number in range(securities):
        security_id = f"S{number:02d}"
        close = close_paths[security_id] if close_paths and security_id in close_paths else 100.0 * np.power(1.001 + number * 0.00001, np.arange(len(dates)))
        for index, session in enumerate(dates):
            value = float(close[index])
            rows.append({
                "security_id": security_id,
                "session_date": session,
                "split_adjusted_open": value * 0.99,
                "split_adjusted_high": value * 1.1,
                "split_adjusted_low": value * 0.9,
                "split_adjusted_close": value,
                "split_adjusted_volume": float(1000 + index),
                "official_membership": True,
                "price_usable_for_features": True,
                "volume_usable_for_relative_volume": True,
                "source_treatment_state": "",
                "factor_version": "fixture-v1",
                "missing_state": "",
                "nontrading_reason": "",
                "coverage_result": "covered",
                "data_basis_version": "synthetic.phase_d1.v1",
                "selected_source": "fixture-a",
            })
    return pd.DataFrame(rows)


def official_membership(bars: pd.DataFrame, decision_sessions: list[pd.Timestamp]) -> pd.DataFrame:
    return bars.loc[bars["session_date"].isin(decision_sessions), [
        "security_id", "session_date", "official_membership", "missing_state", "nontrading_reason", "coverage_result"
    ]].copy()
