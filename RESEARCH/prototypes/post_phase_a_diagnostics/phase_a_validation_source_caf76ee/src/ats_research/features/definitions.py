from __future__ import annotations

import pandas as pd
import polars as pl

from ats_research.features.registry import feature, feature_specs


@feature("momentum_12_1", 1, "daily", "252 market sessions, excluding most recent 21", ("close", "session_calendar"))
def momentum_12_1_expr() -> pl.Expr:
    return pl.col("close").shift(21).over("security_id") / pl.col("close").shift(252).over("security_id") - 1.0


@feature("return_5", 1, "daily", "5 market sessions", ("close", "session_calendar"))
def return_5_expr() -> pl.Expr:
    return pl.col("close") / pl.col("close").shift(5).over("security_id") - 1.0


@feature("realized_volatility_20", 1, "daily", "20 consecutive close-to-close returns", ("close", "session_calendar"))
def realized_volatility_20_expr() -> pl.Expr:
    return pl.col("_return_1").rolling_std(window_size=20, min_samples=20).over("security_id")


@feature("relative_volume_20", 1, "daily", "current volume divided by 20-session mean minus one", ("volume", "session_calendar"))
def relative_volume_20_expr() -> pl.Expr:
    return pl.col("volume") / pl.col("volume").rolling_mean(window_size=20, min_samples=20).over("security_id") - 1.0


@feature("wig_trend_200", 1, "daily", "WIG close divided by 200-session mean minus one", ("WIG.close", "session_calendar"))
def wig_trend_200_expr() -> pl.Expr:
    return pl.col("close") / pl.col("close").rolling_mean(window_size=200, min_samples=200) - 1.0


def compute_polars(session_grid: pd.DataFrame, wig: pd.DataFrame) -> pd.DataFrame:
    grid = pl.from_pandas(session_grid[["security_id", "session_date", "close", "volume", "event_ts", "available_ts"]]).sort(["security_id", "session_date"])
    grid = grid.with_columns((pl.col("close") / pl.col("close").shift(1).over("security_id") - 1.0).alias("_return_1"))
    specs = {spec.name: spec for spec in feature_specs()}
    grid = grid.with_columns(
        momentum_12_1_expr().alias(specs["momentum_12_1"].column),
        return_5_expr().alias(specs["return_5"].column),
        realized_volatility_20_expr().alias(specs["realized_volatility_20"].column),
        relative_volume_20_expr().alias(specs["relative_volume_20"].column),
    )
    wig_pl = pl.from_pandas(wig[["session_date", "close", "event_ts", "available_ts"]]).sort("session_date").with_columns(
        wig_trend_200_expr().alias(specs["wig_trend_200"].column)
    ).select(
        "session_date",
        pl.col(specs["wig_trend_200"].column),
        pl.col("event_ts").alias("wig_event_ts"),
        pl.col("available_ts").alias("wig_available_ts"),
    )
    result = grid.join(wig_pl, on="session_date", how="left").drop("_return_1")
    return result.to_pandas()


def compute_pandas_reference(session_grid: pd.DataFrame, wig: pd.DataFrame) -> pd.DataFrame:
    result = session_grid[["security_id", "session_date", "close", "volume", "event_ts", "available_ts"]].copy()
    result = result.sort_values(["security_id", "session_date"]).reset_index(drop=True)
    group = result.groupby("security_id", sort=False)
    specs = {spec.name: spec for spec in feature_specs()}
    result[specs["momentum_12_1"].column] = group["close"].shift(21) / group["close"].shift(252) - 1.0
    result[specs["return_5"].column] = result["close"] / group["close"].shift(5) - 1.0
    ret1 = result["close"] / group["close"].shift(1) - 1.0
    result[specs["realized_volatility_20"].column] = ret1.groupby(result["security_id"], sort=False).rolling(20, min_periods=20).std().reset_index(level=0, drop=True)
    rolling_volume = group["volume"].rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
    result[specs["relative_volume_20"].column] = result["volume"] / rolling_volume - 1.0
    wig_ref = wig[["session_date", "close", "event_ts", "available_ts"]].sort_values("session_date").copy()
    wig_ref[specs["wig_trend_200"].column] = wig_ref["close"] / wig_ref["close"].rolling(200, min_periods=200).mean() - 1.0
    wig_ref = wig_ref.rename(columns={"event_ts": "wig_event_ts", "available_ts": "wig_available_ts"})
    return result.merge(wig_ref[["session_date", specs["wig_trend_200"].column, "wig_event_ts", "wig_available_ts"]], on="session_date", how="left", validate="many_to_one")


def feature_columns() -> list[str]:
    return [spec.column for spec in feature_specs()]


def cross_sectional_feature_columns() -> list[str]:
    return [spec.column for spec in feature_specs() if spec.name != "wig_trend_200"]


def regime_feature_column() -> str:
    return next(spec.column for spec in feature_specs() if spec.name == "wig_trend_200")
