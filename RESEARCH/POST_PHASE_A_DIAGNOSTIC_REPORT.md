# Post–Phase A diagnostic research report

Authoritative diagnostic run: `postphasea-20260820T122341Z-final`  
Independent reproduction: `postphasea-20260820T122448Z-reproduction`  
Trusted Phase A run: `phasea-2a2b3898aba37814`  
Phase A Git commit: `caf76ee9b7da77829cdc1b32c982a7b895e2c743`  
Diagnostic manifest logical hash: `24cd09ec5e05de800b24e423070f6593426a8a645748bee47dc6f8f7501d487b`

## Executive conclusion

Phase A establishes a reproducible, point-in-time diagnostic panel with an invariant official TOP60 denominator and explicit missing states. In this sample, 12–1 momentum rank has a positive aggregate association with 3/5/10/20-session forward returns: mean rank IC rises from 0.031 to 0.057, both HAC and deterministic moving-block-bootstrap intervals exclude zero, and all four tests survive the declared 16-test Benjamini–Hochberg family. Every non-overlapping offset also has a positive mean. These are real properties of the retained sample, not an iid-standard-error artifact. [C1–C3]

Phase A does **not** establish a stable, monotonic, executable momentum strategy. The association is concentrated after mid-2023, especially in 2024; the early half is near zero at every horizon. Fixed momentum quantiles peak at Q4 rather than Q5, so the full rank distribution is not monotonic. Full-sample Q5-minus-Q1 diagnostic gross returns are only 0.12%, 0.18%, 0.40%, and 0.73% across 3/5/10/20 sessions, and Q5 underperforms Q4 at all four horizons. No “best” horizon is selected. [C2–C5]

The strongest new exploratory observation is that proximity to the prior 252-session high retains positive partial rank association after controlling for momentum. All 16 prespecified proximity tests survive within-family adjustment, and strict 252/252 versus declared 240/252 availability rules are nearly identical. That is a hypothesis worth validating with Phase B data—not deployable alpha—because Stooq adjustment semantics are unverified, annual strength is uneven, and some double-sort cells average only about 2.3 securities per session. [C10]

The proposed trend-conditioned pullback hypothesis is not supported after controlling for momentum: all four positive-WIG-trend partial-IC intervals include zero and adjusted q-values are 0.64–0.91. The raw cells lean toward short-term continuation, not pullback reversal. [C9]

Coverage is materially informative. Only 472 of 1,272 sessions have 60/60 usable prices; all 800 incomplete sessions coincide with active unresolved benign-exit members, so coverage, exit exposure, calendar period, and regime cannot be cleanly disentangled. Momentum mean IC on full-coverage sessions is 0.060–0.119, versus 0.013–0.022 below 60 and negative at every horizon on the 455 sessions with 57/60 usable prices. This is a major interpretation risk, not a reason to redefine the universe. [C11]

Nothing in this report is a portfolio backtest, an execution simulation, a security selection, or evidence of deployable alpha. Returns are diagnostic gross outcomes. Phase C, portfolio construction, cost modeling, and parameter optimization were not performed.

## 1. Robust-looking observations

### 1.1 Integrity and reproducibility

The complete archived Phase A suite passed: 26 tests. Archive validation parsed 30 manifest artifacts and verified physical and logical hashes, 76,320 panel rows, 1,272 sessions, the source snapshot, and local reconstructability of the pinned commit. The pre-existing reproduction report passes configuration, environment-lock, run-ID, metrics, and logical-artifact checks. The final diagnostic replay reproduced all 32 table hashes plus metrics, config, plan, environment lock, and source snapshot. [C1, C14]

The shared checkout changed during concurrent Phase B work (`pyproject.toml`, `ats_research/cli.py`, and `ats_research/validation.py` differ from the Phase A snapshot). The trusted run was therefore validated with its own archived source. No Phase A run, Phase A artifact, Phase A implementation file, test file, or Phase B file was written by this analysis. [C1, C14]

### 1.2 Aggregate momentum rank association

