from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ats_ml.d2_artifacts import D2ArtifactError, publish_immutable, validate_manifest, write_json, write_parquet


def test_immutable_publication_rejects_overwrite_and_detects_tampering(tmp_path: Path) -> None:
    required = {"data.parquet", "proof.json"}

    def build(stage: Path):
        write_parquet(stage / "data.parquet", pd.DataFrame({"value": [1, 2]}))
        write_json(stage / "proof.json", {"status": "PASS"})
        return {"logical": "fixture"}

    validate = lambda path: validate_manifest(path, schema_version="fixture.v1", required_files=required)
    run = publish_immutable(tmp_path, "explicit-v1", build, schema_version="fixture.v1", validate=validate)
    with pytest.raises(D2ArtifactError, match="already exists"):
        publish_immutable(tmp_path, "explicit-v1", build, schema_version="fixture.v1", validate=validate)
    (run / "proof.json").write_text('{"status":"FAIL"}\n', encoding="utf-8")
    with pytest.raises(D2ArtifactError, match="hash mismatch"):
        validate(run)


def test_mutable_run_identity_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(D2ArtifactError, match="explicit immutable"):
        publish_immutable(
            tmp_path, "latest", lambda stage: {}, schema_version="fixture.v1",
            validate=lambda stage: {},
        )


def test_failed_build_is_preserved_for_forensic_review(tmp_path: Path) -> None:
    def fail(stage: Path):
        write_json(stage / "partial.json", {"real_results_may_exist": True})
        raise RuntimeError("fixture failure")

    with pytest.raises(RuntimeError, match="fixture failure"):
        publish_immutable(
            tmp_path, "failed-v1", fail, schema_version="fixture.v1",
            validate=lambda stage: {},
        )
    failed = list(tmp_path.glob(".failed-failed-v1-*"))
    assert len(failed) == 1
    assert (failed[0] / "partial.json").is_file()
