from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path
from typing import Any

from ats_ml.contracts import REPOSITORY_ROOT, FrozenD0Contract, resolve_pinned_inputs
from ats_ml.contracts_v3 import load_frozen_d0_v3_contract
from ats_ml.d2_artifacts import D2ArtifactError
from ats_ml.models import LIGHTGBM_PARAMETERS, RIDGE_PARAMETERS
from ats_ml.structural_v3 import validate_structural_run_v3
from ats_research.hashing import content_hash, sha256_file


EXECUTION_CONFIG = REPOSITORY_ROOT / "source/python/configs/phase_d2_execution.json"
STRUCTURAL_RESOLUTION = REPOSITORY_ROOT / "source/python/configs/phase_d1_structural_resolution_v3.json"
IMPLEMENTATION_GLOBS = (
    "source/python/src/ats_ml/*.py",
    "source/python/tests/test_phase_d2*.py",
    "source/python/configs/phase_d2_execution.json",
    "RESEARCH/prototypes/phase_d2/*.py",
)


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D2ArtifactError(f"cannot read D2 control file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise D2ArtifactError(f"D2 control root is not an object: {path}")
    return value


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=REPOSITORY_ROOT, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def load_execution_config() -> dict[str, Any]:
    config = _json(EXECUTION_CONFIG)
    if config.get("schema_version") != "ats.phase_d2.execution.v1":
        raise D2ArtifactError("unexpected D2 execution schema")
    def strings(value: Any) -> list[str]:
        if isinstance(value, dict):
            return [item for child in value.values() for item in strings(child)]
        if isinstance(value, list):
            return [item for child in value for item in strings(child)]
        return [value.lower()] if isinstance(value, str) else []

    mutable = [value for value in strings(config) if value in {"latest", "current"} or "/latest/" in value or "\\latest\\" in value]
    if mutable:
        raise D2ArtifactError("D2 execution configuration contains a mutable discovery pointer")
    if config.get("publication") != {
        "machine_artifact_before_render": True,
        "mutable_latest_pointer": False,
        "overwrite_existing_run": False,
        "parquet_compression": "zstd",
        "parquet_dictionary_encoding": False,
    }:
        raise D2ArtifactError("D2 publication policy differs from the frozen execution policy")
    return config


def implementation_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in IMPLEMENTATION_GLOBS:
        files.update(path for path in REPOSITORY_ROOT.glob(pattern) if path.is_file())
    return sorted(files, key=lambda value: value.relative_to(REPOSITORY_ROOT).as_posix())


def implementation_identity() -> dict[str, Any]:
    files = implementation_files()
    packages = (
        "numpy", "pandas", "pyarrow", "scikit-learn", "lightgbm", "pytest",
    )
    return {
        "code_commit": _git("rev-parse", "HEAD"),
        "files": {
            path.relative_to(REPOSITORY_ROOT).as_posix(): sha256_file(path) for path in files
        },
        "environment_lock": {
            "path": "RESEARCH/environment/environment.yml",
            "sha256": sha256_file(REPOSITORY_ROOT / "RESEARCH/environment/environment.yml"),
        },
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in packages},
        "ridge_parameters": RIDGE_PARAMETERS,
        "lightgbm_parameters": LIGHTGBM_PARAMETERS,
    }


def validate_execution_authorization(*, require_clean: bool) -> tuple[FrozenD0Contract, dict[str, Any]]:
    execution = load_execution_config()
    contract = load_frozen_d0_v3_contract()
    scientific = execution["scientific_contract"]
    if scientific.get("contract_version") != contract.config.get("contract_version"):
        raise D2ArtifactError("D2 execution does not bind the composed D0 v3 contract")
    registry = REPOSITORY_ROOT / "source/python/configs/phase_d0_feature_registry.json"
    if sha256_file(registry) != scientific.get("feature_registry_sha256"):
        raise D2ArtifactError("D2 feature-registry binding failed")
    authorization = execution["authorization"]
    activation = str(authorization["activation_commit"])
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", activation, "HEAD"],
        cwd=REPOSITORY_ROOT,
    ).returncode != 0:
        raise D2ArtifactError("Phase D2 authorization commit is not an ancestor of HEAD")
    structural = _json(STRUCTURAL_RESOLUTION)
    if structural.get("run_id") != authorization.get("structural_run_id"):
        raise D2ArtifactError("D2 execution binds the wrong D1 structural run")
    if structural.get("logical_hash") != authorization.get("structural_logical_hash"):
        raise D2ArtifactError("D1 structural logical identity differs")
    structural_run = Path("D:/Stock/data/ATS/phase_d_ml/structural_runs") / structural["run_id"]
    structural_manifest = structural_run / "manifest.json"
    if sha256_file(structural_manifest) != authorization.get("structural_manifest_sha256"):
        raise D2ArtifactError("D1 structural manifest physical identity differs")
    validate_structural_run_v3(structural_run)
    paths = resolve_pinned_inputs(contract)
    if require_clean:
        changed = _git("status", "--porcelain", "--untracked-files=no")
        if changed:
            raise D2ArtifactError("tracked files must be clean at real Stage 1 execution")
    resolved = {
        role: {"path": str(path), "sha256": sha256_file(path)} for role, path in paths.items()
    }
    proof = {
        "schema_version": "ats.phase_d2.authorization_proof.v1",
        "status": "PASS",
        "execution_config_sha256": sha256_file(EXECUTION_CONFIG),
        "execution_config": execution,
        "contract_hashes": contract.hashes,
        "structural_resolution_sha256": sha256_file(STRUCTURAL_RESOLUTION),
        "structural_manifest_sha256": sha256_file(structural_manifest),
        "resolved_inputs": resolved,
        "implementation": implementation_identity(),
    }
    proof["proof_hash"] = content_hash(proof)
    return contract, proof
