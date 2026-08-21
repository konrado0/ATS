# Phase A decision-oriented research report

**As of:** 2026-08-20  
**Extended Phase A panel:** 2020-11-27 through 2026-08-18  
**Scope:** diagnostic research only; no optimization, portfolio construction, execution simulation, or claim of deployable alpha

## Executive conclusion

The original Phase A analysis ended on 2025-12-30 because its immutable configuration explicitly stopped at 2025-12-31 and identified its source as `local_snapshot_2025_12_31`; 2025-12-30 was the final WIG trading session present inside that boundary. The local Stooq files and official WIG20/mWIG40 membership snapshots subsequently advanced into 2026. I therefore rebuilt the completed Phase A pipeline, without changing its feature, label, timestamp, universe, or missing-member semantics, through the latest validated common session, 2026-08-18.

The extended sample supports three decision-oriented conclusions:

1. The aggregate momentum rank relationship is positive, but the historical “strong but not extreme” Q4-over-Q5 shape is **not persistent**. It is concentrated in older, incomplete-coverage periods; on 60/60 dates Q4 and Q5 are essentially tied and Q5 is slightly stronger at 20 sessions. Momentum is therefore classified **DATA-CONFOUNDED**, not rejected.
2. The intended strong-stock pullback hypothesis is **NOT SUPPORTED**. Under both frozen strength definitions, deeper five-session weakness predicts lower, not higher, subsequent diagnostic gross returns at every horizon. The dominant sample pattern is short-term continuation, with 2024 the main reversal exception.
3. Proximity to a strict 252-session high is **PROMISING** as a research hypothesis after momentum control. High realized volatility is also **PROMISING as a conditioning/risk variable**, because its highest quintile persistently lags in the later sample. Relative volume is **WEAK**: its aggregate association is small and non-monotonic.

These are sample diagnostics from close-to-close labels, not executable returns. The coverage regime and calendar period are nearly perfectly confounded, so older-versus-newer momentum differences cannot be attributed to missingness, market regime, or either in isolation.

## Final decision table

| Research item | Classification | Decision-oriented reason |
|---|---|---|
| Momentum | **DATA-CONFOUNDED** | Rank IC is positive in aggregate and since 2023, but the Q4-over-Q5 hump occurs in the older 57–59/60 coverage regime and disappears on 60/60 dates, so persistence and coverage cannot be separated. |
| Strong-stock pullback | **NOT SUPPORTED** | In both positive-momentum and upper-half-momentum stocks, deep five-session pullbacks underperform nonnegative five-session returns at every horizon; only 2024 consistently reverses that ordering. |
| Proximity to high | **PROMISING** | A single strict 252-session definition has positive standalone and momentum-controlled rank association at all horizons, with supportive results in most full years, although 2024 incremental association is near zero. |
| Relative volume | **WEAK** | The aggregate rank association is small and the quintile profile is hump-shaped rather than monotonic; it may warrant limited conditioning work but is not persuasive standalone. |
| Volatility | **PROMISING** | The highest-volatility quintile materially underperforms and the negative association strengthens at longer horizons in later years, making it useful to test as a conditioning/risk variable rather than a standalone return rule. |

## Data refresh, integrity, and semantics

### Why the trusted run stopped in 2025

The trusted run `phasea-2a2b3898aba37814` was not silently truncated by a calculation. Its retained configuration states:

- `end_date: 2025-12-31`;
- `source_version: local_snapshot_2025_12_31`.

The WIG source has observations on 2025-12-29 and 2025-12-30 but none on 2025-12-31, so 2025-12-30 is the expected final session under that configuration. Local WIG and sampled stock files now reach 2026-08-18, while official point-in-time WIG20 and mWIG40 snapshots exist at 2026-03-23 and 2026-06-22. The Phase A input was therefore stale relative to the current validated local dataset.

The new immutable extension run is:

- directory: `D:\Stock\data\ATS\decision_oriented_phase_a\runs\extension-20260820T163347Z`;
- run ID: `phasea-9a50dcdb3a4538d7`;
- manifest SHA-256: `1A68F010125B625CA55A21EFD4299D9A744B16BE11979810A71180ABEB813A7F`;
- manifest logical hash: `58f23885b9e9d4bf07bc9afd39824178f70b19f99d368614ce51aae5e669c33a`;
- logical dataset version: `gpw_top60_daily-0f573ba3dd92fa37`;
- universe version: `official_gpwbenchmark_snapshots_2026_08_19-dd316e44b483`;
- environment-lock hash: `24f1d670eb92bf891fe67a0801f7ab0bb8ee817e4639d2e0ff6a7f6de477eee6`.