| Horizon | Sessions / effective sessions | Constituent observations | Mean / median IC | HAC 95% CI | Block-bootstrap 95% CI | BH q |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 1,269 / 575 | 73,309 | 0.0308 / 0.0326 | [0.0149, 0.0467] | [0.0134, 0.0476] | 0.0016 |
| 5 | 1,267 / 377 | 73,191 | 0.0366 / 0.0387 | [0.0170, 0.0562] | [0.0154, 0.0583] | 0.0016 |
| 10 | 1,262 / 197 | 72,896 | 0.0473 / 0.0557 | [0.0211, 0.0734] | [0.0212, 0.0763] | 0.0016 |
| 20 | 1,252 / 99 | 72,306 | 0.0570 / 0.0691 | [0.0199, 0.0941] | [0.0195, 0.0926] | 0.0067 |

Positive-session shares are 55.7%, 56.7%, 62.8%, and 63.4%. Session-IC standard deviations are about 0.19, much larger than the means. Effective sessions fall sharply with horizon, which is consistent with increasing serial dependence from overlapping labels. [C2]

Every non-overlapping offset has positive mean momentum IC: ranges are 0.0287–0.0331 (3 sessions), 0.0336–0.0391 (5), 0.0412–0.0523 (10), and 0.0421–0.0689 (20). Thus overlap can explain smoother aggregate estimates and reduced effective sample size, but not the positive sign in this sample. The prespecified 20-session start/end trims also retain the sign. [C3]

### 1.3 Other registered features

Realized volatility rank has negative aggregate mean IC at all horizons (-0.020, -0.021, -0.029, -0.049); all four survive the 16-test confirmatory family. Relative-volume rank is inconclusive at 3/5 sessions but positive at 10/20 sessions (0.016 and 0.028; q=0.036 and 0.0016). The 20-session relative-volume sign is positive in both fixed early and late halves. These are consistent-in-sample associations, but their fixed-quantile profiles are not fully monotonic. [C6, C7]

The five-session return feature is not rejected at any horizon (q=0.53–0.85). [C8]

## 2. Weak or inconclusive observations

### 2.1 Momentum is not stable through the full sample

The fixed early half (through 2023-06-30) has mean momentum IC of 0.0065, 0.0074, 0.0082, and -0.0004; every HAC interval includes zero. The late half has 0.056, 0.067, 0.089, and 0.119, with intervals excluding zero. [C4]

The 2020 partial period (22 IC sessions) is negative at every horizon. The 2021 estimates are 0.004–0.013 and 2022 estimates range from 0.001 to -0.039. Results turn positive in 2023, become unusually large in 2024 (0.089–0.198), and remain positive but smaller in 2025 (0.037–0.063). Rolling 252-session mean IC becomes negative in 171, 195, 223, and 310 windows at 3/5/10/20 sessions. The aggregate is therefore not broadly distributed over the entire history. [C4]

### 2.2 Momentum quantiles do not form a monotonic staircase

| Horizon | Q1 | Q2 | Q3 | Q4 | Q5 | Q5−Q1 |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 0.01% | 0.12% | 0.26% | 0.31% | 0.12% | 0.12% |
| 5 | 0.02% | 0.20% | 0.42% | 0.51% | 0.20% | 0.18% |
| 10 | 0.03% | 0.47% | 0.76% | 0.98% | 0.43% | 0.40% |
| 20 | 0.15% | 0.96% | 1.42% | 1.90% | 0.88% | 0.73% |

Each quantile has 1,252–1,269 sessions, at least 11 members per session, and 13,956–15,166 constituent observations depending on horizon/quantile. The Q2-to-Q4 interior gradient is positive, but Q5-minus-Q4 is negative at every horizon (-0.18%, -0.31%, -0.55%, and -1.03%). Only 2024 is monotonic across all five momentum quantiles. This is not a broad monotonic rank-return curve and is not an executable long-short spread. [C5]

### 2.3 Trend-conditioned pullbacks

