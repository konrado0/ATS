from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import yaml

from ats_research.bars import validate_feature_availability
from ats_research.config import load_config
from ats_research.features.definitions import cross_sectional_feature_columns, regime_feature_column
from ats_research.hashing import content_hash, logical_frame_hash, logical_manifest_hash, sha256_file
from ats_research.panel import feature_count_column, feature_eligibility_column, feature_key


def require_exact_artifact_set(expected_files: set[str], actual_files: set[str]) -> None:
    if actual_files != expected_files:
        raise ValueError(
            f"manifest/actual artifact set mismatch: missing={sorted(expected_files-actual_files)}, "
            f"unexpected={sorted(actual_files-expected_files)}"
        )


def _logical_hash(path: Path, record: dict[str, object]) -> str:
    format_name = str(record["format"])
    if format_name == "parquet":
        frame = pd.read_parquet(path)
        return logical_frame_hash(frame, list(record.get("sort_by") or []))
    if format_name == "json":
        return content_hash(json.loads(path.read_text(encoding="utf-8")))
    if format_name == "csv":
        return content_hash(path.read_text(encoding="utf-8"))
    if format_name == "yaml":
        return content_hash(path.read_text(encoding="utf-8"))
    if format_name == "zip":
        return sha256_file(path)
    raise ValueError(f"unsupported manifest artifact format: {format_name}")


def _validate_source_snapshot(run_dir: Path, manifest: dict[str, object], project_root: Path) -> None:
    archive_path = run_dir / str(manifest["source_snapshot"])
    expected = dict(manifest["code_file_hashes"])
    with zipfile.ZipFile(archive_path) as archive:
        actual = set(archive.namelist())
        if actual != set(expected):
            raise ValueError(f"source snapshot file set mismatch: missing={sorted(set(expected)-actual)}, extra={sorted(actual-set(expected))}")
        for name, expected_hash in expected.items():
            actual_hash = hashlib.sha256(archive.read(name)).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(f"source snapshot code hash mismatch: {name}")


def validate_run_directory(run_dir: Path, strict_current_checkout: bool = False) -> dict[str, object]:
    run_dir = run_dir.resolve()
    required = [run_dir / "config.yaml", run_dir / "metrics.json", run_dir / "manifest.json", run_dir / "artifacts"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise ValueError(f"run contract files missing: {missing}")
    config = load_config(run_dir / "config.yaml")
    if not run_dir.is_relative_to(config.output_root.resolve()):
        raise ValueError("run directory is outside configured generated-data root")
    yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if logical_manifest_hash(manifest) != manifest["manifest_logical_hash"]:
        raise ValueError("manifest logical hash mismatch")

    records = dict(manifest["output_artifact_hashes"])
    expected_files = set(records)
    actual_files = {"config.yaml", "metrics.json"}
    actual_files.update(path.relative_to(run_dir).as_posix() for path in (run_dir / "artifacts").rglob("*") if path.is_file())
    require_exact_artifact_set(expected_files, actual_files)

    parsed: list[str] = ["manifest.json"]
    for relative in sorted(expected_files):
        path = run_dir / relative
        record = records[relative]
        if not path.is_file():
            raise ValueError(f"manifest-declared artifact missing: {relative}")
        if path.stat().st_size != record["bytes"]:
            raise ValueError(f"artifact byte count mismatch: {relative}")
        if sha256_file(path) != record["sha256"]:
            raise ValueError(f"physical artifact hash mismatch: {relative}")
        format_name = record["format"]
        if format_name == "json":
            json.loads(path.read_text(encoding="utf-8"))
        elif format_name == "csv":
            frame = pd.read_csv(path)
            if record["rows"] is not None and len(frame) != record["rows"]:
                raise ValueError(f"CSV row count mismatch: {relative}")
        elif format_name == "parquet":
            table = pq.read_table(path)
            table.validate(full=True)
            if record["rows"] is not None and table.num_rows != record["rows"]:
                raise ValueError(f"Parquet row count mismatch: {relative}")
        elif format_name == "yaml":
            yaml.safe_load(path.read_text(encoding="utf-8"))
        elif format_name == "zip":
            with zipfile.ZipFile(path) as archive:
                bad = archive.testzip()
                if bad:
                    raise ValueError(f"corrupt source snapshot entry: {bad}")
        else:
            raise ValueError(f"unexpected artifact format: {format_name}")
        if _logical_hash(path, record) != record["logical_hash"]:
            raise ValueError(f"logical artifact hash mismatch: {relative}")
        parsed.append(relative)

    project_root = Path(__file__).resolve().parents[2]
    source_root = config.source_data_root.resolve()
    for relative, expected_hash in manifest["source_file_hashes"].items():
        if sha256_file(source_root / relative) != expected_hash:
            raise ValueError(f"source input hash mismatch: {relative}")
    _validate_source_snapshot(run_dir, manifest, project_root)

    if strict_current_checkout:
        for relative, expected_hash in manifest["code_file_hashes"].items():
            if sha256_file(project_root / relative) != expected_hash:
                raise ValueError(f"current code hash mismatch: {relative}")

    repo_root = Path(__file__).resolve().parents[4]
    commit = str(manifest["git_commit"])
    commit_check = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=repo_root, capture_output=True, check=False)
    if commit_check.returncode != 0:
        raise ValueError(f"recorded Git commit is not locally reconstructable: {commit}")
    if not manifest["git_state"]["implementation_files_tracked"]:
        raise ValueError("manifest says implementation files were not tracked at run time")

    panel = pd.read_parquet(run_dir / "artifacts" / "research_panel.parquet")
    if panel.duplicated(["session_date", "security_id"]).any():
        raise ValueError("duplicate panel semantic keys")
    if not panel["official_member_count"].eq(60).all() or not panel.groupby("session_date").size().eq(60).all():
        raise ValueError("official 60-member denominator is not preserved")
    expected_price = panel.groupby("session_date")["is_price_usable_member"].transform("sum").astype("int64")
    if not panel["price_usable_member_count"].equals(expected_price):
        raise ValueError("price/member denominator mismatch")
    for column in cross_sectional_feature_columns():
        expected_feature = panel.groupby("session_date")[feature_eligibility_column(column)].transform("sum").astype("int64")
        if not panel[feature_count_column(column)].equals(expected_feature):
            raise ValueError(f"feature-specific denominator mismatch: {feature_key(column)}")
    wig_key = feature_key(regime_feature_column())
    if any(column.startswith(f"rank__{wig_key}") or column.startswith(f"quantile__{wig_key}") for column in panel.columns):
        raise ValueError("WIG trend was incorrectly emitted as a cross-sectional rank/quantile")
    validate_feature_availability(panel)
    return {
        "passed": True, "parsed_files": len(parsed), "manifest_artifacts": len(expected_files),
        "panel_rows": len(panel), "sessions": int(panel["session_date"].nunique()),
        "git_commit_reconstructable": True, "source_snapshot_valid": True,
        "validation_mode": "strict_current_checkout" if strict_current_checkout else "archive_integrity",
    }