Archive validation passed: 30 retained artifacts, valid source snapshot, 85,800 official security-date rows, and 1,430 WIG decision sessions. The panel adds 158 sessions beyond the trusted run. Calendar counts are 22 sessions in partial 2020, 251 in 2021, 251 in 2022, 250 in 2023, 249 in 2024, 249 in 2025, and 158 in partial 2026.

Because forward outcomes require future closes, the final eligible decision dates are 2026-08-13, 2026-08-11, 2026-08-04, and 2026-07-21 for the 3-, 5-, 10-, and 20-session labels respectively.

### Feature, label, and timing definitions

- **Momentum 12–1:** close return over 252 market sessions excluding the most recent 21 sessions, as implemented by the Phase A feature registry.
- **Five-session stock return:** the registered close-to-close `return_5` feature.
- **Realized volatility:** standard Phase A measure over 20 consecutive close-to-close returns.
- **Relative volume:** current volume divided by the 20-session mean, minus one.
- **Proximity to high:** prior available close divided by the maximum close across the trailing 252 official WIG sessions ending on that prior source session. The current prior close is included, and a full exact 252-session history is required.
- **Forward labels:** official decision-session close to the close exactly 3, 5, 10, or 20 WIG sessions later. Missing start or exact end-session closes remain null; no forward filling is used.
- **Timestamps:** the source bar event is 17:00 Europe/Warsaw, conservatively available at 17:05, and the decision timestamp is 08:45 before the next WIG session. Every feature input must be available by the decision timestamp.

The label's start price is `close[t]`, which occurs after the 08:45 decision on session `t` and is therefore not known when the signal is formed. The calculation uses `close[t+h] / close[t] - 1` exactly as documented, but it remains a diagnostic association rather than evidence of an executable same-close fill. No result below should be read as a portfolio return.

### Frozen analysis choices

The analysis plan was written before the extended results were inspected. Momentum uses Phase A quintiles. Pullbacks use two conditions—raw 12–1 momentum greater than zero and momentum rank above 0.5—and three fixed buckets: `return_5 <= -5%`, `-5% < return_5 < 0`, and `return_5 >= 0`. Proximity uses only the strict definition above, evaluated with quintiles, a momentum-controlled partial rank association, and one 3×3 momentum-by-proximity table. No horizon, threshold, quantile, or subperiod was selected after seeing results.

## 1. Medium-term momentum

### Aggregate quintiles and rank IC

Values are mean diagnostic gross forward returns. Counts are constituent observations; session IC uses one cross-section per decision session.

| Horizon | Q1 | Q2 | Q3 | Q4 | Q5 | Q4−Q5 | Rank IC | Sessions |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 0.04% (16,007) | 0.16% | 0.26% | 0.34% | 0.19% | **0.15%** | 0.03 | 1,427 |
| 5 | 0.08% | 0.26% | 0.44% | 0.57% | 0.31% | **0.26%** | 0.04 | 1,425 |
| 10 | 0.15% | 0.59% | 0.82% | 1.12% | 0.65% | **0.47%** | 0.05 | 1,420 |
| 20 | 0.33% | 1.19% | 1.52% | 2.20% | 1.26% | **0.94%** | 0.06 | 1,410 |

The average rank relationship increases with horizon, and aggregate Q4 exceeds Q5. That aggregate shape is not stable enough to call a persistent “strong but not extreme” effect.

### Calendar-year results

