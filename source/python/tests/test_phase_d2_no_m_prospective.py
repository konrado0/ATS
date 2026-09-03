from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import ats_ml.d2_no_m_prospective as prospective
from ats_ml.d2_artifacts import D2ArtifactError, file_inventory, write_json
from ats_ml.d2_no_m import NO_M
from ats_research.hashing import sha256_file


CELLS = (NO_M, "C_LINEAR", "C_LIGHTGBM")


def _rewrite_config(package: Path) -> dict:
    config_path = package / "input_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    config["files"] = {
        name: {"sha256": sha256_file(package / name)} for name in prospective.INPUT_FILES
    }
    write_json(config_path, config)
    return config


def _refresh_score(score: Path, package: Path, *, refresh_inputs: bool = True) -> None:
    config = _rewrite_config(package) if refresh_inputs else json.loads((package / "input_config.json").read_text(encoding="utf-8"))
    audit = json.loads((score / "scorer_audit.json").read_text(encoding="utf-8"))
    audit["input_config_sha256"] = sha256_file(package / "input_config.json")
    audit["pinned_input_hashes"] = {name: config["files"][name]["sha256"] for name in prospective.INPUT_FILES}
    audit["prediction_sha256"] = sha256_file(score / "predictions.parquet")
    write_json(score / "scorer_audit.json", audit)
    write_json(score / "manifest.json", {
        "schema_version": "ats.phase_d2_nm.score_package.v3",
        "files": file_inventory(score, exclude={"manifest.json"}),
    })


@pytest.fixture
def score_package(tmp_path: Path) -> tuple[Path, Path]:
    package, score = tmp_path / "input", tmp_path / "score"
    package.mkdir(); score.mkdir()
    calendar = pd.bdate_range("2022-07-01", "2026-10-30")
    decision = pd.Timestamp("2026-08-17")
    information = calendar[calendar.get_loc(decision) - 1]
    endpoint = calendar[calendar.get_loc(decision) + 20]
    pd.DataFrame({"session_date": calendar}).to_parquet(package / "official_calendar.parquet", index=False)
    ids = [f"SEC{i:02d}" for i in range(60)]
    membership = pd.DataFrame({"security_id": ids, "decision_session": decision, "official_membership": True})
    membership.to_parquet(package / "pit_membership.parquet", index=False)
    observations = pd.DataFrame({
        "security_id": ids, "decision_session": decision, "information_session": information,
        "decision_ts": decision.tz_localize("Europe/Warsaw") + pd.Timedelta(hours=8, minutes=45),
        "official_expected_count": 60, "model_exclusion_reason": "",
    })
    observations.to_parquet(package / "observations.parquet", index=False)
    pd.DataFrame({"decision_session": pd.Series(dtype="datetime64[ns]"), "label_endpoint_ts_20": pd.Series(dtype="datetime64[ns, UTC]")}).to_parquet(package / "training_labels.parquet", index=False)
    config = {
        "schema_version": "ats.phase_d2_nm.prospective_input.v3",
        "refit_session": "2026-07-01",
        "decision_sessions": [decision.strftime("%Y-%m-%d")],
        "targets": [{
            "information_session": information.strftime("%Y-%m-%d"),
            "decision_session": decision.strftime("%Y-%m-%d"),
            "decision_ts": (decision.tz_localize("Europe/Warsaw") + pd.Timedelta(hours=8, minutes=45)).isoformat(),
            "target_start_session": decision.strftime("%Y-%m-%d"),
            "target_endpoint_session": endpoint.strftime("%Y-%m-%d"),
            "label_availability_ts": (endpoint.tz_localize("Europe/Warsaw") + pd.Timedelta(hours=9)).isoformat(),
        }],
    }
    expected_block, walk_forward_proof = prospective._derive_expected_walk_forward_block(
        config, {"official_calendar.parquet": pd.DataFrame({"session_date": calendar})}
    )
    write_json(package / "walk_forward_block.json", expected_block)
    write_json(package / "input_config.json", config)
    _rewrite_config(package)
    predictions = pd.concat([
        observations.assign(cell_id=cell, model_score=0.02, threshold=0.01, candidate=True, prediction_generation_ts=pd.Timestamp("2026-08-17T06:00:00Z"))
        for cell in CELLS
    ], ignore_index=True)
    predictions.to_parquet(score / "predictions.parquet", index=False)
    binding = prospective._verified_contract_binding()
    audit = {
        "schema_version": "ats.phase_d2_nm.scorer_audit.v3", "input_package": str(package.resolve()),
        "input_config_sha256": sha256_file(package / "input_config.json"),
        "pinned_input_hashes": {name: json.loads((package / "input_config.json").read_text())["files"][name]["sha256"] for name in prospective.INPUT_FILES},
        "contract_binding": binding, "cells": binding["cells"], "walk_forward_proof": walk_forward_proof,
        "implementation_fingerprint": prospective._implementation_fingerprint(),
        "prediction_sha256": sha256_file(score / "predictions.parquet"),
    }
    write_json(score / "scorer_audit.json", audit)
    write_json(score / "manifest.json", {"schema_version": "ats.phase_d2_nm.score_package.v3", "files": file_inventory(score, exclude={"manifest.json"})})
    return package, score


