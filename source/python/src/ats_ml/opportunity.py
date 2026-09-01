from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from ats_ml.guard import D1ExecutionGuard
from ats_ml.models import ModelScores, validate_model_scores
from ats_research.hashing import content_hash


ABSOLUTE_HURDLE = 0.01
CALIBRATION_QUANTILE = 0.9
_THRESHOLD_SEAL = object()


@dataclass(frozen=True, init=False)
class CalibrationThreshold:
    value: float
    suite_id: str
    calibration_provenance_hash: str

    def __init__(self, value: float, suite_id: str, provenance_hash: str, *, _token: object):
        if _token is not _THRESHOLD_SEAL:
            raise ValueError("calibration thresholds must be produced by the frozen D1 rule")
        object.__setattr__(self, "value", float(value))
        object.__setattr__(self, "suite_id", suite_id)
        object.__setattr__(self, "calibration_provenance_hash", provenance_hash)


def calibration_threshold(scores: ModelScores, guard: D1ExecutionGuard) -> CalibrationThreshold:
    if not isinstance(scores, ModelScores):
        raise ValueError("calibration requires provenance-bearing synthetic model scores")
    validate_model_scores(scores, guard)
    values = scores.values
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        raise ValueError("calibration population has no finite scores")
    value = max(ABSOLUTE_HURDLE, float(np.quantile(finite, CALIBRATION_QUANTILE, method="linear")))
    provenance = content_hash({"scores": scores.provenance_hash, "absolute_hurdle": ABSOLUTE_HURDLE, "quantile": CALIBRATION_QUANTILE})
    return CalibrationThreshold(value, scores.suite_id, provenance, _token=_THRESHOLD_SEAL)


def qualifies(scores: ModelScores, threshold: CalibrationThreshold, guard: D1ExecutionGuard) -> np.ndarray:
    if not isinstance(scores, ModelScores) or not isinstance(threshold, CalibrationThreshold):
        raise ValueError("qualification requires sealed scores and a frozen calibration threshold")
    validate_model_scores(scores, guard)
    if scores.suite_id != threshold.suite_id:
        raise ValueError("qualification score suite differs from calibration")
    values = scores.values
    return np.isfinite(values) & values.__gt__(threshold.value)


def fractional_boundary_weights(scores: Iterable[float], k: int) -> np.ndarray:
    values = np.asarray(list(scores), dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("boundary scores must be a finite one-dimensional vector")
    n = len(values)
    if k < 0:
        raise ValueError("k must be nonnegative")
    if k == 0:
        return np.zeros(n, dtype=float)
    if k >= n:
        return np.ones(n, dtype=float)
    boundary = np.partition(values, n - k)[n - k]
    above = values > boundary
    equal = values == boundary
    a = int(above.sum())
    m = int(equal.sum())
    weights = above.astype(float)
    weights[equal] = (k - a) / m
    if not np.isclose(weights.sum(), float(k), rtol=0.0, atol=1e-12):
        raise AssertionError("fractional boundary weights do not sum to k")
    return weights


def weighted_mean(values: Iterable[float], weights: Iterable[float]) -> float:
    x = np.asarray(list(values), dtype=float)
    w = np.asarray(list(weights), dtype=float)
    if x.shape != w.shape or not np.isfinite(x).all() or not np.isfinite(w).all() or w.sum() <= 0:
        raise ValueError("weighted mean requires aligned finite values and positive total weight")
    return float(np.sum(x * w) / np.sum(w))


def weighted_rate(events: Iterable[bool], weights: Iterable[float]) -> float:
    return weighted_mean(np.asarray(list(events), dtype=float), weights)