| H | Year | Q1 | Q2 | Q3 | Q4 | Q5 | IC |
|---:|---|---:|---:|---:|---:|---:|---:|
| 3 | 2020 partial | 2.37% | 1.72% | 1.24% | 0.88% | 1.06% | -0.077 |
| 3 | 2021 | 0.28% | 0.13% | 0.42% | 0.37% | 0.20% | 0.004 |
| 3 | 2022 | -0.21% | 0.11% | 0.12% | -0.11% | -0.46% | 0.001 |
| 3 | 2023 | -0.03% | 0.14% | 0.27% | 0.57% | 0.17% | 0.033 |
| 3 | 2024 | -0.25% | -0.19% | 0.02% | 0.19% | 0.32% | 0.089 |
| 3 | 2025 | 0.10% | 0.29% | 0.42% | 0.51% | 0.36% | 0.036 |
| 3 | 2026 partial | 0.24% | 0.41% | 0.24% | 0.57% | 0.62% | 0.058 |
| 5 | 2020 partial | 4.34% | 3.24% | 2.35% | 1.25% | 1.82% | -0.146 |
| 5 | 2021 | 0.44% | 0.18% | 0.61% | 0.66% | 0.32% | 0.007 |
| 5 | 2022 | -0.28% | 0.23% | 0.20% | -0.14% | -0.77% | -0.003 |
| 5 | 2023 | -0.07% | 0.21% | 0.45% | 0.88% | 0.28% | 0.043 |
| 5 | 2024 | -0.44% | -0.30% | 0.00% | 0.33% | 0.53% | 0.107 |
| 5 | 2025 | 0.18% | 0.54% | 0.71% | 0.85% | 0.61% | 0.044 |
| 5 | 2026 partial | 0.44% | 0.59% | 0.49% | 0.95% | 1.08% | 0.064 |
| 10 | 2020 partial | 7.13% | 5.47% | 4.33% | 2.18% | 2.84% | -0.173 |
| 10 | 2021 | 1.15% | 0.47% | 1.05% | 1.32% | 0.81% | 0.013 |
| 10 | 2022 | -0.60% | 0.75% | 0.33% | -0.34% | -1.53% | -0.015 |
| 10 | 2023 | -0.20% | 0.33% | 0.93% | 1.66% | 0.55% | 0.056 |
| 10 | 2024 | -0.98% | -0.55% | -0.03% | 0.63% | 1.13% | 0.150 |
| 10 | 2025 | 0.45% | 1.20% | 1.35% | 1.78% | 1.20% | 0.048 |
| 10 | 2026 partial | 0.68% | 1.12% | 1.12% | 1.90% | 2.19% | 0.083 |
| 20 | 2020 partial | 11.01% | 8.70% | 9.25% | 5.16% | 3.97% | -0.222 |
| 20 | 2021 | 2.60% | 1.02% | 1.27% | 2.68% | 1.39% | 0.010 |
| 20 | 2022 | -0.97% | 1.67% | 0.92% | -0.44% | -2.98% | -0.039 |
| 20 | 2023 | -0.43% | 0.74% | 1.80% | 3.07% | 1.01% | 0.079 |
| 20 | 2024 | -1.68% | -1.14% | 0.15% | 1.32% | 2.74% | 0.198 |
| 20 | 2025 | 0.77% | 2.27% | 2.68% | 3.31% | 2.50% | 0.066 |
| 20 | 2026 partial | 1.08% | 2.45% | 1.68% | 3.71% | 3.83% | 0.102 |

Q4 exceeds Q5 in 2021, 2022, 2023, and 2025, but Q5 exceeds Q4 in 2024 and partial 2026. The broad rank relationship is negative or near zero through 2022 and clearly positive from 2023 onward. Thus the aggregate Q4 hump reflects a mixture of periods rather than a stable cross-sectional law.

As a secondary uncertainty check, aggregate Q4−Q5 HAC 95% intervals are [0.02%, 0.29%], [0.04%, 0.48%], [0.06%, 0.88%], and [0.20%, 1.69%] from 3 to 20 sessions; deterministic moving-block intervals are similar. Aggregate momentum IC intervals remain positive. These intervals describe the full mixture and do not resolve the period/coverage confounding.

![Momentum quintile profiles](D:/Stock/data/ATS/decision_oriented_phase_a/analysis_runs/decision-20260820T164218Z/figures/momentum_quintile_profiles.png)

![Momentum Q4 minus Q5 by year](D:/Stock/data/ATS/decision_oriented_phase_a/analysis_runs/decision-20260820T164218Z/figures/momentum_q4_minus_q5_by_year.png)

## 2. Actual trend-conditioned pullback

This test conditions on each stock's own established strength; WIG trend is not used as a stock-ranking variable.

### Aggregate bucket outcomes

