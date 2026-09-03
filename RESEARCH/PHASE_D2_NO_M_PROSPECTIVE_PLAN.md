# Phase D2-NM — retrospective adjudication with conditional prospective monitoring

**Status:** frozen for bounded execution; this document and
`source/python/configs/phase_d2_no_m_followup.json` must be committed before any
previously unopened no-M per-period, tail, concentration, or influence result is
calculated.

**Contract ID:** `phase-d2-nm-followup-20260903-v1`

**Selection history and evidence level:** inspection of accepted Phase D2 results
suggested that removing the frozen market-state block M might improve the rich
LightGBM cell. All 2023 H1 through 2026 H1 results in Stage R are therefore
retrospective hypothesis-development and robustness evidence. They may decide
whether the representation deserves further research, but are not untouched,
independent confirmation, prospective evidence, trading evidence, or deployment
evidence. Only predictions sealed under this contract before their 08:45
Europe/Warsaw decision timestamps can accumulate prospective evidence.

The accepted Phase D2 `STOP — VERIFIED / EXECUTION INTEGRITY NOT FULLY PROVEN`
remains immutable and continues to govern the original C+P+X+M challenger. This
follow-up asks a narrower research-direction question and cannot rewrite that
historical conclusion.

## 1. Bounded decision design

### Exact decision

Does the exact existing C+P+X LightGBM representation show sufficiently broad
and stable incremental information, selective-opportunity behavior, and
chronological persistence to justify keeping a prospective prediction stream
running and possibly discussing one later, specifically motivated feature
research step?

### Cheapest credible experiment

Reuse the sealed accepted D2 predictions and outcomes. Evaluate exactly
`RICH_NO_M_LIGHTGBM`, `C_LINEAR`, and `C_LIGHTGBM` on seven complete half-years.
Use `RICH_LIGHTGBM` only for the direct frozen-M diagnostic. Add no fit, feature,
model, threshold, horizon, subgroup, universe, or vendor search. Build minimal
prospective machinery only if the retrospective classification is `STRONG
RESEARCH DIRECTION` or `WEAK BUT PERSISTENT`.

### Must-have validity work

- Prove that accepted D2 Stage 1 independently fitted and scored
  `RICH_NO_M_LIGHTGBM` at every applicable refit with exactly the frozen 18 C+P+X
  predictors and the frozen LightGBM configuration.
- Bind the feature registry, accepted prediction run, prediction-table logical
  hash, feature lists, estimator configuration, windows, endpoint purges,
  calibration blocks, thresholds, common score masks, prediction hashes, row
  counts, and fit records.
- Use identical semantic rows for every paired comparison; retain official
  denominator 60 and visible missing, unresolved, non-trading, and unavailable
  states.
- Preserve exact 20-session split-adjusted open-to-open outcomes, PIT timing,
  one-session information lag, and session-level dependence.
- Reproduce every classification input with a separate implementation and fail
  closed on any unresolved correctness or comparability question.

### Useful nongating diagnostics

Cumulative paired-delta plots, direct no-M versus full-rich comparison, exact
concentration tables, and the distinction between aggregates already reported in
Phase D2 and newly opened diagnostics explain the result but cannot select a new
scientific object.

### Deferred

Every alternative model, feature set, threshold, target, horizon, subgroup,
universe, vendor, total-return reconstruction, portfolio/backtest, cost, sizing,
fill, execution, Phase D3, feature store, MLflow, service, daemon, scheduler, and
deployment task is deferred. A positive classification permits discussion of one
later specifically motivated feature block; it does not authorize implementing
one.

### Stop/continue rule

Apply the classifications in section 5 mechanically after all validity and
reproduction checks. Only `STRONG RESEARCH DIRECTION` or `WEAK BUT PERSISTENT`
authorizes the minimal prospective stage. `UNSTABLE`, `NEGATIVE`, or `NOT
PROVEN` stops before prospective subsystem work.

## 2. Frozen scientific object

The machine-readable contract is authoritative where prose could be ambiguous.

- challenger: `RICH_NO_M_LIGHTGBM`;
- conventional comparators: `C_LINEAR`, `C_LIGHTGBM`;
- direct M diagnostic only: `RICH_LIGHTGBM`;
- no-M features: the exact accepted 18 C+P+X predictors filtered from feature
  registry SHA-256
  `733bacb9c1132d98eacb4a190cfb3cd96b0163207af46f3745002206b3705ef6`;
- estimator: accepted deterministic `lightgbm.LGBMRegressor` configuration;
- accepted prediction run: `phase-d2-predictions-20260902-v4`;
- required prediction-table logical hash:
  `ad9ea68d66fde122e127d502706f8eeaea162749b6f67a38b1a68ac0c06e8466`;
