# Pre-Phase-D market-state diagnostic

**Status:** completed; stopped for owner review  
**Run:** `pre-phase-d-market-state-20260830-v1`  
**Scope:** descriptive market-state laboratory around the accepted proximity/Q5 result; no Phase D execution, ML, strategy optimization, regime filter, Phase C change, or portfolio rerun

## Verdicts

| Required decision | Verdict |
|---|---|
| WIG extension/input validity | **PASS** |
| Market-state feature causality and coverage | **PASS** |
| Q5 drawdown attribution | **MIXED** |
| Frozen Phase D market-state block | **READY WITH CAVEATS** |
| Safe to proceed to Phase D0/D1 | **YES** |

Overall descriptive evidence is **MIXED**. All 12 predefined numerical block
variables are causal and sufficiently covered, but only two satisfy the frozen
conditional-heterogeneity flag. Every selected episode has at least one leading
or early-contemporaneous variable, while many episode-variable pairs are late or
uninformative. This supports carrying the complete valid block into Phase D; it
does not support a market-timing rule.

The YES verdict authorizes only owner-reviewed Phase D0 planning and Phase D1
fixture/machinery work under the existing charter. It does not start either
phase, authorize Phase D2, or convert any state into ON/OFF.

## Frozen identity and reproduction

The plan and configuration were written and hashed before results:

- analysis plan SHA-256: `ec7da3e408dfb7e247163146247ead837e8ad2352c6a70e998ae0d63581fd6d3`;
- configuration SHA-256: `dff1ea399df74d273ed1ec40e9dac56d50b6fd6813db9b26858c2d7f763fbd56`;
- accepted Phase A v2 logical hash: `1332b211b076b93fde56085974f0fa65b53f1a103d47bc2c12866e41d1b8a0b7`;
- accepted strategy-test v4 logical hash: `7b680c44c18a469648fcb91721530e0d5483568c778249893a19f336f78a5390`;
- primary diagnostic logical hash: `7c47d2cbd8aba1158b2c61ef87fe6f0efa74c0b58aab3e934c4ff52872e689a3`;
- reproduction diagnostic logical hash: `7c47d2cbd8aba1158b2c61ef87fe6f0efa74c0b58aab3e934c4ff52872e689a3`;
- reproduction audit SHA-256: `3acf8b98d2fdb8fdae4e488c8b1e9c30a0ad6851c690212d0f85de658deab3cf`.

The independent reproduction audit is **PASS**. All 17 machine-readable table
artifacts match logically and physically. The primary summary's null
`reproduction_logical_match` is a pre-reproduction field; the later immutable
[reproduction audit](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1-reproduction-audit.json)
is controlling for the final YES verdict.

Primary and reproduction:

- [primary manifest](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/manifest.json)
- [reproduction manifest](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1-reproduction/manifest.json)
- [frozen plan](D:/Stock/ATS/RESEARCH/prototypes/pre_phase_d_market_state/analysis_plan.md)
- [frozen configuration](D:/Stock/ATS/RESEARCH/prototypes/pre_phase_d_market_state/config.json)

## WIG extension and input validity

The exact source `D:/Stock/data/daily/pl/wse indices/wig.txt` is pinned at
SHA-256 `eb984b515e2ba6ffcdd4105605c9d205c3105a2fbb3c4c950da2afad67424735`.
Validation found:

- 8,388 strictly chronological daily WIG rows, 1991-04-16 through 2026-08-18;
- zero duplicate dates, nonfinite values, nonpositive OHLC values, negative
  volumes, or OHLC consistency violations;
- all 1,663 official candidate-panel decision dates aligned to the WIG calendar;
- 1,750 accepted-artifact overlap rows with zero OHLCV differences at the
  frozen tolerance; and
- 158 validated extension rows, 2026-01-02 through 2026-08-18.

The overlap therefore reconciles exactly and the extension is **PASS**. The
validated WIG table exists only inside this research run. No Phase B artifact,
manifest, pointer, or meaning was redesigned or republished. Full details are in
[wig_validation.json](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/wig_validation.json)
and [the overlap reconciliation](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/wig_overlap_reconciliation.csv).

## Frozen market-state block