| Strength condition | Horizon | Deep pullback ≤−5% | Mild pullback | Nonnegative 5-day | Deep minus nonnegative |
|---|---:|---:|---:|---:|---:|
| Positive 12–1 momentum | 3 | 0.08% (5,497) | 0.14% (19,186) | 0.22% (27,724) | -0.12% |
| Positive 12–1 momentum | 5 | 0.21% (5,494) | 0.30% (19,147) | 0.38% (27,672) | -0.17% |
| Positive 12–1 momentum | 10 | 0.50% (5,493) | 0.63% (19,111) | 0.70% (27,472) | -0.20% |
| Positive 12–1 momentum | 20 | 0.84% (5,461) | 1.23% (18,949) | 1.53% (27,208) | -0.68% |
| Upper-half momentum rank | 3 | 0.09% (4,620) | 0.19% (14,867) | 0.27% (22,150) | -0.18% |
| Upper-half momentum rank | 5 | 0.26% (4,619) | 0.38% (14,841) | 0.47% (22,117) | -0.21% |
| Upper-half momentum rank | 10 | 0.53% (4,619) | 0.79% (14,819) | 0.89% (21,989) | -0.35% |
| Upper-half momentum rank | 20 | 1.13% (4,592) | 1.51% (14,708) | 1.88% (21,827) | -0.75% |

Average five-session signals are about -7.85% in the deep bucket, -2.04% in the mild bucket, and +3.7% in the nonnegative bucket. The ordering is continuation rather than pullback reversal under both definitions and every horizon.

### Deep-pullback minus nonnegative by year

| Condition | H | 2020p | 2021 | 2022 | 2023 | 2024 | 2025 | 2026p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Positive momentum | 3 | -1.05% | -0.04% | -0.10% | -0.23% | 0.15% | -0.18% | -0.28% |
| Positive momentum | 5 | -1.94% | -0.17% | -0.35% | -0.29% | 0.43% | -0.10% | -0.35% |
| Positive momentum | 10 | -2.20% | -0.49% | 0.13% | -0.37% | 0.64% | -0.25% | -1.13% |
| Positive momentum | 20 | -4.83% | -1.50% | -0.68% | -1.48% | 0.90% | 0.01% | -1.41% |
| Upper-half rank | 3 | -1.01% | -0.06% | -0.14% | -0.43% | 0.27% | -0.20% | -0.05% |
| Upper-half rank | 5 | -1.88% | -0.15% | -0.27% | -0.47% | 0.49% | -0.17% | -0.25% |
| Upper-half rank | 10 | -2.18% | -0.84% | 0.29% | -0.49% | 0.64% | -0.34% | -1.50% |
| Upper-half rank | 20 | -4.65% | -2.12% | 0.16% | -1.47% | 1.03% | -0.13% | -1.58% |

The 2024 reversal is not representative of most years. At 20 sessions the aggregate deep-minus-nonnegative contrast has a HAC interval of roughly [-1.48%, 0.03%] under positive momentum and [-1.56%, 0.14%] under the upper-half condition; block intervals are similarly close to zero at the upper endpoint. Regardless of interval interpretation, the effect estimate points opposite the intended hypothesis.

![Strong-stock pullback profiles](D:/Stock/data/ATS/decision_oriented_phase_a/analysis_runs/decision-20260820T164218Z/figures/strong_stock_pullback_profiles.png)

## 3. Proximity to the 252-session high

### Standalone and momentum-controlled results

| Horizon | Q1 | Q2 | Q3 | Q4 | Q5 | Rank IC | Partial IC controlling momentum |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | -0.00% | 0.20% | 0.28% | 0.23% | 0.29% | 0.05 | 0.03 |
| 5 | 0.01% | 0.32% | 0.47% | 0.38% | 0.48% | 0.05 | 0.04 |
| 10 | 0.06% | 0.60% | 0.92% | 0.83% | 0.92% | 0.07 | 0.05 |
| 20 | 0.09% | 1.13% | 1.73% | 1.68% | 1.84% | 0.09 | 0.07 |

Mean proximity rises from 0.56 in Q1 through 0.97 in Q5. The relationship is not perfectly monotonic—Q3 and Q5 are similar at several horizons—but the lowest-proximity quintile is distinctly weaker. Partial IC remains positive after linear removal of momentum rank. Its HAC intervals are approximately [0.02, 0.05], [0.02, 0.06], [0.03, 0.07], and [0.04, 0.10].

### Momentum × proximity table

Mean diagnostic gross returns; momentum terciles are rows and proximity terciles columns.

| H | Momentum tercile | Low proximity | Middle proximity | High proximity |
|---:|---|---:|---:|---:|
| 3 | M1 weak | 0.05% | 0.25% | -0.04% |
| 3 | M2 | 0.31% | 0.25% | 0.27% |
| 3 | M3 strong | 0.01% | 0.27% | 0.29% |
| 5 | M1 weak | 0.09% | 0.40% | 0.06% |
| 5 | M2 | 0.56% | 0.41% | 0.44% |
| 5 | M3 strong | 0.09% | 0.47% | 0.49% |
| 10 | M1 weak | 0.18% | 0.86% | 0.32% |
| 10 | M2 | 0.81% | 0.83% | 0.84% |
| 10 | M3 strong | 0.22% | 1.00% | 1.00% |
| 20 | M1 weak | 0.44% | 1.38% | 1.13% |
| 20 | M2 | 1.06% | 1.52% | 1.76% |
| 20 | M3 strong | 0.12% | 1.98% | 1.96% |

