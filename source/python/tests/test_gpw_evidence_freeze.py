from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ats_research.gpw_coverage import expected_trading_coverage_counts
from ats_research.gpw_membership import validate_membership_assertion


def _write_snapshot(root: Path, role: str, count: int) -> tuple[Path, list[str]]:
    path = root / "snapshots" / role / "2019-12-23.csv"
    path.parent.mkdir(parents=True)
    isins = [f"{role}-{index:02d}" for index in range(count)]
    pd.DataFrame({"isin": isins}).to_csv(path, index=False)
    return path, isins


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _membership_fixture(tmp_path: Path) -> tuple[Path, Path, pd.DataFrame]:
    root = tmp_path / "reference"
    wig_path, wig = _write_snapshot(root, "WIG20", 20)
    mid_path, mid = _write_snapshot(root, "mWIG40", 40)
    evidence = root / "manifest.csv"
    evidence.write_text("fixture\n", encoding="utf-8")
    assertion = {
        "schema_version": "ats.gpw_membership_completeness.v1",
        "inclusive_completeness_interval": {"start": "2019-12-23", "end": "2026-08-18"},
        "expected_role_counts_per_session": {"WIG20": 20, "mWIG40": 40},
        "authoritative_membership_inputs": {
            "files": [{"relative_path": "manifest.csv", "sha256": _sha256(evidence)}]
        },
        "effective_snapshots": [
            {"role": "WIG20", "effective_date": "2019-12-23", "relative_path": "snapshots/WIG20/2019-12-23.csv", "sha256": _sha256(wig_path)},
            {"role": "mWIG40", "effective_date": "2019-12-23", "relative_path": "snapshots/mWIG40/2019-12-23.csv", "sha256": _sha256(mid_path)},
        ],
    }
    assertion_path = tmp_path / "assertion.json"
    assertion_path.write_text(json.dumps(assertion), encoding="utf-8")
    rows = []
    for role, identities in (("WIG20", wig), ("mWIG40", mid)):
        rows.extend(
            {"session_date": "2019-12-23", "source_index": role, "isin": isin, "effective_from": "2019-12-23"}
            for isin in identities
        )
    return assertion_path, root, pd.DataFrame(rows)


def test_membership_completeness_fails_closed_outside_boundary_and_on_bad_counts(tmp_path: Path) -> None:
    assertion, root, grid = _membership_fixture(tmp_path)
    assert validate_membership_assertion(assertion, root, grid)["validated_member_sessions"] == 60
    before = grid.copy()
    before["session_date"] = "2019-12-20"
    with pytest.raises(ValueError, match="before asserted"):
        validate_membership_assertion(assertion, root, before)
    after = grid.copy()
    after["session_date"] = "2026-08-19"
    with pytest.raises(ValueError, match="after asserted"):
        validate_membership_assertion(assertion, root, after)
    with pytest.raises(ValueError, match="role count"):
        validate_membership_assertion(assertion, root, grid.iloc[:-1])


def test_membership_completeness_rejects_duplicate_or_cross_role_identity(tmp_path: Path) -> None:
    assertion, root, grid = _membership_fixture(tmp_path)
    duplicate = pd.concat([grid, grid.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError):
        validate_membership_assertion(assertion, root, duplicate)
    overlap = grid.copy()
    overlap.loc[overlap["source_index"].eq("mWIG40").idxmax(), "isin"] = grid.iloc[0]["isin"]
    with pytest.raises(ValueError, match="overlaps"):
        validate_membership_assertion(assertion, root, overlap)


def test_expected_bar_absence_reduces_coverage_not_denominator() -> None:
    expected_trading = pd.Series([True, True, False], dtype=bool)
    source_present = pd.Series([True, False, False], dtype=bool)
    result = expected_trading_coverage_counts(expected_trading, source_present)
    assert result == {
        "expected_trading_member_sessions": 2,
        "covered_expected_trading_member_sessions": 1,
        "missing_expected_trading_member_sessions": 1,
        "coverage_share": 0.5,
    }
