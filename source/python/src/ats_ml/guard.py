from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from typing import Mapping

from ats_ml.contracts import REPOSITORY_ROOT, FrozenD0Contract
from ats_research.hashing import sha256_file


class AuthorizationError(PermissionError):
    pass


class ExecutionClass(str, Enum):
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    REAL_STRUCTURAL = "real_structural"
    REAL_PREDICTIVE = "real_predictive"


class Operation(str, Enum):
    READ_SCHEMA = "read_schema"
    COMPUTE_FEATURE_FIXTURE = "compute_feature_fixture"
    COMPUTE_P_STRUCTURAL = "compute_p_structural"
    BUILD_LABEL_VALUES = "build_label_values"
    RESOLVE_PURGE = "resolve_purge"
    RESOLVE_CONCENTRATION_BINS = "resolve_concentration_bins"
    RESOLVE_FINGERPRINTS = "resolve_fingerprints"
    FIT = "fit"
    PREDICT = "predict"


_CONTEXT_SEAL = object()
FIXTURE_REGISTRY = REPOSITORY_ROOT / "source/python/configs/phase_d1_fixture_registry.json"
FIXTURE_REGISTRY_V3 = REPOSITORY_ROOT / "source/python/configs/phase_d1_fixture_registry_v3.json"


@dataclass(frozen=True, init=False)
class DatasetIdentity:
    manifest_sha256: str
    physical_sha256: str
    logical_hash: str
    run_id: str
    data_basis_version: str

    def __init__(self, manifest_sha256: str, physical_sha256: str, logical_hash: str, run_id: str, data_basis_version: str, *, _token: object):
        if _token is not _CONTEXT_SEAL:
            raise AuthorizationError("dataset identities must be minted by a D1 context factory")
        object.__setattr__(self, "manifest_sha256", manifest_sha256)
        object.__setattr__(self, "physical_sha256", physical_sha256)
        object.__setattr__(self, "logical_hash", logical_hash)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "data_basis_version", data_basis_version)


@dataclass(frozen=True, init=False)
class ExecutionContext:
    classification: ExecutionClass
    identity: DatasetIdentity
    fixture_id: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __init__(self, classification: ExecutionClass, identity: DatasetIdentity, fixture_id: str | None = None, metadata: Mapping[str, str] | None = None, *, _token: object):
        if _token is not _CONTEXT_SEAL:
            raise AuthorizationError("execution contexts must be minted by a D1 context factory")
        object.__setattr__(self, "classification", classification)
        object.__setattr__(self, "identity", identity)
        object.__setattr__(self, "fixture_id", fixture_id)
        object.__setattr__(self, "metadata", dict(metadata or {}))


