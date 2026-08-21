from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def pct(value: float) -> str:
    return "—" if pd.isna(value) else f"{100 * value:.2f}%"


def number(value: float) -> str:
    return "—" if pd.isna(value) else f"{value:.3f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=Path, required=True)
    args = parser.parse_args()
    root = args.tables.resolve()

    q = pd.read_csv(root / "momentum_quintiles.csv")
    ic = pd.read_csv(root / "momentum_rank_ic.csv")
    annual_q = q[q.period_type.eq("calendar_year")].pivot(
        index=["horizon_sessions", "period"], columns="quantile", values="mean_forward_return"
    ).reset_index()
    annual_q.columns = ["horizon", "year", "Q1", "Q2", "Q3", "Q4", "Q5"]
    annual_ic = ic[ic.period_type.eq("calendar_year")][["horizon_sessions", "period", "mean_rank_ic", "sessions"]]
    annual = annual_q.merge(
        annual_ic, left_on=["horizon", "year"], right_on=["horizon_sessions", "period"], how="left"
    ).drop(columns=["horizon_sessions", "period"])
    for column in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
        annual[column] = annual[column].map(pct)
    annual["IC"] = annual["mean_rank_ic"].map(number)
    annual["year"] = annual.apply(
        lambda row: f"{int(row.year)} (partial)" if int(row.year) in {2020, 2026} else str(int(row.year)), axis=1
    )
    print("\nMOMENTUM_ANNUAL\n")
    print(annual[["horizon", "year", "Q1", "Q2", "Q3", "Q4", "Q5", "IC", "sessions"]].to_markdown(index=False))

    pull = pd.read_csv(root / "strong_stock_pullback_contrasts.csv")
    print("\nPULLBACK_ANNUAL_CONTRAST\n")
    annual_pull = pull[pull.period_type.eq("calendar_year")].copy()
    annual_pull["difference"] = annual_pull.mean_return_difference.map(pct)
    pivot = annual_pull.pivot(index=["condition", "horizon_sessions"], columns="period", values="difference").reset_index()
    print(pivot.to_markdown(index=False))

    proxq = pd.read_csv(root / "proximity_quintiles.csv")
    proxi = pd.read_csv(root / "proximity_rank_ic.csv")
    partial = pd.read_csv(root / "proximity_partial_rank_ic.csv")
    pq = proxq[proxq.period_type.eq("calendar_year")].pivot(
        index=["horizon_sessions", "period"], columns="proximity_quintile", values="mean_forward_return"
    ).reset_index()
    pq["Q5-Q1"] = pq[5] - pq[1]
    pi = proxi[proxi.period_type.eq("calendar_year")][["horizon_sessions", "period", "mean_rank_ic"]]
    pp = partial[partial.period_type.eq("calendar_year")][["horizon_sessions", "period", "mean_partial_rank_ic", "sessions"]]
    pa = pq.merge(pi, on=["horizon_sessions", "period"]).merge(pp, on=["horizon_sessions", "period"])
    pa["Q5-Q1"] = pa["Q5-Q1"].map(pct)
    pa["IC"] = pa.mean_rank_ic.map(number)
    pa["partial IC"] = pa.mean_partial_rank_ic.map(number)
    pa["year"] = pa.period.astype(int).map(lambda year: f"{year} (partial)" if year in {2020, 2026} else str(year))
    print("\nPROXIMITY_ANNUAL\n")
    print(pa[["horizon_sessions", "year", "Q5-Q1", "IC", "partial IC", "sessions"]].to_markdown(index=False))

    feature_spread = pd.read_csv(root / "relative_volume_volatility_contrasts.csv")
    feature_ic = pd.read_csv(root / "relative_volume_volatility_rank_ic.csv")
    fs = feature_spread[feature_spread.period_type.eq("calendar_year")][
        ["feature", "horizon_sessions", "period", "mean_return_difference"]
    ].merge(
        feature_ic[feature_ic.period_type.eq("calendar_year")][
            ["feature", "horizon_sessions", "period", "mean_rank_ic"]
        ],
        on=["feature", "horizon_sessions", "period"],
    )
    fs["cell"] = fs.apply(lambda row: f"{pct(row.mean_return_difference)} / {number(row.mean_rank_ic)}", axis=1)
    fp = fs.pivot(index=["feature", "horizon_sessions"], columns="period", values="cell").reset_index()
    print("\nFEATURE_ANNUAL_SPREAD_IC\n")
    print(fp.to_markdown(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