The M3/high-proximity cell has 14,747–14,889 observations depending on horizon. M3/low-proximity is smaller, with 3,540–3,604 observations, but is not a tiny cell. Within strong momentum, low proximity is consistently weaker than middle or high proximity; proximity thus appears to contain information not reducible to the simple momentum rank alone.

### Year stability

Entries are Q5−Q1 / standalone IC / partial IC.

| H | 2020p | 2021 | 2022 | 2023 | 2024 | 2025 | 2026p |
|---:|---|---|---|---|---|---|---|
| 3 | -0.52% / -0.041 / 0.023 | 0.23% / 0.046 / 0.047 | 0.01% / 0.021 / 0.032 | 0.63% / 0.065 / 0.058 | 0.35% / 0.062 / -0.001 | 0.39% / 0.047 / 0.036 | 0.20% / 0.057 / 0.037 |
| 5 | -1.54% / -0.090 / 0.004 | 0.37% / 0.057 / 0.057 | -0.03% / 0.018 / 0.035 | 1.03% / 0.081 / 0.072 | 0.69% / 0.071 / -0.006 | 0.52% / 0.051 / 0.037 | 0.44% / 0.067 / 0.048 |
| 10 | -3.08% / -0.120 / -0.025 | 0.25% / 0.070 / 0.069 | -0.23% / 0.015 / 0.045 | 2.12% / 0.119 / 0.109 | 1.49% / 0.100 / -0.008 | 0.98% / 0.050 / 0.035 | 1.04% / 0.082 / 0.055 |
| 20 | -3.79% / -0.125 / -0.013 | 0.28% / 0.084 / 0.086 | -0.43% / 0.008 / 0.054 | 4.33% / 0.172 / 0.158 | 2.73% / 0.141 / -0.002 | 2.12% / 0.062 / 0.039 | 2.22% / 0.127 / 0.095 |

The partial association is positive in 2021–2023, 2025, and partial 2026; it is near zero in 2024 despite a positive standalone result. Partial 2020 contains only 22 sessions and is not decision-useful. Exact-history eligibility exceeds 92% in every year, reaching about 98–100% from 2023 onward, so the finding is not driven by a small eligible subset.

![Proximity quintile profiles](D:/Stock/data/ATS/decision_oriented_phase_a/analysis_runs/decision-20260820T164218Z/figures/proximity_quintile_profiles.png)

## 4. Relative volume and volatility

### Aggregate quintile relationships

| Feature | H | Q1 | Q2 | Q3 | Q4 | Q5 | Rank IC | Q5−Q1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Relative volume | 3 | 0.10% | 0.18% | 0.24% | 0.23% | 0.21% | 0.01 | 0.10% |
| Relative volume | 5 | 0.21% | 0.31% | 0.38% | 0.36% | 0.36% | 0.01 | 0.16% |
| Relative volume | 10 | 0.38% | 0.52% | 0.82% | 0.79% | 0.71% | 0.02 | 0.33% |
| Relative volume | 20 | 0.72% | 1.09% | 1.52% | 1.46% | 1.49% | 0.03 | 0.77% |
| Realized volatility | 3 | 0.14% | 0.21% | 0.26% | 0.29% | 0.06% | -0.02 | -0.08% |
| Realized volatility | 5 | 0.23% | 0.36% | 0.40% | 0.51% | 0.12% | -0.02 | -0.11% |
| Realized volatility | 10 | 0.51% | 0.73% | 0.84% | 0.93% | 0.23% | -0.03 | -0.28% |
| Realized volatility | 20 | 1.22% | 1.64% | 1.48% | 1.73% | 0.28% | -0.05 | -0.94% |

Relative volume has a modest positive low-to-high spread but its middle quintiles often do best. Realized volatility is also non-monotonic; its interpretable feature is the weak highest-volatility tail, not a smooth rank gradient.

### Year stability

Entries are Q5−Q1 / rank IC.

