# Pre-Phase-D market-state diagnostic — controlling v2 correction

**Status:** completed; stopped for owner review

**Controlling run:** `pre-phase-d-market-state-20260830-v2`

**Scope:** descriptive market-state laboratory around the accepted proximity/Q5 result; no Phase D execution, ML model, strategy optimization, regime filter, Phase C change, or accepted-strategy rerun

## Verdicts

| Required decision | Verdict |
|---|---|
| WIG extension/input validity | **PASS** |
| Market-state feature causality and coverage | **PASS** |
| Q5 drawdown attribution | **MIXED** |
| Frozen Phase D market-state block | **READY WITH CAVEATS** |
| Safe to proceed to Phase D0/D1 | **YES** |

Overall market-state association is **MIXED**. All 12 predefined variables pass
the frozen timing, definition and coverage gates. Only one block variable meets
the descriptive conditional-heterogeneity flag, and every selected drawdown
episode retains late or uninformative counterexamples. The complete valid block
is therefore frozen for later Phase D use without selecting a variable, tercile,
threshold, combination or ON/OFF state.

The final YES means only that the bounded pre-Phase-D evidence package is ready
for owner-reviewed Phase D0/D1 under the existing charter. It does not start
Phase D, authorize Phase D2, establish a timing strategy, or establish
deployable alpha.

## Supersession and bounded correction

The earlier v1 report and its unchanged YES verdict are superseded. V1 used
sample standard deviation instead of the intended cross-sectional IQR for
dispersion, top 12 rather than top five positive members for leadership, and an
uncentered rather than centered WIG volatility ratio. It also allowed 20
right-censored sessions into outcome-state tercile construction, documented a
test command that was not valid from the repository root, and did not directly
test several denominator, lag and missing-state invariants.

V1 remains preserved exactly in Git commit
`797a433dcd5f7fc0c2ce31baae089b64f9dfa62a` and in its immutable run folders.
The bounded source correction is commit
`471ee151aa306e3fa0a20177d0392c5fd564cb0c`. No accepted upstream artifact or
meaning was rewritten.

Before inspecting corrected results, the v2 correction plan and configuration
were written and hashed. The only permitted analytical changes were:

- `top60_return_dispersion_20` = cross-sectional linear-interpolated Q75 minus
  Q25 of usable 20-session split-adjusted member log returns;
- `top60_positive_leadership_share_20` = the sum of the top five positive
  20-session member log returns divided by the sum of all positive returns;
- `wig_volatility_ratio_20_60` = 20-session WIG volatility divided by
  60-session WIG volatility, minus one;
- outcome-conditioned terciles use only sessions with at least one joint
  proximity observation and an exact `label__open_to_open__20`; and
- aggregation proof fields are calculated, published and checked rather than
  initialized as assertions.

All other frozen formulas, lags, coverage thresholds, episode rules,
uncertainty rules and interpretation limits remain unchanged.

## Frozen identity and reproduction

- base analysis plan SHA-256:
  `ec7da3e408dfb7e247163146247ead837e8ad2352c6a70e998ae0d63581fd6d3`;
- base configuration SHA-256:
  `dff1ea399df74d273ed1ec40e9dac56d50b6fd6813db9b26858c2d7f763fbd56`;
- v2 correction plan SHA-256:
  `8916859285dd1301197b52dec10fe140583132c982564093534f2faa26e23ba1`;
- v2 configuration SHA-256:
  `9e4eb2a94f78a2ddce33805d322b6be669494f1c843d11b58914579dcb15afd1`;
- executed v2 freeze SHA-256:
  `81a9325f64ac0d4cdf8741e9e004d0da14323c432063cacbd038262fa559b875`;
- accepted Phase A v2 logical hash:
  `1332b211b076b93fde56085974f0fa65b53f1a103d47bc2c12866e41d1b8a0b7`;
- accepted strategy-test v4 logical hash:
  `7b680c44c18a469648fcb91721530e0d5483568c778249893a19f336f78a5390`;
- primary and reproduction logical hash:
  `b21793076e76f945b72fa1f37bb5a6bab85e40f7e31603ad4ca6d0d7d79a57eb`;
- reproduction audit SHA-256:
  `af9c00258de4ad331fd83e62f6ef44d862dde0315f15a008bfd8ce0d717fd827`.

