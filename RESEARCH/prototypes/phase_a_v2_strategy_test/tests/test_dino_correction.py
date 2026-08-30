from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dino_correction import build_supplement, q5_minus_q1, rank_quantile


ROOT = Path(__file__).resolve().parents[1]


def test_phase_a_average_rank_and_tie_quantile() -> None:
    frame = pd.DataFrame(
        {
            "session_date": pd.to_datetime(["2026-01-02"] * 5),
            "value": [1.0, 2.0, 2.0, 4.0, 5.0],
        }
    )
    result = rank_quantile(frame, "value", pd.Series(True, index=frame.index))
    assert result.tolist() == [1, 3, 3, 4, 5]


def test_q5_minus_q1_is_session_equal_weighted() -> None:
    frame = pd.DataFrame(
        {
            "session_date": pd.to_datetime(["2026-01-02"] * 2 + ["2026-01-05"] * 2),
            "quantile": [1, 5, 1, 5],
            "label": [0.0, 0.1, 0.0, -0.02],
        }
    )
    assert q5_minus_q1(frame, "label") == 0.04


def test_real_dino_supplement_is_event_aware_and_reconciles() -> None:
    config = json.loads((ROOT / "dino_config.json").read_text(encoding="utf-8"))
    result = build_supplement(config)
    transition = result["transition"]
    summary = result["summary"]
    assert summary["incorrect_historical_window"] == ["2024-04-11", "2024-04-18"]
    assert summary["corrected_event_window"] == ["2025-07-30", "2025-07-31"]
    assert summary["event_straddling_observations"] == 20
    assert transition["mechanical_drop_absent"].all()
    assert transition["action_reconciliation_difference"].abs().max() < 1e-12
