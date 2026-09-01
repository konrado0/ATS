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
_SEMANTIC_ROW_SEAL = object()
SEMANTIC_ROW_FIELDS = ("candidate_run_id", "contract_version", "decision_session", "security_id")


def _normalize_semantic_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise MatrixContractError("semantic rows must be supplied as a pandas DataFrame")
    missing = [name for name in SEMANTIC_ROW_FIELDS if name not in frame.columns]
    if missing:
        raise MatrixContractError(f"semantic row keys are absent: {missing}")
    rows = frame.loc[:, list(SEMANTIC_ROW_FIELDS)].copy()
    if rows.isna().any().any():
        raise MatrixContractError("semantic row keys cannot be null")
    sessions = pd.to_datetime(rows["decision_session"], errors="coerce")
    if sessions.isna().any():
        raise MatrixContractError("semantic decision sessions are invalid")
    rows["decision_session"] = sessions.dt.normalize().dt.strftime("%Y-%m-%d")
    for name in ("candidate_run_id", "contract_version", "security_id"):
        rows[name] = rows[name].astype(str)
        if rows[name].str.strip().eq("").any():
            raise MatrixContractError(f"semantic row key cannot be blank: {name}")
    if rows.duplicated(list(SEMANTIC_ROW_FIELDS)).any():
        raise MatrixContractError("duplicate semantic row keys are forbidden")
    return rows.reset_index(drop=True)


@dataclass(frozen=True, init=False)
class SemanticRowLedger:
    """Immutable ordered binding between numerical rows and security-session meaning."""

    _records: tuple[tuple[str, str, str, str], ...]
    logical_hash: str

    def __init__(self, frame: pd.DataFrame, *, _token: object):
        if _token is not _SEMANTIC_ROW_SEAL:
            raise MatrixContractError("semantic row ledgers must be created by the sealed ledger factory")
        rows = _normalize_semantic_rows(frame)
        records = tuple(tuple(str(value) for value in row) for row in rows.itertuples(index=False, name=None))
        object.__setattr__(self, "_records", records)
        object.__setattr__(self, "logical_hash", logical_frame_hash(rows))

    def validate(self) -> None:
        if logical_frame_hash(self.frame) != self.logical_hash:
            raise MatrixContractError("semantic row ledger content changed after sealing")

    def __len__(self) -> int:
        return len(self._records)

    @property
    def frame(self) -> pd.DataFrame:
        return pd.DataFrame.from_records(self._records, columns=SEMANTIC_ROW_FIELDS)


def build_semantic_row_ledger(frame: pd.DataFrame) -> SemanticRowLedger:
    return SemanticRowLedger(frame, _token=_SEMANTIC_ROW_SEAL)


def require_same_semantic_rows(left: SemanticRowLedger, right: SemanticRowLedger) -> None:
    if not isinstance(left, SemanticRowLedger) or not isinstance(right, SemanticRowLedger):
        raise MatrixContractError("row alignment requires sealed semantic row ledgers")
    left.validate()
    right.validate()
    if left.logical_hash != right.logical_hash or left != right:
        raise MatrixContractError("matrix/target semantic row binding differs")


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
    row_ledger: SemanticRowLedger

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
        row_ledger: SemanticRowLedger,
        _token: object,
    ):
        if _token is not _SEAL:
            raise MatrixContractError("model matrices must be created by a D1 sealed-matrix factory")
        validate_predictor_frame(frame, feature_names)
        if not isinstance(row_ledger, SemanticRowLedger):
            raise MatrixContractError("model matrix requires a sealed semantic row ledger")
        row_ledger.validate()
        if len(frame) != len(row_ledger):
            raise MatrixContractError("model matrix and semantic row ledger lengths differ")
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
        object.__setattr__(self, "row_ledger", row_ledger)

    @property
    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self._values.copy(), columns=self.feature_names)

    @property
    def semantic_row_hash(self) -> str:
        return self.row_ledger.logical_hash

    @property
    def semantic_rows(self) -> pd.DataFrame:
        return self.row_ledger.frame

    @property
    def bound_frame(self) -> pd.DataFrame:
        return pd.concat([self.semantic_rows, self.frame], axis=1)


@dataclass(frozen=True, init=False)
class ModelTarget:
    _values: np.ndarray
    context: ExecutionContext
    provenance_hash: str
    data_hash: str
    fixture_id: str
    suite_id: str
    fixture_registry_sha256: str
    row_ledger: SemanticRowLedger

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
        row_ledger: SemanticRowLedger,
        _token: object,
    ):
        if _token is not _SEAL:
            raise MatrixContractError("model targets must be created by the D1 fixture loader")
        if not isinstance(row_ledger, SemanticRowLedger):
            raise MatrixContractError("model target requires a sealed semantic row ledger")
        row_ledger.validate()
        array = np.asarray(values, dtype=float).copy()
        if array.ndim != 1 or len(array) != len(row_ledger) or not np.isfinite(array).all():
            raise MatrixContractError("model target and semantic row ledger are not aligned finite vectors")
        array.setflags(write=False)
        object.__setattr__(self, "_values", array)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "provenance_hash", provenance_hash)
        object.__setattr__(self, "data_hash", data_hash)
        object.__setattr__(self, "fixture_id", fixture_id)
        object.__setattr__(self, "suite_id", suite_id)
        object.__setattr__(self, "fixture_registry_sha256", fixture_registry_sha256)
        object.__setattr__(self, "row_ledger", row_ledger)

    @property
    def values(self) -> np.ndarray:
        return self._values.copy()

    @property
    def semantic_row_hash(self) -> str:
        return self.row_ledger.logical_hash

    @property
    def semantic_rows(self) -> pd.DataFrame:
        return self.row_ledger.frame

    @property
    def bound_frame(self) -> pd.DataFrame:
        frame = self.semantic_rows
        frame["target"] = self.values
        return frame


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


