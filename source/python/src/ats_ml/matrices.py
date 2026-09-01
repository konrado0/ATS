from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ats_ml.contracts import FrozenD0Contract
from ats_ml.guard import D1ExecutionGuard, ExecutionContext, Operation, synthetic_fixture_context
from ats_research.hashing import content_hash, logical_frame_hash


class MatrixContractError(ValueError):
    pass


_SEAL = object()


def _matrix_payload_hash(frame: pd.DataFrame, feature_names: tuple[str, ...]) -> str:
    validate_predictor_frame(frame, feature_names)
    return logical_frame_hash(frame.loc[:, list(feature_names)])


def _target_payload_hash(values: Any) -> str:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or not np.isfinite(array).all():
        raise MatrixContractError("synthetic target must be a finite one-dimensional array")
    return logical_frame_hash(pd.DataFrame({"target": array}))


@dataclass(frozen=True, init=False)
class ModelMatrix:
    _values: np.ndarray
    context: ExecutionContext
    feature_names: tuple[str, ...]
    provenance_hash: str
    data_hash: str
    fixture_id: str | None
    suite_id: str | None
    fixture_registry_sha256: str | None

    def __init__(
        self,
        frame: pd.DataFrame,
        context: ExecutionContext,
        feature_names: tuple[str, ...],
        provenance_hash: str,
        *,
        data_hash: str,
        fixture_id: str | None,
        suite_id: str | None,
        fixture_registry_sha256: str | None,
        _token: object,
    ):
        if _token is not _SEAL:
            raise MatrixContractError("model matrices must be created by a D1 sealed-matrix factory")
        validate_predictor_frame(frame, feature_names)
        values = frame.loc[:, list(feature_names)].to_numpy(dtype=float, copy=True)
        values.setflags(write=False)
        object.__setattr__(self, "_values", values)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "feature_names", feature_names)
        object.__setattr__(self, "provenance_hash", provenance_hash)
        object.__setattr__(self, "data_hash", data_hash)
        object.__setattr__(self, "fixture_id", fixture_id)
        object.__setattr__(self, "suite_id", suite_id)
        object.__setattr__(self, "fixture_registry_sha256", fixture_registry_sha256)

    @property
    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self._values.copy(), columns=self.feature_names)


@dataclass(frozen=True, init=False)
class ModelTarget:
    _values: np.ndarray
    context: ExecutionContext
    provenance_hash: str
    data_hash: str
    fixture_id: str
    suite_id: str
    fixture_registry_sha256: str

    def __init__(
        self,
        values: np.ndarray,
        context: ExecutionContext,
        provenance_hash: str,
        *,
        data_hash: str,
        fixture_id: str,
        suite_id: str,
        fixture_registry_sha256: str,
        _token: object,
    ):
        if _token is not _SEAL:
            raise MatrixContractError("model targets must be created by the D1 fixture loader")
        array = np.asarray(values, dtype=float).copy()
        array.setflags(write=False)
        object.__setattr__(self, "_values", array)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "provenance_hash", provenance_hash)
        object.__setattr__(self, "data_hash", data_hash)
        object.__setattr__(self, "fixture_id", fixture_id)
        object.__setattr__(self, "suite_id", suite_id)
        object.__setattr__(self, "fixture_registry_sha256", fixture_registry_sha256)

    @property
    def values(self) -> np.ndarray:
        return self._values.copy()


def validate_predictor_frame(frame: pd.DataFrame, expected: tuple[str, ...]) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise MatrixContractError("predictor input must be a pandas DataFrame")
    if isinstance(frame.columns, pd.MultiIndex) or not all(isinstance(value, str) for value in frame.columns):
        raise MatrixContractError("predictor names must be a flat string index")
    if frame.columns.has_duplicates:
        raise MatrixContractError("duplicate predictor names are forbidden")
    actual = tuple(frame.columns)
    if actual != expected:
        missing = [name for name in expected if name not in actual]
        extras = [name for name in actual if name not in expected]
        raise MatrixContractError(f"predictor allowlist mismatch; missing={missing}, extras={extras}, order_equal={set(actual) == set(expected)}")
    values = frame.to_numpy(dtype=float)
    if np.isinf(values).any():
        raise MatrixContractError("infinite predictor values are forbidden")


def feature_allowlist(contract: FrozenD0Contract, representation: str, p_survivors: tuple[str, ...] | None = None) -> tuple[str, ...]:
    if representation == "C":
        return contract.feature_blocks["C"]
    if representation != "C+P+X+M":
        raise MatrixContractError(f"unsupported frozen representation: {representation}")
    survivors = p_survivors or contract.feature_blocks["P"]
    if not set(survivors).issubset(contract.feature_blocks["P"]) or len(survivors) < 5:
        raise MatrixContractError("resolved P allowlist is invalid")
    return contract.feature_blocks["C"] + tuple(survivors) + contract.feature_blocks["X"] + contract.feature_blocks["M"]


def cell_feature_allowlists(contract: FrozenD0Contract, p_survivors: tuple[str, ...] | None = None) -> dict[str, tuple[str, ...]]:
    return {cell["cell_id"]: feature_allowlist(contract, cell["features"], p_survivors) for cell in contract.config["comparison"]["cells"]}