- target: `label__open_to_open__20` on `split_adjusted_price_return`, excluding
  cash distributions and retaining known dividend price gaps;
- refits: first official January/July session, trailing 36 calendar months,
  exact endpoint purge, three six-month prequential calibration blocks, then a
  distinct final refit;
- threshold: `max(0.010000, numpy linear empirical q90)` separately by cell and
  refit, strict `score > threshold`, no quota, zero-candidate sessions valid;
- episode rule: first qualifying observation is the anchor; later qualifying
  observations remain in the episode until more than 20 official sessions have
  elapsed since the preceding qualifying observation; and
- identity: security identity is excluded from predictors and never resolves a
  score or outcome tie.

If independent no-M fitting and scoring cannot be proved exactly, stop with
`NOT PROVEN` before Stage R.

## 3. Frozen historical populations

Use every complete outcome-available half-year and no other historical period:

| Population ID | Sessions |
|---|---|
| `RETRO_2023_H1` | 2023-01-02 through 2023-06-30 |
| `RETRO_2023_H2` | 2023-07-03 through 2023-12-29 |
| `RETRO_2024_H1` | 2024-01-02 through 2024-06-28 |
| `RETRO_2024_H2` | 2024-07-01 through 2024-12-30 |
| `RETRO_2025_H1` | 2025-01-02 through 2025-06-30 |
| `RETRO_2025_H2` | 2025-07-01 through 2025-12-30 |
| `RETRO_2026_H1` | 2026-01-02 through 2026-06-30 |

The pooled population is the ordered union of all seven with equal weight per
defined session. The 2024 pooled and 2025 H1–2026 H1 pooled no-M rank aggregates
were already inspected and must be labeled as such. The 2023 no-M breakdown,
all half-year no-M breakdowns, tails, concentration, and influence results are
newly opened under this freeze. No security-session is treated as an independent
inferential observation.

## 4. Frozen diagnostics

### Rank diagnostics

For each half-year and pooled across seven, calculate session Spearman rank IC
on the identical common outcome-evaluable rows, requiring at least 45 paired rows
and nonconstant score and outcome. Report each cell's mean and median session IC;
paired no-M-minus-`C_LINEAR`, no-M-minus-`C_LIGHTGBM`, and no-M-minus-full-rich
session-IC deltas; delta mean and median; positive-delta count and fraction;
defined/usable session counts; row and distinct-security counts; and 95% intervals.

Uncertainty is the accepted deterministic circular moving-block bootstrap over
ordered decision sessions: 5,000 samples, 20-session blocks, PCG64 seed
`20260831`, identical resample indices for paired cells, linear 2.5%/97.5%
quantiles, and at least 99% defined replicates. Report cumulative paired-delta
series without using them as additional gates.

For each comparator, recompute the pooled mean paired delta after leaving out
each half-year. Separately identify the largest contributing security as the
identity-neutral boundary set whose removal causes the largest decrease in the
pooled mean paired delta, including all exact ties, and report every leave-one-
security-out result in that set. No refit or recalibration is permitted.

### Selective-opportunity diagnostics

For each half-year and pooled, report candidate rows and fraction, opportunity
sessions and fraction, idle sessions and fraction, effective episode anchors,
represented securities, anchor-level mean and median 20-session outcome,
equal-session no-M minus eligible-universe outcome, no-M minus each same-session
frequency-matched conventional outcome, severe outcome (`<= -0.10`) frequency
and comparator differences, plus security, session, and chronological
concentration and largest-contributor influence.

Frequency matching uses the common outcome-evaluable score population and the
integer number of no-M episode anchors on each session. The comparator's kth
score boundary is selected by score only; observations above receive weight 1,
below receive 0, and all exact boundary ties receive equal fractional weight so
weights sum exactly to k. Sessions with k=0 remain in frequency/idle reporting
and have no tail contrast. Tail comparisons aggregate available per-session
contrasts with equal session weight. The median is across all evaluable no-M
episode anchors. Severe outcomes use the same weights and session populations.

Concentration reports largest and top-five shares and HHI by security and
session, half-year shares/HHI, contiguous chronological-quartile shares, and the
maximum rolling 20-session episode share. Exact contributor-boundary ties are
included without identity resolution. Recompute rank and tail conclusions after
removing each largest-contributor boundary security, with no refit or threshold
change.

### Frozen dominance and coherence definitions

A result is dominated when any one security, one decision session, one
half-year, or one contiguous 20-session cluster accounts for at least 50% of all
positive no-M episode-outcome excess over the same-session eligible universe,
or when removing the identified largest contributor changes a positive pooled
delta against either conventional comparator to nonpositive. Half-year rank
dominance also holds when one half-year accounts for at least 50% of the sum of
positive session paired deltas against either conventional comparator.

