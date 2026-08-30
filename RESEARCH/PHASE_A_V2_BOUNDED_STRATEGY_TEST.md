# Phase A v2 bounded long-only strategy test

## Overall decision

# CONTINUE TO ONE BOUNDED VALIDATION STEP

The repaired v4 test clears every data, exact-horizon, accounting,
reproducibility, and prespecified economic hurdle. On the controlling
2020-11-27 through 2026-08-18 common period, the equal-capital 20-sleeve Q5
composite earns a +15.02% after-cost price-only CAGR versus +12.39% for the
same-eligible-universe benchmark, a +2.63 percentage-point excess. Sixteen of
20 offsets have positive excess terminal wealth, all 20 Q5 offsets are positive
absolutely, three of five full years have positive excess return, and neither
the strongest year nor any single contribution group is necessary for the sign.

This is permission for one further bounded validation step. It is not deployable
alpha. The tested history contributed to selecting the hypothesis, so this is an
economic translation/falsification exercise rather than out-of-sample validation.

## v4 repair and v3 supersession

V3 is not accepted as final. Its last valid cohort had no explicit zero target
at the exact t+20 endpoint: 114 of 120 sleeves retained holdings after their
intended endpoint, for as many as 19 extra sessions. It also annualized CAGR and
turnover over resolved NAV observations, producing portfolio-dependent durations
instead of the declared period duration.

The v4 contract was frozen before execution and changes no signal, period,
offset, weighting, cost, event term, or hurdle. It:

- records the exact t+20 endpoint for every entry cohort;
- emits one final terminal liquidation per sleeve at that endpoint's
  source-native open, with explicit zeros for every previously targeted name;
- requires zero holdings and unit cash weight from that endpoint through period
  end, with no later fills;
- annualizes CAGR and turnover over the shared elapsed period sessions while
  retaining resolved observations as a separate diagnostic; and
- independently reconstructs all endpoints from the daily calendar in the final
  audit.

The audit passes 120/120 endpoint groups. Common-period elapsed duration is
1,430 sessions for Q5, benchmark, and Q1; resolved observations remain visible
at 1,419, 1,408, and 1,430 respectively. Expanded duration is 1,663 sessions
for all three portfolios, with 1,652, 1,641, and 1,663 resolved observations.

V1-v3 remain immutable evidence but none is a valid final economic result.

## Final verdict matrix

| Dimension | Verdict |
|---|---|
| Dino correction | **PASS** |
| Signal and PIT reconciliation | **PASS** |
| Exact t+20 terminal horizon | **PASS** |
| Portfolio accounting | **PASS** |
| Immutable reproduction | **PASS** |
| Q5 absolute economics | **PASS** |
| Q5 benchmark-relative economics | **PASS** |
| Stability/concentration | **PASS** |
| Overall decision | **CONTINUE TO ONE BOUNDED VALIDATION STEP** |

All 11 frozen economic checks pass. The machine-readable matrix is
`RESEARCH/prototypes/phase_a_v2_strategy_test/final_verdict_matrix.csv`.

## Frozen scope and immutable identity

Q5, the feature-eligible official TOP60 benchmark, and Q1 were run independently
for all 20 offsets with PLN 1,000,000 per sleeve, fractional quantities, 10 bps
commission, 15 bps adverse slippage, prior-close information, next eligible
source-native open execution, and source-native close valuation. Unavailable new
targets retain cash; targets are never silently renormalized.

- analysis plan SHA-256: `55e12ad580ea2c321a236f476089d9f47a08f1f59499a44b307f11f9369eaeca`;
- v4 repair plan SHA-256: `e2f228fca11f3fc08c181057aeedce2dfc95884f5e06ff19284988a7c83a1513`;
- base configuration SHA-256: `83d3df0c5c9fb30bd842612b4233963ce43d9ee292645773d0583d3558b28d2f`;
- frozen v4 overlay SHA-256: `a7f9b5937711ef8044a6b63a4c1fd5e9d47a100e3104bfa3ba2ec68609924621`;
- v4 freeze-file SHA-256: `bd78b290d49821d4cc93578383323136bdde20d27a12c15b8df51aec4eaae1de`;
- candidate manifest SHA-256: `e77ce37cb51c3a1e5608b4b2c9b112abe51635bdae1ce64db0b5aa7d4780331a`;
- candidate panel physical SHA-256: `c23ffbfc6aaab8bafd466bd980f906ec4476fd051aebcc8c0fa3b7e57a9f8c15`;
- Phase A v2 logical identity: `1332b211b076b93fde56085974f0fa65b53f1a103d47bc2c12866e41d1b8a0b7`;
- v4 strategy-test logical hash: `7b680c44c18a469648fcb91721530e0d5483568c778249893a19f336f78a5390`;
- decision-session checksum: `8c5d3454a075ec90c49434624d253ccd386d00d6dee80a1d803ebf2d72f1774c`;
- selected-name checksum: `0e9fec15075dc7979673144ec22af7e1bbe014e534d8cda3086ff0bd6c933be6`;
- target-weight checksum: `bd6b03bbef39910b4e6066cd055795138a98bf1fa1ec700a747bcbeb14739988`.

