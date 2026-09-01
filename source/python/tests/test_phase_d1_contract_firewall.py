from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from ats_ml.contracts import ContractError, load_frozen_d0_contract, resolve_pinned_inputs
from ats_ml.guard import AuthorizationError, DatasetIdentity, ExecutionClass, ExecutionContext, Operation, pinned_real_context, pinned_real_predictive_context
from ats_ml.matrices import MatrixContractError, ModelMatrix, load_authorized_model_fixture, validate_predictor_frame
from phase_d1_helpers import d1_contract_guard_context


def test_frozen_d0_loader_and_pinned_input_resolution() -> None:
    contract = load_frozen_d0_contract()
    assert contract.config["contract_version"] == "phase-d0-20260831-v2"
    assert len(contract.registry_order) == 30
    assert {key: len(value) for key, value in contract.feature_blocks.items()} == {"C": 6, "P": 8, "X": 4, "M": 12}
    assert all(path.is_file() for path in resolve_pinned_inputs(contract).values())


def test_real_identity_cannot_be_downgraded_by_path_or_metadata() -> None:
    contract, guard, synthetic = d1_contract_guard_context()
    real = pinned_real_context(contract)
    with pytest.raises(AuthorizationError, match="predictive"):
        guard.require(Operation.FIT, real)
    forged = SimpleNamespace(classification=ExecutionClass.SYNTHETIC_FIXTURE, identity=real.identity, fixture_id="phase-d1-fixture-core", metadata={"path": "fixture.parquet"})
    with pytest.raises(AuthorizationError, match="relabeled synthetic"):
        guard.require(Operation.FIT, forged)
    copied = SimpleNamespace(classification=ExecutionClass.SYNTHETIC_FIXTURE, identity=real.identity, fixture_id="phase-d1-fixture-core", metadata={"path": "renamed/copy.parquet", "description": "synthetic"})
    with pytest.raises(AuthorizationError, match="relabeled synthetic"):
        guard.require(Operation.PREDICT, copied)
    guard.require(Operation.FIT, synthetic)


def test_real_predictive_is_rejected_for_every_operation() -> None:
    contract = load_frozen_d0_contract()
    guard = __import__("ats_ml.guard", fromlist=["D1ExecutionGuard"]).D1ExecutionGuard(contract)
    real = pinned_real_context(contract)
    predictive = pinned_real_predictive_context(contract)
    for operation in Operation:
        with pytest.raises(AuthorizationError, match="disabled"):
            guard.require(operation, predictive)


def test_model_allowlist_rejects_identity_proxies_labels_and_order_changes() -> None:
    contract, _, _ = d1_contract_guard_context()
    expected = contract.feature_blocks["C"]
    valid = pd.DataFrame(np.zeros((3, len(expected))), columns=expected)
    validate_predictor_frame(valid, expected)
    bad_names = [
        "ticker", "isin", "security_id", "company_name", "nominal_price", "raw_unscaled_volume",
        "selected_source", "source_lineage", "file_path", "sector", "missingness_indicator",
        "ticker_hash", "identity_ordinal", "identity_one_hot_A", "identity_frequency", "target_encoded_identity",
        "label__open_to_open__20",
    ]
    for name in bad_names:
        with pytest.raises(MatrixContractError, match="allowlist mismatch"):
            validate_predictor_frame(valid.assign(**{name: 0.0}), expected)
    with pytest.raises(MatrixContractError, match="order_equal=True"):
        validate_predictor_frame(valid.loc[:, list(reversed(expected))], expected)
    duplicate = valid.copy()
    duplicate.columns = list(expected[:-1]) + [expected[-2]]
    with pytest.raises(MatrixContractError):
        validate_predictor_frame(duplicate, expected)


def test_bare_dataframe_cannot_claim_to_be_a_sealed_matrix() -> None:
    contract, guard, context = d1_contract_guard_context()
    expected = contract.feature_blocks["C"]
    sealed, target = load_authorized_model_fixture("phase-d1-fixture-linear-train", expected, contract, guard)
    assert isinstance(sealed, ModelMatrix)
    assert target is not None
    frame = pd.DataFrame(np.zeros((2, len(expected))), columns=expected)
    with pytest.raises(MatrixContractError, match="factory"):
        ModelMatrix(frame, context, expected, "x", data_hash="0" * 64, fixture_id="phase-d1-fixture-linear-train", suite_id="linear", fixture_registry_sha256=guard.fixture_registry_sha256, _token=object())


def test_context_and_partial_real_identity_cannot_be_forged_or_authorized() -> None:
    contract, guard, _ = d1_contract_guard_context()
    with pytest.raises(AuthorizationError, match="minted"):
        DatasetIdentity("a", "b", "c", "d", "e", _token=object())
    real = pinned_real_context(contract)
    partial = SimpleNamespace(
        manifest_sha256=real.identity.manifest_sha256,
        physical_sha256="x",
        logical_hash="y",
        run_id="z",
        data_basis_version="q",
    )
    forged = SimpleNamespace(classification=ExecutionClass.REAL_STRUCTURAL, identity=partial, fixture_id=None, metadata={})
    with pytest.raises(AuthorizationError, match="pinned candidate identity"):
        guard.require(Operation.COMPUTE_P_STRUCTURAL, forged)


def test_execution_class_is_closed_enum() -> None:
    with pytest.raises(ValueError):
        ExecutionClass("SYNTHETIC_FIXTURE")
    with pytest.raises(ValueError):
        ExecutionClass("real")
