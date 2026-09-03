# Phase D2-NM retrospective adjudication

Status: **WEAK BUT PERSISTENT — prospective monitoring justified**

Date: 2026-09-03

The frozen C+P+X LightGBM follow-up provides broad enough retrospective
hypothesis-development evidence to keep a prospective prediction stream running.
It does not establish alpha, independent confirmation, portfolio economics, or
deployment readiness. Phase D3, a portfolio/backtest, and a new feature block
remain unauthorized.

## Integrity and scientific object

The plan and machine contract were frozen in commit `c44ec50` before the new
per-half-year, tail, concentration, or influence diagnostics were calculated.
The accepted prediction table is `phase-d2-predictions-20260902-v4`, scientific
logical hash
`ad9ea68d66fde122e127d502706f8eeaea162749b6f67a38b1a68ac0c06e8466`.

`RICH_NO_M_LIGHTGBM` was already independently fitted at all eight accepted
January/July refits. Every retained record binds the exact same 18 C+P+X feature
allowlist, frozen LightGBM parameters, three separately fitted calibration
blocks, exact endpoint-purged final fit, threshold frozen before final refit,
common outer score population, score hashes, fit/score row counts, and no outer
outcome access. Reuse of the accepted predictions was therefore required; no
model was refit for Stage R.

The accepted run's historical process-level qualification remains: labels were
loaded eagerly for all training periods before the block loop, so literal
sequential label-file admission was not retained as an execution trace. The
actual model-fit rows and endpoints were independently bounded and reproduced;
the extra loaded labels were not passed to an estimator. This follow-up does not
upgrade the accepted run's execution-integrity wording.

## Historical population and rank findings

All evidence below is retrospective hypothesis-development and robustness
evidence. The pooled population contains 871 sessions, 51,902 scored semantic
rows, and 51,900 available 20-session outcomes. Every session has 56–60 scored
securities; the official membership denominator remains 60.

| Half-year | Sessions | Rows | no-M IC | Δ vs C linear | Δ vs C LightGBM | Δ vs full rich |
|---|---:|---:|---:|---:|---:|---:|
| 2023 H1 | 124 | 7,440 | 0.070403 | +0.192833 | +0.104474 | +0.010695 |
| 2023 H2 | 126 | 7,555 | -0.024482 | -0.010294 | +0.003652 | -0.077607 |
| 2024 H1 | 124 | 7,436 | -0.026416 | -0.006251 | -0.000009 | -0.025636 |
| 2024 H2 | 125 | 7,458 | 0.082449 | +0.020430 | +0.065792 | +0.069949 |
| 2025 H1 | 123 | 7,254 | -0.011226 | +0.023009 | +0.008294 | -0.010804 |
| 2025 H2 | 126 | 7,410 | 0.103284 | +0.045469 | +0.092100 | +0.055890 |
| 2026 H1 | 123 | 7,349 | 0.112213 | -0.058621 | +0.048745 | +0.040988 |
| **Pooled** | **871** | **51,902** | **0.043755** | **+0.029554** | **+0.046221** | **+0.009032** |

No-M's pooled median session IC is 0.049094. The positive session-delta fractions
are 54.76% versus `C_LINEAR` and 60.85% versus `C_LIGHTGBM`. Mean delta is
positive in four of seven half-years versus `C_LINEAR` and six of seven versus
`C_LIGHTGBM`; the median half-year deltas are +0.020430 and +0.048745.

The accepted 20-session moving-block 95% interval is [-0.008742, +0.070653]
against `C_LINEAR` and [+0.018968, +0.072022] against `C_LIGHTGBM`. Intervals are
reported uncertainty, not an extra retrospective classification gate. Every
leave-one-half-year-out pooled delta remains positive against both comparators;
the smallest is +0.002450 versus `C_LINEAR` after omitting 2023 H1. Removing the
largest contributing security does not reverse either positive pooled delta.

The pooled 2024 and 2025 H1–2026 H1 no-M rank aggregates were already inspected
when the hypothesis was formed. Their half-year decompositions and the 2023,
tail, concentration, and influence results were newly opened after the freeze.

## Selective-opportunity findings

| Half-year | Episodes | Mean | Median | vs eligible | vs C linear | vs C LightGBM |
|---|---:|---:|---:|---:|---:|---:|
| 2023 H1 | 14 | -1.44% | -1.24% | -3.89% | +1.99% | +4.52% |
| 2023 H2 | 19 | -2.85% | -1.88% | -3.19% | -1.37% | +5.07% |
| 2024 H1 | 85 | +1.84% | +0.72% | +0.68% | +1.81% | +4.10% |
| 2024 H2 | 86 | +2.20% | +0.03% | +2.49% | +4.93% | +2.07% |
| 2025 H1 | 58 | +5.48% | +5.12% | +1.25% | +4.23% | +2.82% |
| 2025 H2 | 40 | +0.84% | -0.11% | -1.00% | -0.82% | -1.33% |
| 2026 H1 | 62 | +4.80% | +4.36% | +0.13% | -1.53% | -3.82% |
| **Pooled** | **364** | **+2.53%** | **+1.24%** | **+0.35%** | **+1.77%** | **+1.60%** |