The independent reproduction audit is **PASS**: all 17 table artifact names,
logical hashes and physical hashes match. The immutable primary and
reproduction summaries correctly say provisional `safe_to_proceed=NO` because
they were generated before the independent audit and source commits. The later
[reproduction audit](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2-reproduction-audit.json)
and this post-commit controlling report supply the final YES.

Evidence locations:

- [primary manifest](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/manifest.json)
- [reproduction manifest](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2-reproduction/manifest.json)
- [v2 correction plan](D:/Stock/ATS/RESEARCH/prototypes/pre_phase_d_market_state/v2_correction_plan.md)
- [v2 configuration](D:/Stock/ATS/RESEARCH/prototypes/pre_phase_d_market_state/config_v2.json)
- [executed v2 freeze](D:/Stock/ATS/RESEARCH/prototypes/pre_phase_d_market_state/plan_freeze_v2.json)

## WIG extension and input validity

The exact WIG source
`D:/Stock/data/daily/pl/wse indices/wig.txt` is pinned at SHA-256
`eb984b515e2ba6ffcdd4105605c9d205c3105a2fbb3c4c950da2afad67424735`.
Validation found 8,388 strictly chronological rows from 1991-04-16 through
2026-08-18; zero duplicate dates, nonfinite values, nonpositive OHLC values,
negative volumes or OHLC-consistency violations; and all 1,663 candidate-panel
decision dates aligned with the GPW calendar. The 1,750-row overlap with the
accepted WIG artifact is exact at the frozen tolerance, and 158 validated rows
extend it from 2026-01-02 through 2026-08-18.

The WIG extension/input verdict is **PASS**. The extension is local to this
research run; no Phase B artifact was redesigned or republished. See
[wig_validation.json](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/wig_validation.json)
and [overlap reconciliation](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/wig_overlap_reconciliation.csv).

## Frozen market-state block

Every value uses data available at the immediately preceding information-session
close and is attached to the next decision session under accepted Phase A v2
timing. The feature table has 1,663 decision sessions from 2019-12-23 through
2026-08-18. The coverage gate uses all 1,430 accepted-v4 common-period sessions.

| Variable | Valid sessions | Gate |
|---|---:|---|
| `wig_log_return_20` | 1,430 / 1,430 | PASS |
| `wig_log_return_60` | 1,430 / 1,430 | PASS |
| `wig_trend_200` | 1,430 / 1,430 | PASS |
| `wig_trend_acceleration_20_60` | 1,430 / 1,430 | PASS |
| `wig_drawdown_252` | 1,430 / 1,430 | PASS |
| `wig_downside_semivolatility_20` | 1,430 / 1,430 | PASS |
| `wig_volatility_ratio_20_60` | 1,430 / 1,430 | PASS |
| `top60_breadth_positive_60` | 1,430 / 1,430 | PASS |
| `top60_breadth_change_10` | 1,430 / 1,430 | PASS |
| `top60_return_dispersion_20` | 1,430 / 1,430 | PASS |
| `top60_average_pairwise_correlation_60` | 1,430 / 1,430 | PASS |
| `top60_positive_leadership_share_20` | 1,429 / 1,430 | PASS |

Each TOP60 cross-sectional row retains official denominator 60, usable count,
the exact excluded-member states, aggregation denominator, lag-10 aggregation
denominator where applicable, unavailable-member count and positive-observation
count where applicable. The minimum usable-member threshold is the frozen 45/60.
Correlation requires at least 45 usable members and complete 60-session member
return windows; leadership requires at least 45 usable members, complete
20-session windows and a positive-return denominator. The lone controlling
leadership null is a zero-positive-denominator state.

There are zero timing, official-denominator, unavailable-as-negative or
mechanical-duplication violations. Full evidence is in
[feature_coverage_gate.csv](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/feature_coverage_gate.csv),
[market_state_coverage.csv](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/market_state_coverage.csv),
and [market_state_features.parquet](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/market_state_features.parquet).
The optional 5%-of-252-session-high supplement passes its frozen coverage gate
but remains outside the 12-variable block.

## Accepted Q5 drawdown attribution

The accepted v4 composite NAV was read unchanged and was not rerun.

