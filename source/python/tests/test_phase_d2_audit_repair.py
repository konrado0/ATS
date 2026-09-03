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


def passing_integrity_checks(module) -> list[dict[str, object]]:
    return [
        {"check_id": check_id, "status": module.AUDIT_PASS}
        for check_id in sorted(module.EXPECTED_INTEGRITY_CHECK_IDS)
    ]


def classify(module, checks, **overrides) -> str:
    arguments = {
        "independent_core_status": module.AUDIT_PASS,
        "scientific_stop_verified": True,
        "accepted_verdict": "STOP",
        "integrity_checks": checks,
        "sealed_evidence_status": module.AUDIT_PASS,
    }
    arguments.update(overrides)
    return module.classify_audit(**arguments)


def replace_check(checks, check_id: str, status: str) -> list[dict[str, object]]:
    return [
        {**item, "status": status} if item["check_id"] == check_id else item
        for item in checks
    ]


def test_audit_classifier_all_evidence_passes() -> None:
    module = load_audit_module()
    assert classify(module, passing_integrity_checks(module)) == module.AUDIT_PASS


def test_audit_classifier_allows_only_the_recognized_historical_qualification() -> None:
    module = load_audit_module()
    checks = replace_check(
        passing_integrity_checks(module),
        module.SEQUENTIAL_ADMISSION_CHECK,
        module.AUDIT_NOT_PROVEN,
    )
    assert classify(module, checks) == module.AUDIT_QUALIFIED_PASS


def test_audit_classifier_does_not_absorb_unrelated_not_proven() -> None:
    module = load_audit_module()
    checks = replace_check(
        passing_integrity_checks(module),
        "endpoint_derived_purge",
        module.AUDIT_NOT_PROVEN,
    )
    assert classify(module, checks) == module.AUDIT_NOT_PROVEN


@pytest.mark.parametrize(
    "check_id",
    ["sequential_locked_label_admission", "endpoint_derived_purge"],
)
def test_audit_classifier_fails_on_any_integrity_failure(check_id: str) -> None:
    module = load_audit_module()
    checks = replace_check(passing_integrity_checks(module), check_id, module.AUDIT_FAIL)
    assert classify(module, checks) == module.AUDIT_FAIL


def test_audit_classifier_fails_when_independent_core_fails() -> None:
    module = load_audit_module()
    assert classify(
        module,
        passing_integrity_checks(module),
        independent_core_status=module.AUDIT_FAIL,
    ) == module.AUDIT_FAIL


def test_audit_classifier_fails_when_sealed_evidence_is_invalid() -> None:
    module = load_audit_module()
    assert classify(
        module,
        passing_integrity_checks(module),
        sealed_evidence_status=module.AUDIT_FAIL,
    ) == module.AUDIT_FAIL


@pytest.mark.parametrize(
    ("override", "value"),
    [
        ("scientific_stop_verified", False),
        ("accepted_verdict", None),
        ("accepted_verdict", "CONTINUE"),
    ],
)
def test_audit_classifier_is_not_proven_without_scientific_or_accepted_stop(
    override: str, value: object
) -> None:
    module = load_audit_module()
    assert classify(
        module, passing_integrity_checks(module), **{override: value}
    ) == module.AUDIT_NOT_PROVEN


def test_audit_classifier_failure_combinations_cannot_produce_qualified_pass() -> None:
    module = load_audit_module()
    checks = replace_check(
        passing_integrity_checks(module),
        module.SEQUENTIAL_ADMISSION_CHECK,
        module.AUDIT_NOT_PROVEN,
    )
    checks = replace_check(checks, "actual_minimums", module.AUDIT_FAIL)
    assert classify(
        module,
        checks,
        independent_core_status=module.AUDIT_FAIL,
        scientific_stop_verified=False,
        accepted_verdict="CONTINUE",
    ) == module.AUDIT_FAIL


def test_audit_classifier_rejects_missing_or_unexpected_integrity_requirements() -> None:
    module = load_audit_module()
    checks = passing_integrity_checks(module)
    assert classify(module, checks[:-1]) == module.AUDIT_NOT_PROVEN
    assert classify(
        module, [*checks, {"check_id": "unexpected", "status": module.AUDIT_PASS}]
    ) == module.AUDIT_NOT_PROVEN


@pytest.mark.parametrize(
    ("status", "expected_exit_code"),
    [
        ("PASS", 0),
        ("PASS WITH EXECUTION-INTEGRITY QUALIFICATION", 0),
        ("FAIL", 1),
        ("NOT PROVEN", 1),
        ("unexpected", 1),
    ],
)
def test_audit_process_exit_code_follows_overall_classification(
    status: str, expected_exit_code: int
) -> None:
    module = load_audit_module()
    assert module.audit_exit_code(status) == expected_exit_code
