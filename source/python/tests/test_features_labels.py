from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd

from ats_research.features.definitions import compute_pandas_reference, compute_polars, feature_columns
from ats_research.features.registry import feature_specs
from ats_research.labels.forward_returns import compute_forward_returns, label_definitions


def _synthetic_grid(sessions: int = 300, securities: int = 2) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2020-01-01", periods=sessions)
    rows = []
    for security_number in range(securities):
        for index, session in enumerate(dates):
            close = float(100 + security_number * 10 + index)
            rows.append(
                {
                    "security_id": f"s{security_number}",
                    "session_date": session,
                    "close": close,
                    "volume": float(1000 + security_number * 100 + index),
                    "event_ts": session.tz_localize("Europe/Warsaw") + pd.Timedelta(hours=17),
                    "available_ts": session.tz_localize("Europe/Warsaw") + pd.Timedelta(hours=17, minutes=5),
                }
            )
    grid = pd.DataFrame(rows)
    wig = pd.DataFrame(
        {
            "session_date": dates,
            "close": np.arange(sessions, dtype=float) + 1000,
            "event_ts": dates.tz_localize("Europe/Warsaw") + pd.Timedelta(hours=17),
            "available_ts": dates.tz_localize("Europe/Warsaw") + pd.Timedelta(hours=17, minutes=5),
        }
    )
    return grid, wig


def test_feature_lagging_and_lookback_boundaries() -> None:
    grid, wig = _synthetic_grid()
    result = compute_polars(grid, wig).sort_values(["security_id", "session_date"])
    specs = {spec.name: spec for spec in feature_specs()}
    first = result.loc[result["security_id"].eq("s0")].reset_index(drop=True)
    momentum = specs["momentum_12_1"].column
    return_5 = specs["return_5"].column
    vol = specs["realized_volatility_20"].column
    trend = specs["wig_trend_200"].column
    assert first.loc[:251, momentum].isna().all()
    assert np.isclose(first.loc[252, momentum], (100 + 252 - 21) / 100 - 1)
    assert first.loc[:4, return_5].isna().all()
    assert np.isclose(first.loc[5, return_5], 105 / 100 - 1)
    assert first.loc[:19, vol].isna().all()
    assert first.loc[20, vol] >= 0
    assert first.loc[:198, trend].isna().all()
    assert first.loc[199, trend] == first.loc[199, trend]


def test_pandas_reference_and_polars_numeric_agreement() -> None:
    grid, wig = _synthetic_grid()
    polars = compute_polars(grid, wig).sort_values(["security_id", "session_date"]).reset_index(drop=True)
    pandas = compute_pandas_reference(grid, wig).sort_values(["security_id", "session_date"]).reset_index(drop=True)
    for column in feature_columns():
        assert np.allclose(polars[column], pandas[column], rtol=1e-11, atol=1e-12, equal_nan=True), column


def test_forward_label_alignment_and_unavailable_final_sessions() -> None:
    dates = pd.bdate_range("2024-01-01", periods=7)
    grid = pd.DataFrame({"security_id": "one", "session_date": dates, "close": [10, 11, 12, 13, 14, 15, 16]})
    labels = compute_forward_returns(grid, (3, 5))
    defs = {item.horizon_sessions: item for item in label_definitions((3, 5))}
    assert np.isclose(labels.loc[0, defs[3].column], 13 / 10 - 1)
    assert np.isclose(labels.loc[1, defs[5].column], 16 / 11 - 1)
    assert labels.loc[4:, defs[3].column].isna().all()
    assert labels.loc[2:, defs[5].column].isna().all()


def test_missing_exact_end_session_produces_null_label() -> None:
    dates = pd.bdate_range("2024-01-01", periods=5)
    grid = pd.DataFrame({"security_id": "one", "session_date": dates, "close": [10.0, 11.0, 12.0, np.nan, 14.0]})
    labels = compute_forward_returns(grid, (3,))
    column = label_definitions((3,))[0].column
    assert pd.isna(labels.loc[0, column])
    assert np.isclose(labels.loc[1, column], 14 / 11 - 1)


def test_feature_namespace_does_not_import_labels() -> None:
    feature_root = Path(__file__).resolve().parents[1] / "src" / "ats_research" / "features"
    for path in feature_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(name.startswith("ats_research.labels") for name in imports), path


def test_feature_fingerprint_includes_shared_pipeline() -> None:
    for spec in feature_specs():
        assert len(spec.expression_fingerprint) == 64
        assert len(spec.pipeline_fingerprint) == 64
        assert len(spec.code_fingerprint) == 64
        assert spec.code_fingerprint != spec.expression_fingerprint
