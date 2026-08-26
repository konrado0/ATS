from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ats_research.gpw_split_adjustment import (
    logical_split_output_hash,
    select_whole_bars,
    transform_split_adjusted,
)


def bars(*, series: str = "bossa:v1", basis: str = "source_native", volume=np.nan) -> pd.DataFrame:
    rows = [
        ("2025-01-02", 100.0, 105.0, 95.0, 100.0, volume),
        ("2025-01-03", 20.0, 21.0, 19.0, 20.0, volume),
        ("2025-01-06", 21.0, 22.0, 20.0, 21.0, volume),
    ]
    return pd.DataFrame(
        [
            {
                "security_id": "SEC",
                "isin": "ISIN",
                "session_date": date,
                "selected_source": "bossa_mstall",
                "source_series_version": series,
                "data_basis": basis,
                "native_open": open_,
                "native_high": high,
                "native_low": low,
                "native_close": close,
                "native_volume": vol,
                "volume_basis": "shares" if pd.notna(vol) else "missing",
                "volume_precision_state": "exact_source_reported_shares" if pd.notna(vol) else "missing_volume",
                "volume_usable_for_relative_volume": pd.notna(vol),
                "volume_ineligibility_reason": "" if pd.notna(vol) else "missing_volume",
                "source_lineage": "fixture",
                "source_hash": "fixture-hash",
            }
            for date, open_, high, low, close, vol in rows
        ]
    )


def event(event_id="split", effective="2025-01-03", price=0.2, volume=5.0) -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "event_id": event_id,
            "security_id": "SEC",
            "event_status": "confirmed",
            "first_post_event_session": effective,
            "pre_event_ohlc_multiplier": price,
            "pre_event_volume_multiplier": volume,
        }]
    )


def treatment(state="source_unadjusted_for_event", event_id="split", series="bossa:v1") -> pd.DataFrame:
    return pd.DataFrame([{"event_id": event_id, "source_series_version": series, "treatment_state": state}])


def test_unadjusted_split_and_volume_transform_preserve_native_and_envelope() -> None:
    native = bars(volume=10.0)
    output = transform_split_adjusted(native, event(), treatment(), factor_version="v1")
    assert output.loc[0, "split_adjusted_close"] == 20.0
    assert output.loc[0, "split_adjusted_volume"] == 50.0
    assert output.loc[0, "applied_event_ids"] == "split"
    assert output.loc[1, "split_adjusted_close"] == output.loc[1, "native_close"]
    assert output[["native_open", "native_high", "native_low", "native_close", "native_volume"]].equals(
        native[["native_open", "native_high", "native_low", "native_close", "native_volume"]]
    )


def test_already_adjusted_split_passes_through() -> None:
    output = transform_split_adjusted(
        bars(volume=10.0), event(), treatment("source_already_adjusted_for_event"), factor_version="v1"
    )
    assert output["cumulative_price_factor"].eq(1.0).all()
    assert output["applied_event_ids"].eq("").all()


def test_reverse_split_and_multiple_cumulative_events() -> None:
    native = bars(volume=10.0)
    events = pd.concat([event("forward", "2025-01-03", 0.5, 2.0), event("reverse", "2025-01-06", 5.0, 0.2)])
    treatments = pd.concat([treatment(event_id="forward"), treatment(event_id="reverse")])
    output = transform_split_adjusted(native, events, treatments, factor_version="v1")
    assert output.loc[0, "cumulative_price_factor"] == 2.5
    assert output.loc[0, "cumulative_volume_factor"] == 0.4
    assert output.loc[1, "cumulative_price_factor"] == 5.0


def test_unknown_treatment_and_invalid_ratio_fail_closed() -> None:
    with pytest.raises(ValueError, match="unknown treatment"):
        transform_split_adjusted(bars(), event(), treatment("unknown"), factor_version="v1")
    with pytest.raises(ValueError, match="invalid split ratio"):
        transform_split_adjusted(bars(), event(price=0.0), treatment(), factor_version="v1")


