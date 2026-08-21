from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from ats_research.artifacts import ArtifactWriter
from ats_research.config import PhaseAConfig
from ats_research.hashing import logical_frame_hash, logical_manifest_hash
from ats_research.validation import require_exact_artifact_set


def _config(tmp_path: Path) -> PhaseAConfig:
    source = tmp_path / "data"
    source.mkdir()
    return PhaseAConfig(
        source_data_root=source,
        output_root=source / "ATS",
        start_date=date(2020, 11, 27),
        end_date=date(2021, 1, 1),
        warmup_start=date(2019, 1, 1),
        source_name="test",
        source_version="v1",
        schema_version="v1",
        universe_id="test",
        universe_version="v1",
        logical_dataset_name="test",
    )


def test_logical_frame_hash_is_order_independent_with_semantic_sort() -> None:
    frame = pd.DataFrame({"key": [2, 1], "value": [2.5, 1.5]})
    assert logical_frame_hash(frame, ["key"]) == logical_frame_hash(frame.iloc[::-1], ["key"])


def test_parquet_physical_and_logical_hashes_are_deterministic(tmp_path: Path) -> None:
    config = _config(tmp_path)
    frame = pd.DataFrame({"key": [2, 1], "value": [2.5, 1.5]})
    first = ArtifactWriter(config.output_root / "one", config).parquet("artifacts/test.parquet", frame, ["key"])
    second = ArtifactWriter(config.output_root / "two", config).parquet("artifacts/test.parquet", frame.iloc[::-1], ["key"])
    assert first.logical_hash == second.logical_hash
    assert first.sha256 == second.sha256


def test_manifest_logical_hash_ignores_only_wall_clock_timestamp() -> None:
    first = {"run_id": "x", "creation_timestamp": "2024-01-01T00:00:00Z", "value": 1}
    second = {"run_id": "x", "creation_timestamp": "2025-01-01T00:00:00Z", "value": 1}
    assert logical_manifest_hash(first) == logical_manifest_hash(second)
    second["value"] = 2
    assert logical_manifest_hash(first) != logical_manifest_hash(second)


def test_generated_output_root_cannot_leave_source_data_ats(tmp_path: Path) -> None:
    source = tmp_path / "data"
    source.mkdir()
    with pytest.raises(ValueError):
        PhaseAConfig(
            source_data_root=source,
            output_root=tmp_path / "elsewhere",
            start_date=date(2020, 11, 27), end_date=date(2021, 1, 1), warmup_start=date(2019, 1, 1),
            source_name="test", source_version="v1", schema_version="v1", universe_id="test",
            universe_version="v1", logical_dataset_name="test",
        )


def test_artifact_writer_rejects_path_escape(tmp_path: Path) -> None:
    config = _config(tmp_path)
    writer = ArtifactWriter(config.output_root / "run", config)
    with pytest.raises(ValueError):
        writer.json("../escaped.json", {"bad": True})


def test_manifest_file_set_must_match_both_directions() -> None:
    require_exact_artifact_set({"config.yaml", "metrics.json", "artifacts/a.parquet"}, {"config.yaml", "metrics.json", "artifacts/a.parquet"})
    with pytest.raises(ValueError, match="missing"):
        require_exact_artifact_set({"config.yaml", "metrics.json"}, {"config.yaml"})
    with pytest.raises(ValueError, match="unexpected"):
        require_exact_artifact_set({"config.yaml"}, {"config.yaml", "artifacts/extra.csv"})
