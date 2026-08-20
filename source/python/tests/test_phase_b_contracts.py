from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ats_contracts.schemas import SCHEMA_VERSION, SCHEMAS, schema_for
from ats_contracts.validation import ContractError, validate_table


SID1 = str(uuid.UUID("11111111-1111-4111-8111-111111111111"))
SID2 = str(uuid.UUID("22222222-2222-4222-8222-222222222222"))


def bar_table(*, duplicate: bool = False, bad_ohlc: bool = False, bad_timing: bool = False, schema_version: str = SCHEMA_VERSION) -> pa.Table:
    event = datetime(2025, 1, 2, 21, 0, tzinfo=timezone.utc)
    rows = 2 if duplicate else 1
    values = {
        "security_id": [SID1] * rows, "market": ["US"] * rows, "venue_mic": ["XNAS"] * rows,
        "frequency": ["daily"] * rows, "event_ts": [event] * rows, "session_date": [date(2025, 1, 2)] * rows,
        "available_ts": [event.replace(minute=5) if not bad_timing else event.replace(hour=20)] * rows,
        "open": [10.0] * rows, "high": ([9.0] if bad_ohlc else [11.0]) * rows,
        "low": [9.0] * rows, "close": [10.5] * rows, "volume": [100.0] * rows,
        "turnover": [None] * rows, "currency": ["USD"] * rows, "source": ["fixture"] * rows,
        "source_record_id": [f"row-{index}" for index in range(rows)], "adjustment_state": ["raw"] * rows,
        "adjustment_version": ["v1"] * rows, "ingest_batch_id": ["batch"] * rows,
        "ingested_at": [datetime(2025, 1, 3, tzinfo=timezone.utc)] * rows, "quality_state": ["accepted"] * rows,
        "quality_flags": ["[]"] * rows, "resolution_state": ["resolved"] * rows,
        "schema_version": [schema_version] * rows,
    }
    return pa.Table.from_pydict(values, schema=schema_for("bars"))


def alias_table(*, provisional: bool = False) -> pa.Table:
    status = "provisional_source_scoped" if provisional else "resolved"
    return pa.Table.from_pydict({
        "security_id": [SID1, SID2], "identifier_type": ["ticker", "ticker"],
        "identifier_value": ["ABC", "ABC"], "raw_identifier": ["ABC", "ABC"],
        "market": ["US", "US"], "venue_mic": ["XNAS", "XNAS"], "vendor": [None, None],
        "valid_from": [date(2020, 1, 1), date(2021, 1, 1)], "valid_to": [date(2022, 1, 1), None],
        "source": ["fixture", "fixture"], "provenance": ["one", "two"],
        "resolution_status": [status, status], "schema_version": [SCHEMA_VERSION, SCHEMA_VERSION],
    }, schema=schema_for("security_aliases"))


def test_all_exact_schemas_round_trip_through_parquet(tmp_path: Path) -> None:
    for name, schema in SCHEMAS.items():
        path = tmp_path / f"{name}.parquet"
        pq.write_table(pa.Table.from_batches([], schema=schema), path, compression="zstd", compression_level=3)
        assert pq.read_schema(path).remove_metadata() == schema


def test_valid_bar_contract_passes() -> None:
    assert validate_table("bars", bar_table())["passed"] is True


@pytest.mark.parametrize(
    ("table", "message"),
    [
        (lambda: bar_table(duplicate=True), "duplicate semantic key"),
        (lambda: bar_table(bad_ohlc=True), "inconsistent OHLC"),
        (lambda: bar_table(bad_timing=True), "availability precedes"),
        (lambda: bar_table(schema_version="ats.canonical.v999"), "incompatible schema"),
    ],
)
def test_bar_contracts_fail_closed(table, message: str) -> None:
    with pytest.raises(ContractError, match=message):
        validate_table("bars", table())


def test_unexpected_schema_and_unknown_enum_fail_closed() -> None:
    with pytest.raises(ContractError, match="unexpected schema"):
        validate_table("bars", bar_table().append_column("surprise", pa.array([1])))
    data = bar_table().to_pydict(); data["frequency"] = ["weekly"]
    values = pa.Table.from_pydict(data, schema=schema_for("bars"))
    with pytest.raises(ContractError, match="unknown enum"):
        validate_table("bars", values)


def test_resolved_alias_overlap_fails_but_provisional_candidates_remain_visible() -> None:
    with pytest.raises(ContractError, match="overlapping alias intervals"):
        validate_table("security_aliases", alias_table())
    assert validate_table("security_aliases", alias_table(provisional=True))["rows"] == 2