A coherent selective-tail advantage requires all four descriptive signs:
pooled no-M opportunity mean above the eligible universe, above each
frequency-matched conventional comparator, and pooled no-M opportunity median
strictly positive. Tail evidence is inconsistent with a positive rank result
when fewer than four half-years have positive no-M-minus-eligible tail contrast
or the coherent pooled-tail definition fails.

### Direct no-M versus full-rich diagnostic

Report whether removing M improves pooled mean rank IC, improves mean rank IC in
at least four of seven half-years, improves pooled selective-tail mean and
median, changes candidate frequency by at least 20% relatively or 1 percentage
point absolutely, and changes every reported concentration measure. This is a
fixed ablation description only; `RICH_LIGHTGBM` is not selectable.

## 5. Mechanical retrospective classification

Apply in this order.

1. `NOT PROVEN` if any PIT, population, timing, outcome, independent-fit,
   artifact, or reproduction requirement is not established.
2. `NEGATIVE` if no-M pooled mean session-IC delta is nonpositive against the
   stronger conventional comparator and the coherent selective-tail definition
   fails. The stronger comparator is the one with the larger pooled mean session
   IC; an exact tie resolves to `C_LINEAR`.
3. `STRONG RESEARCH DIRECTION` only if pooled mean session-IC delta is at least
   `+0.005` against both conventional comparators; each contrast is positive in
   at least five of seven half-years; the median of the seven half-year mean
   deltas is positive against each; pooled no-M mean IC exceeds full-rich
   LightGBM; the coherent selective-tail definition passes; no dominance
   definition triggers; and all validity and reproduction checks pass.
4. `WEAK BUT PERSISTENT` if pooled mean session-IC delta is positive against
   both conventional comparators; each contrast is positive in at least four of
   seven half-years; no-M pooled mean IC exceeds full-rich LightGBM; no security
   or half-year dominance definition triggers; and at least one strong-direction
   materiality, persistence, median-half-year, tail, session/cluster dominance,
   or concentration condition fails.
5. Otherwise classify `UNSTABLE`. This includes a positive pooled result with
   fewer than four positive half-years against either comparator, material sign
   changes, security/session/cluster/half-year dominance, an inconsistent tail,
   or removal of M helping only in an isolated period.

Statistical intervals describe uncertainty and are reported; they are not an
additional academic significance gate for this retrospective research-direction
decision.

## 6. Conditional prospective stage

Build the following only after a mechanically reproduced `STRONG RESEARCH
DIRECTION` or `WEAK BUT PERSISTENT` result.

Reuse exactly the same 18 features, LightGBM parameters, two comparators,
20-session label, January/July refits, trailing 36-month window, endpoint purge,
three-block calibration, threshold, episode rule, PIT TOP60 population, and
split-adjusted price basis. Retrospective results cannot change them.

A row is prospectively eligible only if its immutable publication is sealed no
later than the decision session's 08:45 Europe/Warsaw timestamp. Record
information session, decision session/timestamp, generation timestamp,
publication/seal timestamp, target start and endpoint, label availability,
prospective eligibility, monitoring-only status, and exclusion reason. A late
row is monitoring-only forever. A missed row remains missed and is never
backfilled.

The accepted 35 July–August 2026 monitoring sessions remain historical canary
evidence. New timely rows enter `POST_FREEZE_2026`. After the final 20-session
outcomes mature, report an early prospective checkpoint with exact sample size
and accepted uncertainty. Fewer than 40 qualifying decision sessions is
`INSUFFICIENT`, not failure. Later 2027 rows may accumulate under the unchanged
contract, but this task does not wait for them.

Minimal permitted machinery is an explicit three-cell contract, prediction-only
command using pinned inputs, append-only immutable publication, objective timing
eligibility, block-scoped label access for refits, rejection of outcomes and late
predictions, and a concise manual runbook. Do not build a service or scheduler.

## 7. Required evidence and integration

Publish machine-readable per-session, per-half-year, tail, concentration,
classification, provenance, and independent-reproduction outputs without
overwriting accepted D2 artifacts. Publish a concise retrospective report and a
fresh-kernel executable owner-review notebook at
`source/python/notebooks/05_phase_d_no_m_followup.ipynb` that reads sealed outputs
without fitting models.

Commit this freeze first. Commit implementation and results separately. Preserve
the three unrelated untracked environment paths. Completed, accurately qualified
evidence is then fast-forwarded to `master`, validated after merge, and pushed
normally. None of those integration steps authorizes Phase D3, a portfolio test,
a new feature block, or deployment.
