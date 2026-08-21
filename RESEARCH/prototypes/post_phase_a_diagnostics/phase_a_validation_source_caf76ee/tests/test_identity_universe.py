from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from ats_research.identity import IdentityResolutionError, resolve_alias, stable_security_id
from ats_research.universe import BENIGN_EXIT_ISINS, load_exit_events, membership_at, membership_intervals


DATA_ROOT = Path("D:/Stock/data")
REFERENCE_ROOT = DATA_ROOT / "reference" / "gpw_indices"


def test_validity_dated_alias_resolution() -> None:
    first = stable_security_id("PL0000000001")
    second = stable_security_id("PL0000000002")
    aliases = pd.DataFrame(
        [
            {"security_id": first, "identifier_type": "ticker", "identifier_value": "ABC", "valid_from": pd.Timestamp("2020-01-01"), "valid_to": pd.Timestamp("2021-12-31"), "resolution_status": "resolved"},
            {"security_id": second, "identifier_type": "ticker", "identifier_value": "ABC", "valid_from": pd.Timestamp("2022-01-01"), "valid_to": pd.Timestamp("2024-12-31"), "resolution_status": "resolved"},
        ]
    )
    assert resolve_alias(aliases, "ticker", "ABC", date(2021, 6, 1)) == first
    assert resolve_alias(aliases, "ticker", "ABC", date(2022, 6, 1)) == second
    assert resolve_alias(aliases, "ticker", "ABC", date(2025, 1, 1)) is None


def test_ambiguous_overlapping_alias_fails_closed() -> None:
    aliases = pd.DataFrame(
        [
            {"security_id": "one", "identifier_type": "ticker", "identifier_value": "ABC", "valid_from": pd.Timestamp("2020-01-01"), "valid_to": pd.Timestamp("2022-12-31"), "resolution_status": "resolved"},
            {"security_id": "two", "identifier_type": "ticker", "identifier_value": "ABC", "valid_from": pd.Timestamp("2022-01-01"), "valid_to": pd.Timestamp("2023-12-31"), "resolution_status": "resolved"},
        ]
    )
    with pytest.raises(IdentityResolutionError):
        resolve_alias(aliases, "ticker", "ABC", date(2022, 6, 1))


def test_membership_interval_boundaries_and_benign_exit_dates() -> None:
    intervals = membership_intervals(REFERENCE_ROOT, pd.Timestamp("2020-11-27"), pd.Timestamp("2025-12-31"))
    boundaries = {
        "PLLOTOS00025": ("2022-08-03", "2022-08-04"),
        "PLPGNIG00014": ("2022-11-04", "2022-11-07"),
        "PLSTSHL00012": ("2023-08-31", "2023-09-01"),
        "PLCIECH00018": ("2023-10-03", "2023-10-04"),
        "PLTIM0000016": ("2024-02-06", "2024-02-07"),
    }
    for isin, (last_member, first_nonmember) in boundaries.items():
        assert membership_at(intervals, isin, last_member)
        assert not membership_at(intervals, isin, first_nonmember)


def test_five_benign_exits_are_preserved() -> None:
    exits = load_exit_events(DATA_ROOT / "analysis" / "top60_exit_event_audit.csv")
    selected = exits.loc[exits["isin"].isin(BENIGN_EXIT_ISINS)]
    assert set(selected["isin"]) == set(BENIGN_EXIT_ISINS)
    assert selected["exit_bucket"].eq("benign corporate exits").all()
    assert selected["backtest_treatment"].notna().all()


def test_real_post_start_unresolved_members_are_exactly_the_five_exits() -> None:
    mapping = pd.read_csv(REFERENCE_ROOT / "stooq_symbol_map.csv")
    intervals = membership_intervals(REFERENCE_ROOT, pd.Timestamp("2020-11-27"), pd.Timestamp("2025-12-31"))
    post_start = mapping.loc[mapping["isin"].isin(set(intervals["isin"]))]
    unresolved = set(post_start.loc[post_start["status"].eq("missing"), "isin"])
    assert unresolved == set(BENIGN_EXIT_ISINS)