Within positive WIG trend, momentum-controlled partial ICs for five-session return are 0.0008, 0.0011, 0.0034, and 0.0162. HAC and bootstrap intervals include zero; BH q-values are 0.91, 0.91, 0.91, and 0.64. [C9]

Raw positive-trend terciles rise rather than reverse: for the 20-session outcome, bottom/middle/top short-term-return terciles average 0.93%, 1.49%, and 1.59%. The 3×3 momentum-controlled cells average 5.85–7.18 securities per session, but some individual session-cells contain one security. The conditional pullback hypothesis is not rejected only in the strict statistical sense; the retained evidence does not show a stable pullback premium. [C9]

## 3. Possible artifacts and data-quality concerns

### 3.1 Expected denominator, missing members, and exits

The official count is 60 on every session. Usable prices range from 57 to 60: 472 sessions are 60/60, 91 are 59/60, 254 are 58/60, and 455 are 57/60. All 1,964 missing member-sessions have reason `unresolved_vendor_alias` and belong to LOTOS, PGNiG, STS Holding, CIECH, or TIM. Momentum feature eligibility ranges from 55 to 60 because exact history is additionally required. [C11]

Coverage is not separable from benign-exit exposure in this dataset: the 800 below-60 sessions are exactly the 800 sessions with at least one active unresolved exit; the 472 full-coverage sessions are the no-active-exit sessions. Full coverage is also more often in positive WIG trend (about 83.8% versus 73.8%). Missing-member count has a small negative correlation with subsequent WIG return (-0.043 to -0.081 across horizons). [C11]

Momentum IC is materially different by coverage:

| Coverage | IC sessions (h=3 / h=20) | Mean IC h=3 | Mean IC h=20 |
|---|---:|---:|---:|
| 60/60 usable | 469 / 452 | 0.060 | 0.119 |
| Below 60 | 800 / 800 | 0.013 | 0.022 |
| Exactly 57 | 455 / 455 | -0.004 | -0.035 |
| 58–59 | 345 / 345 | 0.037 | 0.097 |

At 57/60 and horizon 20, Q5 averages -0.56% while Q1–Q4 average 1.57%–1.84%. Excluding low-coverage dates therefore changes both sign and shape, not only precision. But this cannot be interpreted causally because coverage, exit identities, period, and regime move together. [C11]

Observable outcomes for price-usable members lacking enough momentum history are worse than for momentum-eligible members: mean diagnostic returns are -0.45%, -0.77%, -1.59%, and -3.08% versus +0.16%, +0.27%, +0.54%, and +1.06%. This indicates non-random feature missingness, but it is an uncontrolled comparison and does not reveal the unobserved outcomes of members with no vendor series. [C11]

Individual exit windows are unstable and sometimes tiny. For example, 20-session momentum IC during LOTOS and PGNiG exposure is -0.023 and -0.031; during CIECH it is 0.003; during STS it is 0.037; during TIM it is 0.172 over only 104 sessions. Several 20-session after-windows contain only 20 IC sessions and extreme values. LOTOS, PGNiG, and CIECH exposure begins at or before the research start, so a 20-session pre-exposure comparison is unavailable. These cells should not support action. [C11]

### 3.2 Price and timestamp semantics

All retained bars say `vendor_adjusted_semantics_unverified`. OHLC validation passes and duplicate bar keys are absent, but independent split/dividend/corporate-action semantics were not retained. This is especially important for momentum and trailing-high calculations. [C13]

Phase A conservatively assumes a daily bar event at 17:00 Europe/Warsaw and availability at 17:05, then forms the next WIG session’s decision at 08:45. The archive validates `available_ts <= decision_ts`, but the vendor’s exact publication latency is not independently demonstrated. Membership is based on validity-dated official snapshots; announcement-time completeness and assumptions between snapshots remain potential point-in-time risks. [C13]

Security identity uses deterministic UUIDv5 over `XWAR:<official ISIN>` and validity-dated aliases, mitigating ticker continuity risk. It does not resolve the five absent Stooq mappings or reconstruct their corporate-event outcomes. [C13]

### 3.3 Statistical limitations