def test_rejects_derived_input_and_regeneration_hash_is_identical() -> None:
    native = bars()
    first = transform_split_adjusted(native, event(), treatment(), factor_version="v1")
    second = transform_split_adjusted(native.copy(), event(), treatment(), factor_version="v1")
    assert logical_split_output_hash(first) == logical_split_output_hash(second)
    with pytest.raises(ValueError, match="derived or non-native"):
        transform_split_adjusted(bars(basis="split_adjusted_price"), event(), treatment(), factor_version="v1")
    with pytest.raises(ValueError, match="already contains"):
        transform_split_adjusted(first.assign(data_basis="source_native"), event(), treatment(), factor_version="v1")


def test_missing_and_rounded_volume_precision_are_preserved() -> None:
    missing = transform_split_adjusted(bars(), event(), treatment(), factor_version="v1")
    assert missing["split_adjusted_volume"].isna().all()
    rounded_native = bars(volume=1230.0)
    rounded_native["volume_precision_state"] = "vendor_displayed_rounded_volume"
    rounded_native["volume_basis"] = "vendor_displayed_shares"
    rounded = transform_split_adjusted(rounded_native, event(), treatment(), factor_version="v1")
    assert rounded.loc[0, "split_adjusted_volume"] == 6150.0
    assert rounded.loc[0, "volume_precision_state"] == "vendor_displayed_rounded_volume"


def test_whole_bar_source_selection_and_source_switch() -> None:
    bossa = bars(volume=10.0).iloc[[0]].assign(source_priority=1, selected_source="bossa_mstall")
    investing = bars(volume=99.0).iloc[:2].assign(source_priority=3, selected_source="investing_com")
    selected = select_whole_bars([bossa, investing])
    assert list(selected["selected_source"]) == ["bossa_mstall", "investing_com"]
    assert list(selected["native_volume"]) == [10.0, 99.0]


def test_not_applicable_is_accepted_and_unaffected_security_is_unchanged() -> None:
    native = bars()
    other = bars().assign(security_id="OTHER", isin="OTHER")
    output = transform_split_adjusted(
        pd.concat([native, other], ignore_index=True), event(), treatment("not_applicable"), factor_version="v1"
    )
    other_out = output.loc[output["security_id"].eq("OTHER")]
    assert other_out["split_adjusted_close"].equals(other_out["native_close"])


def test_source_switch_around_event_uses_each_series_treatment() -> None:
    native = bars(volume=10.0)
    native.loc[native["session_date"].eq("2025-01-03"), "source_series_version"] = "investing:v1"
    native.loc[native["session_date"].eq("2025-01-03"), "selected_source"] = "investing_com"
    native.loc[native["session_date"].eq("2025-01-06"), "source_series_version"] = "investing:v1"
    native.loc[native["session_date"].eq("2025-01-06"), "selected_source"] = "investing_com"
    treatments = pd.DataFrame(
        [
            {"event_id": "split", "source_series_version": "bossa:v1", "treatment_state": "source_unadjusted_for_event"},
            {"event_id": "split", "source_series_version": "investing:v1", "treatment_state": "source_already_adjusted_for_event"},
        ]
    )
    output = transform_split_adjusted(native, event(), treatments, factor_version="v1")
    assert list(output["split_adjusted_close"]) == [20.0, 20.0, 21.0]


def test_fixed_universe_denominator_fixture_is_exactly_20_plus_40() -> None:
    session = pd.Timestamp("2025-01-02")
    fixture = pd.DataFrame(
        [
            {"session_date": session, "role": role, "isin": f"{role}-{index}"}
            for role, count in (("WIG20", 20), ("mWIG40", 40))
            for index in range(count)
        ]
    )
    counts = fixture.groupby("role").size().to_dict()
    assert counts == {"WIG20": 20, "mWIG40": 40}
    assert len(fixture) == fixture["isin"].nunique() == 60