| Type/rank | Peak | Trough | Recovery | Q5 loss | Benchmark loss | Relative loss |
|---|---|---|---|---:|---:|---:|
| Absolute 1 | 2021-11-04 | 2022-09-29 | 2024-02-23 | -38.18% | -35.16% | -4.65% |
| Absolute 2 | 2024-05-20 | 2024-11-19 | 2025-03-24 | -17.75% | -15.45% | -2.72% |
| Absolute 3 | 2025-03-25 | 2025-04-07 | 2025-04-29 | -10.59% | -10.11% | -0.53% |
| Absolute 4 | 2025-07-18 | 2025-10-14 | 2026-01-02 | -9.63% | -1.76% | -8.01% |
| Relative 1 | 2020-12-21 | 2023-01-11 | 2024-02-29 | +4.10% | +20.50% | -13.61% |
| Relative 2 | 2025-01-20 | 2025-10-14 | 2026-04-13 | +3.22% | +15.81% | -10.87% |
| Relative 3 | 2024-04-25 | 2024-08-07 | 2024-12-16 | -8.97% | -3.44% | -5.73% |

All required peak-minus-20, peak, peak-plus-5/10/20, trough,
trough-plus-20 and recovery anchors are retained with information-session dates
and state values in [episode_state_anchors.csv](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/episode_state_anchors.csv).

Attribution remains **MIXED**. Every episode has at least one leading or
early-contemporaneous variable, but the warning sets differ materially:

- absolute episodes 1–4 have respectively 6, 3, 5 and 5 useful block variables;
- relative episodes 1–3 have respectively 2, 3 and 6 useful block variables;
- absolute episode 4 retains six uninformative block variables;
- relative episode 1 retains seven uninformative block variables; and
- relative episode 2 retains nine uninformative block variables.

No common market-level warning is reliably early across all episodes. The full
leading/early/late/uninformative classifications, including all counterexamples,
are in [episode_classifications.csv](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/episode_classifications.csv).

## Proximity conditional on state

The unchanged diagnostic uses `proximity_to_max_high_252`, average-tie ranks,
accepted Q5, `label__open_to_open__20`, and
`split_adjusted_price_return`. Session coverage remains 1,430 from 2020-11-27
through 2026-08-18. Outcome-conditioned tables use 1,410 label-available
sessions through 2026-07-21; the 20 right-censored sessions remain visible in
coverage with `outcome_population=false` and cannot influence tercile cutoffs.

Values below are T1 / T2 / T3. Returns are descriptive constituent/session
forward outcomes, not portfolio returns.

| Feature | Rank IC | Q5 return | Q5 − eligible | ≤ −5% | ≤ −10% |
|---|---:|---:|---:|---:|---:|
| `top60_average_pairwise_correlation_60` | .103 / .095 / .032 | 1.56% / 1.61% / 1.32% | .90% / .55% / -.23% | 25.1% / 23.2% / 25.3% | 9.4% / 8.7% / 10.9% |
| `top60_breadth_change_10` | .075 / .064 / .092 | 1.88% / 1.14% / 1.47% | .60% / .07% / .55% | 23.6% / 26.3% / 23.8% | 9.1% / 10.3% / 9.8% |
| `top60_breadth_positive_60` | .066 / .054 / .113 | .42% / 1.86% / 2.25% | .09% / .42% / .73% | 26.8% / 25.1% / 19.9% | 12.0% / 9.7% / 6.0% |
| `top60_positive_leadership_share_20` | .093 / .088 / .050 | .93% / 2.25% / 1.29% | .60% / .78% / -.15% | 26.5% / 22.6% / 24.4% | 10.1% / 8.4% / 10.5% |
| `top60_return_dispersion_20` | .105 / .078 / .047 | 1.57% / 1.69% / 1.22% | .56% / .53% / .13% | 22.4% / 24.9% / 26.4% | 8.5% / 10.1% / 10.6% |
| `wig_downside_semivolatility_20` | .115 / .054 / .061 | 1.48% / 1.99% / 1.02% | .83% / .60% / -.21% | 23.7% / 23.8% / 25.8% | 8.4% / 9.7% / 10.8% |
| `wig_drawdown_252` | .067 / .059 / .104 | .96% / 1.99% / 1.54% | .21% / .24% / .78% | 25.7% / 22.4% / 25.1% | 11.6% / 8.6% / 8.4% |
| `wig_log_return_20` | .051 / .080 / .099 | 1.34% / 1.93% / 1.21% | -.09% / .62% / .70% | 23.9% / 24.9% / 24.8% | 10.3% / 9.4% / 9.3% |
| `wig_log_return_60` | .065 / .081 / .085 | .13% / 2.53% / 1.84% | -.03% / .69% / .56% | 28.1% / 21.8% / 22.6% | 13.0% / 8.1% / 7.1% |
| `wig_trend_200` | .035 / .116 / .080 | .41% / 3.00% / 1.07% | -.18% / .84% / .56% | 27.5% / 18.8% / 26.8% | 12.4% / 7.1% / 9.0% |
| `wig_trend_acceleration_20_60` | .071 / .067 / .092 | 1.95% / 1.51% / 1.03% | .23% / .47% / .52% | 21.8% / 25.6% / 26.2% | 8.8% / 9.0% / 11.4% |
| `wig_volatility_ratio_20_60` | .058 / .083 / .090 | 1.04% / 1.02% / 2.43% | .25% / .57% / .40% | 23.7% / 27.7% / 22.3% | 9.2% / 10.9% / 9.0% |
| Optional `top60_share_within_5pct_high_252` | .042 / .067 / .121 | .40% / 2.27% / 1.78% | -.21% / .28% / 1.15% | 27.9% / 20.9% / 24.3% | 12.8% / 7.5% / 8.2% |