The panel has 76,320 security-date rows, but the maximum time-series sample is 1,272 sessions. Security-date rows are not independent because securities share market and sector shocks. Overlapping forward labels create serial dependence; the horizon-lag HAC and moving-block bootstrap reduce but do not eliminate model uncertainty. The effective-session diagnostic falls to about 99 for 20-session momentum. [C2, C13]

There are four declared families: 10/16 confirmatory Phase A tests, 0/4 positive-trend tests, 16/16 proximity tests, and 21/32 alternative-anchor tests have q≤0.05. Family rejection counts do not prove economic importance, stability, causal structure, or tradability. Annual, rolling, coverage, and cell diagnostics are descriptive and were not mined as additional tests. [C13]

## 4. Hypotheses worth testing next

### 4.1 Proximity to the prior high, conditional on momentum

The strict definition is prior-session close divided by the maximum high over the 252 WIG sessions ending on that prior session. The decision session is excluded; all 252 highs are required. The sole near-high threshold is 0.95. The declared sensitivity allows at least 240 of the same 252 highs without forward fill. [C10]

After controlling for momentum rank, strict partial IC is 0.0367, 0.0420, 0.0536, and 0.0706, with all HAC and bootstrap intervals above zero. Standardized two-rank regression coefficients are 0.045, 0.052, 0.066, and 0.084. All 16 definition/method/horizon tests have q≤0.0002. Strict versus relaxed results differ negligibly and use only 11 fewer constituent observations at each horizon. [C10]

The result is not uniformly stable: 2024 partial IC is approximately zero at every horizon, and the partial 2020 sample is negative at 10/20 sessions. The strict momentum-by-proximity double sort is highly imbalanced; its sparsest cell averages 2.29–2.30 securities per session and sometimes has one. The diagnostic controls only momentum, not sector, size, volatility, liquidity, or corporate-action artifacts. Phase B should test the exact frozen definition on independently verified adjusted and, where possible, raw prices with complete corporate-action lineage. [C10]

### 4.2 Explain the post-2023 momentum concentration

A justified follow-up is to test whether the late-sample association reflects market regime, changing membership composition, improved data coverage, or a genuine change in the cross-sectional relation. This must use prespecified regimes and independent data contracts, not an optimized breakpoint. The current early/late result is a warning and a hypothesis, not evidence for choosing a start date. [C4, C11]

### 4.3 Relative-volume and low-volatility associations

The 20-session relative-volume association is positive in both fixed halves, while realized-volatility association is negative in aggregate. Follow-up should test whether these survive sector/size controls, independently verified adjustments, and cleaner membership/exit coverage. Fixed quantile shapes should be the primary guard against effects driven by one tail. [C6, C7]

## 5. Results that should not be acted on

- Do not act on a selected momentum horizon. Increasing IC with horizon occurs alongside stronger overlap, a falling effective time-series sample, and a common late-period concentration.
- Do not treat Q5−Q1 values as strategy returns. Q5 is below Q4 at every horizon, and no portfolio, turnover, cash, execution, or cost model exists.
- Do not trade the 2024 momentum episode or use the fixed early/late split as a timing rule.
- Do not implement a positive-trend pullback strategy; the momentum-controlled family is not rejected and raw results lean toward continuation.
- Do not implement the trailing-high result until adjustment and corporate-action semantics are independently verified and sparse cells are addressed on new data.
- Do not exclude 57/60 sessions to improve results. Their weakness is diagnostically important and confounded with unresolved exits and time.
- Do not infer extreme missing-member performance. Their returns are unobserved; the data needed for that comparison are absent.
- Do not choose the alternative label anchor with the largest IC. Anchor comparison is sensitivity analysis, not optimization.

## Data and methodology

### Data contract