The selected-name checksum is unchanged from v3 because v4 changes accounting
endpoints, not entry selections. The run provenance names implementation commit
`b9f7afa32b5aad346fc352ba6261035100aa5dda` and exact hashes for the adapter,
accepted Phase C engine/contracts, configuration, plans, freeze, and event
supplement.

## Dino, signal, and PIT gates

The accepted Phase A v2 run remains unchanged. Its configured 2024-04-11 through
2024-04-18 Dino window is recorded as incorrect; the confirmed split boundary is
2025-07-30 to 2025-07-31. Native close changes -90.1175%, split-adjusted close
changes -1.1753%, and native price plus one 10-for-1 quantity action matches the
split-adjusted return within `1.1e-16`. Excluding the 20 straddling label
observations changes mean session rank IC by +0.000219 and Q5-minus-Q1 by
+0.002624 percentage points, without sign reversal. Dino correction: **PASS**.

The adapter independently recomputes the exact prior-close divided by trailing
252-session max-high feature, feature-specific eligibility, average tie ranks,
percentiles, and quintiles from the pinned candidate panel:

- official rows and exact joined rows: 99,780 / 99,780;
- official denominator: minimum 60, maximum 60;
- maximum feature and percentile difference: 0;
- eligibility and quintile mismatches: 0.

Signal and PIT reconciliation: **PASS**.

## Exact horizon, events, and accounting

The accepted `DailyPortfolioEngine` is used through a research-only adapter; no
accepted Phase C engine or contract code was changed. Every last valid cohort is
liquidated at its exact t+20 open, producing 120 terminal decisions and 9,845
explicit terminal zero-target rows. The independent audit derives those dates
without using the scheduler's endpoint labels and verifies 120/120 groups,
complete zero-target sets, zero holdings and 100% cash from the endpoint onward,
and no post-endpoint fills.

All 120 ledgers pass cash and NAV conservation, source-native-open fill lineage,
exact commission/slippage, single action application, and nonnegative cash.
Required sleeve-event rows are PLAY 6, Dino 48, LOTOS 80, PGNiG 40, and TIM 8;
Dino has 48 required and 48 applied actions.

