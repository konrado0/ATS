from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PORTFOLIOS = ("q5", "eligible_universe_benchmark", "q1")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(run: Path) -> dict[str, Any]:
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    mismatches = []
    for relative, metadata in manifest["files"].items():
        path = run / relative
        observed = sha256_file(path) if path.is_file() else None
        if observed != metadata["sha256"]:
            mismatches.append(
                {"path": relative, "expected_sha256": metadata["sha256"], "observed_sha256": observed}
            )
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "logical_payload_hash": manifest["logical_payload_hash"],
        "selection_checksums": manifest["selection_checksums"],
        "verified_files": len(manifest["files"]),
        "mismatches": mismatches,
        "manifest": manifest,
    }


def load_tables(run: Path) -> dict[str, pd.DataFrame]:
    tables = run / "tables"
    return {
        "composite_metrics": pd.read_csv(tables / "composite_metrics.csv"),
        "composite_nav": pd.read_csv(tables / "composite_nav.csv", parse_dates=["session_date"]),
        "composite_yearly": pd.read_csv(tables / "composite_yearly_metrics.csv"),
        "contributions": pd.read_parquet(tables / "contributions.parquet"),
        "daily_nav": pd.read_parquet(tables / "daily_nav.parquet"),
        "decision_sessions": pd.read_parquet(tables / "decision_sessions.parquet"),
        "economic_gate": pd.read_csv(tables / "economic_gate.csv"),
        "event_preflight": pd.read_csv(tables / "event_preflight.csv"),
        "fills": pd.read_parquet(tables / "fills.parquet"),
        "ledger": pd.read_csv(tables / "ledger_reconciliation.csv"),
        "offset_relative": pd.read_csv(tables / "offset_relative_metrics.csv"),
        "portfolio_metrics": pd.read_csv(tables / "portfolio_metrics.csv"),
        "target_weights": pd.read_parquet(tables / "target_weights.parquet"),
        "yearly": pd.read_csv(tables / "yearly_metrics.csv"),
    }


def recompute_composite_metrics(composite_nav: pd.DataFrame) -> pd.DataFrame:
    rows = []
    initial_cash = 1_000_000.0
    for (period, portfolio), nav in composite_nav.groupby(["period", "portfolio"], sort=True):
        clean = nav.dropna(subset=["nav"]).copy()
        returns = clean["daily_return"].dropna()
        sessions = len(nav)
        resolved_sessions = len(clean)
        terminal = float(nav.sort_values("session_date").iloc[-1]["nav"])
        cumulative = terminal / initial_cash - 1.0
        cagr = (terminal / initial_cash) ** (252.0 / sessions) - 1.0
        volatility = float(returns.std(ddof=1) * math.sqrt(252))
        drawdown = clean["nav"] / clean["nav"].cummax() - 1.0
        rows.append(
            {
                "period": period,
                "portfolio": portfolio,
                "sessions": sessions,
                "resolved_sessions": resolved_sessions,
                "terminal_nav": terminal,
                "cumulative_return": cumulative,
                "cagr": cagr,
                "annualized_volatility": volatility,
                "return_volatility_ratio": cagr / volatility,
                "maximum_drawdown": float(drawdown.min()),
            }
        )
    return pd.DataFrame(rows)