- Market/universe: GPW TOP60 = WIG20 + mWIG40, universe version `official_gpwbenchmark_snapshots_2026_08_19-bfc71f12a5ae`.
- Dataset: `gpw_top60_daily-a2f5abb2e7e8f019`, source `stooq_local_bulk`, source version `local_snapshot_2025_12_31`.
- Decision sample: 2020-11-27 through 2025-12-30, 1,272 WIG sessions, exactly 60 official rows per session.
- Warmup bars: 2019-01-02 onward. Analysis labels use exact WIG-session endpoints with no forward fill.
- Environment: the retained Phase A `environment_lock.json`; diagnostic runtime Python 3.12.13, pandas 3.0.5, NumPy 1.26.4, PyArrow 25.0.0, SciPy 1.17.1.

### Exact feature semantics

Let `s` be the WIG session immediately preceding decision session `t`. Security and WIG data for `s` have event time 17:00 and conservative availability 17:05; decision time is 08:45 on `t`.

- `momentum_12_1__v1 = close[s-21] / close[s-252] - 1` on the complete WIG-session grid.
- `return_5__v1 = close[s] / close[s-5] - 1`.
- `realized_volatility_20__v1` is the sample standard deviation of 20 consecutive close-to-close returns ending at `s`.
- `relative_volume_20__v1 = volume[s] / mean(volume[s-19:s]) - 1`; the current prior-session volume is included.
- `wig_trend_200__v1 = WIG close[s] / mean(WIG close[s-199:s]) - 1`; it is a market regime, never a cross-sectional rank or quantile.

Ranks use only the named feature’s eligible denominator. Fixed quantile is `ceil(percentile rank × 5)`. Missing exact endpoints and rolling observations remain null.

### Exact trusted-label semantics

For the pre-open decision session `t`, `forward_return_h_v1 = close[t+h] / close[t] - 1`, with `t` as WIG-session zero. Start and end closes must exist on exact WIG sessions. The start close occurs after the 08:45 decision. The label is a diagnostic close-to-close outcome; daily bars do not establish a same-close executable fill.

### Statistical methods

- Session IC: cross-sectional Spearman correlation.
- HAC: Bartlett/Newey–West long-run variance with lag equal to label horizon.
- Moving-block bootstrap: 1,000 deterministic circular resamples, block length `max(20, horizon)`, seed 20260820 plus a stable test identifier.
- Multiplicity: Benjamini–Hochberg within each family declared in `analysis_plan.md`.
- Non-overlap: full WIG decision-session index modulo horizon, all offsets retained; missing ICs do not change schedules.
- Time: calendar years, fixed early/late split at 2023-07-01, 2020–2021 versus 2022–2025, and descriptive 252-session rolling means with 126-session minimum.
- Endpoint sensitivity: only first 20, last 20, or both 20-session trims.
- Effective sessions: sample variance divided by HAC variance of the mean, capped at observed sessions; descriptive only.

## Label-anchor sensitivity

Two decision-aligned alternatives were calculated from exact daily observations without modifying trusted labels:

1. `open[t]` to `close[t+h]`: h WIG-session gaps plus the exit-session intraday interval.
2. `open[t]` to `open[t+h]`: h open-to-open WIG-session intervals.

For momentum, open-to-open mean IC is almost unchanged from trusted close-to-close: differences are +0.0017, +0.0008, +0.0002, and +0.0016. Open-to-close IC is higher by +0.0163, +0.0114, +0.0092, and +0.0052. Eligible samples are identical to trusted momentum samples, so these differences are anchoring effects rather than sample attrition. [C12]

For each anchor, 1,964 official member-sessions have both entry and exit missing because the vendor series is unresolved. Exact horizon-tail exits are additionally missing for 180, 300, 600, and 1,200 member-sessions at 3/5/10/20 sessions. Daily `open` is an observed field, not proof of auction availability, fillability, or achievable execution. The stronger open-to-close result must not be selected. [C12]

## Diagnostics not performable from retained evidence

