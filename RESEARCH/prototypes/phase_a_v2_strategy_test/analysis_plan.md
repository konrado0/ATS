# Phase A v2 bounded long-only strategy test — frozen plan

This plan is frozen before deriving the strategy selections, event exposures, or
portfolio outcomes. It implements a cheap falsification test of the already
selected max-high proximity hypothesis. It does not search for a variant and it
cannot authorize deployment.

## Immutable inputs and preflight order

The exact candidate panel, its manifest, native and adjusted logical hashes, the
accepted Phase A v2 adapted panel and identity, the Dino correction supplement,
the accepted Phase C contracts, and the accepted TOP60 exit audit are pinned in
`config.json`. Mutable catalog or `latest` paths are prohibited.

The accepted Phase A v2 run remains unchanged. The historical Dino window
2024-04-11 through 2024-04-18 is recorded as incorrect. The separate correction
must pass on the confirmed 2025-07-30 to 2025-07-31 split boundary before any
strategy selection or portfolio run is permitted.

After that gate, the adapter independently recomputes the exact Phase A v2
feature, eligibility, average ranks, percentiles, and quintiles from the pinned
candidate panel and requires exact name/quintile agreement with the accepted
adapted panel. Every decision session must retain 60 official members.

## Frozen signal and schedules

For decision session `t`, the feature is prior-session close divided by the
maximum high over the exact 252 ordered sessions ending on the prior session.
Only the accepted feature-specific eligible mask may enter ranks. Ranks use
average tie ranks; percentile is rank divided by eligible count; quintile is
`ceil(percentile * 5)` clipped to 1 through 5.

Q5 is the selected long-only sleeve, all feature-eligible official members form
the primary benchmark, and Q1 is a separate long-only diagnostic. Each target
set is equal weighted. No target set, name, or missing weight is replaced or
renormalized. Previously targeted names that are no longer selected receive an
explicit zero target. A new target without an execution open retains its weight
as cash.

For each declared period, order its sessions and construct offsets 0 through 19.
Offset `o` uses `sessions[o::20]`, retaining only decisions whose exact
20-session endpoint remains inside the period. The decision session open is the
first open after the information-forming prior close. This is the exact Phase A
v2 timing and non-overlapping schedule convention; no offset is selected.

The primary period is 2020-11-27 through 2026-08-18. The expanded period is
2019-12-23 through 2026-08-18. The common period alone controls the decision.

## Frozen accounting

Feature calculation remains outside `ats_portfolio`. A thin research adapter
instantiates the accepted `DailyPortfolioEngine` without changing Phase C code,
contracts, standard runners, or accounting semantics. Each sleeve starts with
PLN 1,000,000, uses fractional quantities, pays 10 bps commission and 15 bps
adverse slippage per fill, and prohibits leverage, borrowing, shorting, and
negative cash.

Execution and valuation use source-native opens and closes under
`raw_with_explicit_actions`. Confirmed actions encountered by frozen holdings are
applied once through existing Phase C action contracts. Dino receives one 10-for-1
quantity action on 2025-07-31; adjusted signal prices are never fed into that
action path. The accepted one-session stale close policy may value a documented
short missing/non-trading interval, but stale or synthetic prices may never fill
an order. Longer unresolved valuation stays unresolved.

The result is price-only: `cash_distributions_included = false` and
`cash_dividend_price_gaps_preserved = true`. It is not total return.

Before accounting, frozen holdings are crossed against the accepted exit audit.
Only encountered suspension, terminal, merger, takeover, or delisting paths are
retained. Established terms use the smallest explicit action input. A material
unresolved held event stops the study as `NOT PROVEN`; it is never valued at zero
or carried indefinitely.

## Frozen metrics and concentration definitions

Daily after-cost NAV includes the first session return from initial cash. Report
cumulative return, CAGR, annualized volatility, return/volatility, maximum
drawdown, calendar/partial-year returns, fills, rebalances, cumulative and
annualized one-way turnover, commission/slippage/total cost in PLN and as a
fraction of initial capital, average/maximum cash weight, average holdings,
maximum single-name weight, unavailable/deferred/stale/unresolved counts, and
simple exposure/contribution concentration.

Security cash-flow contribution is negative signed fill notional minus commission
plus explicit corporate cash and terminal market value. It reconciles exactly to
terminal wealth less initial capital. LOTOS, PGNiG, and ORLEN are one known merger
lineage group so a conversion cannot create a false source/successor concentration.
To test whether one security is necessary, remove each grouped Q5-minus-benchmark
terminal contribution in turn; every resulting excess terminal amount must stay
positive. This is a deletion diagnostic, not a rerun or re-ranking.

For Q5 versus benchmark report relative terminal wealth, excess CAGR, tracking
error, information ratio, relative drawdown, yearly excess returns, and all
offset outcomes. Composite NAV is the equal-capital mean of 20 sleeves; sleeves
not yet started remain at PLN 1,000,000. Offsets are not independent samples.

The strongest-year check removes all daily returns in whichever full year
2021–2025 has the largest Q5-minus-benchmark calendar return and requires the
remaining relative terminal wealth to stay above one. It does not require the
2-point hurdle after deletion.

## Frozen decision rules

Any failed provenance, exact-name, PIT/denominator, event valuation, action
single-application, cash/position/NAV reconciliation, causality, or immutable
reproduction gate yields `NOT PROVEN` rather than an economic failure.

Only the common-period equal-sleeve composite may pass the economic gate, and it
must satisfy every threshold in `config.json`: positive Q5 price-only CAGR; at
least 2 percentage points excess CAGR; higher return/volatility than benchmark;
drawdown no more than 5 points worse; positive median excess offset and at least
12 of 20 positive offsets; positive yearly excess in at least three of 2021–2025;
positive direction without the strongest year and without each contribution
group; same expanded-period direction; and Q5 itself beating the benchmark.

Any mixed, borderline, or failed economic hurdle returns exactly
`STOP OR DESCOPE PROXIMITY STRATEGY RESEARCH`. Only a clean pass returns
`CONTINUE TO ONE BOUNDED VALIDATION STEP`.

This sample contributed to hypothesis selection. The exercise is economic
translation/falsification, not out-of-sample validation.
