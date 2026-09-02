from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import numpy as np

from ats_research.hashing import content_hash, logical_frame_hash, sha256_file


class D2ArtifactError(ValueError):
    pass


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(float(value)) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(
        json.dumps(json_ready(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
    )


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D2ArtifactError(f"cannot read JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise D2ArtifactError(f"JSON artifact root is not an object: {path}")
    return value


def write_parquet(path: Path, frame: pd.DataFrame) -> None:
    frame.to_parquet(path, index=False, compression="zstd", use_dictionary=False)


def frame_identity(frame: pd.DataFrame, *, sort_by: list[str] | None = None) -> dict[str, Any]:
    return {
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "logical_hash": logical_frame_hash(frame, sort_by=sort_by),
    }


def file_inventory(root: Path, *, exclude: tuple[str, ...] = ("manifest.json",)) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda value: value.as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative in exclude:
            continue
        inventory[relative] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    return inventory


def publish_immutable(
    root: Path,
    run_id: str,
    build: Callable[[Path], dict[str, Any]],
    *,
    schema_version: str,
    validate: Callable[[Path], dict[str, Any]],
) -> Path:
    if not run_id or any(token in run_id.lower() for token in ("latest", "current")):
        raise D2ArtifactError("D2 publication requires an explicit immutable run ID")
    root.mkdir(parents=True, exist_ok=True)
    destination = root / run_id
    if destination.exists():
        raise D2ArtifactError(f"immutable D2 run already exists: {destination}")
    stage = root / f".stage-{run_id}-{uuid.uuid4().hex}"
    stage.mkdir()
    try:
        logical_payload = build(stage)
        files = file_inventory(stage)
        manifest = {
            "schema_version": schema_version,
            "run_id": run_id,
            "logical_hash": content_hash(logical_payload),
            "logical_payload": logical_payload,
            "files": files,
            "mutable_latest_pointer": False,
        }
        write_json(stage / "manifest.json", manifest)
        validate(stage)
        os.replace(stage, destination)
    except Exception:
        if stage.exists():
            failed = root / stage.name.replace(".stage-", ".failed-", 1)
            os.replace(stage, failed)
        raise
    validate(destination)
    return destination


def validate_manifest(
    run_dir: Path,
    *,
    schema_version: str,
    required_files: set[str] | None = None,
) -> dict[str, Any]:
    manifest = read_json(run_dir / "manifest.json")
    if manifest.get("schema_version") != schema_version:
        raise D2ArtifactError(f"unexpected manifest schema in {run_dir}")
    if manifest.get("run_id") != run_dir.name and not run_dir.name.startswith(".stage-"):
        raise D2ArtifactError("run directory and manifest identity differ")
    if manifest.get("mutable_latest_pointer") is not False:
        raise D2ArtifactError("mutable discovery pointers are forbidden")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise D2ArtifactError("manifest file inventory is absent")
    actual = {path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_file()}
    expected = {"manifest.json", *files}
    if actual != expected:
        raise D2ArtifactError(f"artifact inventory mismatch: expected={sorted(expected)}, actual={sorted(actual)}")
    if required_files is not None and set(files) != required_files:
        raise D2ArtifactError(f"sealed file allowlist mismatch: {sorted(set(files) ^ required_files)}")
    for relative, record in files.items():
        path = run_dir / relative
        if path.stat().st_size != record.get("bytes") or sha256_file(path) != record.get("sha256"):
            raise D2ArtifactError(f"physical artifact hash mismatch: {relative}")
    logical_payload = manifest.get("logical_payload")
    if not isinstance(logical_payload, dict) or manifest.get("logical_hash") != content_hash(logical_payload):
        raise D2ArtifactError("manifest logical identity mismatch")
    return manifest
