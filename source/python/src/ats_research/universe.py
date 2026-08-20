from __future__ import annotations

from pathlib import Path

import pandas as pd


BENIGN_EXIT_ISINS = frozenset({"PLLOTOS00025", "PLPGNIG00014", "PLSTSHL00012", "PLCIECH00018", "PLTIM0000016"})


class UniverseError(ValueError):
    pass


def membership_intervals(reference_root: Path, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    manifest = pd.read_csv(reference_root / "manifest.csv")
    frames: list[pd.DataFrame] = []
    for component in ("WIG20", "mWIG40"):
        files = sorted((reference_root / "snapshots" / component).glob("*.csv"), key=lambda path: path.stem)
        dated = [(pd.Timestamp(path.stem), path) for path in files]
        for index, (effective_from, path) in enumerate(dated):
            effective_to = dated[index + 1][0] - pd.Timedelta(days=1) if index + 1 < len(dated) else pd.Timestamp("2262-04-11")
            if effective_to < start or effective_from > end:
                continue
            frame = pd.read_csv(path)
            meta = manifest.loc[(manifest["index"] == component) & (pd.to_datetime(manifest["effective_date"]) == effective_from)]
            if len(meta) != 1:
                raise UniverseError(f"missing or duplicate manifest row for {path}")
            frame["effective_from"] = effective_from
            frame["effective_to"] = effective_to
            frame["universe_component"] = component
            frame["universe_id"] = "GPW_TOP60_WIG20_MWIG40"
            frame["source"] = "GPW Benchmark official portfolio"
            frame["source_id"] = str(meta.iloc[0]["source_id"])
            frame["source_path"] = path.relative_to(reference_root.parent.parent).as_posix()
            frame["raw_identifier"] = frame["isin"]
            frame["resolution_status"] = "official_isin_resolved"
            frames.append(frame)
    if not frames:
        raise UniverseError("no membership snapshots overlap requested interval")
    result = pd.concat(frames, ignore_index=True)
    keys = ["universe_component", "effective_from", "isin"]
    if result.duplicated(keys).any():
        raise UniverseError("duplicate official membership semantic keys")
    return result.sort_values(keys).reset_index(drop=True)


def load_exit_events(path: Path) -> pd.DataFrame:
    exits = pd.read_csv(path)
    actual = set(exits["isin"])
    if not BENIGN_EXIT_ISINS.issubset(actual):
        raise UniverseError(f"benign exits missing from research: {sorted(BENIGN_EXIT_ISINS - actual)}")
    if not exits.loc[exits["isin"].isin(BENIGN_EXIT_ISINS), "exit_bucket"].eq("benign corporate exits").all():
        raise UniverseError("one of the five established exits is no longer classified benign")
    for column in ["trading_suspension_from", "last_trading_date", "membership_exit_effective_date", "delisting_effective_date"]:
        exits[column] = pd.to_datetime(exits[column], errors="coerce")
    return exits


def session_membership(
    intervals: pd.DataFrame,
    sessions: pd.Series,
    vendor_resolution: pd.DataFrame,
    exits: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for session in pd.to_datetime(sessions):
        current = intervals.loc[intervals["effective_from"].le(session) & intervals["effective_to"].ge(session)].copy()
        if len(current) != 60 or current["isin"].nunique() != 60:
            raise UniverseError(f"official TOP60 is not exactly 60 unique members on {session.date()}: rows={len(current)}, unique={current['isin'].nunique()}")
        current["session_date"] = session
        rows.append(current)
    panel = pd.concat(rows, ignore_index=True)
    panel = panel.merge(vendor_resolution, on="isin", how="left", validate="many_to_one")
    exit_columns = [
        "isin", "exit_bucket", "event_type", "trading_suspension_from", "last_trading_date",
        "membership_exit_effective_date", "delisting_effective_date", "backtest_treatment",
    ]
    panel = panel.merge(exits[exit_columns], on="isin", how="left", validate="many_to_one")
    panel["corporate_exit_state"] = panel["exit_bucket"].fillna("none")
    panel["official_member_count"] = 60
    return panel.sort_values(["session_date", "universe_component", "isin"]).reset_index(drop=True)


def membership_at(intervals: pd.DataFrame, isin: str, session: str) -> bool:
    date_value = pd.Timestamp(session)
    return bool(((intervals["isin"] == isin) & intervals["effective_from"].le(date_value) & intervals["effective_to"].ge(date_value)).any())

