from __future__ import annotations

import pytest

from ats_ml.d2_stages import (
    BLOCKS,
    INTEGRITY_GATE_NAMES,
    _integrity_gates,
    prediction_scientific_hash,
    validate_evaluation_stage,
    require_stage_outcome_access,
)


def test_2024_cannot_open_before_stage2a_is_sealed() -> None:
    with pytest.raises(PermissionError, match="predecessor"):
        require_stage_outcome_access("stage2b", BLOCKS["stage2b"], set())


def test_locked_cannot_open_before_stage2b_is_sealed() -> None:
    with pytest.raises(PermissionError, match="predecessor"):
        require_stage_outcome_access("stage2c", BLOCKS["stage2c"], {"stage2a"})


def test_each_stage_rejects_later_outcome_blocks() -> None:
    with pytest.raises(PermissionError, match="unpermitted"):
        require_stage_outcome_access("stage2a", [*BLOCKS["stage2a"], *BLOCKS["stage2b"]], set())
    require_stage_outcome_access("stage2a", BLOCKS["stage2a"], set())
    require_stage_outcome_access("stage2b", BLOCKS["stage2b"], {"stage2a"})
    require_stage_outcome_access("stage2c", BLOCKS["stage2c"], {"stage2a", "stage2b"})


def test_evaluation_validator_rejects_unrelated_directory_before_reading_it(tmp_path) -> None:
    unrelated = tmp_path / ".stage-stage2b-fixture"
    unrelated.mkdir()
    with pytest.raises(ValueError, match="identity is invalid"):
        validate_evaluation_stage(unrelated, "stage2a")


def test_reproduction_identity_excludes_operational_package_metadata() -> None:
    primary = {
        "logical_hash": "a" * 64,
        "run_id": "primary",
        "logical_payload": {"prediction_identity": {"logical_hash": "c" * 64}},
    }
    reproduction = {
        "logical_hash": "b" * 64,
        "run_id": "reproduction",
        "logical_payload": {"prediction_identity": {"logical_hash": "c" * 64}},
    }
    assert primary["logical_hash"] != reproduction["logical_hash"]
    assert prediction_scientific_hash(primary) == prediction_scientific_hash(reproduction)


def test_execution_integrity_rows_are_classified_from_supplied_evidence() -> None:
    checks = {
        name: {"value": True, "evidence": f"derived {name}"}
        for name in INTEGRITY_GATE_NAMES
    }
    checks["endpoint_derived_purge"]["value"] = False
    checks["stage_information_order"]["value"] = None
    rows = _integrity_gates("stage2b", "DEVELOPMENT", checks)
    status = {row["gate_id"]: row["status"] for row in rows}
    assert status["stage2b__pit_membership_and_information_timing"] == "PASS"
    assert status["stage2b__endpoint_derived_purge"] == "FAIL"
    assert status["stage2b__stage_information_order"] == "NOT PROVEN"
    assert all(row["evidence"].startswith("derived ") for row in rows)

    with pytest.raises(ValueError, match="differs from the frozen gate set"):
        _integrity_gates("stage2b", "DEVELOPMENT", {"unexpected": {"value": True, "evidence": "x"}})
