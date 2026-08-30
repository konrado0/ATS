# Phase A v2 bounded long-only strategy test

## Overall decision

# CONTINUE TO ONE BOUNDED VALIDATION STEP

The exact frozen `proximity_to_max_high_252` Q5 portfolio clears every data,
accounting, reproducibility, and prespecified economic hurdle. On the controlling
2020-11-27 through 2026-08-18 common period, the equal-capital 20-sleeve Q5
composite earns a +15.43% after-cost price-only CAGR versus +12.80% for the
same-eligible-universe benchmark, a +2.63 percentage-point excess. Sixteen of
20 offsets have positive excess terminal wealth, all 20 Q5 offsets are positive
absolutely, three of five full years have positive excess return, and neither
the strongest year nor any single contribution group is necessary for the sign.

This is permission for one further bounded validation step. It is not deployable
alpha. The tested history contributed to selecting the hypothesis, so this is an
economic translation/falsification exercise rather than out-of-sample validation.

## Final verdict matrix

| Dimension | Verdict |
|---|---|
| Dino correction | **PASS** |
| Signal and PIT reconciliation | **PASS** |
| Portfolio accounting | **PASS** |
| Q5 absolute economics | **PASS** |
| Q5 benchmark-relative economics | **PASS** |
| Stability/concentration | **PASS** |
| Overall decision | **CONTINUE TO ONE BOUNDED VALIDATION STEP** |

All 11 frozen economic checks pass. The machine-readable matrix is
`RESEARCH/prototypes/phase_a_v2_strategy_test/final_verdict_matrix.csv`.

## Frozen scope and immutable identity

No feature, lookback, quintile, horizon, offset, weighting, cost, period,
execution schedule, or hurdle was changed after results. Q5, the
feature-eligible official TOP60 benchmark, and Q1 were run independently for all
20 offsets with PLN 1,000,000 per sleeve, fractional quantities, 10 bps
commission, 15 bps adverse slippage, next eligible source-native open execution,
and source-native close valuation. Departed names receive explicit zero targets;
unavailable targets retain cash.

- analysis plan SHA-256: `55e12ad580ea2c321a236f476089d9f47a08f1f59499a44b307f11f9369eaeca`;
- base configuration SHA-256: `83d3df0c5c9fb30bd842612b4233963ce43d9ee292645773d0583d3558b28d2f`;
- frozen v3 overlay SHA-256: `c1b39cf736056dc0f2130366165339a481d99cfd2a084fad3ff9fbd863c7de4e`;
- v3 freeze-file SHA-256: `98ee1125818c68caa2259b16a0b68bb2f018d1e9a9b4d9ebbf9f69c4e42357c7`;
- candidate manifest SHA-256: `e77ce37cb51c3a1e5608b4b2c9b112abe51635bdae1ce64db0b5aa7d4780331a`;
- candidate panel physical SHA-256: `c23ffbfc6aaab8bafd466bd980f906ec4476fd051aebcc8c0fa3b7e57a9f8c15`;
- Phase A v2 logical identity: `1332b211b076b93fde56085974f0fa65b53f1a103d47bc2c12866e41d1b8a0b7`;
- v3 strategy-test logical hash: `aaca0ccea49ce54ac0e62a3c5d1cf7aaaae493e9f6a44a0872eff49b132967f5`;
- decision-session checksum: `861ccd92d5909279455a647c37a62384cd90630ae481e4ad1a3d39b4573848f8`;
- selected-name checksum: `0e9fec15075dc7979673144ec22af7e1bbe014e534d8cda3086ff0bd6c933be6`;
- target-weight checksum: `a59b426a1e107522d0abcbb0c66cdd43a88a6d77e5c5814bcc8fa34e0b4bf297`.

The run records pre-run repository commit `7d3251ff48335c32bac2214333a1e74b6fefafd2`
and exact hashes for the research adapter, accepted Phase C engine/contracts,
configuration, plan, freeze, and PLAY supplement. The final scoped publication
commit is recorded at completion below.

## Dino correction gate

The accepted Phase A v2 run remains unchanged. Its configured
2024-04-11 through 2024-04-18 Dino window is recorded as incorrect. The
confirmed split boundary is 2025-07-30 to 2025-07-31.