Only `top60_average_pairwise_correlation_60` meets the frozen block
heterogeneity flag: T3-minus-T1 IC is -0.0706 with 95% deterministic
20-session block interval [-0.1368, -0.0027], and T3-minus-T1 Q5-minus-eligible
is -1.130 percentage points with interval [-2.093, -0.205] points.

Corrected IQR dispersion does **not** meet the flag: its IC difference is
-0.0584 with interval [-0.1139, +0.0012], and Q5-minus-eligible difference is
-0.437 points with interval [-1.228, +0.367]. Top-five leadership also does
not meet the flag. The optional 5%-of-high supplement meets its descriptive
flag, but it remains outside the frozen block and cannot select it.

Downside distributions, chronological/year stability, all 20 non-overlapping
offsets and deterministic block uncertainty remain machine-readable:

- [conditional summary and downside distributions](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/conditional_summary.csv)
- [chronological/year stability](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/conditional_yearly.csv)
- [all 20 offsets](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/conditional_offsets.csv)
- [deterministic block uncertainty](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/block_uncertainty.csv)
- [frozen T3-minus-T1 flags](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/tercile_differences.csv)
- [session diagnostics and coverage](D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2/tables/proximity_session_diagnostics.csv)

No filtered portfolio, regime-filtered CAGR, optimized threshold or lookback,
chosen variable or tercile, changed proximity benchmark, or ON/OFF state was
calculated.

## Phase D block decision

Carry all 12 valid predefined numerical variables into owner-reviewed Phase D0.
Remove none for weak historical association. Keep the optional 5%-of-high
supplement separate unless the owner later amends the Phase D0 contract before
model results.

The block is **READY WITH CAVEATS**, not READY, because the accepted candidate
panel remains research-grade `split_adjusted_price_return`, excludes cash
distributions, preserves dividend price gaps, and does not prove exhaustive
authoritative split discovery; the full history is not a genuinely untouched
test; and mixed association does not establish causality, timing value, a
market mechanism or deployable alpha.

## Validation, Git preservation and stop boundary

The exact repository-root command is:

```powershell
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' -m pytest -q 'D:\Stock\ATS\RESEARCH\prototypes\pre_phase_d_market_state\tests'
```

It reports **9 passed**. The focused fixtures now cover centered volatility
ratio, IQR dispersion, top-five leadership, preceding-information-session lag,
official denominator 60, missing members not counted as negatives, the 45/60
boundary, wrong-denominator rejection, calculated missing-state violations and
right-censored outcome exclusion.

The v1 evidence commit and bounded v2 source commit contain only this diagnostic
scope. Pre-existing roadmap, Phase D charter and environment-repair work remain
unmodified and uncommitted by this task. Exact commands, environment/Git state,
input hashes and code fingerprints are retained in the immutable v2 run.

**Stop for owner review. Do not start Phase D.**