Every feature value is computed through the immediately preceding WIG session
close and then attached to the next decision session. The output covers 1,663
decision sessions from 2019-12-23 through 2026-08-18. The controlling coverage
gate uses all 1,430 accepted-v4 common-period sessions from 2020-11-27 through
2026-08-18.

| Variable | Controlling valid sessions | Valid fraction | Gate |
|---|---:|---:|---|
| `wig_log_return_20` | 1,430 / 1,430 | 100.00% | PASS |
| `wig_log_return_60` | 1,430 / 1,430 | 100.00% | PASS |
| `wig_trend_200` | 1,430 / 1,430 | 100.00% | PASS |
| `wig_trend_acceleration_20_60` | 1,430 / 1,430 | 100.00% | PASS |
| `wig_drawdown_252` | 1,430 / 1,430 | 100.00% | PASS |
| `wig_downside_semivolatility_20` | 1,430 / 1,430 | 100.00% | PASS |
| `wig_volatility_ratio_20_60` | 1,430 / 1,430 | 100.00% | PASS |
| `top60_breadth_positive_60` | 1,430 / 1,430 | 100.00% | PASS |
| `top60_breadth_change_10` | 1,430 / 1,430 | 100.00% | PASS |
| `top60_return_dispersion_20` | 1,430 / 1,430 | 100.00% | PASS |
| `top60_average_pairwise_correlation_60` | 1,430 / 1,430 | 100.00% | PASS |
| `top60_positive_leadership_share_20` | 1,429 / 1,430 | 99.93% | PASS |

There are zero timing, denominator, unavailable-as-negative, or mechanical-
duplication failures. Across the full 1,662 TOP60-computable sessions,
correlation uses 59-60 members (mean 59.88); 20-session dispersion and
leadership use 59-60 (mean 59.93); and breadth uses 59-60 (mean 59.88).
The one controlling leadership null is the frozen zero-positive-denominator
state, not a negative observation.

Every TOP60 row retains official denominator 60, usable count and exact
pipe-separated `isin:state` exclusions in
[market_state_coverage.csv](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/market_state_coverage.csv).
The numerical block and information-session lineage are in
[market_state_features.parquet](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/market_state_features.parquet).

The optional `top60_share_within_5pct_high_252` supplement is valid under its
45/60 gate but remains outside the 12-variable block. It did not select or alter
the block.

## Accepted Q5 drawdown episodes

The accepted v4 composite NAV was read unchanged. It was not rerun or modified.

| Type/rank | Peak | Trough | Recovery | Q5 loss | Benchmark loss | Relative loss |
|---|---|---|---|---:|---:|---:|
| Absolute 1 | 2021-11-04 | 2022-09-29 | 2024-02-23 | -38.18% | -35.16% | -4.65% |
| Absolute 2 | 2024-05-20 | 2024-11-19 | 2025-03-24 | -17.75% | -15.45% | -2.72% |
| Absolute 3 | 2025-03-25 | 2025-04-07 | 2025-04-29 | -10.59% | -10.11% | -0.53% |
| Absolute 4 | 2025-07-18 | 2025-10-14 | 2026-01-02 | -9.63% | -1.76% | -8.01% |
| Relative 1 | 2020-12-21 | 2023-01-11 | 2024-02-29 | +4.10% | +20.50% | -13.61% |
| Relative 2 | 2025-01-20 | 2025-10-14 | 2026-04-13 | +3.22% | +15.81% | -10.87% |
| Relative 3 | 2024-04-25 | 2024-08-07 | 2024-12-16 | -8.97% | -3.44% | -5.73% |

The authoritative episode-state table reports every predefined state value at
peak-20, peak, peak+5, peak+10, peak+20, trough, trough+20 and recovery for each
of the seven episodes: [episode_state_anchors.csv](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/episode_state_anchors.csv).
It also records decision date, preceding information date, adverse percentile
and frozen classification. No absent member or anchor was filled.

Attribution is mixed:

- absolute episode 1 had six leading/early variables and no uninformative block
  variable; dispersion, breadth change, 20-session WIG return, acceleration,
  leadership and volatility ratio supplied the early set;
- absolute episode 2 had three useful early variables, while correlation was
  uninformative and most others were late;
- absolute episode 3 had four useful variables but breadth, dispersion, WIG
  60-session return and WIG trend were uninformative;