def _build_registered_recipe(entry: dict[str, object], feature_names: tuple[str, ...]) -> tuple[pd.DataFrame, np.ndarray | None]:
    rows = int(entry["rows"])
    seed = int(entry["seed"])
    rng = np.random.default_rng(seed)
    raw = rng.normal(size=(rows, len(feature_names)))
    frame = pd.DataFrame(raw.copy(), columns=feature_names)
    transform = str(entry["matrix_transform"])
    if transform == "linear_train":
        frame.iloc[0, 0] = np.nan
        target = np.nan_to_num(raw[:, 0]) * 0.7 - raw[:, 1] * 0.2
    elif transform == "linear_eval":
        frame.iloc[:, :] = 1e9
        target = None
    elif transform == "nonlinear_train":
        frame.iloc[::19, 2] = np.nan
        target = (raw[:, 0] > 0).astype(float) * (raw[:, 1] ** 2) - 0.1 * raw[:, 3]
    elif transform == "no_signal_train":
        target = np.zeros(rows, dtype=float)
    elif transform == "all_missing_train":
        frame.iloc[:, 2] = np.nan
        target = np.zeros(rows, dtype=float)
    else:
        raise MatrixContractError(f"unsupported frozen fixture recipe: {transform}")
    return frame, target


def load_authorized_model_fixture(
    fixture_id: str,
    feature_names: tuple[str, ...],
    contract: FrozenD0Contract,
    guard: D1ExecutionGuard,
) -> tuple[ModelMatrix, ModelTarget | None]:
    entry = guard.fixture_entry(fixture_id)
    if entry.get("kind") != "model":
        raise MatrixContractError("fixture is not authorized for model plumbing")
    if tuple(entry.get("feature_names", [])) != feature_names:
        raise MatrixContractError("fixture feature allowlist differs from the requested frozen allowlist")
    frame, target_values = _build_registered_recipe(entry, feature_names)
    matrix_hash = _matrix_payload_hash(frame, feature_names)
    if matrix_hash != entry.get("model_matrix_sha256"):
        raise MatrixContractError("registered fixture matrix hash mismatch")
    context = synthetic_fixture_context(contract, guard, fixture_id)
    suite_id = str(entry["suite_id"])
    provenance = content_hash({"fixture": fixture_id, "registry": guard.fixture_registry_sha256, "matrix": matrix_hash})
    matrix = ModelMatrix(
        frame, context, feature_names, provenance,
        data_hash=matrix_hash, fixture_id=fixture_id, suite_id=suite_id,
        fixture_registry_sha256=guard.fixture_registry_sha256, _token=_SEAL,
    )
    target = None
    if target_values is not None:
        target_hash = _target_payload_hash(target_values)
        if target_hash != entry.get("model_target_sha256"):
            raise MatrixContractError("registered fixture target hash mismatch")
        target = ModelTarget(
            target_values, context, provenance,
            data_hash=target_hash, fixture_id=fixture_id, suite_id=suite_id,
            fixture_registry_sha256=guard.fixture_registry_sha256, _token=_SEAL,
        )
    return matrix, target


def validate_authorized_model_matrix(matrix: ModelMatrix, guard: D1ExecutionGuard) -> dict[str, object]:
    if matrix.fixture_id is None or matrix.fixture_registry_sha256 != guard.fixture_registry_sha256:
        raise MatrixContractError("matrix is not bound to the current repository fixture registry")
    entry = guard.fixture_entry(matrix.fixture_id)
    if entry.get("kind") != "model" or entry.get("model_matrix_sha256") != matrix.data_hash:
        raise MatrixContractError("matrix content is not an authorized model fixture")
    if _matrix_payload_hash(matrix.frame, matrix.feature_names) != matrix.data_hash:
        raise MatrixContractError("sealed matrix content changed after authorization")
    return entry


def validate_authorized_model_target(target: ModelTarget, guard: D1ExecutionGuard) -> dict[str, object]:
    if target.fixture_registry_sha256 != guard.fixture_registry_sha256:
        raise MatrixContractError("target is not bound to the current repository fixture registry")
    entry = guard.fixture_entry(target.fixture_id)
    if entry.get("kind") != "model" or entry.get("model_target_sha256") != target.data_hash:
        raise MatrixContractError("target content is not an authorized model fixture")
    if _target_payload_hash(target.values) != target.data_hash:
        raise MatrixContractError("sealed target content changed after authorization")
    return entry


def build_four_cell_matrices(
    observations: pd.DataFrame,
    contract: FrozenD0Contract,
    context: ExecutionContext,
    guard: D1ExecutionGuard,
    *,
    p_survivors: tuple[str, ...] | None = None,
) -> dict[str, ModelMatrix]:
    guard.require(Operation.COMPUTE_FEATURE_FIXTURE, context)
    if "model_score_eligible" not in observations:
        raise MatrixContractError("common decision-time score mask is absent")
    eligible = observations.loc[observations["model_score_eligible"].fillna(False)].copy()
    if not {"decision_session", "security_id"}.issubset(eligible.columns):
        raise MatrixContractError("semantic row keys are absent")
    if eligible.duplicated(["decision_session", "security_id"]).any():
        raise MatrixContractError("duplicate semantic row keys are forbidden")
    canonical_predictors = [name for name in contract.registry_order if name in eligible.columns]
    eligible = eligible.sort_values(["decision_session", *canonical_predictors], kind="mergesort", na_position="last")
    key_hash = logical_frame_hash(eligible[["decision_session", *canonical_predictors]], ["decision_session", *canonical_predictors])
    result: dict[str, ModelMatrix] = {}
    for cell_id, names in cell_feature_allowlists(contract, p_survivors).items():
        frame = eligible.loc[:, list(names)].copy()
        data_hash = _matrix_payload_hash(frame, names)
        result[cell_id] = ModelMatrix(
            frame, context, names, key_hash,
            data_hash=data_hash, fixture_id=None, suite_id=None,
            fixture_registry_sha256=None, _token=_SEAL,
        )
    lengths = {len(matrix.frame) for matrix in result.values()}
    hashes = {matrix.provenance_hash for matrix in result.values()}
    if len(lengths) != 1 or len(hashes) != 1:
        raise MatrixContractError("the four cells do not share identical rows")
    return result
