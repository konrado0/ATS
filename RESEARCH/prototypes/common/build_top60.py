from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DATA_ROOT = Path("D:/Stock/data")
START = pd.Timestamp("2020-11-27")
WARMUP_START = pd.Timestamp("2019-01-01")


def snapshot_intervals(index_name: str) -> pd.DataFrame:
    folder = DATA_ROOT / "reference" / "gpw_indices" / "snapshots" / index_name
    files = sorted(folder.glob("*.csv"), key=lambda item: item.stem)
    files = [item for item in files if pd.Timestamp(item.stem) >= START]
    frames: list[pd.DataFrame] = []
    for position, file in enumerate(files):
        frame = pd.read_csv(file)
        frame["effective_from"] = pd.Timestamp(file.stem)
        frame["effective_to"] = (
            pd.Timestamp(files[position + 1].stem) - pd.Timedelta(days=1)
            if position + 1 < len(files)
            else pd.Timestamp("2262-04-11")
        )
        frame["universe_component"] = index_name
        frames.append(frame[["isin", "company_name", "effective_from", "effective_to", "universe_component"]])
    return pd.concat(frames, ignore_index=True)


def read_stooq(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [column.strip("<>").lower() for column in frame.columns]
    frame["timestamp"] = pd.to_datetime(frame["date"].astype(str), format="%Y%m%d", errors="coerce")
    frame = frame.loc[frame["timestamp"] >= WARMUP_START]
    return frame[["timestamp", "open", "high", "low", "close", "vol"]].rename(columns={"vol": "volume"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    membership = pd.concat([snapshot_intervals("WIG20"), snapshot_intervals("mWIG40")], ignore_index=True)
    mapping = pd.read_csv(DATA_ROOT / "reference" / "gpw_indices" / "stooq_symbol_map.csv")
    usable = mapping.loc[mapping["status"].isin(["exact", "mapped_renamed", "mapped_successor"]), ["isin", "stooq_symbol", "status"]].copy()
    usable["status_priority"] = usable["status"].map({"exact": 0, "mapped_renamed": 1, "mapped_successor": 2})
    usable = usable.sort_values(["isin", "status_priority"]).drop_duplicates("isin")
    usable = usable.drop(columns="status_priority")
    membership = membership.merge(usable, on="isin", how="left", validate="many_to_one")
    membership["security_id"] = membership["isin"]
    membership["price_available"] = membership["stooq_symbol"].notna()

    price_frames: list[pd.DataFrame] = []
    missing_files: list[dict[str, str]] = []
    for row in membership[["isin", "stooq_symbol"]].drop_duplicates().itertuples(index=False):
        if pd.isna(row.stooq_symbol):
            continue
        symbol = str(row.stooq_symbol)
        path = DATA_ROOT / "daily" / "pl" / "wse stocks" / f"{symbol.lower()}.txt"
        if not path.exists() or path.stat().st_size == 0:
            missing_files.append({"isin": row.isin, "symbol": symbol, "path": str(path)})
            continue
        frame = read_stooq(path)
        frame["security_id"] = row.isin
        frame["vendor_symbol"] = symbol
        price_frames.append(frame)

    prices = pd.concat(price_frames, ignore_index=True).sort_values(["security_id", "timestamp"])
    prices["market"] = "GPW"
    prices["frequency"] = "daily"
    prices.to_parquet(args.output / "top60_prices.parquet", index=False, compression="zstd")
    membership.sort_values(["effective_from", "universe_component", "isin"]).to_parquet(
        args.output / "top60_membership.parquet", index=False, compression="zstd"
    )

    wig = read_stooq(DATA_ROOT / "daily" / "pl" / "wse indices" / "wig.txt")
    wig.to_parquet(args.output / "wig.parquet", index=False, compression="zstd")
    report = {
        "prices_rows": len(prices),
        "securities_with_prices": int(prices["security_id"].nunique()),
        "membership_rows": len(membership),
        "membership_unique_securities": int(membership["isin"].nunique()),
        "unresolved_membership_rows": int((~membership["price_available"]).sum()),
        "missing_local_files": missing_files,
        "start": str(START.date()),
        "warmup_start": str(WARMUP_START.date()),
    }
    (args.output / "top60_build_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