| Feature | H | 2020p | 2021 | 2022 | 2023 | 2024 | 2025 | 2026p |
|---|---:|---|---|---|---|---|---|---|
| Relative volume | 3 | 0.87% / 0.076 | 0.19% / 0.002 | 0.04% / 0.007 | -0.17% / -0.016 | 0.13% / 0.008 | 0.21% / 0.027 | 0.19% / 0.031 |
| Relative volume | 5 | 0.57% / 0.039 | 0.20% / -0.005 | 0.24% / 0.017 | -0.21% / -0.014 | 0.04% / 0.002 | 0.36% / 0.040 | 0.33% / 0.037 |
| Relative volume | 10 | -0.45% / 0.024 | 0.64% / 0.013 | 0.46% / 0.024 | -0.19% / -0.006 | 0.11% / 0.004 | 0.68% / 0.049 | 0.38% / 0.033 |
| Relative volume | 20 | -1.36% / 0.011 | 0.45% / 0.013 | 1.60% / 0.049 | 0.13% / 0.014 | 0.94% / 0.042 | 0.73% / 0.025 | 1.09% / 0.052 |
| Volatility | 3 | 0.39% / 0.036 | 0.20% / -0.014 | -0.19% / -0.031 | -0.12% / -0.023 | 0.12% / 0.006 | -0.44% / -0.039 | -0.10% / -0.021 |
| Volatility | 5 | 0.80% / 0.070 | 0.32% / -0.019 | -0.23% / -0.032 | -0.18% / -0.023 | 0.25% / 0.010 | -0.74% / -0.050 | -0.16% / -0.022 |
| Volatility | 10 | 0.40% / 0.072 | 0.56% / -0.026 | -0.42% / -0.038 | -0.25% / -0.030 | 0.34% / 0.014 | -1.50% / -0.070 | -0.68% / -0.043 |
| Volatility | 20 | 0.33% / 0.043 | 0.00% / -0.038 | -1.00% / -0.064 | -0.69% / -0.053 | 0.26% / -0.005 | -2.67% / -0.096 | -2.22% / -0.097 |

At 20 sessions, the relative-volume Q5−Q1 moving-block interval is approximately [0.39%, 1.16%], while the volatility interval is [-1.76%, -0.11%]. These secondary checks do not make either an executable standalone rule. Relative volume is better regarded as a weak potential condition; volatility's extreme tail is a clearer conditioning or risk-segmentation candidate.

![Relative volume and volatility](D:/Stock/data/ATS/decision_oriented_phase_a/analysis_runs/decision-20260820T164218Z/figures/relative_volume_volatility_profiles.png)

## 5. Missing-member sensitivity

### Coverage composition

| Coverage group | Sessions | Date span | Mean usable members |
|---|---:|---|---:|
| All dates | 1,430 | 2020-11-27 to 2026-08-18 | 58.63 |
| 57/60 | 455 | 2020-11-27 to 2022-11-04 | 57.00 |
| 58–59/60 | 345 | 2022-08-04 to 2024-02-06 | 58.26 |
| 60/60 | 630 | 2024-02-07 to 2026-08-18 | 60.00 |

Calendar and coverage regimes are almost deterministic: partial 2020 and 2021 are entirely 57/60; 2022 is 72.5% 57/60 and 27.5% 58–59/60; 2023 is entirely 58–59/60; 2024 is 10.4% 58–59/60 and 89.6% 60/60; 2025 and partial 2026 are entirely 60/60.

### Momentum by coverage group

| Coverage | H | Rank IC | Q5−Q1 | Q4−Q5 |
|---|---:|---:|---:|---:|
| 57/60 | 3 | -0.00 | -0.27% | 0.22% |
| 57/60 | 5 | -0.01 | -0.51% | 0.42% |
| 57/60 | 10 | -0.02 | -1.00% | 0.84% |
| 57/60 | 20 | -0.03 | -2.30% | 2.13% |
| 58–59/60 | 3 | 0.04 | 0.24% | 0.33% |
| 58–59/60 | 5 | 0.05 | 0.43% | 0.50% |
| 58–59/60 | 10 | 0.07 | 0.92% | 0.82% |
| 58–59/60 | 20 | 0.10 | 1.92% | 1.40% |
| 60/60 | 3 | 0.06 | 0.39% | 0.01% |
| 60/60 | 5 | 0.07 | 0.66% | 0.01% |
| 60/60 | 10 | 0.09 | 1.36% | 0.01% |
| 60/60 | 20 | 0.11 | 2.78% | -0.20% |