def test_valid_score_package_requires_exact_pinned_top60(score_package) -> None:
    _package, score = score_package
    frame, validation, _targets, _audit = prospective._verify_score_package(score)
    assert len(frame) == 180
    assert validation["official_rows_per_cell_session"] == 60


def test_forged_or_backdated_publication_timestamp_is_rejected(score_package) -> None:
    package, score = score_package
    frame = pd.read_parquet(score / "predictions.parquet")
    frame["publication_completed_ts"] = "2000-01-01T00:00:00Z"
    frame.to_parquet(score / "predictions.parquet", index=False)
    _refresh_score(score, package)
    with pytest.raises(D2ArtifactError, match="publisher-authority"):
        prospective._verify_score_package(score)


@pytest.mark.parametrize("mode", ["one", "extra", "wrong", "duplicate"])
def test_missing_extra_wrong_or_duplicate_top60_identities_fail(score_package, mode) -> None:
    package, score = score_package
    frame = pd.read_parquet(score / "predictions.parquet")
    if mode == "one":
        frame = frame.groupby("cell_id", sort=False).head(1)
    elif mode == "extra":
        extra = frame.groupby("cell_id", sort=False).head(1).copy()
        extra["security_id"] = "EXTRA"
        frame = pd.concat([frame, extra], ignore_index=True)
    elif mode == "wrong":
        frame.loc[0, "security_id"] = "NOT_OFFICIAL"
    else:
        frame.loc[1, "security_id"] = frame.loc[0, "security_id"]
    frame.to_parquet(score / "predictions.parquet", index=False)
    _refresh_score(score, package)
    with pytest.raises(D2ArtifactError, match="population|identity|duplicate"):
        prospective._verify_score_package(score)


def test_missing_scorer_audit_is_rejected(score_package) -> None:
    _package, score = score_package
    (score / "scorer_audit.json").unlink()
    with pytest.raises(D2ArtifactError, match="sidecar"):
        prospective._verify_score_package(score)


def test_changed_input_hash_is_rejected(score_package) -> None:
    package, score = score_package
    observations = pd.read_parquet(package / "observations.parquet")
    observations.loc[0, "official_expected_count"] = 59
    observations.to_parquet(package / "observations.parquet", index=False)
    with pytest.raises(D2ArtifactError, match="pinned prospective input mismatch"):
        prospective._verify_score_package(score)


def test_corrupt_contract_binding_is_rejected(score_package) -> None:
    package, score = score_package
    audit = json.loads((score / "scorer_audit.json").read_text())
    audit["contract_binding"]["scientific_contract_sha256"] = "0" * 64
    write_json(score / "scorer_audit.json", audit)
    write_json(score / "manifest.json", {"schema_version": "ats.phase_d2_nm.score_package.v3", "files": file_inventory(score, exclude={"manifest.json"})})
    with pytest.raises(D2ArtifactError, match="contract binding"):
        prospective._verify_score_package(score)


def test_invalid_information_session_is_rejected(score_package) -> None:
    package, score = score_package
    observations = pd.read_parquet(package / "observations.parquet")
    observations["information_session"] = observations["decision_session"]
    observations.to_parquet(package / "observations.parquet", index=False)
    _refresh_score(score, package)
    with pytest.raises(D2ArtifactError, match="preceding official"):
        prospective._verify_score_package(score)


def test_decision_timestamp_must_be_exactly_0845_warsaw(score_package) -> None:
    package, score = score_package
    observations = pd.read_parquet(package / "observations.parquet")
    observations["decision_ts"] = pd.to_datetime(observations["decision_ts"], utc=True) + pd.Timedelta(minutes=1)
    observations.to_parquet(package / "observations.parquet", index=False)
    _refresh_score(score, package)
    with pytest.raises(D2ArtifactError, match="08:45 Europe/Warsaw"):
        prospective._verify_score_package(score)


