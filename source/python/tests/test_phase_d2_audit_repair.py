from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

from ats_ml.contracts import REPOSITORY_ROOT


def load_audit_module():
    prototype = REPOSITORY_ROOT / "RESEARCH/prototypes/phase_d2"
    sys.path.insert(0, str(prototype))
    try:
        spec = importlib.util.spec_from_file_location(
            "phase_d2_audit_v2_fixture", prototype / "audit_phase_d2_v2.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(prototype))


def test_session_and_period_concentration_is_derived_from_episode_anchors(tmp_path: Path) -> None:
    module = load_audit_module()
    stage = tmp_path / "stage2b"
    stage.mkdir()
    pd.DataFrame({
        "block_id": ["H1", "H1", "H1", "H1", "H2"],
        "decision_session": pd.to_datetime([
            "2024-01-02", "2024-01-02", "2024-01-02", "2024-02-01", "2024-07-01"
        ]),
    }).to_parquet(stage / "episode_anchors.parquet", index=False)
    result = module.session_concentration(tmp_path, "stage2b")
    assert result["status"] == "PASS"
    assert result["episode_count"] == 5
    assert result["largest_session_episode_share"] == pytest.approx(0.6)
    assert result["top5_session_episode_share"] == pytest.approx(1.0)
    assert result["session_episode_hhi"] == pytest.approx(0.44)
    assert result["largest_block_episode_share"] == pytest.approx(0.8)
    assert result["block_episode_hhi"] == pytest.approx(0.68)
    assert result["largest_session_boundary"] == ["2024-01-02"]


def test_zero_episode_session_concentration_is_not_proven(tmp_path: Path) -> None:
    module = load_audit_module()
    stage = tmp_path / "stage2c"
    stage.mkdir()
    pd.DataFrame({
        "block_id": pd.Series(dtype="str"),
        "decision_session": pd.Series(dtype="datetime64[ns]"),
    }).to_parquet(stage / "episode_anchors.parquet", index=False)
    result = module.session_concentration(tmp_path, "stage2c")
    assert result["status"] == "NOT PROVEN"
    assert result["session_episode_hhi"] is None