class D1ExecutionGuard:
    """Authorization is identity-bound; paths and descriptive metadata are inert."""

    _SYNTHETIC_ALLOWED = {
        Operation.READ_SCHEMA,
        Operation.COMPUTE_FEATURE_FIXTURE,
        Operation.BUILD_LABEL_VALUES,
        Operation.RESOLVE_PURGE,
        Operation.RESOLVE_CONCENTRATION_BINS,
        Operation.RESOLVE_FINGERPRINTS,
        Operation.FIT,
        Operation.PREDICT,
    }
    _STRUCTURAL_ALLOWED = {
        Operation.READ_SCHEMA,
        Operation.COMPUTE_P_STRUCTURAL,
        Operation.RESOLVE_PURGE,
        Operation.RESOLVE_CONCENTRATION_BINS,
        Operation.RESOLVE_FINGERPRINTS,
    }

    def __init__(self, contract: FrozenD0Contract, fixture_registry: Path = FIXTURE_REGISTRY):
        self._pinned = contract.pinned_identity
        self._fixture_registry_path = fixture_registry
        try:
            registry = json.loads(fixture_registry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AuthorizationError(f"cannot load the D1 fixture registry: {exc}") from exc
        if registry.get("schema_version") not in {"ats.phase_d1.fixture_registry.v2", "ats.phase_d1.fixture_registry.v3"}:
            raise AuthorizationError("unexpected D1 fixture-registry schema")
        self._fixture_registry = registry
        self._fixture_registry_sha256 = sha256_file(fixture_registry)

    def matches_any_pinned_real_marker(self, identity: DatasetIdentity) -> bool:
        comparisons = (
            identity.manifest_sha256 == self._pinned["candidate_manifest_sha256"],
            identity.physical_sha256 == self._pinned["candidate_panel_sha256"],
            identity.logical_hash == self._pinned["candidate_logical_hash"],
            identity.run_id == self._pinned["candidate_run_id"],
            identity.data_basis_version == self._pinned["candidate_data_basis_version"],
        )
        return any(comparisons)

    def matches_exact_pinned_real_identity(self, identity: DatasetIdentity) -> bool:
        comparisons = (
            identity.manifest_sha256 == self._pinned["candidate_manifest_sha256"],
            identity.physical_sha256 == self._pinned["candidate_panel_sha256"],
            identity.logical_hash == self._pinned["candidate_logical_hash"],
            identity.run_id == self._pinned["candidate_run_id"],
            identity.data_basis_version == self._pinned["candidate_data_basis_version"],
        )
        return all(comparisons)

    @property
    def fixture_registry_sha256(self) -> str:
        return self._fixture_registry_sha256

    @property
    def fixture_registry_path(self) -> Path:
        return self._fixture_registry_path

    def fixture_entry(self, fixture_id: str) -> dict[str, object]:
        entry = self._fixture_registry.get("fixtures", {}).get(fixture_id)
        if not isinstance(entry, dict):
            raise AuthorizationError(f"fixture is not registered: {fixture_id}")
        return entry

    def require_fixture_payload(self, context: ExecutionContext, role: str, payload_sha256: str) -> None:
        self.require(Operation.COMPUTE_FEATURE_FIXTURE if role.startswith("model_") else Operation.BUILD_LABEL_VALUES, context)
        entry = self.fixture_entry(str(context.fixture_id))
        expected = entry.get(f"{role}_sha256")
        if expected != payload_sha256:
            raise AuthorizationError(f"fixture payload is not authorized for role {role}")

    def require(self, operation: Operation, context: ExecutionContext) -> None:
        any_real_marker = self.matches_any_pinned_real_marker(context.identity)
        if context.classification is ExecutionClass.REAL_PREDICTIVE:
            raise AuthorizationError("real_predictive execution is disabled throughout Phase D1")
        if context.classification is ExecutionClass.SYNTHETIC_FIXTURE:
            if any_real_marker:
                raise AuthorizationError("a pinned real dataset identity cannot be relabeled synthetic")
            if not context.fixture_id or context.fixture_id not in self._fixture_registry.get("fixtures", {}):
                raise AuthorizationError("synthetic execution requires a registered repository fixture identity")
            if operation not in self._SYNTHETIC_ALLOWED:
                raise AuthorizationError(f"operation {operation.value} is not authorized for synthetic fixtures")
            return
        if context.classification is ExecutionClass.REAL_STRUCTURAL:
            if not self.matches_exact_pinned_real_identity(context.identity):
                raise AuthorizationError("real_structural execution requires the pinned candidate identity")
            if operation not in self._STRUCTURAL_ALLOWED:
                raise AuthorizationError(f"operation {operation.value} is predictive or otherwise forbidden in D1")
            return
        raise AuthorizationError(f"unsupported execution classification: {context.classification}")


def pinned_real_context(contract: FrozenD0Contract) -> ExecutionContext:
    pinned = contract.pinned_identity
    return ExecutionContext(
        classification=ExecutionClass.REAL_STRUCTURAL,
        identity=DatasetIdentity(
            manifest_sha256=pinned["candidate_manifest_sha256"],
            physical_sha256=pinned["candidate_panel_sha256"],
            logical_hash=pinned["candidate_logical_hash"],
            run_id=pinned["candidate_run_id"],
            data_basis_version=pinned["candidate_data_basis_version"],
            _token=_CONTEXT_SEAL,
        ),
        metadata={"factor_version": "ats.gpw.split_adjustment.v1"},
        _token=_CONTEXT_SEAL,
    )


def pinned_real_predictive_context(contract: FrozenD0Contract) -> ExecutionContext:
    structural = pinned_real_context(contract)
    return ExecutionContext(
        ExecutionClass.REAL_PREDICTIVE,
        structural.identity,
        metadata={"authorization": "disabled"},
        _token=_CONTEXT_SEAL,
    )


def synthetic_fixture_context(contract: FrozenD0Contract, guard: D1ExecutionGuard, fixture_id: str) -> ExecutionContext:
    entry = guard.fixture_entry(fixture_id)
    logical_hash = str(entry.get("fixture_logical_hash", ""))
    if len(logical_hash) != 64:
        raise AuthorizationError(f"fixture logical hash is not pinned: {fixture_id}")
    identity = DatasetIdentity(
        manifest_sha256=guard.fixture_registry_sha256,
        physical_sha256=logical_hash,
        logical_hash=logical_hash,
        run_id=fixture_id,
        data_basis_version="synthetic.phase_d1.v1",
        _token=_CONTEXT_SEAL,
    )
    return ExecutionContext(
        ExecutionClass.SYNTHETIC_FIXTURE,
        identity,
        fixture_id,
        {"factor_version": "fixture-v1", "fixture_suite": str(entry.get("suite_id", fixture_id))},
        _token=_CONTEXT_SEAL,
    )