- absolute episode 4 had five useful variables, but dispersion, WIG downside
  semivolatility, WIG drawdown, WIG trend and volatility ratio were
  uninformative; the optional high-share supplement was also uninformative;
- relative episode 1 had only three early variables and seven uninformative
  block/supplement variables;
- relative episode 2 had five useful variables but eight uninformative
  block/supplement variables; and
- relative episode 3 had five useful variables, seven late variables and one
  uninformative variable.

Thus every episode has some market-level warning, but no common warning block is
reliably early across all episodes. The complete non-selected classifications
are retained in [episode_classifications.csv](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/episode_classifications.csv),
and accepted-NAV loss attribution by state tercile is retained in
[drawdown_contribution.csv](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/drawdown_contribution.csv).

## Proximity conditional on state

The diagnostic keeps `proximity_to_max_high_252`, average-tie ranks, the
accepted Q5 definition, `label__open_to_open__20`, and
`split_adjusted_price_return`. It covers 1,430 common-period decision sessions;
the last exact 20-session label is 2026-07-21. Official denominator is always
60. Feature-usable count is 57-60; no unavailable row is made negative. Terciles
are full-sample descriptive labels only and are not Phase D features.

Values below are T1 / T2 / T3. Returns are constituent/session descriptive
forward outcomes, not portfolio returns.

| Feature | IC | Q5 return | Q5 - eligible | <= -5% | <= -10% |
|---|---:|---:|---:|---:|---:|
| `top60_average_pairwise_correlation_60` | .104 / .094 / .033 | 1.47% / 1.73% / 1.29% | 0.91% / 0.56% / -0.23% | 25.6% / 22.8% / 25.3% | 9.7% / 8.5% / 10.9% |
| `top60_breadth_change_10` | .075 / .062 / .094 | 1.88% / 1.05% / 1.56% | 0.60% / 0.04% / 0.59% | 23.6% / 26.7% / 23.4% | 9.1% / 10.7% / 9.4% |
| `top60_breadth_positive_60` | .066 / .054 / .113 | 0.42% / 1.86% / 2.25% | 0.09% / 0.42% / 0.73% | 26.8% / 25.1% / 19.9% | 12.0% / 9.7% / 6.0% |
| `top60_positive_leadership_share_20` | .103 / .073 / .056 | 0.95% / 2.30% / 1.19% | 0.70% / 0.64% / -0.10% | 26.2% / 23.1% / 24.3% | 10.2% / 8.4% / 10.4% |
| `top60_return_dispersion_20` | .136 / .063 / .033 | 1.54% / 1.85% / 1.10% | 1.03% / 0.49% / -0.28% | 21.9% / 24.9% / 27.1% | 7.6% / 9.0% / 12.8% |
| `wig_downside_semivolatility_20` | .118 / .051 / .063 | 1.38% / 2.06% / 1.05% | 0.85% / 0.59% / -0.20% | 24.5% / 23.3% / 25.6% | 8.7% / 9.4% / 10.8% |
| `wig_drawdown_252` | .068 / .060 / .104 | 0.94% / 2.01% / 1.54% | 0.22% / 0.22% / 0.80% | 25.7% / 22.5% / 25.0% | 11.5% / 8.7% / 8.3% |
| `wig_log_return_20` | .053 / .080 / .098 | 1.36% / 1.87% / 1.25% | -0.08% / 0.63% / 0.68% | 23.8% / 25.3% / 24.6% | 10.2% / 9.7% / 9.1% |
| `wig_log_return_60` | .065 / .081 / .086 | 0.13% / 2.49% / 1.89% | -0.03% / 0.69% / 0.57% | 28.3% / 21.7% / 22.4% | 13.0% / 8.1% / 7.0% |
| `wig_trend_200` | .035 / .118 / .077 | 0.46% / 2.96% / 1.05% | -0.18% / 0.84% / 0.57% | 27.4% / 18.8% / 27.1% | 12.2% / 7.2% / 9.0% |
| `wig_trend_acceleration_20_60` | .070 / .068 / .092 | 1.94% / 1.52% / 1.01% | 0.22% / 0.48% / 0.53% | 21.8% / 25.7% / 26.3% | 8.8% / 9.0% / 11.5% |
| `wig_volatility_ratio_20_60` | .056 / .083 / .091 | 1.00% / 1.06% / 2.42% | 0.22% / 0.58% / 0.41% | 23.9% / 27.5% / 22.3% | 9.3% / 10.9% / 9.0% |
| Optional: `top60_share_within_5pct_high_252` | .041 / .069 / .121 | 0.38% / 2.40% / 1.76% | -0.21% / 0.32% / 1.14% | 28.1% / 20.2% / 24.3% | 12.9% / 7.1% / 8.2% |

