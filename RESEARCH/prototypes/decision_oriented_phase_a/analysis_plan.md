# Frozen decision-oriented Phase A analysis plan

Frozen before inspection of the extended-panel results on 2026-08-20.

## Scope and sample

- Use the completed Phase A pipeline and its official point-in-time WIG20 plus
  mWIG40 denominator.
- Extend the configured end date from 2025-12-31 to the latest validated common
  local Stooq/WIG session supported by official membership snapshots, initially
  proposed as 2026-08-18 and subject only to pre-analysis input validation.
- Preserve the Phase A decision timestamp, feature timestamps, feature
  definitions, label definitions, official denominator, missing states, and
  3/5/10/20-session horizons.
- Retain the trusted run unchanged. Write the extension run beneath
  `D:/Stock/data/ATS/decision_oriented_phase_a/runs` via the pipeline's explicit
  destination override.
- Report diagnostic gross equal-weight returns, never portfolio or strategy
  returns.

## 1. Medium-term momentum

- Feature: registered `momentum_12_1` and its session cross-sectional rank.
- Buckets: fixed Phase A quintiles Q1 through Q5, where Q1 is weakest and Q5
  strongest.
- Report mean forward return, constituent observations, sessions, rank IC,
  Q5-Q1, and Q5-Q4 for each horizon overall and by calendar year.
- Diagnose whether Q4 exceeding Q5 is repeated across years or concentrated in
  one period. Do not select a horizon or quantile.

## 2. Strong-stock pullback

Run the same analysis separately under two frozen definitions of established
strength:

1. raw `momentum_12_1 > 0`;
2. `momentum_12_1_rank > 0.5` within the session.

Within each condition, use the stock's registered `return_5` and three fixed,
economically interpretable buckets:

- deep pullback: `return_5 <= -0.05`;
- mild pullback: `-0.05 < return_5 < 0`;
- no pullback/positive: `return_5 >= 0`.

Report bucket mean `return_5`, forward returns, observations, sessions, and
calendar-year stability for all four horizons. The directional contrast is deep
pullback minus no-pullback/positive. No threshold will be changed.

## 3. Proximity to high

- Single definition: at decision session `t`, use the latest available close
  from the prior source session divided by the maximum close over the trailing
  252 official WIG sessions ending on that source session. Thus the latest
  available close is included in the trailing high, and only information known
  before the decision is used.
- Require the full 252-session history and exact session alignment; otherwise
  mark the feature ineligible.
- Standalone: fixed cross-sectional proximity quintiles and rank IC.
- Conditional: session-level partial rank association after linear removal of
  momentum rank, plus a fixed 3-by-3 table using momentum and proximity rank
  terciles.
- Report overall and calendar-year results for 3/5/10/20 sessions.

## 4. Relative volume and volatility

- Use registered `relative_volume_20` and `realized_volatility_20` ranks.
- Report fixed quintile forward returns, rank IC, Q5-Q1, observations, and
  sessions overall and by year for every horizon.
- Judge standalone shape and whether stable tail separation makes either more
  useful as a future conditioning variable. Do not construct a strategy.

## 5. Missing-member sensitivity

Use the official count as denominator and group decision sessions by usable
price count:

- all dates;
- 60/60;
- 58-59/60;
- 57/60.

Report sessions, official rows, usable rows, feature/label-eligible rows,
missing reasons, and momentum IC/Q1-Q5/Q4/Q5 diagnostics by horizon. Also show
coverage composition by calendar year. Treat differences descriptively because
coverage and calendar period are confounded.

Assess whether the five missing histories justify targeted reconstruction using
their share of official rows/sessions, concentration by year, and whether
low-coverage results differ enough to affect period conclusions. Do not impute
unobserved returns.

## Secondary uncertainty

- For overall rank IC and the principal spread/contrast series, retain a HAC
  interval with lag equal to the forward horizon and a deterministic 20-session
  moving-block bootstrap interval with 1,000 resamples.
- Present intervals as secondary robustness checks. Do not lead with p-values,
  q-values, or significance labels.

## Decision classifications

Classify each requested row as exactly one of `PROMISING`, `WEAK`,
`NOT SUPPORTED`, or `DATA-CONFOUNDED`, based on economic magnitude,
monotonicity, year stability, and sample sufficiency. Preserve null and adverse
results.
