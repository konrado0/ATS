from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ats_research.identity import build_identity_tables, stable_security_id
from ats_research.investing_manual import (
    InvestingManualValidationError,
    listing_state,
    parse_investing_manual_history,
)
from ats_research.universe import membership_intervals


FIXTURE = Path(__file__).parent / "fixtures" / "investing_manual" / "sample.tsv"
DATA_ROOT = Path("D:/Stock/data")


def _write_variant(tmp_path: Path, data_line: str, extra_line: str | None = None) -> Path:
    header = "\nData\n\nOstatnio\n\nOtwarcie\n\nMax.\n\nMin.\n\nWol.\n\nZmiana%\n"
    path = tmp_path / "variant.tsv"
    path.write_text(header + data_line + ("\n" + extra_line if extra_line else "") + "\n", encoding="utf-8")
    return path


def test_parses_reverse_order_decimal_commas_and_rounded_k_m_volume() -> None:
    result = parse_investing_manual_history(FIXTURE)
    assert result.inspection["input_order"] == "descending"
    assert result.inspection["volume_forms"] == ["K", "M"]
    assert result.bars["session_date"].is_monotonic_increasing
    assert result.bars["close"].tolist() == [12.0, 12.2, 12.5]
    assert result.bars["volume"].tolist() == [1_000.0, 12_340.0, 1_250_000.0]
    assert result.bars["volume_rounding_uncertainty_shares"].tolist() == [5.0, 5.0, 5_000.0]
    assert result.bars["display_rounded_volume"].all()
    assert "_displayed_change_pct" not in result.bars


@pytest.mark.parametrize(
    "line, message",
    [
        ("32.01.2022\t12,00\t12,00\t12,00\t12,00\t1,00K\t0.00%", "invalid date"),
        ("03.01.2022\tbad\t12,00\t12,00\t12,00\t1,00K\t0.00%", "malformed close"),
        ("03.01.2022\t12,00\t12,00\t12,00\t12,00\t1,00B\t0.00%", "unsupported volume"),
        ("03.01.2022\t12,00\t12,00\t11,00\t12,00\t1,00K\t0.00%", "invalid OHLCV"),
    ],
)
def test_rejects_malformed_or_unsupported_rows(tmp_path: Path, line: str, message: str) -> None:
    with pytest.raises(InvestingManualValidationError, match=message):
        parse_investing_manual_history(_write_variant(tmp_path, line))


def test_rejects_duplicate_dates(tmp_path: Path) -> None:
    line = "03.01.2022\t12,00\t12,00\t12,00\t12,00\t1,00K\t0.00%"
    with pytest.raises(InvestingManualValidationError, match="duplicate dates"):
        parse_investing_manual_history(_write_variant(tmp_path, line, line))


def test_supplemental_mapping_reuses_existing_identity_and_retains_source(tmp_path: Path) -> None:
    isin = "PLSTSHL00012"
    mapping = {
        "source": "investing_com_manual_history",
        "parser_version": "investing_com_manual_tsv_v1",
        "mappings": [
            {
                "isin": isin,
                "security_id": stable_security_id(isin),
                "source_file": "raw/investing/sts.tsv",
                "listing_date": "2021-12-10",
                "last_trade_date": "2023-10-04",
            }
        ],
    }
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    intervals = membership_intervals(DATA_ROOT / "reference" / "gpw_indices", pd.Timestamp("2022-01-01"), pd.Timestamp("2024-01-01"))
    identities = build_identity_tables(
        intervals, DATA_ROOT / "reference" / "gpw_indices" / "stooq_symbol_map.csv", "XWAR", mapping_path
    )
    selected = identities.vendor_resolution.loc[identities.vendor_resolution["isin"].eq(isin)].iloc[0]
    assert selected["security_id"] == stable_security_id(isin)
    assert selected["vendor_resolution_status"] == "supplemental_external_mapping"
    alias = identities.aliases.loc[identities.aliases["security_id"].eq(stable_security_id(isin)) & identities.aliases["vendor"].eq("investing.com")]
    assert len(alias) == 1
    assert not alias["source"].str.contains("stooq", case=False).any()


def test_sts_prelisting_is_not_vendor_missingness() -> None:
    assert listing_state("2021-12-09", "2021-12-10") == "not_yet_listed"
    assert listing_state("2021-12-10", "2021-12-10") == "listed"
