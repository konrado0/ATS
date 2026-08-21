from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class SimulationResult:
    equity: pd.DataFrame
    trades: pd.DataFrame


def weekly_targets(features: pd.DataFrame, top_n: int = 10) -> dict[pd.Timestamp, list[str]]:
    valid = features.dropna(subset=["momentum_12_1"]).copy()
    valid["week"] = valid["timestamp"].dt.to_period("W-FRI")
    signal_dates = valid.groupby("week")["timestamp"].max()
    targets: dict[pd.Timestamp, list[str]] = {}
    for signal_date in signal_dates:
        cross_section = valid.loc[valid["timestamp"] == signal_date]
        targets[signal_date] = cross_section.nlargest(top_n, "momentum_12_1")["security_id"].tolist()
    return targets


def simulate(
    prices: pd.DataFrame,
    targets: dict[pd.Timestamp, list[str]],
    initial_cash: float = 1_000_000.0,
    commission_bps: float = 10.0,
    slippage_bps: float = 15.0,
) -> SimulationResult:
    prices = prices.sort_values(["timestamp", "security_id"])
    sessions = pd.Index(sorted(prices["timestamp"].unique()))
    opens = prices.pivot(index="timestamp", columns="security_id", values="open").reindex(sessions)
    closes = prices.pivot(index="timestamp", columns="security_id", values="close").reindex(sessions)
    execution_targets: dict[pd.Timestamp, list[str]] = {}
    for signal_date, securities in targets.items():
        location = sessions.searchsorted(signal_date, side="right")
        if location < len(sessions):
            execution_targets[pd.Timestamp(sessions[location])] = securities

    cash = initial_cash
    holdings: dict[str, float] = {}
    last_prices: dict[str, float] = {}
    trades: list[dict] = []
    equity_rows: list[dict] = []
    commission = commission_bps / 10_000
    slippage = slippage_bps / 10_000

    for session in sessions:
        open_row = opens.loc[session]
        close_row = closes.loc[session]
        for security, value in close_row.dropna().items():
            last_prices[security] = float(value)

        if session in execution_targets:
            selected = [security for security in execution_targets[session] if pd.notna(open_row.get(security))]
            mark_value = cash + sum(quantity * float(open_row.get(security, last_prices.get(security, np.nan))) for security, quantity in holdings.items() if pd.notna(open_row.get(security, last_prices.get(security, np.nan))))
            target_weight = 0.995 / len(selected) if selected else 0.0
            all_securities = set(holdings) | set(selected)
            for security in sorted(all_securities):
                raw_price = open_row.get(security)
                if pd.isna(raw_price):
                    continue
                current_quantity = holdings.get(security, 0.0)
                target_quantity = mark_value * target_weight / float(raw_price) if security in selected else 0.0
                quantity = target_quantity - current_quantity
                if abs(quantity) < 1e-12:
                    continue
                fill_price = float(raw_price) * (1 + slippage if quantity > 0 else 1 - slippage)
                notional = quantity * fill_price
                fee = abs(notional) * commission
                cash -= notional + fee
                holdings[security] = target_quantity
                if abs(target_quantity) < 1e-12:
                    holdings.pop(security, None)
                trades.append({"timestamp": session, "security_id": security, "quantity": quantity, "fill_price": fill_price, "commission": fee, "cash_after": cash})

        market_value = sum(quantity * last_prices.get(security, 0.0) for security, quantity in holdings.items())
        equity_rows.append({"timestamp": session, "cash": cash, "market_value": market_value, "equity": cash + market_value, "positions": len(holdings)})

    return SimulationResult(pd.DataFrame(equity_rows), pd.DataFrame(trades))
