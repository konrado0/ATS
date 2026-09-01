from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ats_research.hashing import sha256_file


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
D0_CONFIG = REPOSITORY_ROOT / "source/python/configs/phase_d0_reference.json"
D0_REGISTRY = REPOSITORY_ROOT / "source/python/configs/phase_d0_feature_registry.json"
D0_MANIFEST = REPOSITORY_ROOT / "RESEARCH/PHASE_D0_MANIFEST.json"
EXPECTED_CONTRACT_VERSION = "phase-d0-20260831-v2"
EXPECTED_D0_HASHES = {
    "RESEARCH/PHASE_D0_EXPERIMENT_PLAN.md": "10645dd41f1aea1f74c9f137a2f0dfd34e0a0f41f6355854c0cf9ed4b9ba0baa",
    "source/python/configs/phase_d0_reference.json": "ef5a7f0fa76a104ff86cae7c2ad520867a0720e1c6e508558ef31316e7e153ae",
    "source/python/configs/phase_d0_feature_registry.json": "733bacb9c1132d98eacb4a190cfb3cd96b0163207af46f3745002206b3705ef6",
    "RESEARCH/PHASE_D0_MANIFEST.json": "7fe34d679511eb4d75b269f5a908c6ac5e624d624aa067645286576f0f9e918c",
}


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class FrozenD0Contract:
    config: dict[str, Any]
    registry: dict[str, Any]
    manifest: dict[str, Any]
    hashes: dict[str, str]

    @property
    def feature_blocks(self) -> dict[str, tuple[str, ...]]:
        return {key: tuple(value) for key, value in self.config["feature_blocks"].items()}

    @property
    def registry_order(self) -> tuple[str, ...]:
        return tuple(item["canonical_name"] for item in self.registry["features"])

    @property
    def feature_specs(self) -> dict[str, dict[str, Any]]:
        return {item["canonical_name"]: item for item in self.registry["features"]}

    @property
    def pinned_identity(self) -> dict[str, str]:
        inputs = self.config["input"]
        return {
            "candidate_run_id": inputs["candidate_run_id"],
            "candidate_manifest_sha256": inputs["candidate_manifest_sha256"],
            "candidate_panel_sha256": inputs["candidate_panel_sha256"],
            "candidate_logical_hash": inputs["candidate_logical_hash"],
            "candidate_data_basis_version": inputs["candidate_data_basis_version"],
        }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read frozen contract JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"frozen contract root must be an object: {path}")
    return value


def load_frozen_d0_contract() -> FrozenD0Contract:
    config = _read_json(D0_CONFIG)
    registry = _read_json(D0_REGISTRY)
    manifest = _read_json(D0_MANIFEST)
    versions = {
        config.get("contract_version"),
        registry.get("contract_version"),
        manifest.get("contract_version"),
    }
    if versions != {EXPECTED_CONTRACT_VERSION}:
        raise ContractError(f"D0 contract version mismatch: {sorted(str(v) for v in versions)}")
    if config.get("schema_version") != "ats.phase_d0.reference.v1":
        raise ContractError("unexpected D0 reference schema")
    if registry.get("schema_version") != "ats.phase_d0.feature_registry.v1":
        raise ContractError("unexpected D0 feature-registry schema")
    names = [item.get("canonical_name") for item in registry.get("features", [])]
    if len(names) != 30 or len(set(names)) != 30:
        raise ContractError("the frozen registry must contain 30 unique predictors")
    flattened = [name for block in ("C", "P", "X", "M") for name in config["feature_blocks"][block]]
    if names != flattened:
        raise ContractError("registry order and frozen C/P/X/M blocks differ")
    actual_hashes = {
        "RESEARCH/PHASE_D0_EXPERIMENT_PLAN.md": sha256_file(REPOSITORY_ROOT / "RESEARCH/PHASE_D0_EXPERIMENT_PLAN.md"),
        "source/python/configs/phase_d0_reference.json": sha256_file(D0_CONFIG),
        "source/python/configs/phase_d0_feature_registry.json": sha256_file(D0_REGISTRY),
        "RESEARCH/PHASE_D0_MANIFEST.json": sha256_file(D0_MANIFEST),
    }
    if actual_hashes != EXPECTED_D0_HASHES:
        changed = sorted(path for path, digest in actual_hashes.items() if EXPECTED_D0_HASHES.get(path) != digest)
        raise ContractError(f"accepted D0 v2 bytes changed outside a versioned amendment: {changed}")
    declared = {item["path"]: item["sha256"] for item in manifest.get("artifacts", [])}
    for path in ("RESEARCH/PHASE_D0_EXPERIMENT_PLAN.md", "source/python/configs/phase_d0_reference.json", "source/python/configs/phase_d0_feature_registry.json"):
        if declared.get(path) != actual_hashes[path]:
            raise ContractError(f"frozen D0 artifact hash mismatch: {path}")
    if "latest" in json.dumps(config, sort_keys=True).lower():
        raise ContractError("mutable latest pointers are forbidden")
    return FrozenD0Contract(config=config, registry=registry, manifest=manifest, hashes=actual_hashes)


def resolve_pinned_inputs(contract: FrozenD0Contract) -> dict[str, Path]:
    inputs = contract.config["input"]
    resolved = {
        "candidate_manifest": Path(inputs["candidate_manifest"]),
        "candidate_panel": Path(inputs["candidate_panel"]),
        "market_state_manifest": Path(inputs["market_state_manifest"]),
        "market_state_feature_artifact": Path(inputs["market_state_feature_artifact"]),
    }
    for role, path in resolved.items():
        if "latest" in path.as_posix().lower() or not path.is_file():
            raise ContractError(f"missing or mutable pinned input for {role}: {path}")
    expected = {
        "candidate_manifest": inputs["candidate_manifest_sha256"],
        "candidate_panel": inputs["candidate_panel_sha256"],
        "market_state_manifest": inputs["market_state_manifest_sha256"],
        "market_state_feature_artifact": inputs["market_state_feature_artifact_sha256"],
    }
    for role, path in resolved.items():
        if sha256_file(path) != expected[role]:
            raise ContractError(f"pinned input hash mismatch for {role}")
    candidate_manifest = _read_json(resolved["candidate_manifest"])
    pinned = contract.pinned_identity
    if candidate_manifest.get("run_id") != pinned["candidate_run_id"]:
        raise ContractError("candidate run identity mismatch")
    if candidate_manifest.get("schema_version") != "ats.gpw_split_candidate_manifest.v1":
        raise ContractError("candidate manifest schema mismatch")
    if candidate_manifest.get("data_basis_version") != pinned["candidate_data_basis_version"]:
        raise ContractError("candidate data-basis mismatch")
    if candidate_manifest.get("adjusted_logical_hash") != pinned["candidate_logical_hash"]:
        raise ContractError("candidate logical hash mismatch")
    if candidate_manifest.get("physical_file_hashes", {}).get("candidate_panel.parquet") != pinned["candidate_panel_sha256"]:
        raise ContractError("candidate manifest does not bind the pinned panel bytes")
    return resolved
