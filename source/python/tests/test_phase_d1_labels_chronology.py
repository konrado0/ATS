from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ats_ml.guard import AuthorizationError
from ats_ml.chronology import chronological_quartiles, derive_chronological_folds
from ats_ml.labels import build_primary_labels, label_endpoints
from ats_ml.observations import ObservationContractError, attach_outcome_availability
from phase_d1_helpers import d1_contract_guard_context, stock_bars


def test_primary_open_label_exact_endpoint_and_intervening_missing_does_not_recount() -> None:
    _, guard, context = d1_contract_guard_context("phase-d1-fixture-label-exact")
    calendar = pd.DatetimeIndex([
        pd.Timestamp("2024-01-02") + pd.Timedelta(days=value)
        for value in [0, 1, 2, 5, 6, 9, 10, 11, 12, 15, 16, 17, 18, 19, 22, 23, 24, 25, 26, 29, 30, 31]
    ])
    bars = stock_bars(calendar)
    observations = pd.DataFrame({"security_id": "S00", "decision_session": [calendar[0], calendar[1]]})
    bars.loc[bars["session_date"].eq(calendar[10]), "split_adjusted_open"] = np.nan
    labels = build_primary_labels(bars, observations, calendar, guard, context).frame
    first = labels.loc[labels["decision_session"].eq(calendar[0])].iloc[0]
    second = labels.loc[labels["decision_session"].eq(calendar[1])].iloc[0]
    assert first["label_endpoint_session"] == calendar[20]
    assert np.isclose(first["label__open_to_open__20"], bars.loc[bars["session_date"].eq(calendar[20]), "split_adjusted_open"].iloc[0] / bars.loc[bars["session_date"].eq(calendar[0]), "split_adjusted_open"].iloc[0] - 1.0)
    assert second["label_endpoint_session"] == calendar[21]
    assert first["label_state"] == "AVAILABLE"


def test_missing_label_start_endpoint_and_right_censor_are_explicit() -> None:
    _, guard, context = d1_contract_guard_context("phase-d1-fixture-label-missing")
    calendar = pd.bdate_range("2024-01-02", periods=23)
    bars = stock_bars(calendar)
    bars.loc[bars["session_date"].eq(calendar[0]), "split_adjusted_open"] = np.nan
    bars.loc[bars["session_date"].eq(calendar[21]), "split_adjusted_open"] = np.nan
    observations = pd.DataFrame({"security_id": "S00", "decision_session": [calendar[0], calendar[1], calendar[5]]})
    result = build_primary_labels(bars, observations, calendar, guard, context).frame.set_index("decision_session")
    assert result.loc[calendar[0], "label_state"] == "LABEL_START_MISSING"
    assert result.loc[calendar[1], "label_state"] == "LABEL_ENDPOINT_MISSING"
    assert result.loc[calendar[5], "label_state"] == "LABEL_RIGHT_CENSORED"
    assert result["label__open_to_open__20"].isna().all()


def test_real_or_arbitrary_label_payload_cannot_be_reclassified_synthetic() -> None:
    contract, guard, wrong_context = d1_contract_guard_context()
    calendar = pd.bdate_range("2024-01-02", periods=23)
    bars = stock_bars(calendar)
    observations = pd.DataFrame({"security_id": "S00", "decision_session": [calendar[0]]})
    with pytest.raises(AuthorizationError, match="payload"):
        build_primary_labels(bars, observations, calendar, guard, wrong_context)
    _, _, label_context = d1_contract_guard_context("phase-d1-fixture-label-missing")
    with pytest.raises(AuthorizationError, match="payload"):
        build_primary_labels(bars, observations, calendar, guard, label_context)
    with pytest.raises(ObservationContractError, match="sealed"):
        attach_outcome_availability(observations.assign(model_score_eligible=True, scored_count=1), pd.DataFrame(), guard, wrong_context)  # type: ignore[arg-type]


def test_endpoint_derived_purge_uses_timestamps_not_observation_row_counts() -> None:
    contract, guard, context = d1_contract_guard_context()
    calendar = pd.bdate_range("2019-01-02", "2026-08-18")
    calendar = calendar[~calendar.strftime("%m-%d").isin(["01-06", "05-01", "05-03", "11-11", "12-24", "12-25", "12-26"])]
    fold_rows, resolutions = derive_chronological_folds(calendar, contract, guard, context)
    purged_counts: list[int] = []
    for fold_id, boundaries in resolutions.items():
        for boundary in boundaries[:2]:
            assert boundary.purged_sessions > 0
            assert boundary.last_retained_session < boundary.first_purged_session
            purged_counts.append(boundary.purged_sessions)
        group = fold_rows.loc[fold_rows["fold_id"].eq(fold_id)]
        assert group.groupby(["partition", "decision_session"])["retained"].nunique().max() == 1
    assert any(count != 20 for count in purged_counts), "adversarial calendar must disagree with fixed 20-row subtraction"
    selection_fit = fold_rows.loc[(fold_rows["fold_id"] == "MODEL_SELECTION_2022") & (fold_rows["partition"] == "fit")]
    last_retained = selection_fit.loc[selection_fit["retained"], "decision_session"].max()
    boundary = pd.Timestamp(contract.config["chronology"]["folds"][0]["calibration_start"])
    endpoint = selection_fit.loc[selection_fit["decision_session"].eq(last_retained), "label_endpoint_session"].iloc[0]
    assert endpoint < boundary
    first_purged = selection_fit.loc[~selection_fit["retained"], "decision_session"].min()
    purged_endpoint = selection_fit.loc[selection_fit["decision_session"].eq(first_purged), "label_endpoint_session"].iloc[0]
    assert purged_endpoint >= boundary


def test_chronological_quartiles_are_contiguous_array_split_bins() -> None:
    sessions = pd.bdate_range("2025-01-02", periods=11)
    bins = chronological_quartiles(sessions)
    assert [item["session_count"] for item in bins] == [3, 3, 3, 2]
    assert bins[0]["first_session"] == "2025-01-02"
    assert bins[-1]["last_session"] == str(sessions[-1].date())


def test_feature_namespace_cannot_import_labels_or_future_outcomes() -> None:
    feature_path = Path(__file__).resolve().parents[1] / "src/ats_ml/features.py"
    tree = ast.parse(feature_path.read_text(encoding="utf-8"))
    imports: list[str] = []
    string_literals: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            string_literals.append(node.value.lower())
    assert not any(name.startswith("ats_ml.labels") for name in imports)
    assert not any("label__" in value or "forward_return" in value for value in string_literals)


def test_endpoint_metadata_builder_never_requires_price_values() -> None:
    calendar = pd.bdate_range("2025-01-02", periods=25)
    result = label_endpoints([calendar[0], calendar[4]], calendar)
    assert tuple(result.columns) == ("decision_session", "label_endpoint_session", "label_endpoint_ts")
    assert result.loc[0, "label_endpoint_session"] == calendar[20]
    assert result.loc[1, "label_endpoint_session"] == calendar[24]
