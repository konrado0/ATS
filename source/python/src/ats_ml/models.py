from __future__ import annotations

from dataclasses import dataclass
import hashlib
import pickle
from typing import Any

import lightgbm as lgb
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ats_ml.guard import D1ExecutionGuard, Operation
from ats_ml.matrices import (
    MatrixContractError,
    ModelMatrix,
    ModelTarget,
    validate_authorized_model_matrix,
    validate_authorized_model_target,
    validate_predictor_frame,
)
from ats_research.hashing import content_hash


RIDGE_PARAMETERS: dict[str, Any] = {
    "alpha": 1.0,
    "fit_intercept": True,
    "solver": "lsqr",
    "tol": 1e-6,
    "max_iter": 10000,
}
LIGHTGBM_PARAMETERS: dict[str, Any] = {
    "boosting_type": "gbdt",
    "objective": "regression_l2",
    "n_estimators": 300,
    "learning_rate": 0.03,
    "num_leaves": 15,
    "max_depth": 4,
    "min_child_samples": 100,
    "subsample": 1.0,
    "colsample_bytree": 1.0,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 20260831,
    "n_jobs": 1,
    "deterministic": True,
    "force_col_wise": True,
    "verbosity": -1,
}
_MODEL_SCORE_SEAL = object()
_FIT_STATE_SEAL = object()


def _estimator_hash(estimator: Any) -> str:
    return hashlib.sha256(pickle.dumps(estimator, protocol=5)).hexdigest()


@dataclass(frozen=True, init=False)
class _FittedState:
    adapter_class: str
    estimator_id: int
    estimator_hash: str
    feature_names: tuple[str, ...]
    fixture_suite: str
    fit_provenance_hash: str

    def __init__(self, adapter: "_BaseAdapter", matrix: ModelMatrix, *, _token: object):
        if _token is not _FIT_STATE_SEAL or adapter.estimator is None or matrix.suite_id is None:
            raise MatrixContractError("fit state must be minted after an authorized adapter fit")
        object.__setattr__(self, "adapter_class", adapter.__class__.__name__)
        object.__setattr__(self, "estimator_id", id(adapter.estimator))
        object.__setattr__(self, "estimator_hash", _estimator_hash(adapter.estimator))
        object.__setattr__(self, "feature_names", matrix.feature_names)
        object.__setattr__(self, "fixture_suite", matrix.suite_id)
        object.__setattr__(self, "fit_provenance_hash", matrix.provenance_hash)


@dataclass(frozen=True, init=False)
class ModelScores:
    _values: np.ndarray
    context: Any
    fixture_id: str
    suite_id: str
    model_class: str
    provenance_hash: str

    def __init__(self, values: np.ndarray, matrix: ModelMatrix, model_class: str, fit_provenance_hash: str, *, _token: object):
        if _token is not _MODEL_SCORE_SEAL or matrix.fixture_id is None or matrix.suite_id is None:
            raise MatrixContractError("model scores must be emitted by a fitted authorized D1 adapter")
        array = np.asarray(values, dtype=float)
        if array.ndim != 1 or len(array) != len(matrix.frame) or not np.isfinite(array).all():
            raise MatrixContractError("adapter score output is not a finite row-aligned vector")
        array = array.copy()
        array.setflags(write=False)
        object.__setattr__(self, "_values", array)
        object.__setattr__(self, "context", matrix.context)
        object.__setattr__(self, "fixture_id", matrix.fixture_id)
        object.__setattr__(self, "suite_id", matrix.suite_id)
        object.__setattr__(self, "model_class", model_class)
        object.__setattr__(self, "provenance_hash", content_hash({"fit": fit_provenance_hash, "matrix": matrix.data_hash, "model": model_class}))

    @property
    def values(self) -> np.ndarray:
        return self._values.copy()


class _BaseAdapter:
    def __init__(self, guard: D1ExecutionGuard):
        self.guard = guard
        self.estimator: Any = None
        self._fit_state: _FittedState | None = None

    def _validate_fit(self, matrix: ModelMatrix, target: ModelTarget) -> None:
        if not isinstance(matrix, ModelMatrix) or not isinstance(target, ModelTarget):
            raise MatrixContractError("fit accepts only sealed Phase D1 fixture objects")
        self.guard.require(Operation.FIT, matrix.context)
        self.guard.require(Operation.FIT, target.context)
        matrix_entry = validate_authorized_model_matrix(matrix, self.guard)
        target_entry = validate_authorized_model_target(target, self.guard)
        if matrix_entry != target_entry or matrix.context != target.context or len(matrix.frame) != len(target.values):
            raise MatrixContractError("matrix/target provenance or row count differs")
        if matrix.fixture_id != target.fixture_id or matrix.suite_id != target.suite_id:
            raise MatrixContractError("matrix and target are not the same authorized fixture")
        validate_predictor_frame(matrix.frame, matrix.feature_names)
        finite_by_column = np.isfinite(matrix.frame.to_numpy(dtype=float)).any(axis=0)
        if not finite_by_column.all():
            missing = [name for name, valid in zip(matrix.feature_names, finite_by_column, strict=True) if not valid]
            raise MatrixContractError(f"registered fit feature has no finite value: {missing}")

    def _validate_predict(self, matrix: ModelMatrix) -> None:
        if not isinstance(matrix, ModelMatrix):
            raise MatrixContractError("predict accepts only a sealed Phase D1 fixture matrix")
        self.guard.require(Operation.PREDICT, matrix.context)
        entry = validate_authorized_model_matrix(matrix, self.guard)
        state = self._fit_state
        if state is None or state.adapter_class != self.__class__.__name__:
            raise MatrixContractError("adapter has no sealed authorized fit state")
        if self.estimator is None or id(self.estimator) != state.estimator_id or _estimator_hash(self.estimator) != state.estimator_hash:
            raise MatrixContractError("fitted estimator was replaced or mutated after authorization")
        if matrix.feature_names != state.feature_names:
            raise MatrixContractError("prediction feature allowlist differs from fit")
        if entry.get("suite_id") != state.fixture_suite:
            raise MatrixContractError("prediction fixture suite differs from fit")
        validate_predictor_frame(matrix.frame, state.feature_names)

    def predict(self, matrix: ModelMatrix) -> ModelScores:
        self._validate_predict(matrix)
        assert self._fit_state is not None
        values = np.asarray(self.estimator.predict(matrix.frame), dtype=float)
        return ModelScores(values, matrix, self.__class__.__name__, self._fit_state.fit_provenance_hash, _token=_MODEL_SCORE_SEAL)


class RidgeAdapter(_BaseAdapter):
    def fit(self, matrix: ModelMatrix, target: ModelTarget) -> "RidgeAdapter":
        self._validate_fit(matrix, target)
        self.estimator = Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=False, keep_empty_features=False)),
            ("scaler", StandardScaler(with_mean=True, with_std=True)),
            ("ridge", Ridge(**RIDGE_PARAMETERS)),
        ])
        self.estimator.fit(matrix.frame, target.values)
        self._fit_state = _FittedState(self, matrix, _token=_FIT_STATE_SEAL)
        return self


class LightGBMAdapter(_BaseAdapter):
    def fit(self, matrix: ModelMatrix, target: ModelTarget) -> "LightGBMAdapter":
        self._validate_fit(matrix, target)
        self.estimator = lgb.LGBMRegressor(**LIGHTGBM_PARAMETERS)
        self.estimator.fit(matrix.frame, target.values)
        self._fit_state = _FittedState(self, matrix, _token=_FIT_STATE_SEAL)
        return self
