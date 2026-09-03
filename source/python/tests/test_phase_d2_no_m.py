from __future__ import annotations

import pandas as pd
import pytest

from ats_ml.d2_no_m import BLOCK_MAP, FULL_RICH, NO_M, classify, load_contract, verify_scientific_object
import ats_ml.d2_no_m_prospective as prospective
from ats_ml.d2_no_m_prospective import validate_prediction_batch
from ats_ml.d2_artifacts import D2ArtifactError
from ats_ml.d2_metrics import episode_anchor_flags, fractional_boundary_weights


def test_contract_freezes_exact_cells_periods_and_classification_order() -> None:
    contract = load_contract()
    assert contract["cells"]["challenger"] == NO_M
    assert contract["cells"]["comparators"] == ["C_LINEAR", "C_LIGHTGBM"]
    assert contract["cells"]["direct_m_diagnostic_only"] == FULL_RICH
    assert [row["id"] for row in contract["historical_populations"]] == list(BLOCK_MAP.values())
    assert contract["classification_order"] == [
        "NOT PROVEN", "NEGATIVE", "STRONG RESEARCH DIRECTION", "WEAK BUT PERSISTENT", "UNSTABLE"
    ]


def test_accepted_no_m_was_independently_fitted_exactly() -> None:
    proof = verify_scientific_object()
    assert proof["status"] == "PASS"
    assert proof["independently_fitted"] is True
    assert proof["no_m_refit_count"] == 8
    assert len(proof["no_m_features"]) == 18
    assert all(all(record["checks"].values()) for record in proof["records"])