The Q4-over-Q5 pattern is confined to the incomplete-coverage regimes. This is also the older sample, so the table cannot identify a causal missingness effect. It does show that the apparent hump should not be generalized to the complete-coverage period.

The five unresolved histories—Ciech, Lotos, PGNiG, STS, and TIM—account for 1,964 of 85,800 official rows (2.29%). Missing exposures are 714, 421, 486, 239, and 104 rows respectively, all retained as `unresolved_vendor_alias`; they were never used to redefine the official denominator. Their missing returns cannot be inferred from observed members.

**Reconstruction decision:** targeted reconstruction is justified if ATS needs to decide whether pre-2024 momentum behavior or the Q4 hump is genuine, especially for Ciech, PGNiG, and Lotos. It is unlikely to change the descriptive result for the post-February-2024 60/60 subset. Reconstruction should restore issuer/ticker continuity and adjustment provenance, not simply fill prices opportunistically.

![Coverage groups by year](D:/Stock/data/ATS/decision_oriented_phase_a/analysis_runs/decision-20260820T164218Z/figures/coverage_groups_by_year.png)

## Interpretation boundaries

- The sample contains only about 5.7 years, including a 22-session partial 2020 and a partial 2026. Year results are descriptive.
- Forward labels overlap, and securities within a session are cross-sectionally dependent. Constituent-row counts are not independent sample sizes; the effective time-series sample is at most the number of sessions shown.
- HAC and moving-block intervals are secondary robustness summaries, not a cure for short history, regime concentration, or coverage-period confounding.
- Point-in-time membership is retained, but five unresolved vendor histories remain a survivorship/coverage concern in older periods.
- Price adjustment and corporate-action treatment remain inherited from the validated Phase A Stooq inputs. The analysis did not independently reconstruct every corporate action.
- The proximity feature requires exact 252-session history and uses only prior-session information. It is report-specific and does not alter the canonical Phase A run.
- All quintile returns are gross equal-weight diagnostics. They omit execution timing, costs, liquidity, tradability, and turnover.

## Reproducibility and retained artifacts

The frozen plan and report-specific code are in `D:\Stock\ATS\RESEARCH\prototypes\decision_oriented_phase_a`. The successful immutable analysis run is `D:\Stock\data\ATS\decision_oriented_phase_a\analysis_runs\decision-20260820T164218Z`; its manifest SHA-256 is `EB1BC84E21EF58D6941126E9F7F6EA8501F375E5C5C73DC55C0BE9F8520302FC`. It contains 20 machine-readable tables, six figures, the plan and configuration, metrics, logs, hashes, and a complete report-code snapshot.

Principal commands used:

```powershell
& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' `
  'D:\Stock\ATS\RESEARCH\prototypes\decision_oriented_phase_a\build_extended_panel.py' `
  --config 'D:\Stock\ATS\RESEARCH\prototypes\decision_oriented_phase_a\config.yaml' `
  --destination 'D:\Stock\data\ATS\decision_oriented_phase_a\runs\extension-20260820T163347Z'

& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' `
  'D:\Stock\ATS\RESEARCH\prototypes\decision_oriented_phase_a\analyze_decisions.py' `
  --panel-run 'D:\Stock\data\ATS\decision_oriented_phase_a\runs\extension-20260820T163347Z' `
  --analysis-plan 'D:\Stock\ATS\RESEARCH\prototypes\decision_oriented_phase_a\analysis_plan.md' `
  --config 'D:\Stock\ATS\RESEARCH\prototypes\decision_oriented_phase_a\config.yaml' `
  --output 'D:\Stock\data\ATS\decision_oriented_phase_a\analysis_runs\decision-20260820T164218Z'

& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' -m pytest `
  'D:\Stock\ATS\source\python\tests\test_features_labels.py' `
  'D:\Stock\ATS\source\python\tests\test_identity_universe.py' `
  'D:\Stock\ATS\source\python\tests\test_inference.py' `
  'D:\Stock\ATS\source\python\tests\test_panel_diagnostics.py' `
  'D:\Stock\ATS\source\python\tests\test_phase_a_archive_integrity.py' -q

$env:PYTHONPATH='D:\Stock\ATS\source\python\src'
& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' `
  -m ats_research validate `
  --run-dir 'D:\Stock\data\ATS\phase_a\runs\phasea-2a2b3898aba37814'

& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' `
  'D:\Stock\ATS\RESEARCH\prototypes\decision_oriented_phase_a\analyze_decisions.py' `
  --panel-run 'D:\Stock\data\ATS\decision_oriented_phase_a\runs\extension-20260820T163347Z' `
  --analysis-plan 'D:\Stock\ATS\RESEARCH\prototypes\decision_oriented_phase_a\analysis_plan.md' `
  --config 'D:\Stock\ATS\RESEARCH\prototypes\decision_oriented_phase_a\config.yaml' `
  --output 'D:\Stock\data\ATS\decision_oriented_phase_a\analysis_runs\decision-20260820T170000Z-reproduction'