def independent_endpoint_audit(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    daily = tables["daily_nav"].copy()
    decisions = tables["decision_sessions"].copy()
    targets = tables["target_weights"].copy()
    fills = tables["fills"].copy()
    daily["session_date"] = pd.to_datetime(daily["session_date"])
    decisions["decision_date"] = pd.to_datetime(decisions["decision_date"])
    targets["decision_date"] = pd.to_datetime(targets["decision_date"])
    fills["timestamp"] = pd.to_datetime(fills["timestamp"])
    rows = []
    for period in sorted(daily["period"].unique()):
        calendar = pd.DatetimeIndex(sorted(daily.loc[daily["period"].eq(period), "session_date"].unique()))
        for offset in range(20):
            entry_indices = [index for index in range(offset, len(calendar), 20) if index + 20 < len(calendar)]
            if not entry_indices:
                continue
            expected_entries = [calendar[index] for index in entry_indices]
            expected_terminal = calendar[entry_indices[-1] + 20]
            for portfolio in PORTFOLIOS:
                sleeve_decisions = decisions.loc[
                    decisions["period"].eq(period)
                    & decisions["offset"].eq(offset)
                    & decisions["portfolio"].eq(portfolio)
                ]
                actual_entries = sorted(
                    sleeve_decisions.loc[
                        sleeve_decisions["decision_type"].eq("entry_rebalance"), "decision_date"
                    ].tolist()
                )
                terminal_rows = sleeve_decisions.loc[
                    sleeve_decisions["decision_type"].eq("terminal_liquidation")
                ]
                terminal_date_match = len(terminal_rows) == 1 and terminal_rows.iloc[0]["decision_date"] == expected_terminal
                endpoint_column_match = bool(
                    sleeve_decisions.loc[sleeve_decisions["decision_type"].eq("entry_rebalance")]
                    .sort_values("decision_date")["scheduled_endpoint_date"]
                    .pipe(pd.to_datetime)
                    .reset_index(drop=True)
                    .eq(pd.Series([calendar[index + 20] for index in entry_indices]))
                    .all()
                )
                sleeve_targets = targets.loc[
                    targets["period"].eq(period)
                    & targets["offset"].eq(offset)
                    & targets["portfolio"].eq(portfolio)
                ]
                positive_names = set(
                    sleeve_targets.loc[sleeve_targets["target_weight"].astype(str).ne("0"), "security_id"]
                )
                terminal_targets = sleeve_targets.loc[sleeve_targets["decision_date"].eq(expected_terminal)]
                terminal_names = set(terminal_targets["security_id"])
                terminal_targets_complete = bool(positive_names) and terminal_names == positive_names
                terminal_targets_zero = bool(len(terminal_targets)) and terminal_targets["target_weight"].astype(str).eq("0").all()
                after = daily.loc[
                    daily["period"].eq(period)
                    & daily["offset"].eq(offset)
                    & daily["portfolio"].eq(portfolio)
                    & daily["session_date"].ge(expected_terminal)
                ].sort_values("session_date")
                cash_after = bool(
                    len(after)
                    and after["nav"].notna().all()
                    and after["holdings_count"].eq(0).all()
                    and np.allclose(after["cash_weight"].astype(float), 1.0, rtol=0, atol=1e-12)
                )
                fills_after = fills.loc[
                    fills["period"].eq(period)
                    & fills["offset"].eq(offset)
                    & fills["portfolio"].eq(portfolio)
                    & fills["timestamp"].dt.tz_localize(None).dt.normalize().gt(expected_terminal)
                ]
                checks = {
                    "entry_schedule_match": actual_entries == expected_entries,
                    "entry_endpoint_column_match": endpoint_column_match,
                    "one_exact_terminal_liquidation": terminal_date_match,
                    "terminal_targets_complete": terminal_targets_complete,
                    "terminal_targets_all_zero": bool(terminal_targets_zero),
                    "cash_and_zero_holdings_from_terminal_through_period_end": cash_after,
                    "no_fills_after_terminal": fills_after.empty,
                }
                rows.append(
                    {
                        "period": period,
                        "offset": offset,
                        "portfolio": portfolio,
                        "expected_entry_decisions": len(expected_entries),
                        "expected_terminal_date": expected_terminal.date().isoformat(),
                        "terminal_zero_targets": len(terminal_targets),
                        **checks,
                        "status": "PASS" if all(checks.values()) else "FAIL",
                    }
                )
    return {
        "status": "PASS" if rows and all(row["status"] == "PASS" for row in rows) else "FAIL",
        "groups": len(rows),
        "passes": sum(row["status"] == "PASS" for row in rows),
        "rows": rows,
    }


def independent_gate(tables: dict[str, pd.DataFrame]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cm = recompute_composite_metrics(tables["composite_nav"])
    cy = tables["composite_yearly"]
    comp = tables["composite_nav"]
    relative = tables["offset_relative"]
    contributions = tables["contributions"]

    def row(period: str, portfolio: str) -> pd.Series:
        return cm.loc[cm["period"].eq(period) & cm["portfolio"].eq(portfolio)].iloc[0]

    common_q5 = row("common", "q5")
    common_bm = row("common", "eligible_universe_benchmark")
    expanded_q5 = row("expanded", "q5")
    expanded_bm = row("expanded", "eligible_universe_benchmark")
    common_offsets = relative.loc[relative["period"].eq("common")]

    yearly = cy.loc[cy["period"].eq("common")].pivot(index="year", columns="portfolio", values="return")
    yearly["excess"] = yearly["q5"] - yearly["eligible_universe_benchmark"]
    full = yearly.loc[yearly.index.isin(range(2021, 2026))]
    strongest_year = int(full["excess"].idxmax())

    no_year = comp.loc[comp["period"].eq("common") & ~comp["session_date"].dt.year.eq(strongest_year)]
    no_year_returns = no_year.pivot(index="session_date", columns="portfolio", values="daily_return")
    q5_without = (1.0 + no_year_returns["q5"].dropna()).prod()
    bm_without = (1.0 + no_year_returns["eligible_universe_benchmark"].dropna()).prod()
    relative_without = q5_without / bm_without

    common_contributions = contributions.loc[contributions["period"].eq("common")]
    grouped = common_contributions.groupby(["portfolio", "contribution_group"])["terminal_pnl_contribution"].mean()
    contribution_pivot = grouped.unstack(0, fill_value=0.0)
    terminal_excess = common_q5["terminal_nav"] - common_bm["terminal_nav"]
    deletion = {
        str(group): terminal_excess
        - (values.get("q5", 0.0) - values.get("eligible_universe_benchmark", 0.0))
        for group, values in contribution_pivot.iterrows()
    }
    minimum_deleted = min(deletion.values())

    definitions = [
        ("q5_positive_after_cost_price_only_cagr", common_q5["cagr"] > 0, common_q5["cagr"]),
        ("minimum_excess_cagr_2pp", common_q5["cagr"] - common_bm["cagr"] >= 0.02, common_q5["cagr"] - common_bm["cagr"]),
        ("q5_return_volatility_ratio_exceeds_benchmark", common_q5["return_volatility_ratio"] > common_bm["return_volatility_ratio"], common_q5["return_volatility_ratio"] - common_bm["return_volatility_ratio"]),
        ("maximum_drawdown_disadvantage_at_most_5pp", common_q5["maximum_drawdown"] >= common_bm["maximum_drawdown"] - 0.05, common_q5["maximum_drawdown"] - common_bm["maximum_drawdown"]),
        ("median_offset_positive_excess", common_offsets["relative_terminal_wealth"].median() > 1, common_offsets["relative_terminal_wealth"].median() - 1),
        ("at_least_12_positive_excess_offsets", int(common_offsets["positive_excess"].sum()) >= 12, int(common_offsets["positive_excess"].sum())),
        ("at_least_3_positive_full_years_2021_2025", int((full["excess"] > 0).sum()) >= 3, int((full["excess"] > 0).sum())),
        ("strongest_year_not_necessary", relative_without > 1, relative_without),
        ("single_security_not_necessary", minimum_deleted > 0, minimum_deleted),
        ("expanded_same_economic_direction", expanded_q5["cagr"] > 0 and expanded_q5["cagr"] > expanded_bm["cagr"], expanded_q5["cagr"] - expanded_bm["cagr"]),
        ("q5_itself_beats_benchmark", common_q5["terminal_nav"] > common_bm["terminal_nav"], common_q5["terminal_nav"] / common_bm["terminal_nav"]),
    ]
    rows = [
        {"gate": name, "status": "PASS" if bool(passed) else "FAIL", "observed": float(observed)}
        for name, passed, observed in definitions
    ]
    contribution_concentration = {}
    for portfolio in ("q5", "eligible_universe_benchmark", "q1"):
        values = contribution_pivot.get(portfolio, pd.Series(dtype=float)).astype(float)
        absolute = values.abs()
        shares = absolute / absolute.sum() if absolute.sum() else absolute
        largest_group = str(shares.idxmax()) if len(shares) else None
        contribution_concentration[portfolio] = {
            "groups": int(len(values)),
            "largest_absolute_contribution_group": largest_group,
            "largest_absolute_contribution_share": float(shares.max()) if len(shares) else None,
            "absolute_contribution_hhi": float((shares**2).sum()) if len(shares) else None,
        }
    return rows, {
        "strongest_full_year": strongest_year,
        "relative_wealth_without_strongest_year": float(relative_without),
        "minimum_excess_terminal_pln_after_single_group_deletion": float(minimum_deleted),
        "single_group_deletion_terminal_excess_pln": deletion,
        "terminal_contribution_concentration": contribution_concentration,
    }


def metric_summary(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    cm = recompute_composite_metrics(tables["composite_nav"])
    pm = tables["portfolio_metrics"]
    daily = tables["daily_nav"]
    rows = []
    for period in ("common", "expanded"):
        for portfolio in PORTFOLIOS:
            composite = cm.loc[cm["period"].eq(period) & cm["portfolio"].eq(portfolio)].iloc[0]
            sleeves = pm.loc[pm["period"].eq(period) & pm["portfolio"].eq(portfolio)]
            observations = daily.loc[daily["period"].eq(period) & daily["portfolio"].eq(portfolio)]
            rows.append(
                {
                    "period": period,
                    "portfolio": portfolio,
                    "composite_cumulative_return": float(composite["cumulative_return"]),
                    "composite_cagr": float(composite["cagr"]),
                    "composite_annualized_volatility": float(composite["annualized_volatility"]),
                    "composite_return_volatility_ratio": float(composite["return_volatility_ratio"]),
                    "composite_maximum_drawdown": float(composite["maximum_drawdown"]),
                    "offset_cumulative_return_min": float(sleeves["cumulative_return"].min()),
                    "offset_cumulative_return_median": float(sleeves["cumulative_return"].median()),
                    "offset_cumulative_return_max": float(sleeves["cumulative_return"].max()),
                    "offset_cagr_min": float(sleeves["cagr"].min()),
                    "offset_cagr_median": float(sleeves["cagr"].median()),
                    "offset_cagr_max": float(sleeves["cagr"].max()),
                    "turnover_cumulative_mean": float(sleeves["turnover_cumulative"].mean()),
                    "turnover_cumulative_min": float(sleeves["turnover_cumulative"].min()),
                    "turnover_cumulative_max": float(sleeves["turnover_cumulative"].max()),
                    "turnover_annualized_mean": float(sleeves["turnover_annualized"].mean()),
                    "turnover_annualized_min": float(sleeves["turnover_annualized"].min()),
                    "turnover_annualized_max": float(sleeves["turnover_annualized"].max()),
                    "commission_pln_equal_sleeve_mean": float(sleeves["commission_pln"].mean()),
                    "commission_drag_initial_equal_sleeve_mean": float(sleeves["commission_drag_initial"].mean()),
                    "slippage_pln_equal_sleeve_mean": float(sleeves["slippage_pln"].mean()),
                    "slippage_drag_initial_equal_sleeve_mean": float(sleeves["slippage_drag_initial"].mean()),
                    "total_cost_pln_equal_sleeve_mean": float(sleeves["total_cost_pln"].mean()),
                    "total_cost_drag_initial_equal_sleeve_mean": float(sleeves["total_cost_drag_initial"].mean()),
                    "fills_total": int(sleeves["fills"].sum()),
                    "fills_median": float(sleeves["fills"].median()),
                    "fills_min": int(sleeves["fills"].min()),
                    "fills_max": int(sleeves["fills"].max()),
                    "rebalances_total": int(sleeves["rebalances"].sum()),
                    "rebalances_median": float(sleeves["rebalances"].median()),
                    "rebalances_min": int(sleeves["rebalances"].min()),
                    "rebalances_max": int(sleeves["rebalances"].max()),
                    "average_cash_weight": float(observations["cash_weight"].mean()),
                    "maximum_cash_weight": float(observations["cash_weight"].max()),
                    "average_holdings_count": float(observations["holdings_count"].mean()),
                    "maximum_single_name_weight": float(observations["max_single_name_weight"].max()),
                    "unresolved_sleeve_sessions": int(sleeves["unresolved_sessions"].sum()),
                    "stale_sleeve_sessions": int(sleeves["stale_sessions"].sum()),
                    "rejected_sleeve_sessions": int(sleeves["rejected_sessions"].sum()),
                    "deferred_sleeve_sessions": int(sleeves["deferred_sessions"].sum()),
                }
            )
    return rows


def relative_summary(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    comp = tables["composite_nav"]
    cm = recompute_composite_metrics(comp)
    offset = tables["offset_relative"]
    result: dict[str, Any] = {}
    for period in ("common", "expanded"):
        nav = comp.loc[comp["period"].eq(period)].pivot(index="session_date", columns="portfolio", values="nav")
        returns = comp.loc[comp["period"].eq(period)].pivot(index="session_date", columns="portfolio", values="daily_return")
        relative = nav["q5"] / nav["eligible_universe_benchmark"]
        active = returns["q5"] - returns["eligible_universe_benchmark"]
        tracking = float(active.std(ddof=1) * math.sqrt(252))
        q5 = cm.loc[cm["period"].eq(period) & cm["portfolio"].eq("q5")].iloc[0]
        bm = cm.loc[cm["period"].eq(period) & cm["portfolio"].eq("eligible_universe_benchmark")].iloc[0]
        current = offset.loc[offset["period"].eq(period)]
        result[period] = {
            "relative_terminal_wealth": float(relative.dropna().iloc[-1]),
            "excess_cagr": float(q5["cagr"] - bm["cagr"]),
            "tracking_error": tracking,
            "information_ratio": float(active.mean() * 252 / tracking),
            "relative_drawdown": float((relative / relative.cummax() - 1.0).min()),
            "positive_absolute_offsets": int(current["positive_absolute"].sum()),
            "positive_excess_offsets": int(current["positive_excess"].sum()),
            "offset_relative_terminal_wealth_min": float(current["relative_terminal_wealth"].min()),
            "offset_relative_terminal_wealth_median": float(current["relative_terminal_wealth"].median()),
            "offset_relative_terminal_wealth_max": float(current["relative_terminal_wealth"].max()),
            "offset_excess_cagr_min": float(current["excess_cagr"].min()),
            "offset_excess_cagr_median": float(current["excess_cagr"].median()),
            "offset_excess_cagr_max": float(current["excess_cagr"].max()),
        }
    return result


def unresolved_diagnostics(daily: pd.DataFrame) -> dict[str, Any]:
    rows = []
    terminal_unresolved = []
    for (period, offset, portfolio), sleeve in daily.groupby(["period", "offset", "portfolio"], sort=True):
        unresolved = sleeve["valuation_status"].eq("unresolved").to_numpy()
        longest = 0
        current = 0
        for value in unresolved:
            current = current + 1 if value else 0
            longest = max(longest, current)
        terminal_resolved = bool(pd.notna(sleeve.sort_values("session_date").iloc[-1]["nav"]))
        row = {
            "period": period,
            "offset": int(offset),
            "portfolio": portfolio,
            "unresolved_sessions": int(unresolved.sum()),
            "longest_consecutive_unresolved_sessions": int(longest),
            "terminal_nav_resolved": terminal_resolved,
        }
        rows.append(row)
        if not terminal_resolved:
            terminal_unresolved.append(row)
    return {
        "status": "PASS" if not terminal_unresolved else "NOT PROVEN",
        "all_terminal_navs_resolved": not terminal_unresolved,
        "terminal_unresolved_sleeves": terminal_unresolved,
        "maximum_consecutive_unresolved_sessions": max(row["longest_consecutive_unresolved_sessions"] for row in rows),
        "sleeves": rows,
    }


def compare_reproduction(primary: dict[str, Any], reproduction: dict[str, Any]) -> dict[str, Any]:
    primary_files = primary["manifest"]["files"]
    reproduction_files = reproduction["manifest"]["files"]
    differing = sorted(
        relative
        for relative in set(primary_files) | set(reproduction_files)
        if primary_files.get(relative, {}).get("sha256") != reproduction_files.get(relative, {}).get("sha256")
    )
    logical_match = primary["logical_payload_hash"] == reproduction["logical_payload_hash"]
    selection_match = primary["selection_checksums"] == reproduction["selection_checksums"]
    return {
        "status": "PASS" if logical_match and selection_match and not differing else "FAIL",
        "logical_payload_hash_match": logical_match,
        "selection_checksums_match": selection_match,
        "physical_file_hashes_match": not differing,
        "differing_files": differing,
        "primary_logical_payload_hash": primary["logical_payload_hash"],
        "reproduction_logical_payload_hash": reproduction["logical_payload_hash"],
    }


def gate_row_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return bool(
        left["gate"] == right["gate"]
        and left["status"] == right["status"]
        and np.isclose(float(left["observed"]), float(right["observed"]), rtol=1e-12, atol=1e-12)
    )


def audit(run: Path, reproduction: Path | None) -> dict[str, Any]:
    primary = verify_manifest(run)
    tables = load_tables(run)
    independent, concentration = independent_gate(tables)
    published = tables["economic_gate"][["gate", "status", "observed"]].to_dict(orient="records")
    gate_match = all(gate_row_matches(left, right) for left, right in zip(independent, published, strict=True))
    ledger = tables["ledger"]
    events = tables["event_preflight"]
    unresolved = unresolved_diagnostics(tables["daily_nav"])
    endpoints = independent_endpoint_audit(tables)
    dino_required = int(events.loc[events["isin"].eq("PLDINPL00011"), "action_required"].sum())
    dino_applied = int(ledger["dino_applications"].sum())
    accounting_pass = (
        bool(ledger["status"].eq("PASS").all())
        and unresolved["all_terminal_navs_resolved"]
        and dino_required == dino_applied
        and endpoints["status"] == "PASS"
    )
    gate_status = {row["gate"]: row["status"] for row in independent}
    absolute_pass = gate_status["q5_positive_after_cost_price_only_cagr"] == "PASS"
    relative_pass = all(
        gate_status[name] == "PASS"
        for name in (
            "minimum_excess_cagr_2pp",
            "q5_return_volatility_ratio_exceeds_benchmark",
            "maximum_drawdown_disadvantage_at_most_5pp",
            "q5_itself_beats_benchmark",
        )
    )
    stability_pass = all(
        gate_status[name] == "PASS"
        for name in (
            "median_offset_positive_excess",
            "at_least_12_positive_excess_offsets",
            "at_least_3_positive_full_years_2021_2025",
            "strongest_year_not_necessary",
            "single_security_not_necessary",
            "expanded_same_economic_direction",
        )
    )
    all_economic = all(row["status"] == "PASS" for row in independent)
    overall = (
        "NOT PROVEN — MATERIAL EXECUTION OR DATA BLOCKER"
        if not accounting_pass
        else "CONTINUE TO ONE BOUNDED VALIDATION STEP"
        if all_economic
        else "STOP OR DESCOPE PROXIMITY STRATEGY RESEARCH"
    )
    run_summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    signal = json.loads((run / "signal_reconciliation.json").read_text(encoding="utf-8"))
    portfolio_metrics = tables["portfolio_metrics"]
    recomputed_metrics = recompute_composite_metrics(tables["composite_nav"])
    metric_columns = [
        "sessions", "resolved_sessions", "terminal_nav", "cumulative_return", "cagr", "annualized_volatility",
        "return_volatility_ratio", "maximum_drawdown",
    ]
    metric_comparison = tables["composite_metrics"].merge(
        recomputed_metrics, on=["period", "portfolio"], suffixes=("_published", "_recomputed"), validate="one_to_one"
    )
    composite_metrics_match = all(
        np.allclose(
            metric_comparison[f"{column}_published"].astype(float),
            metric_comparison[f"{column}_recomputed"].astype(float),
            rtol=0,
            atol=1e-12,
        )
        for column in metric_columns
    )
    offset_counts = portfolio_metrics.groupby(["period", "portfolio"])["offset"].nunique()
    rebalance_pivot = portfolio_metrics.pivot(index=["period", "offset"], columns="portfolio", values="rebalances")
    validation_checks = {
        "manifest_integrity": primary["status"],
        "exact_feature_rank_quintile_agreement": signal["status"],
        "composite_metrics_recomputed_from_daily_nav": "PASS" if composite_metrics_match else "FAIL",
        "official_denominator_exactly_60": "PASS" if signal["official_denominator_min"] == signal["official_denominator_max"] == 60 else "FAIL",
        "all_20_offsets_for_every_period_and_portfolio": "PASS" if bool(offset_counts.eq(20).all()) else "FAIL",
        "exact_t_plus_20_terminal_liquidation_and_cash_after": endpoints["status"],
        "common_elapsed_sessions_identical_across_portfolios": "PASS" if bool(
            portfolio_metrics.loc[portfolio_metrics["period"].eq("common"), "sessions"].eq(
                portfolio_metrics.loc[portfolio_metrics["period"].eq("common"), "sessions"].iloc[0]
            ).all()
        ) else "FAIL",
        "expanded_elapsed_sessions_identical_across_portfolios": "PASS" if bool(
            portfolio_metrics.loc[portfolio_metrics["period"].eq("expanded"), "sessions"].eq(
                portfolio_metrics.loc[portfolio_metrics["period"].eq("expanded"), "sessions"].iloc[0]
            ).all()
        ) else "FAIL",
        "identical_rebalance_schedule_across_q5_benchmark_q1": "PASS" if bool(rebalance_pivot.nunique(axis=1).eq(1).all()) else "FAIL",
        "fills_use_source_native_open": "PASS" if bool(ledger["fill_source_native_open"].all()) else "FAIL",
        "commission_exact": "PASS" if bool(ledger["commission_exact"].all()) else "FAIL",
        "slippage_exact": "PASS" if bool(ledger["slippage_exact"].all()) else "FAIL",
        "cash_conservation": "PASS" if bool(ledger["cash_conservation"].all()) else "FAIL",
        "nav_conservation": "PASS" if bool(ledger["nav_conservation"].all()) else "FAIL",
        "no_negative_cash": "PASS" if bool(ledger["no_negative_cash"].all()) else "FAIL",
        "corporate_action_single_application": "PASS" if bool(ledger["corporate_action_single_application"].all()) else "FAIL",
        "dino_required_equals_applied": "PASS" if dino_required == dino_applied else "FAIL",
        "all_terminal_navs_resolved": "PASS" if unresolved["all_terminal_navs_resolved"] else "NOT PROVEN",
        "required_event_terms_established": "PASS" if bool(
            events.loc[events["action_required"], "terms_status"].isin(
                ["confirmed_split_evidence", "established_accepted_evidence", "established_official_event_supplement"]
            ).all()
        ) else "NOT PROVEN",
    }
    verdict_matrix = [
        {"dimension": "Dino correction", "verdict": run_summary["dino_correction"]},
        {"dimension": "Signal and PIT reconciliation", "verdict": signal["status"]},
        {"dimension": "Portfolio accounting", "verdict": "PASS" if accounting_pass else "NOT PROVEN"},
        {"dimension": "Q5 absolute economics", "verdict": "PASS" if absolute_pass else "FAIL"},
        {"dimension": "Q5 benchmark-relative economics", "verdict": "PASS" if relative_pass else "FAIL"},
        {"dimension": "Stability/concentration", "verdict": "PASS" if stability_pass else "FAIL"},
        {"dimension": "Overall decision", "verdict": overall},
    ]
    result: dict[str, Any] = {
        "schema_version": "ats.phase_a_v2_strategy_test.audit.v2",
        "audit_code_sha256": sha256_file(Path(__file__).resolve()),
        "run": run.resolve().as_posix(),
        "manifest_integrity": {key: value for key, value in primary.items() if key != "manifest"},
        "independent_gate_status": "PASS" if gate_match and accounting_pass and all(row["status"] == "PASS" for row in independent) else "FAIL",
        "published_gate_exact_match": gate_match,
        "independent_economic_gate": independent,
        "final_verdict_matrix": verdict_matrix,
        "validation_checks": validation_checks,
        "metric_summary": metric_summary(tables),
        "relative_summary": relative_summary(tables),
        "concentration_diagnostics": concentration,
        "accounting": {
            "ledger_reconciliations": int(len(ledger)),
            "ledger_passes": int(ledger["status"].eq("PASS").sum()),
            "all_ledgers_pass": bool(ledger["status"].eq("PASS").all()),
            "status": "PASS" if accounting_pass else "NOT PROVEN",
            "unresolved_valuation_diagnostics": unresolved,
            "terminal_endpoint_audit": endpoints,
            "required_event_rows": int(events["action_required"].sum()),
            "required_event_rows_by_isin": {
                str(key): int(value)
                for key, value in events.loc[events["action_required"]].groupby("isin").size().items()
            },
            "required_event_terms_all_established": bool(
                events.loc[events["action_required"], "terms_status"].isin(
                    ["confirmed_split_evidence", "established_accepted_evidence", "established_official_event_supplement"]
                ).all()
            ),
            "dino_required_sleeves": dino_required,
            "dino_action_applications": dino_applied,
            "dino_required_equals_applied": dino_required == dino_applied,
        },
    }
    if reproduction is not None:
        reproduced = verify_manifest(reproduction)
        result["reproduction_manifest_integrity"] = {key: value for key, value in reproduced.items() if key != "manifest"}
        result["reproduction"] = compare_reproduction(primary, reproduced)
        result["validation_checks"]["immutable_reproduction_logical_and_physical_hashes"] = result["reproduction"]["status"]
        if result["reproduction"]["status"] != "PASS":
            result["independent_gate_status"] = "FAIL"
            result["final_verdict_matrix"][-1]["verdict"] = "NOT PROVEN — MATERIAL EXECUTION OR DATA BLOCKER"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--reproduction", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run, args.reproduction)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