The fixed 20-session block intervals flag only two of the 12 block variables:

- correlation: T3-minus-T1 Q5-minus-eligible is -1.14 percentage points,
  95% block interval [-2.14, -0.13] points; the IC difference is -0.071 but its
  interval includes zero;
- dispersion: T3-minus-T1 IC is -0.103, interval [-0.175, -0.020], and
  Q5-minus-eligible is -1.31 points, interval [-2.34, -0.22].

The optional within-5%-of-high supplement also flags (+0.080 IC and +1.35
points Q5-minus-eligible, both intervals excluding zero), but by construction it
cannot select or change the final block.

Downside distributions support the dispersion contrast but are not uniform. In
dispersion T1/T2/T3 the Q5 fifth percentiles are -11.73% / -12.39% / -15.59%
and <=-10% frequencies are 7.6% / 9.0% / 12.8%. Correlation's fifth percentiles
are -13.10% / -12.28% / -14.05%, a weaker ordering. The optional high-share
supplement's fifth percentiles are -15.75% / -11.40% / -11.73%.

Chronological stability is heterogeneous. For the two flagged variables,
correlation T1 has positive Q5-minus-eligible in 5/6 represented years versus
3/7 for T3; dispersion T1 has 5/6 versus 3/7 for T3. Every group still contains
negative calendar evidence. Across the 20 non-overlapping offsets, correlation
T1/T3 is positive in 19/20 versus 5/20 offsets; dispersion T1/T3 is 20/20 versus
6/20. Offsets are schedule variants of the same history, not independent
observations.

All prespecified numerical details remain machine-readable:

- [overall and downside distributions](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/conditional_summary.csv)
- [chronological/year stability](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/conditional_yearly.csv)
- [all 20 non-overlapping offsets](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/conditional_offsets.csv)
- [deterministic block uncertainty](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/block_uncertainty.csv)
- [T3-minus-T1 frozen flags](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/tercile_differences.csv)
- [session IC, Q5 and coverage](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/tables/proximity_session_diagnostics.csv)

No filtered portfolio, regime-filtered CAGR, selected state variable/tercile,
optimized threshold, changed proximity benchmark, or ON/OFF representation was
calculated.

## Phase D block decision

Carry all 12 valid predefined numerical variables into Phase D0's owner-reviewed
feature contract. Remove none for weak association. Correlation and leadership
were clean and inexpensive under the frozen coverage gates, so neither is marked
NOT PROVEN. Keep the 5%-of-high supplement separate unless the owner later
explicitly amends the Phase D0 contract before model results; this diagnostic
does not authorize its promotion.

The block is **READY WITH CAVEATS**, not READY, because:

- the candidate panel remains research-grade `split_adjusted_price_return`, not
  a canonical Phase B or total-return publication;
- cash distributions are excluded and dividend price gaps are preserved;
- exhaustive authoritative split discovery remains NOT PROVEN under the
  accepted upstream meaning;
- the full history already influenced ATS hypothesis development and is not a
  genuinely untouched test; and
- association is mixed and does not establish causality, a market-state
  mechanism, timing value, or deployable alpha.

## Validation, environment and stop boundary

Focused fixtures: **4 passed in 1.64s**. The retained environment is Python
3.12.13, pandas 3.0.5, NumPy 1.26.4, PyArrow 25.0.0 and SciPy 1.17.1. Git HEAD
was `3b63399fe296545c240e0b5ec03031b34e31f166`; the full dirty state is retained
in [environment_git.json](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/environment_git.json).
Existing roadmap/charter/environment changes were not altered. No commit was
created.

Exact commands are retained in [commands.json](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/commands.json).
Code fingerprints are in [feature_definitions.json](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1/feature_definitions.json).

**Stop for owner review. Do not start Phase D.**