def test_episode_rule_is_row_order_and_identity_order_invariant() -> None:
    frame = pd.DataFrame({
        "security_id": ["B", "A", "A", "B"],
        "decision_session": pd.to_datetime(["2026-01-02", "2026-01-02", "2026-01-05", "2026-01-05"]),
        "candidate": [True, True, True, False],
    })
    calendar = pd.to_datetime(["2026-01-02", "2026-01-05"])
    left = episode_anchor_flags(frame, calendar).sort_values(["decision_session", "security_id"]).reset_index(drop=True)
    right = episode_anchor_flags(frame.sample(frac=1, random_state=7), calendar).sort_values(["decision_session", "security_id"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right)


def test_frequency_match_ties_are_fractional_and_identity_free() -> None:
    scores = pd.Series([0.5, 0.5, 0.5, 0.1])
    weights = fractional_boundary_weights(scores, 2)
    assert weights.sum() == pytest.approx(2.0)
    assert list(weights[:3]) == pytest.approx([2 / 3, 2 / 3, 2 / 3])
    permuted = fractional_boundary_weights(scores.iloc[[2, 0, 3, 1]], 2)
    assert sorted(permuted) == pytest.approx(sorted(weights))


def _classification_inputs(delta_linear: float, delta_tree: float, positives: tuple[int, int], *, tail_ok: bool = True):
    names = list(BLOCK_MAP.values())
    rank = {name: {"paired": {
        "C_LINEAR": {"mean": 0.01 if index < positives[0] else -0.01},
        "C_LIGHTGBM": {"mean": 0.01 if index < positives[1] else -0.01},
    }} for index, name in enumerate(names)}
    rank["RETRO_2023_2026_H1"] = {
        "mean_ic": {NO_M: 0.04, FULL_RICH: 0.03, "C_LINEAR": 0.02, "C_LIGHTGBM": 0.01},
        "paired": {"C_LINEAR": {"mean": delta_linear}, "C_LIGHTGBM": {"mean": delta_tree}},
    }
    tail = {"RETRO_2023_2026_H1": {
        "minus_eligible": 0.01 if tail_ok else -0.01,
        "minus_comparator": {"C_LINEAR": 0.01 if tail_ok else -0.01, "C_LIGHTGBM": 0.01 if tail_ok else -0.01},
        "episode_median_outcome": 0.01 if tail_ok else -0.01,
    }}
    concentration = {
        "security_positive_excess": {"largest_share": 0.1}, "session_positive_excess": {"largest_share": 0.1},
        "half_year_positive_excess": {"largest_share": 0.2}, "largest_rolling_20_session_positive_excess_share": 0.2,
        "rank_half_year_positive_delta": {"C_LINEAR": {"largest_positive_delta_share": 0.3}, "C_LIGHTGBM": {"largest_positive_delta_share": 0.3}},
    }
    influence = {"details": {"A": {"mean_delta": {"C_LINEAR": delta_linear / 2, "C_LIGHTGBM": delta_tree / 2}}}}
    return rank, tail, concentration, influence


@pytest.mark.parametrize(
    ("delta_linear", "delta_tree", "positives", "tail_ok", "expected"),
    [
        (0.006, 0.006, (5, 5), True, "STRONG RESEARCH DIRECTION"),
        (0.004, 0.006, (4, 5), True, "WEAK BUT PERSISTENT"),
        (0.004, 0.006, (3, 5), True, "UNSTABLE"),
        (-0.001, 0.006, (3, 5), False, "NEGATIVE"),
    ],
)
def test_retrospective_classification_boundaries(delta_linear, delta_tree, positives, tail_ok, expected) -> None:
    args = _classification_inputs(delta_linear, delta_tree, positives, tail_ok=tail_ok)
    assert classify(*args, validity_pass=True)["classification"] == expected
    assert classify(*args, validity_pass=False)["classification"] == "NOT PROVEN"


def _prospective_frame(seal: str) -> pd.DataFrame:
    rows = []
    for cell in (NO_M, "C_LINEAR", "C_LIGHTGBM"):
        rows.append({
            "information_session": "2026-09-02", "decision_session": "2026-09-03",
            "decision_ts": "2026-09-03T08:45:00+02:00", "cell_id": cell, "security_id": "A",
            "model_score": 0.02, "threshold": 0.01, "candidate": True,
            "prediction_generation_ts": seal, "publication_seal_ts": seal,
            "target_start_session": "2026-09-03", "target_endpoint_session": "2026-10-01",
            "label_availability_ts": "2026-10-01T09:00:00+02:00",
            "prospective_eligible": pd.Timestamp(seal) <= pd.Timestamp("2026-09-03T08:45:00+02:00"),
            "monitoring_only": pd.Timestamp(seal) > pd.Timestamp("2026-09-03T08:45:00+02:00"),
            "exclusion_reason": "" if pd.Timestamp(seal) <= pd.Timestamp("2026-09-03T08:45:00+02:00") else "SEALED_AFTER_DECISION_TS",
            "official_expected_count": 60, "model_exclusion_reason": "",
        })
    return pd.DataFrame(rows)


def test_prediction_sealed_before_0845_is_prospective() -> None:
    assert validate_prediction_batch(_prospective_frame("2026-09-03T08:44:59+02:00"))["prospective_rows"] == 3


def test_prediction_sealed_after_0845_is_monitoring_only() -> None:
    assert validate_prediction_batch(_prospective_frame("2026-09-03T08:45:01+02:00"))["monitoring_only_rows"] == 3


def test_prediction_artifact_rejects_outcomes_and_wrong_cells() -> None:
    frame = _prospective_frame("2026-09-03T08:44:59+02:00").assign(label__open_to_open__20=0.1)
    with pytest.raises(D2ArtifactError, match="outcome-bearing"):
        validate_prediction_batch(frame)
    with pytest.raises(D2ArtifactError, match="exactly the frozen three cells"):
        validate_prediction_batch(frame.drop(columns="label__open_to_open__20").iloc[:-1])


def test_zero_candidate_session_is_valid_and_unknown_state_fails_closed() -> None:
    frame = _prospective_frame("2026-09-03T08:44:59+02:00")
    frame["model_score"] = 0.0
    frame["candidate"] = False
    assert validate_prediction_batch(frame)["status"] == "PASS"
    frame["model_score"] = float("nan")
    frame["prospective_eligible"] = False
    frame["model_exclusion_reason"] = "UNKNOWN_SPLIT_STATE"
    frame["exclusion_reason"] = "UNKNOWN_SPLIT_STATE"
    assert validate_prediction_batch(frame)["visible_exclusion_rows"] == 3
    frame.loc[0, "model_score"] = 0.02
    frame.loc[0, "candidate"] = True
    frame.loc[0, "prospective_eligible"] = True
    with pytest.raises(D2ArtifactError, match="unknown split or membership"):
        validate_prediction_batch(frame)


def test_append_only_publication_conflicts_and_missed_sessions(tmp_path, monkeypatch) -> None:
    stream = tmp_path / "stream"
    monkeypatch.setattr(prospective, "STREAM_ROOT", stream)
    prospective.initialize_stream(registered_ts="2026-09-03T06:00:00Z", reason="fixture")
    batch = tmp_path / "batch.parquet"
    _prospective_frame("2026-09-03T08:44:59+02:00").to_parquet(batch, index=False)
    assert prospective.append_prediction_batch(batch, batch_id="fixture-v1").is_dir()
    with pytest.raises(D2ArtifactError, match="conflicting duplicate"):
        prospective.append_prediction_batch(batch, batch_id="fixture-v2")
    assert prospective.record_missed_session(decision_session="2026-09-04", reason="missing input").is_file()
    with pytest.raises(D2ArtifactError, match="append-only"):
        prospective.record_missed_session(decision_session="2026-09-04", reason="retry")


def test_wrong_official_denominator_is_rejected() -> None:
    frame = _prospective_frame("2026-09-03T08:44:59+02:00")
    frame["official_expected_count"] = 59
    with pytest.raises(D2ArtifactError, match="official denominator 60"):
        validate_prediction_batch(frame)