There are 3,040 raw candidate rows, 364 de-overlapped episode anchors, 77
represented securities, 777 raw opportunity sessions, and 94 idle sessions.
The pooled severe-outcome frequency is 9.07%; its difference is -2.16 points
versus frequency-matched `C_LINEAR` and -4.96 points versus `C_LIGHTGBM`.
The pooled tail has all four required descriptive signs, but its uncertainty is
not decisive: the 95% lower bounds are -0.82 points versus eligible, -0.19 points
versus `C_LINEAR`, and -0.72 points versus `C_LIGHTGBM`.

Positive no-M excess is not dominated under the frozen 50% rule. Largest shares
are 12.13% for one security, 5.78% for one session, 25.96% for one half-year,
35.69% for one chronological quartile, and 11.77% for one rolling 20-session
cluster. Security positive-excess HHI is 0.03690 and session HHI is 0.01428.

## Direct removal-of-M diagnostic

Removing M improves pooled mean session IC by +0.009032 and improves four of
seven half-years. No-M's pooled episode mean/median are +2.53%/+1.24%, versus
+0.65%/-0.32% for full-rich LightGBM. Candidate-row frequency falls from 7.59%
to 5.86%, a material 1.73-point (22.8% relative) reduction. Episode-count
concentration is reported in the sealed `direct_no_m_vs_full_rich.json`; this
diagnostic does not select another challenger or authorize changing M.

## Mechanical classification and reproduction

The result is `WEAK BUT PERSISTENT`. It passes positive pooled delta against both
comparators, at least four positive half-years against each, pooled superiority
to full-rich LightGBM, and the no-security/no-half-year-dominance rules. It is not
`STRONG RESEARCH DIRECTION` because only four of seven half-years are positive
against `C_LINEAR`; five are required.

Primary sealed run:
`D:\Stock\data\ATS\phase_d_ml\followup_runs\phase-d2-nm-followup-20260903-v1`
(logical hash
`d5215ca376887be6116a35d59f1ca49cbc56cf0f6d37551ac5925b4f8f0e193c`).

An independently coded evaluator reloaded the raw accepted predictions and
outcomes, reconstructed episodes and frequency matches, recomputed all
classification inputs including all-security influence, and matched the primary
classification. Status is `PASS`; scientific logical hash is
`e3b091c5883551c1f1ae128de0d41aea8bacb19e6f972fd4630d5f9d7cfe2a6c`.

## Prospective status and boundary

The original empty registration, `phase-d2-nm-post-freeze-2026-v1`, is preserved
byte-for-byte and is now explicitly recorded as
`NON_OPERATIONAL_SUPERSEDED_EMPTY_REGISTRATION`. It contained zero predictions,
so no prospective evidence was damaged. The repaired append-only stream is
`phase-d2-nm-post-freeze-2026-v2`, currently
`ACTIVE_EMPTY_AWAITING_ELIGIBLE_SESSION` with zero predictions. The accepted 35
sessions remain historical canary evidence only and are not backfilled.

The v2 scorer accepts an explicit hash-pinned observation, label, walk-forward,
PIT membership, and official-calendar package. It admits labels only for the
current refit block and emits an atomic score package with no outcomes and no
publication claims. The publisher independently verifies the scorer audit,
package manifest, input hashes, scientific and operational contracts, accepted
feature allowlists and models, exact 60-member PIT identity set for all three
cells, one-session information lag, 08:45 decision timestamp, and exact
20-session target timestamps. Only after the batch directory is atomically
finalized does the publisher capture completion time and issue an immutable
receipt. Eligibility comes only from that post-finalization time; a late batch is
monitoring-only forever. There is no daemon or scheduler. Fewer than 40 timely
`POST_FREEZE_2026` sessions will make the early checkpoint `INSUFFICIENT`, not
failed.

## Remaining caveats and authority

- Historical evidence is selection-contaminated retrospective robustness, not
  independent or prospective confirmation.
- The accepted D2 process-level sequential label-admission trace remains not
  proven, although exact estimator inputs, endpoint purges, predictions, and the
  full classification were independently reconstructed.
- Results are split-adjusted price-only and exclude cash distributions while
  retaining known dividend gaps.
- Opportunity rows and episodes are not trades; costs, sizing, fills, liquidity,
  cash, turnover, and portfolio returns were not tested.
- The repaired prospective stream has zero qualifying post-freeze sessions at
  publication and supplies no prospective performance evidence yet.

Retrospective evidence integrity: `PASS`

Retrospective classification: `WEAK BUT PERSISTENT`

Prospective monitoring justified: `YES`

Prospective stream started: `YES — v2 active empty; v1 superseded empty`

Phase D3 authorized: `NO`

Portfolio/backtest authorized: `NO`

New feature block authorized: `NO`

Deployment claim: `NO`
