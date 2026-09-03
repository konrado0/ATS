from __future__ import annotations

import pandas as pd

from ats_ml.d2_no_m_linear_mechanism import BLOCK_MAP, CELLS, CONTRASTS, _spearman, load_contract


def test_mechanism_contract_is_exact_and_rank_only() -> None:
    contract = load_contract()
    assert contract["status"] == "FROZEN_BEFORE_REAL_MODEL_FIT"
    assert set(contract["cells"]) == set(CELLS)
    assert [row["id"] for row in contract["historical_populations"]] == list(BLOCK_MAP.values())
    assert contract["evaluation"]["rank_only"] is True
    assert contract["evaluation"]["calculate_candidate_thresholds"] is False
    assert len(CONTRASTS) == 6


def test_average_rank_spearman_is_identity_and_order_invariant() -> None:
    frame = pd.DataFrame({"security_id": ["D", "A", "C", "B"], "score": [1.0, 1.0, 2.0, 3.0], "outcome": [0.2, 0.1, 0.4, 0.3]})
    repeated = pd.concat([frame] * 12, ignore_index=True)
    left = _spearman(repeated.score, repeated.outcome)
    right = _spearman(repeated.sample(frac=1, random_state=11).score, repeated.sample(frac=1, random_state=11).outcome)
    assert left == right


def test_prediction_field_denylist_excludes_rank_and_tail_fields() -> None:
    tokens = load_contract()["stage1"]["forbidden_prediction_fields_containing"]
    for name in ("label__open_to_open__20", "rank_ic", "candidate", "threshold", "episode", "classification"):
        assert any(token in name.lower() for token in tokens)