def test_incorrect_target_endpoint_is_rejected(score_package) -> None:
    package, score = score_package
    config = json.loads((package / "input_config.json").read_text())
    config["targets"][0]["target_endpoint_session"] = "2026-09-30"
    write_json(package / "input_config.json", config)
    _refresh_score(score, package, refresh_inputs=False)
    with pytest.raises(D2ArtifactError, match="target timing"):
        prospective._verify_score_package(score)


@pytest.mark.parametrize("mutation", ["fit_window", "calibration_blocks", "purge_boundary"])
def test_altered_walk_forward_training_procedure_fails_closed(score_package, mutation) -> None:
    package, score = score_package
    block_path = package / "walk_forward_block.json"
    block = json.loads(block_path.read_text())
    if mutation == "fit_window":
        block["estimator_window_start"] = block["estimator_window_sessions"][1]
    elif mutation == "calibration_blocks":
        block["inner_score_blocks"] = block["inner_score_blocks"][:2]
    else:
        block["inner_score_blocks"][0]["fit_boundary_session"] = block["inner_score_blocks"][0]["score_sessions"][1]
    write_json(block_path, block)
    _refresh_score(score, package)
    with pytest.raises(D2ArtifactError, match="walk-forward block"):
        prospective._verify_score_package(score)


@pytest.mark.parametrize("mutation", ["lightgbm_parameter", "ridge_parameter", "preprocessing"])
def test_altered_estimator_parameters_or_preprocessing_fail_closed(score_package, mutation) -> None:
    package, score = score_package
    audit = json.loads((score / "scorer_audit.json").read_text())
    definitions = audit["implementation_fingerprint"]["model_definitions"]
    if mutation == "lightgbm_parameter":
        definitions["LIGHTGBM"]["parameters"]["num_leaves"] = 31
    elif mutation == "ridge_parameter":
        definitions["RIDGE"]["parameters"]["alpha"] = 2.0
    else:
        definitions["RIDGE"]["preprocessing"][0]["strategy"] = "mean"
    write_json(score / "scorer_audit.json", audit)
    write_json(score / "manifest.json", {"schema_version": "ats.phase_d2_nm.score_package.v3", "files": file_inventory(score, exclude={"manifest.json"})})
    with pytest.raises(D2ArtifactError, match="estimator parameters, or preprocessing"):
        prospective._verify_score_package(score)


def test_publication_crossing_0845_is_permanently_monitoring_only(score_package, tmp_path, monkeypatch) -> None:
    _package, score = score_package
    stream = tmp_path / "stream"
    stream.mkdir(); write_json(stream / "registration.json", {"stream_id": prospective.STREAM_ID})
    monkeypatch.setattr(prospective, "STREAM_ROOT", stream)
    times = iter([pd.Timestamp("2026-08-17T06:44:59Z"), pd.Timestamp("2026-08-17T06:45:01Z")])
    destination = prospective.append_prediction_batch(score, batch_id="crossing-v1", now_provider=lambda: next(times))
    receipt = json.loads((stream / "receipts/crossing-v1.json").read_text())
    assert destination.is_dir()
    assert receipt["eligibility_authority"] == "publisher_post_atomic_finalization_clock"
    assert receipt["sessions"][0]["prospective_eligible"] is False
    assert receipt["sessions"][0]["monitoring_only"] is True
    assert receipt["sessions"][0]["exclusion_reason"] == "PUBLISHED_AFTER_DECISION_TS"


def test_empty_v1_is_preserved_and_superseded_by_v2(tmp_path, monkeypatch) -> None:
    streams, legacy, repaired = tmp_path / "streams", tmp_path / "streams/v1", tmp_path / "streams/v2"
    legacy.mkdir(parents=True); write_json(legacy / "registration.json", {"stream_id": "v1"})
    before = sha256_file(legacy / "registration.json")
    monkeypatch.setattr(prospective, "STREAMS_ROOT", streams)
    monkeypatch.setattr(prospective, "LEGACY_STREAM_ROOT", legacy)
    monkeypatch.setattr(prospective, "STREAM_ROOT", repaired)
    monkeypatch.setattr(prospective, "SUPERSESSION_ROOT", streams / "supersessions")
    prospective.initialize_repaired_stream(reason="bounded repair", now_provider=lambda: pd.Timestamp("2026-09-03T12:00:00Z"))
    assert sha256_file(legacy / "registration.json") == before
    marker = json.loads((streams / "supersessions/phase-d2-nm-post-freeze-2026-v2.json").read_text())
    assert marker["status"] == "NON_OPERATIONAL_SUPERSEDED_EMPTY_REGISTRATION"
    assert json.loads((repaired / "registration.json").read_text())["status"] == "ACTIVE_EMPTY_AWAITING_ELIGIBLE_SESSION"