- Native close moves from PLN 502.00 to PLN 49.61, a mechanical -90.1175% unit-price change.
- Split-adjusted close moves from PLN 50.20 to PLN 49.61, or -1.1753%.
- Native price plus one 10-for-1 quantity action matches the split-adjusted return within `1.1e-16`.
- Twenty 20-session label observations straddle the actual event.
- Mean session rank IC is +0.076779 before and +0.076998 after excluding those Dino observations, a +0.000219 shift.
- Mean session Q5-minus-Q1 is +1.480929% before and +1.483553% after exclusion, a +0.002624 percentage-point shift.

There is no sign reversal or practical undermining. Dino correction: **PASS**.

## Signal and PIT reconciliation

The adapter independently recomputed the exact prior-close divided by trailing
252-session max-high feature, feature-specific eligibility, average tie ranks,
percentiles, and quintiles from the pinned candidate panel.

- official rows: 99,780;
- exact joined rows: 99,780;
- official denominator: minimum 60, maximum 60;
- maximum feature difference: 0;
- eligibility mismatches: 0;
- maximum percentile difference: 0;
- quintile mismatches: 0.

Signal and PIT reconciliation: **PASS**.

## Corporate events and portfolio accounting

The research-only adapter uses the accepted `DailyPortfolioEngine`; no Phase C
code or standard runner was changed. All 120 sleeves pass cash conservation,
NAV conservation, source-native-open fill lineage, exact commission/slippage,
single action application, and nonnegative-cash reconciliation.

Required sleeve-event rows were PLAY 6, Dino 48, LOTOS 80, PGNiG 40, and TIM 8.
All use established accepted or official terms. Dino has 48 required and 48
observed applications.

