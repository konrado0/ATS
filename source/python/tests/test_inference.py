from __future__ import annotations

import numpy as np
import pandas as pd

from ats_research.diagnostics import (
    _benjamini_hochberg,
    _block_bootstrap_mean_ci,
    _hac_standard_error,
    _safe_spearman,
)
from ats_research.hashing import content_hash
from ats_research.run import _environment_lock


def test_hac_and_block_bootstrap_are_finite_and_deterministic() -> None:
    rng = np.random.default_rng(42)
    innovations = rng.normal(size=400)
    values = np.empty(400)
    values[0] = innovations[0]
    for index in range(1, len(values)):
        values[index] = 0.8 * values[index - 1] + innovations[index]
    hac = _hac_standard_error(values, 20)
    naive = values.std(ddof=1) / np.sqrt(len(values))
    first = _block_bootstrap_mean_ci(values, 200, 20, 0.95, 123)
    second = _block_bootstrap_mean_ci(values, 200, 20, 0.95, 123)
    assert np.isfinite(hac)
    assert hac > naive
    assert first == second
    assert first[0] < values.mean() < first[1]


def test_benjamini_hochberg_is_monotone_in_sorted_p_values() -> None:
    p_values = pd.Series([0.001, 0.02, 0.04, np.nan])
    adjusted = _benjamini_hochberg(p_values)
    assert adjusted.iloc[:3].between(0, 1).all()
    assert adjusted.iloc[0] <= adjusted.iloc[1] <= adjusted.iloc[2]
    assert pd.isna(adjusted.iloc[3])


def test_environment_lock_hash_is_stable_within_environment() -> None:
    assert content_hash(_environment_lock()) == content_hash(_environment_lock())


def test_spearman_handles_read_only_pandas_views() -> None:
    frame = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [1, 3, 2, 5, 4]})
    assert np.isfinite(_safe_spearman(frame, "x", "y"))