PLAY remains non-executable from 2020-12-22 in the pinned panel and receives the
unchanged official PLN 39 cash settlement once on 2020-12-23, based on Iliad's
[announcement](https://www.iliad.fr/media/CP_211220_Eng_bc232d35ea.pdf),
[squeeze-out notice](https://iliad-strapi.s3.fr-par.scw.cloud/Play_Squeeze_out_notice_Eng_PL_a3e26f4977.pdf),
and [2020 financial statements](https://www.iliad.fr/media/ILIAD_DEU_2020_Eng_d1e283f4ae.pdf).

Every v4 sleeve has resolved terminal NAV. Bounded gaps remain visible rather
than filled: the longest unresolved run is 11 sessions. In the common period Q5
has 184 unresolved and 22 stale sleeve-sessions; benchmark has 404 unresolved
and 42 stale sleeve-sessions; Q1 has none. Deferred sessions are 11, 23, and 0;
rejected sessions are zero. Portfolio accounting: **PASS**.

## Primary common-period economics

All results are after costs and price-only. Cash distributions are excluded and
cash-dividend price gaps are preserved.

| Portfolio | Cumulative return | CAGR over 1,430 sessions | Annualized volatility | Return/volatility | Maximum drawdown |
|---|---:|---:|---:|---:|---:|
| Q5 | +121.22% | +15.02% | 17.91% | 0.838 | -38.18% |
| Eligible-universe benchmark | +94.04% | +12.39% | 17.44% | 0.710 | -35.44% |
| Q1 long-only control | -24.15% | -4.76% | 24.33% | -0.195 | -63.98% |

Q5 versus benchmark:

- relative terminal wealth: `1.140043`;
- excess CAGR: `+2.6261` percentage points;
- active-return volatility/tracking error: `8.7243%`;
- information ratio: `0.455`;
- relative maximum drawdown: `-13.61%`;
- offset relative-wealth range/median: `0.875` to `1.477`, median `1.141`;
- offset excess-CAGR range/median: `-2.62` to `+7.89` percentage points, median `+2.62`;
- positive Q5 absolute offsets: `20/20`;
- positive Q5 excess offsets: `16/20`.

### Common-period offset portfolios

| Off | Q5 return | Q5 CAGR | Benchmark return | Benchmark CAGR | Q1 return | Q1 CAGR | Relative wealth | Excess CAGR |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 89.73% | 11.95% | 102.11% | 13.20% | -16.18% | -3.06% | 0.939 | -1.25% |
| 1 | 105.04% | 13.49% | 103.98% | 13.38% | -15.21% | -2.87% | 1.005 | 0.10% |
| 2 | 101.17% | 13.11% | 102.96% | 13.29% | -20.77% | -4.02% | 0.991 | -0.18% |
| 3 | 106.79% | 13.66% | 105.70% | 13.55% | -20.50% | -3.96% | 1.005 | 0.11% |
| 4 | 84.48% | 11.39% | 104.14% | 13.40% | -14.20% | -2.66% | 0.904 | -2.01% |
| 5 | 123.02% | 15.18% | 101.41% | 13.13% | -18.72% | -3.59% | 1.107 | 2.05% |
| 6 | 119.56% | 14.87% | 98.33% | 12.83% | -29.80% | -6.04% | 1.107 | 2.04% |
| 7 | 134.75% | 16.23% | 96.74% | 12.67% | -27.56% | -5.52% | 1.193 | 3.56% |
| 8 | 156.13% | 18.03% | 92.65% | 12.25% | -33.93% | -7.04% | 1.330 | 5.78% |
| 9 | 159.34% | 18.29% | 86.10% | 11.57% | -32.09% | -6.59% | 1.394 | 6.72% |
| 10 | 166.15% | 18.83% | 80.25% | 10.94% | -35.83% | -7.52% | 1.477 | 7.89% |
| 11 | 158.92% | 18.25% | 84.52% | 11.40% | -29.08% | -5.88% | 1.403 | 6.85% |
| 12 | 137.48% | 16.46% | 87.38% | 11.70% | -29.04% | -5.87% | 1.267 | 4.76% |
| 13 | 97.12% | 12.70% | 85.81% | 11.54% | -27.10% | -5.42% | 1.061 | 1.17% |
| 14 | 107.77% | 13.75% | 84.43% | 11.39% | -20.19% | -3.90% | 1.127 | 2.36% |
| 15 | 118.64% | 14.78% | 89.24% | 11.90% | -10.09% | -1.86% | 1.155 | 2.88% |
| 16 | 122.24% | 15.11% | 91.50% | 12.13% | -27.44% | -5.50% | 1.161 | 2.98% |
| 17 | 71.48% | 9.97% | 95.96% | 12.59% | -29.12% | -5.89% | 0.875 | -2.62% |
| 18 | 127.40% | 15.58% | 96.24% | 12.62% | -17.86% | -3.41% | 1.159 | 2.96% |
| 19 | 137.11% | 16.43% | 91.40% | 12.12% | -28.39% | -5.71% | 1.239 | 4.31% |

Offsets are schedule variants of the same sample, not independent observations.

### Calendar and partial-year returns

| Period/year | Q5 | Benchmark | Excess | Q1 | Note |
|---|---:|---:|---:|---:|---|
| Common 2020 | +4.59% | +4.32% | +0.27% | +4.62% | partial from 2020-11-27 |
| Common 2021 | +21.36% | +26.48% | -5.13% | +21.01% | full |
| Common 2022 | -19.08% | -22.16% | +3.09% | -22.38% | full; bounded unresolved event sessions |
| Common 2023 | +29.98% | +22.02% | +7.96% | -14.73% | full |
| Common 2024 | +5.21% | -6.26% | +11.46% | -23.91% | full; strongest excess year |
| Common 2025 | +20.50% | +24.87% | -4.36% | +3.33% | full |
| Common 2026 | +34.48% | +20.76% | +13.72% | +15.12% | partial through 2026-08-18; terminal cash paths included |
| Expanded 2019 | -0.01% | +0.08% | -0.09% | +0.32% | partial from 2019-12-23 |
| Expanded 2020 | +33.59% | +5.31% | +28.28% | -7.25% | full |

Three of five full common-period years 2021-2025 have positive excess return.
Removing all 2024 daily returns leaves relative terminal wealth `1.145055`, so
the strongest year is not necessary.

## Turnover, costs, cash, and exposure

Values are equal-sleeve means unless marked total. Cost drag is cumulative cost
divided by each sleeve's initial PLN 1,000,000, not counterfactual attribution.

| Period / portfolio | Cum. turnover | Annual turnover | Commission | Slippage | Total cost / initial | Fills total | Rebalances total | Avg cash | Avg holdings | Max name |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Common Q5 | 65.707x | 11.579x | PLN 89,240 | PLN 133,863 | PLN 223,103 / 22.31% | 24,617 | 1,430 | 1.42% | 11.83 | 17.14% |
| Common benchmark | 8.224x | 1.449x | PLN 11,224 | PLN 16,838 | PLN 28,062 / 2.81% | 84,446 | 1,430 | 1.42% | 58.47 | 7.91% |
| Common Q1 | 33.283x | 5.865x | PLN 30,846 | PLN 46,269 | PLN 77,115 / 7.71% | 19,300 | 1,430 | 1.40% | 11.26 | 31.42% |
| Expanded Q5 | 73.960x | 11.207x | PLN 122,976 | PLN 184,469 | PLN 307,446 / 30.74% | 28,368 | 1,663 | 1.22% | 11.85 | 29.35% |
| Expanded benchmark | 9.670x | 1.465x | PLN 12,608 | PLN 18,914 | PLN 31,522 / 3.15% | 98,307 | 1,663 | 1.22% | 58.51 | 7.91% |
| Expanded Q1 | 38.811x | 5.881x | PLN 31,816 | PLN 47,723 | PLN 79,539 / 7.95% | 22,348 | 1,663 | 1.20% | 11.23 | 31.42% |

The increased cash means versus v3 include the mandatory cash-only remainder
after each sleeve's final exact t+20 liquidation. Daily records retain actual
NAV, cash, weights, holdings, rejected/deferred weight, and valuation state.

## Stability and concentration

- Q5's largest absolute terminal contribution group is `isin:CY1000031710`,
  9.16% of absolute contributions; HHI is 0.0303 across 92 lineage groups.
- Benchmark largest absolute contribution share is 3.49%, HHI 0.0182; Q1 is
  10.16%, HHI 0.0351.
- Removing each grouped Q5-minus-benchmark terminal contribution in turn leaves
  at least PLN 137,884.10 of positive excess terminal value.
- Maximum observed single-name weight is 17.14% in common Q5 and 29.35% in
  expanded Q5.

Stability/concentration: **PASS**.

## Secondary expanded period

The expanded 2019-12-23 through 2026-08-18 result has the same direction and
does not control the decision.

| Portfolio | Cumulative return | CAGR over 1,663 sessions | Volatility | Return/volatility | Maximum drawdown |
|---|---:|---:|---:|---:|---:|
| Q5 | +182.57% | +17.05% | 19.67% | 0.867 | -37.90% |
| Benchmark | +95.94% | +10.73% | 20.05% | 0.535 | -37.50% |
| Q1 | -32.58% | -5.80% | 28.99% | -0.200 | -63.97% |

Expanded Q5 relative terminal wealth is `1.442092`; excess CAGR is +6.32
percentage points; tracking error is 10.39%; information ratio is 0.661; and
relative drawdown is -23.28%. Nineteen of 20 offsets have positive excess
terminal wealth and all 20 Q5 offsets are positive absolutely.

### Expanded-period offset portfolios

| Off | Q5 return | Q5 CAGR | Benchmark return | Benchmark CAGR | Q1 return | Q1 CAGR | Relative wealth | Excess CAGR |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 246.43% | 20.72% | 110.17% | 11.91% | -31.40% | -5.55% | 1.648 | 8.80% |
| 1 | 254.72% | 21.15% | 107.02% | 11.66% | -29.50% | -5.16% | 1.714 | 9.49% |
| 2 | 252.33% | 21.03% | 102.68% | 11.30% | -31.93% | -5.66% | 1.738 | 9.73% |
| 3 | 190.94% | 17.57% | 93.12% | 10.49% | -36.62% | -6.68% | 1.507 | 7.08% |
| 4 | 221.14% | 19.34% | 90.31% | 10.24% | -33.67% | -6.03% | 1.687 | 9.10% |
| 5 | 195.63% | 17.85% | 91.12% | 10.31% | -32.39% | -5.76% | 1.547 | 7.54% |
| 6 | 218.34% | 19.18% | 90.80% | 10.29% | -32.54% | -5.79% | 1.668 | 8.90% |
| 7 | 244.78% | 20.63% | 94.57% | 10.61% | -22.42% | -3.77% | 1.772 | 10.02% |
| 8 | 182.03% | 17.01% | 95.51% | 10.69% | -12.43% | -1.99% | 1.443 | 6.32% |
| 9 | 234.55% | 20.08% | 93.73% | 10.54% | -35.98% | -6.54% | 1.727 | 9.54% |
| 10 | 149.56% | 14.86% | 92.86% | 10.46% | -38.96% | -7.21% | 1.294 | 4.40% |
| 11 | 195.52% | 17.84% | 94.86% | 10.64% | -34.44% | -6.20% | 1.517 | 7.21% |
| 12 | 165.18% | 15.93% | 94.88% | 10.64% | -40.48% | -7.56% | 1.361 | 5.29% |
| 13 | 109.23% | 11.84% | 96.35% | 10.77% | -33.99% | -6.10% | 1.066 | 1.07% |
| 14 | 119.87% | 12.68% | 97.31% | 10.85% | -35.16% | -6.35% | 1.114 | 1.83% |
| 15 | 137.77% | 14.02% | 93.76% | 10.54% | -40.55% | -7.58% | 1.227 | 3.48% |
| 16 | 122.05% | 12.85% | 95.87% | 10.72% | -34.54% | -6.22% | 1.134 | 2.13% |
| 17 | 94.42% | 10.60% | 96.21% | 10.75% | -26.12% | -4.48% | 0.991 | -0.15% |
| 18 | 167.47% | 16.08% | 93.84% | 10.55% | -30.09% | -5.28% | 1.380 | 5.53% |
| 19 | 149.40% | 14.85% | 93.90% | 10.56% | -38.42% | -7.08% | 1.286 | 4.30% |

## Q5 strength versus weak Q1

The common Q5-minus-Q1 CAGR contrast is +19.77 percentage points. Q5 exceeds
the benchmark by +2.63 points, while the benchmark exceeds Q1 by +17.15 points;
about 86.7% of the Q5-minus-Q1 gap is therefore associated with Q1 weakness
relative to the benchmark. The frozen continuation rule still passes because Q5
itself is positive and independently beats the benchmark after costs. Q1 is a
diagnostic, not a financed short portfolio.

## Reproducibility and validation

Primary run:
`D:/Stock/data/ATS/phase_a_v2_strategy_test/runs/phase-a-v2-strategy-test-20260830-v4`

Clean reproduction:
`D:/Stock/data/ATS/phase_a_v2_strategy_test/reproductions/phase-a-v2-strategy-test-20260830-v4`

Independent audit:
`D:/Stock/data/ATS/phase_a_v2_strategy_test/audits/phase-a-v2-strategy-test-20260830-v4-audit.json`

The reproduction matches logical hash
`7b680c44c18a469648fcb91721530e0d5483568c778249893a19f336f78a5390`,
all selection checksums, and every manifest-declared physical file hash. The
audit independently recomputes composite metrics and the 11-row gate, verifies
120/120 ledgers and endpoint groups, and passes exact-horizon, elapsed-duration,
terminal-resolution, event, and reproduction checks.

The published versus independently recomputed single-group deletion value
differed by PLN `2.33e-10` solely from floating-point aggregation order. The
audit verifier now permits relative machine-scale noise (`rtol=1e-12`,
`atol=1e-12`) while requiring identical gate names/statuses; a regression test
rejects material differences. Final independent audit: **PASS**.

Focused validation results:

- research adapter/Dino/PLAY/endpoint/audit tests: 19 passed;
- accepted Phase C contracts, golden ledgers, and state transitions: 33 passed.

Exact commands are retained in
`RESEARCH/prototypes/phase_a_v2_strategy_test/validation_commands.json`.

## Boundaries and single next validation need

This basis is not total return: `cash_distributions_included = false` and
`cash_dividend_price_gaps_preserved = true`. Absolute results may understate
investor returns, and cross-sectional dividend differences can affect relative
economics. Source-native opens are an execution proxy rather than evidence that
the opening auction could absorb the required fractional target at the assumed
25 bps cost. Authoritative exhaustive split discovery remains **NOT PROVEN**.

The single most important next validation need is **genuinely later untouched
holdout data**. The present sample helped select max-high proximity; another
variant, filter, or in-sample sensitivity would not address that dependence. Do
not implement or optimize that next step within this decision.