The first PLAY supplement correctly established the official PLN 39 squeeze-out
effective and paid on 2020-12-23, based on Iliad's
[announcement](https://www.iliad.fr/media/CP_211220_Eng_bc232d35ea.pdf),
[squeeze-out notice](https://iliad-strapi.s3.fr-par.scw.cloud/Play_Squeeze_out_notice_Eng_PL_a3e26f4977.pdf),
and [2020 financial statements](https://www.iliad.fr/media/ILIAD_DEU_2020_Eng_d1e283f4ae.pdf).
Frozen v2 nevertheless failed because the pinned candidate has no native open on
2020-12-22; offset 10 could not execute its zero target and remained unresolved.
V3 narrowly records 2020-12-21 as the last observed native-price session,
blocks fabricated fills from 2020-12-22, and applies the unchanged PLN 39 cash
action once on 2020-12-23. V1 and v2 expanded economics are rejected and retained
only as diagnostic evidence.

Every v3 sleeve has a resolved terminal NAV. Bounded suspension/settlement gaps
remain visible rather than being filled: the longest run is 11 sessions. In the
common period Q5 has 184 unresolved and 22 stale sleeve-sessions; the benchmark
has 404 unresolved and 42 stale sleeve-sessions; Q1 has none. There are no
rejected sessions. Deferred sessions are 11 for Q5, 23 for the benchmark, and 0
for Q1. The composite is unresolved whenever any constituent sleeve is
unresolved, so unaffected offsets cannot conceal a gap. Returns bridge only
between established pre-event and settled post-event NAVs.

Portfolio accounting: **PASS**.

## Primary common-period economics

All results below are after costs and price-only. Cash distributions are not
included and cash-dividend price gaps are preserved.

| Portfolio | Cumulative return | CAGR | Annualized volatility | Return/volatility | Maximum drawdown |
|---|---:|---:|---:|---:|---:|
| Q5 | +124.39% | +15.43% | 17.95% | 0.860 | -38.18% |
| Eligible-universe benchmark | +96.04% | +12.80% | 17.48% | 0.733 | -35.44% |
| Q1 long-only control | -21.93% | -4.27% | 24.38% | -0.175 | -63.98% |

Q5 versus benchmark:

- relative terminal wealth: `1.144590`;
- excess CAGR: `+2.6302` percentage points;
- active-return volatility/tracking error: `8.7440%`;
- information ratio: `0.462`;
- relative maximum drawdown: `-13.61%`;
- offset relative-wealth range/median: `0.881` to `1.477`, median `1.130`;
- offset excess-CAGR range/median: `-2.62` to `+7.91` percentage points, median `+2.37`;
- positive Q5 absolute offsets: `20/20`;
- positive Q5 excess offsets: `16/20`.

### Common-period offset portfolios

| Off | Q5 return | Q5 CAGR | Benchmark return | Benchmark CAGR | Q1 return | Q1 CAGR | Relative wealth | Excess CAGR |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 88.18% | 11.86% | 100.47% | 13.24% | -14.62% | -2.75% | 0.939 | -1.37% |
| 1 | 106.19% | 13.69% | 102.87% | 13.48% | -13.77% | -2.58% | 1.016 | 0.22% |
| 2 | 100.88% | 13.17% | 101.56% | 13.35% | -18.73% | -3.59% | 0.997 | -0.18% |
| 3 | 104.46% | 13.52% | 103.91% | 13.58% | -19.63% | -3.78% | 1.003 | -0.06% |
| 4 | 82.25% | 11.23% | 100.84% | 13.27% | -14.81% | -2.79% | 0.907 | -2.04% |
| 5 | 119.43% | 14.95% | 97.05% | 12.89% | -20.37% | -3.94% | 1.114 | 2.07% |
| 6 | 115.37% | 14.57% | 93.98% | 12.57% | -31.79% | -6.52% | 1.110 | 2.00% |
| 7 | 131.31% | 16.03% | 93.35% | 12.51% | -29.11% | -5.88% | 1.196 | 3.53% |
| 8 | 151.18% | 17.74% | 89.29% | 12.08% | -35.21% | -7.36% | 1.327 | 5.66% |
| 9 | 159.49% | 18.42% | 85.37% | 11.66% | -32.58% | -6.71% | 1.400 | 6.76% |
| 10 | 178.44% | 19.91% | 88.56% | 12.00% | -31.20% | -6.38% | 1.477 | 7.91% |
| 11 | 174.38% | 19.60% | 91.99% | 12.36% | -24.84% | -4.91% | 1.429 | 7.24% |
| 12 | 147.09% | 17.40% | 96.59% | 12.84% | -22.16% | -4.32% | 1.257 | 4.56% |
| 13 | 104.95% | 13.57% | 94.70% | 12.65% | -20.82% | -4.03% | 1.053 | 0.92% |
| 14 | 113.38% | 14.39% | 91.67% | 12.33% | -15.07% | -2.84% | 1.113 | 2.06% |
| 15 | 125.63% | 15.52% | 96.65% | 12.85% | -4.81% | -0.86% | 1.147 | 2.68% |
| 16 | 135.08% | 16.37% | 98.42% | 13.03% | -22.82% | -4.46% | 1.185 | 3.34% |
| 17 | 77.02% | 10.66% | 100.93% | 13.28% | -25.63% | -5.08% | 0.881 | -2.62% |
| 18 | 132.41% | 16.16% | 99.79% | 13.19% | -14.79% | -2.78% | 1.163 | 2.97% |
| 19 | 140.64% | 16.88% | 92.84% | 12.47% | -25.76% | -5.11% | 1.248 | 4.40% |

Offsets are schedule variants of the same historical sample, not independent
statistical observations.

### Calendar and partial-year returns

| Period/year | Q5 | Benchmark | Excess | Q1 | Note |
|---|---:|---:|---:|---:|---|
| Common 2020 | +4.59% | +4.32% | +0.27% | +4.62% | partial from 2020-11-27 |
| Common 2021 | +21.36% | +26.48% | -5.13% | +21.01% | full |
| Common 2022 | -19.08% | -22.16% | +3.09% | -22.38% | full; bounded unresolved event sessions |
| Common 2023 | +29.98% | +22.02% | +7.96% | -14.73% | full |
| Common 2024 | +5.21% | -6.26% | +11.46% | -23.91% | full; strongest excess year |
| Common 2025 | +20.50% | +24.87% | -4.36% | +3.33% | full |
| Common 2026 | +36.41% | +22.00% | +14.41% | +18.51% | partial through 2026-08-18 |
| Expanded 2019 | -0.01% | +0.08% | -0.09% | +0.32% | partial from 2019-12-23 |
| Expanded 2020 | +33.59% | +5.31% | +28.28% | -7.25% | full |

Three of the five full common-period years 2021–2025 have positive excess
return. Removing all 2024 daily returns leaves relative terminal wealth
`1.149622`, so the strongest year is not necessary.

## Turnover, costs, cash, and exposure

Values are equal-sleeve means unless marked total. Cost drag is cumulative cost
divided by each sleeve's initial PLN 1,000,000, not a counterfactual performance
attribution.

| Period / portfolio | Cum. turnover | Annual turnover | Commission | Slippage | Total cost / initial | Fills total | Rebalances total | Avg cash | Avg holdings | Max name |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Common Q5 | 64.707x | 11.477x | PLN 87,025 | PLN 130,536 | PLN 217,562 / 21.76% | 24,377 | 1,410 | 0.68% | 11.92 | 17.14% |
| Common benchmark | 7.224x | 1.291x | PLN 9,282 | PLN 13,920 | PLN 23,202 / 2.32% | 83,246 | 1,410 | 0.68% | 58.91 | 7.91% |
| Common Q1 | 32.283x | 5.689x | PLN 30,087 | PLN 45,128 | PLN 75,215 / 7.52% | 19,060 | 1,410 | 0.66% | 11.35 | 31.42% |
| Expanded Q5 | 72.960x | 11.117x | PLN 120,148 | PLN 180,220 | PLN 300,368 / 30.04% | 28,128 | 1,643 | 0.59% | 11.93 | 29.35% |
| Expanded benchmark | 8.670x | 1.330x | PLN 10,647 | PLN 15,968 | PLN 26,615 / 2.66% | 97,107 | 1,643 | 0.58% | 58.89 | 7.91% |
| Expanded Q1 | 37.811x | 5.730x | PLN 31,141 | PLN 46,709 | PLN 77,850 / 7.78% | 22,108 | 1,643 | 0.57% | 11.30 | 31.42% |

Maximum cash weight is 100% because each offset sleeve remains entirely in cash
before its first scheduled rebalance. Decision-session records retain expected
members, feature-eligible members, selected count, excluded/missing states,
intended invested/cash weight, and rejected/deferred weight. Daily records retain
actual NAV, cash, cash weight, holdings, maximum name weight, and valuation state.

## Stability and concentration

- The Q5 largest absolute terminal contribution group is
  `isin:CY1000031710`, 9.98% of absolute contributions; absolute-contribution
  HHI is 0.0318 across 92 lineage groups.
- Benchmark largest absolute contribution share is 3.64%, HHI 0.0182; Q1 is
  10.10%, HHI 0.0347.
- Removing each grouped Q5-minus-benchmark terminal contribution in turn leaves
  at least PLN 132,919.66 of positive excess terminal value.
- Maximum observed single-name weight is 17.14% in common Q5 and 29.35% in
  expanded Q5 between rebalances. This is visible concentration, but no one
  contribution group is necessary for the positive common-period sign.

Stability/concentration: **PASS**.

## Secondary expanded period

The expanded 2019-12-23 through 2026-08-18 result has the same economic
direction and does not control the decision.

| Portfolio | Cumulative return | CAGR | Volatility | Return/volatility | Maximum drawdown |
|---|---:|---:|---:|---:|---:|
| Q5 | +186.91% | +17.44% | 19.70% | 0.885 | -37.90% |
| Benchmark | +98.04% | +11.06% | 20.08% | 0.551 | -37.50% |
| Q1 | -30.57% | -5.38% | 29.03% | -0.185 | -63.97% |

Expanded Q5 relative terminal wealth is `1.448755`; excess CAGR is +6.38
percentage points; tracking error is 10.41%; information ratio is 0.667; and
relative drawdown is -23.28%. Nineteen of 20 offsets have positive excess
terminal wealth and all 20 Q5 offsets are positive absolutely. The common period
already passes without this stronger early interval.

### Expanded-period offset portfolios

| Off | Q5 return | Q5 CAGR | Benchmark return | Benchmark CAGR | Q1 return | Q1 CAGR | Relative wealth | Excess CAGR |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 241.36% | 20.57% | 106.54% | 11.77% | -32.87% | -5.86% | 1.653 | 8.80% |
| 1 | 247.86% | 20.92% | 103.41% | 11.51% | -30.87% | -5.44% | 1.710 | 9.41% |
| 2 | 252.55% | 21.16% | 101.90% | 11.38% | -32.42% | -5.77% | 1.746 | 9.79% |
| 3 | 204.37% | 18.48% | 102.03% | 11.39% | -32.04% | -5.68% | 1.507 | 7.09% |
| 4 | 240.32% | 20.51% | 98.01% | 11.05% | -29.70% | -5.20% | 1.719 | 9.47% |
| 5 | 207.59% | 18.67% | 100.51% | 11.26% | -25.83% | -4.43% | 1.534 | 7.41% |
| 6 | 230.98% | 20.00% | 99.93% | 11.21% | -26.73% | -4.60% | 1.655 | 8.79% |
| 7 | 254.10% | 21.24% | 102.20% | 11.40% | -17.44% | -2.86% | 1.751 | 9.84% |
| 8 | 191.05% | 17.68% | 103.17% | 11.49% | -7.29% | -1.14% | 1.433 | 6.19% |
| 9 | 253.88% | 21.23% | 100.73% | 11.28% | -31.91% | -5.66% | 1.763 | 9.95% |
| 10 | 157.62% | 15.51% | 97.75% | 11.02% | -35.95% | -6.53% | 1.303 | 4.48% |
| 11 | 202.02% | 18.37% | 98.39% | 11.09% | -31.98% | -5.67% | 1.522 | 7.27% |
| 12 | 169.13% | 16.30% | 96.35% | 10.92% | -38.29% | -7.05% | 1.371 | 5.39% |
| 13 | 107.52% | 11.77% | 94.76% | 10.76% | -32.76% | -5.84% | 1.066 | 1.00% |
| 14 | 121.11% | 12.85% | 96.24% | 10.89% | -34.05% | -6.11% | 1.127 | 1.96% |
| 15 | 137.42% | 14.08% | 92.42% | 10.56% | -39.02% | -7.22% | 1.234 | 3.52% |
| 16 | 119.55% | 12.73% | 94.16% | 10.71% | -33.83% | -6.07% | 1.131 | 2.02% |
| 17 | 92.07% | 10.46% | 93.04% | 10.61% | -26.65% | -4.59% | 0.995 | -0.16% |
| 18 | 163.16% | 15.88% | 89.64% | 10.31% | -31.51% | -5.57% | 1.388 | 5.57% |
| 19 | 144.64% | 14.60% | 89.66% | 10.31% | -40.16% | -7.49% | 1.290 | 4.29% |

## Q5 strength versus weak Q1

The common Q5-minus-Q1 CAGR contrast is +19.70 percentage points. Q5 exceeds
the benchmark by +2.63 points, while the benchmark exceeds Q1 by +17.07 points;
86.65% of the Q5-minus-Q1 CAGR gap is therefore associated with Q1 weakness
relative to the benchmark. The original spread is principally a weak-Q1
phenomenon, but the frozen continuation rule still passes because Q5 itself is
positive and independently beats the benchmark after costs. Q1 is diagnostic,
not a financed short portfolio.

## Reproducibility and validation

Primary run:
`D:/Stock/data/ATS/phase_a_v2_strategy_test/runs/phase-a-v2-strategy-test-20260829-v3`

Clean reproduction:
`D:/Stock/data/ATS/phase_a_v2_strategy_test/reproductions/phase-a-v2-strategy-test-20260829-v3`

Independent audit:
`D:/Stock/data/ATS/phase_a_v2_strategy_test/audits/phase-a-v2-strategy-test-20260829-v3-audit.json`

The reproduction matches logical hash
`aaca0ccea49ce54ac0e62a3c5d1cf7aaaae493e9f6a44a0872eff49b132967f5`,
all three selection checksums, and every manifest-declared physical file hash.
The audit independently recomputes composite metrics from daily NAV, reproduces
the published 11-row gate exactly, verifies all 120 ledgers, and fails closed on
terminal-unresolved sleeves.

Focused validation results:

- research adapter/Dino/PLAY/audit tests: 14 passed;
- accepted Phase C contracts, golden ledgers, and state transitions: 33 passed.

Exact commands and working directory are retained in
`RESEARCH/prototypes/phase_a_v2_strategy_test/validation_commands.json`.
The final requirement audit is
`RESEARCH/prototypes/phase_a_v2_strategy_test/final_requirements_audit.csv`.

## Boundaries and single next validation need

This basis is not total return:

- `cash_distributions_included = false`;
- `cash_dividend_price_gaps_preserved = true`.

Absolute results may understate investor returns, and cross-sectional dividend
differences can affect relative economics. Source-native opens are also an
execution proxy rather than evidence that the opening auction could absorb the
required fractional target at the assumed 25 bps cost per traded notional.
Authoritative exhaustive split discovery remains `NOT PROVEN`, although no
additional concrete held-path anomaly appeared in this frozen test.

The single most important next validation need is **genuinely later untouched
holdout data**. The present sample helped select max-high proximity; another
variant, filter, or in-sample sensitivity would not address that dependence.
Do not implement or optimize that next step within this decision.

The scoped code, small configurations/tests, and this report are committed only
after the successful reproduction and final audit.
