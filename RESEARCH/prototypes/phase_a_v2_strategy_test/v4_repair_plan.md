# Phase A v2 bounded strategy test v4 repair plan

Frozen on 2026-08-30 before any v4 portfolio execution or result inspection.

## Scope

v4 repairs two implementation and measurement defects found in v3. It does not change the frozen Phase A v2 signal, membership denominator, eligibility, ranking, quantiles, periods, 20 offsets, equal weighting, next-open execution, 10 bps commission, 15 bps slippage, corporate-action terms, or economic hurdles.

## Exact terminal horizon contract

- A cohort may start only when its exact t+20 ordered-session endpoint is inside the declared period.
- Every entry decision records that exact scheduled endpoint.
- For each period, offset, and portfolio sleeve, the final valid cohort receives one explicit `terminal_liquidation` decision at its exact t+20 session open.
- That terminal decision emits explicit zero targets for every security ever targeted by the sleeve. No incomplete replacement cohort starts there.
- Every security held by the final cohort must have a source-native terminal-session open. Absence is a fail-closed execution blocker.
- From the terminal execution through the declared period end, the sleeve must have zero holdings, unit cash weight, resolved NAV, and no later fills.

## Annualization contract

- CAGR and annualized turnover use the full elapsed ordered-session count in the declared period for every portfolio and offset.
- Intermediate unresolved NAV observations remain visible and are counted in elapsed duration.
- `resolved_sessions` is reported separately. Volatility and drawdown continue to use resolved NAV/return observations and are not silently imputed.
- The common-period elapsed-session denominator must be identical across Q5, the eligible-universe benchmark, and Q1; the same requirement applies to the expanded period.

## Independent verification

The final audit independently reconstructs each offset schedule from the daily calendar, derives the last valid cohort's t+20 endpoint, verifies the entry endpoint column, terminal decision, complete zero-target set, cash-only post-endpoint path, and absence of later fills. Regression tests must demonstrate that post-horizon holdings fail this audit and that CAGR uses elapsed rather than resolved observations.

## Supersession

v1-v3 are preserved as immutable evidence but are not valid final economic results. v4 supersedes them only if primary and clean reproduction hashes match and the independent audit passes.