```

The five-file Phase A test set returned **22 passed** (6.33 seconds before the final wrapper cleanup and 5.93 seconds afterward). Archive-integrity validation of the trusted run returned `passed: true`, 76,320 panel rows, 1,272 sessions, 30 manifest artifacts, a valid source snapshot, and reconstructable Git commit. Its retained reproduction report also states `passed: true`, with matching configuration, environment-lock, metrics, run ID, and logical artifact hashes.

The report calculation was then repeated into the fresh immutable directory `decision-20260820T170000Z-reproduction`. All 20 CSV tables matched the primary analysis run byte-for-byte; metrics matched after excluding only their creation timestamp; the plan and configuration hashes matched. The reproduction source ZIP contains the same four computational entries plus the later-created `make_report_snippets.py`, so the ZIP bytes appropriately differ. This extra presentation helper did not participate in the calculations. The reproduction manifest SHA-256 is `2F64D64FCF912B47547821D134F0310436AF993A6052F105CB67AF63259DEA27`.

The extension manifest records current repository commit `bb82e256ad35b695b1419d3a84685da0622b9fe2`; the trusted Phase A commit remains `caf76ee9b7da77829cdc1b32c982a7b895e2c743`. Relative to the trusted manifest, only the Phase A CLI and archive-validator hashes differ; feature, label, panel, diagnostics, inference, bars, universe, and artifact code hashes match. No Phase A or Phase B implementation file was edited for this report. The working tree's pre-existing `source/python/README.md` modification was left untouched.

During the original report calculations, `conda run` emitted a non-fatal OpenCL vendor cleanup warning caused by a broken activation/deactivation hook. The repaired wrapper now calls the cloned environment's Python executable directly while retaining isolated temp, Matplotlib, and Numba locations. A final smoke run passed native/scientific checks for NumPy, SciPy, pandas, scikit-learn, Numba, PyArrow, Matplotlib, Torch, and the cloned Conda library directory; the subsequent 22 Phase A tests passed with no hook warning. No packages were installed, upgraded, or removed. Every retained extension, analysis, validation, and reproduction used in this report exited successfully; no result was inferred from a crashed process.

Two earlier analysis directories are intentionally retained as failed immutable attempts: one exposed a pandas read-only rank array and one exposed duplicate display labels. Both defects were confined to report-specific code and corrected without modifying Phase A or Phase B.

### Diagnostics not performed or not identifiable

- Same-close diagnostic labels do not establish an executable entry price; no execution, transaction-cost, or portfolio simulation was attempted.
- Coverage group differences are not causally identifiable because coverage and calendar time are confounded.
- The counterfactual returns of the five missing histories cannot be recovered from retained Phase A evidence; targeted source reconstruction is required.
- A complete independent audit of Stooq adjustment factors and every corporate action was outside this focused report. The validated Phase A adjustment state was inherited rather than re-engineered.

### Claim-to-artifact map

| Claim | Primary retained table |
|---|---|
| Momentum quintiles and annual stability | `tables/momentum_quintiles.csv`, `tables/momentum_rank_ic.csv`, `tables/momentum_contrasts.csv` |
| Strong-stock pullback ordering | `tables/strong_stock_pullback.csv`, `tables/strong_stock_pullback_contrasts.csv` |
| Proximity standalone and incremental association | `tables/proximity_quintiles.csv`, `tables/proximity_rank_ic.csv`, `tables/proximity_partial_rank_ic.csv` |
| Momentum × proximity cells | `tables/proximity_momentum_3x3.csv` |
| Relative-volume and volatility shapes | `tables/relative_volume_volatility_quintiles.csv`, `tables/relative_volume_volatility_rank_ic.csv` |
| Coverage and calendar confounding | `tables/coverage_summary.csv`, `tables/coverage_by_year.csv`, `tables/coverage_momentum_sensitivity.csv` |
| Five unresolved histories | `tables/five_exit_history_exposure.csv`, `tables/missing_reasons_by_coverage_year.csv` |
| Secondary intervals | `tables/secondary_uncertainty.csv` |