1. **Extreme subsequent performance of members with no vendor mapping:** no entry/exit prices exist for the 1,964 member-sessions; the counterfactual return is unobservable.
2. **Exit-adjusted returns for the five benign exits:** conversion/cash terms are documented, but no canonical corporate-action-adjusted security return series was retained for this diagnostic panel.
3. **Independent verification of Stooq adjustment semantics:** every bar is marked vendor-adjusted but unverified; raw/adjusted lineage is missing.
4. **Exact open or close execution feasibility:** daily OHLC does not establish auction publication time, order eligibility, fills, spreads, or tradeability.
5. **Clean causal separation of coverage from exits or calendar regime:** all incomplete-coverage sessions coincide with active unresolved exits.
6. **Full pre/during/post comparison for LOTOS, PGNiG, and CIECH:** their exposure starts at or before the research sample, leaving no prespecified 20-session pre-window.
7. **Long-regime history:** 2020 contributes only 22 IC sessions, and the whole sample spans roughly five years with strong regime concentration.
8. **PNG figures:** a minimal two-point matplotlib Agg `savefig` terminates the pinned environment with Windows status `-1066598273`. The environment was not modified; all intended plotted values and sample sizes remain in tables.

## Questions Phase B data contracts should make easier

- Can every bar expose independently documented raw/adjusted state, adjustment factor, corporate-action event, and version lineage?
- Can open/close observations carry auction/trading-status and exact availability metadata rather than a conservative blanket time?
- Can membership intervals retain announcement time, effective time, source snapshot, correction lineage, and explicit interval assumptions?
- Can unresolved vendor mappings and later resolutions be versioned without rewriting historical evidence?
- Can corporate exits provide canonical conversion/cash events so diagnostic labels can remain exact through mergers, suspensions, and delistings?
- Can feature and label eligibility emit standardized reason codes and counts as first-class columns for every derived result?
- Can independent dataset versions support the same frozen hypotheses without reusing the exploratory sample?
- Can sector, size, liquidity, stale-price, suspension, and tradeability facts be joined point-in-time for controlled diagnostics?

## Reproducibility and completion record

Authoritative files are under:

`D:\Stock\data\ATS\post_phase_a_diagnostics\runs\postphasea-20260820T122341Z-final`

The run contains `config.yaml`, `analysis_plan.md`, `metrics.json`, `manifest.json`, `environment_lock.json`, `input_hashes.json`, 32 CSV tables, a 610,560-row member-level anchor-state Parquet audit, validation logs, `validation_report.json`, `figures/README.txt`, and deterministic `source_snapshot.zip`.

The independent reproduction is:

`D:\Stock\data\ATS\post_phase_a_diagnostics\runs\postphasea-20260820T122448Z-reproduction`

All 32 logical table hashes match. Metrics, config, analysis plan, environment lock, and source snapshot hashes also match. The two manifest logical hashes differ because run ID and run-specific command logs are intentionally distinct.

Exact principal commands and results:

```powershell
$env:PYTHONPATH='D:\Stock\ATS\RESEARCH\prototypes\post_phase_a_diagnostics\phase_a_validation_source_caf76ee\src'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\Users\konra\anaconda3\envs\ats-stack-research\python.exe' -m pytest -p no:cacheprovider 'D:\Stock\ATS\RESEARCH\prototypes\post_phase_a_diagnostics\phase_a_validation_source_caf76ee\tests'
# 26 passed

& 'C:\Users\konra\anaconda3\envs\ats-stack-research\python.exe' -m ats_research validate --run-dir 'D:\Stock\data\ATS\phase_a\runs\phasea-2a2b3898aba37814'
# passed; 30 manifest artifacts, 76,320 rows, 1,272 sessions, source snapshot valid

& 'C:\Users\konra\anaconda3\envs\ats-stack-research\python.exe' 'D:\Stock\ATS\RESEARCH\prototypes\post_phase_a_diagnostics\run_diagnostics.py' --config 'D:\Stock\ATS\RESEARCH\prototypes\post_phase_a_diagnostics\config.yaml' --run-id 'postphasea-20260820T122341Z-final'
# passed; 32 tables; manifest logical hash 24cd09ec5e05de800b24e423070f6593426a8a645748bee47dc6f8f7501d487b

& 'C:\Users\konra\anaconda3\envs\ats-stack-research\python.exe' 'D:\Stock\ATS\RESEARCH\prototypes\post_phase_a_diagnostics\run_diagnostics.py' --config 'D:\Stock\data\ATS\post_phase_a_diagnostics\runs\postphasea-20260820T122341Z-final\config.yaml' --run-id 'postphasea-20260820T122448Z-reproduction'
# passed; all 32 table hashes and all logical metric/config/plan/environment/source hashes match
```