def _registered_fixture_semantic_rows(fixture_id: str, rows: int, contract_version: str) -> pd.DataFrame:
    row_number = np.arange(rows, dtype=int)
    session_number = row_number // 60
    sessions = pd.Timestamp("2000-01-03") + pd.to_timedelta(session_number * 7, unit="D")
    return pd.DataFrame({
        "candidate_run_id": fixture_id,
        "contract_version": contract_version,
        "decision_session": sessions,
        "security_id": [f"SYNTHETIC-{value % 60:03d}" for value in row_number],
    })


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
    row_ledger = build_semantic_row_ledger(
        _registered_fixture_semantic_rows(fixture_id, len(frame), contract.config["contract_version"])
    )
    matrix_hash = _matrix_payload_hash(frame, feature_names)
    if matrix_hash != entry.get("model_matrix_sha256"):
        raise MatrixContractError("registered fixture matrix hash mismatch")
    if row_ledger.logical_hash != entry.get("semantic_row_sha256"):
        raise MatrixContractError("registered fixture semantic-row hash mismatch")
    context = synthetic_fixture_context(contract, guard, fixture_id)
    suite_id = str(entry["suite_id"])
    provenance = content_hash({
        "fixture": fixture_id,
        "registry": guard.fixture_registry_sha256,
        "matrix": matrix_hash,
        "semantic_rows": row_ledger.logical_hash,
    })
    matrix = ModelMatrix(
        frame, context, feature_names, provenance,
        data_hash=matrix_hash, fixture_id=fixture_id, suite_id=suite_id,
        fixture_registry_sha256=guard.fixture_registry_sha256, row_ledger=row_ledger, _token=_SEAL,
    )
    target = None
    if target_values is not None:
        target_hash = _target_payload_hash(target_values)
        if target_hash != entry.get("model_target_sha256"):
            raise MatrixContractError("registered fixture target hash mismatch")
        target = ModelTarget(
            target_values, context, provenance,
            data_hash=target_hash, fixture_id=fixture_id, suite_id=suite_id,
            fixture_registry_sha256=guard.fixture_registry_sha256, row_ledger=row_ledger, _token=_SEAL,
        )
    return matrix, target


def validate_authorized_model_matrix(matrix: ModelMatrix, guard: D1ExecutionGuard) -> dict[str, object]:
    if matrix.fixture_id is None or matrix.fixture_registry_sha256 != guard.fixture_registry_sha256:
        raise MatrixContractError("matrix is not bound to the current repository fixture registry")
    entry = guard.fixture_entry(matrix.fixture_id)
    if entry.get("kind") != "model" or entry.get("model_matrix_sha256") != matrix.data_hash:
        raise MatrixContractError("matrix content is not an authorized model fixture")
    matrix.row_ledger.validate()
    if entry.get("semantic_row_sha256") != matrix.semantic_row_hash:
        raise MatrixContractError("matrix semantic row binding is not the authorized fixture ledger")
    if _matrix_payload_hash(matrix.frame, matrix.feature_names) != matrix.data_hash:
        raise MatrixContractError("sealed matrix content changed after authorization")
    return entry


def validate_authorized_model_target(target: ModelTarget, guard: D1ExecutionGuard) -> dict[str, object]:
    if target.fixture_registry_sha256 != guard.fixture_registry_sha256:
        raise MatrixContractError("target is not bound to the current repository fixture registry")
    entry = guard.fixture_entry(target.fixture_id)
    if entry.get("kind") != "model" or entry.get("model_target_sha256") != target.data_hash:
        raise MatrixContractError("target content is not an authorized model fixture")
    target.row_ledger.validate()
    if entry.get("semantic_row_sha256") != target.semantic_row_hash:
        raise MatrixContractError("target semantic row binding is not the authorized fixture ledger")
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
    if not set(SEMANTIC_ROW_FIELDS).issubset(eligible.columns):
        raise MatrixContractError("semantic row keys are absent")
    if eligible.duplicated(list(SEMANTIC_ROW_FIELDS)).any():
        raise MatrixContractError("duplicate semantic row keys are forbidden")
    canonical_predictors = [name for name in contract.registry_order if name in eligible.columns]
    eligible = eligible.sort_values(
        ["decision_session", *canonical_predictors, "security_id", "candidate_run_id", "contract_version"],
        kind="mergesort",
        na_position="last",
    ).reset_index(drop=True)
    row_ledger = build_semantic_row_ledger(eligible)
    provenance = content_hash({"semantic_rows": row_ledger.logical_hash, "row_count": len(row_ledger)})
    result: dict[str, ModelMatrix] = {}
    for cell_id, names in cell_feature_allowlists(contract, p_survivors).items():
        frame = eligible.loc[:, list(names)].copy()
        data_hash = _matrix_payload_hash(frame, names)
        result[cell_id] = ModelMatrix(
            frame, context, names, provenance,
            data_hash=data_hash, fixture_id=None, suite_id=None,
            fixture_registry_sha256=None, row_ledger=row_ledger, _token=_SEAL,
        )
    lengths = {len(matrix.frame) for matrix in result.values()}
    hashes = {matrix.provenance_hash for matrix in result.values()}
    row_hashes = {matrix.semantic_row_hash for matrix in result.values()}
    if len(lengths) != 1 or len(hashes) != 1 or len(row_hashes) != 1:
        raise MatrixContractError("the four cells do not share identical rows")
    return result
