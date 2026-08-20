from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ats_data.discovery import scan_table
from ats_data.reconciliation import reconcile_gpw


PHASE_A = Path(r"D:\Stock\data\ATS\phase_a\runs\phasea-2a2b3898aba37814")
GPW = Path(r"D:\Stock\data\ATS\phase_b\versions\phaseb-dd0bb7a8679ab9c658e9\manifest.json")
US = Path(r"D:\Stock\data\ATS\phase_b\versions\phaseb-1ffe35fd776b58a5df7c\manifest.json")


@pytest.mark.skipif(not GPW.exists(), reason="Phase B GPW reference publication unavailable")
def test_gpw_reference_reconciles_and_retains_denominator_states() -> None:
    result = reconcile_gpw(PHASE_A, GPW)
    assert result["passed"] is True and result["numeric_tolerance"] == 0.0
    membership = scan_table(GPW, "universe_membership").collect()
    assert membership["official_denominator"].unique().to_list() == [60]
    assert membership.filter(membership["member_state"] == "benign_corporate_exit").height == 45


@pytest.mark.skipif(not US.exists(), reason="Phase B U.S. reference publication unavailable")
def test_us_reference_keeps_provisional_and_malformed_records_visible() -> None:
    master = scan_table(US, "security_master").select(["identity_status", "issuer_id", "valid_from"]).collect()
    assert master.height == 15_355
    assert master["identity_status"].unique().to_list() == ["provisional_source_scoped"]
    assert master["issuer_id"].null_count() == 15_355
    assert master.filter(master["valid_from"] == date(1900, 1, 1)).height == 0
    assert scan_table(US, "ingestion_issues").collect().height == 135