An initial shared-checkout validation passed 26 tests but stopped on a current-code hash mismatch because Phase B had modified `pyproject.toml`; later concurrent changes also affected `cli.py` and `validation.py`. The archived source validation above is authoritative. Failed and superseded diagnostic attempts were preserved under unique run IDs; no run directory was overwritten or deleted.

## Appendix: claim-to-artifact map

All paths below are relative to the authoritative diagnostic run.

| Claim | Evidence artifact | Relevant fields |
|---|---|---|
| C1 integrity | `validation_report.json`; `logs/phase_a_tests.txt`; `logs/phase_a_archive_validation.txt`; `input_hashes.json` | pass states, artifact/source hashes, code mismatches |
| C2 aggregate IC and uncertainty | `tables/ic_distribution_uncertainty.csv` | distribution tails, sign shares, HAC/bootstrap intervals, effective sessions, BH q |
| C3 overlap and endpoint sensitivity | `tables/non_overlapping_offset_ic.csv`; `tables/endpoint_shift_sensitivity.csv` | every offset, session/constituent counts, fixed trims |
| C4 calendar and rolling stability | `tables/annual_period_ic.csv`; `tables/rolling_ic_252.csv` | calendar year, early/late, episode, rolling count/mean |
| C5 fixed quantiles and monotonicity | `tables/quantile_results_by_period.csv`; `tables/quantile_monotonicity.csv`; `tables/quantile_adjacent_differences.csv` | all quantiles, counts, gradients, edge differences |
| C6 realized volatility | same IC/period/quantile tables as C2/C4/C5 | feature=`realized_volatility_20__v1` |
| C7 relative volume | same IC/period/quantile tables as C2/C4/C5 | feature=`relative_volume_20__v1` |
| C8 short-term return | same IC/period/quantile tables as C2/C4/C5 | feature=`return_5__v1` |
| C9 trend-conditioned pullbacks | `tables/trend_conditioned_pullback_cells.csv`; `tables/trend_momentum_double_sort.csv`; `tables/trend_conditioned_partial_ic.csv`; `tables/trend_conditioned_period_stability.csv` | regime, terciles, counts, partial IC, BH q |
| C10 proximity to high | `tables/proximity_coverage.csv`; `tables/proximity_incremental_tests.csv`; `tables/proximity_period_stability.csv`; `tables/proximity_momentum_double_sort.csv`; `tables/proximity_near_high_counts.csv` | strict/relaxed definitions, methods, years, cells, counts, q |
| C11 coverage/missingness/exits | `tables/coverage_missingness_ic.csv`; `tables/coverage_missingness_quantiles.csv`; `tables/coverage_missing_reason_distribution.csv`; `tables/membership_change_exit_ic.csv`; `tables/membership_change_exit_quantiles.csv`; `tables/missingness_market_relationship.csv`; `tables/feature_missing_observable_outcomes.csv` | official/usable/feature/label denominators, reasons, periods |
| C12 anchor sensitivity | `tables/label_anchor_comparison.csv`; `tables/label_anchor_annual_stability.csv`; `tables/label_anchor_momentum_quantiles.csv`; `tables/label_anchor_state_counts.csv`; `audit/label_anchor_member_states.parquet` | entry/exit semantics, paired effects, eligibility states |
| C13 risk and multiplicity | `tables/data_quality_risk_register.csv`; `tables/multiple_testing_families.csv`; `analysis_plan.md` | unresolved risks, declared families, all adjusted results |
| C14 reproducibility | `manifest.json`; `metrics.json`; `environment_lock.json`; `source_snapshot.zip`; reproduction run manifest | logical hashes and source/environment pins |

