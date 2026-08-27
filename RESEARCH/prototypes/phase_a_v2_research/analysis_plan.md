# Phase A v2 frozen analysis plan

Frozen on 2026-08-27 before inspection or computation of Phase A v2 results. This
plan may change only to correct a demonstrated implementation error; any change
must be recorded in `plan_deviations.json` and creates a new plan hash.

## Inputs and immutable periods

- Candidate input: `D:/Stock/data/ATS/gpw_split_normalization/runs/gpw-split-normalization-20260826-v4/candidate_panel.parquet` under manifest SHA-256
  `e77ce37cb51c3a1e5608b4b2c9b112abe51635bdae1ce64db0b5aa7d4780331a`.
- Trusted original control: `D:/Stock/data/ATS/phase_a/runs/phasea-2a2b3898aba37814`, observed manifest SHA-256
  `aca68c02508e567ddf6a6666b78f076354a147a29bd034a1632ca21418aaac19`.
- Extended Stooq control: `D:/Stock/data/ATS/decision_oriented_phase_a/runs/extension-20260820T163347Z`, observed manifest SHA-256
  `1a68f010125b625ca55a21efd4299d9a744b16be11979810a71180abeb813a7f`.
- Extended accepted analysis: `D:/Stock/data/ATS/decision_oriented_phase_a/analysis_runs/decision-20260820T164218Z`.
- Paired and full-new common interval: 2020-11-27 through 2026-08-18.
- Added interval: 2019-12-23 through 2020-11-26.
- Expanded new interval: 2019-12-23 through 2026-08-18.
- Evaluation endpoint is fixed at 2026-08-18. A label is censored unless its
  exact endpoint is on or before that date.
- Never resolve a `latest` pointer. Accepted Phase A/B/C artifacts are read-only.

## Price, universe, timing, and missingness semantics

- New basis name: `split_adjusted_price_return`; it uses source/native OHLC
  transformed only by the pinned split factors. Cash distributions are not
  included and cash-dividend price gaps are preserved. It is not total return,
  dividend-neutral return, or a reproduction of the Stooq basis.
- Old basis name: accepted Stooq-adjusted or economic-return-like basis; it is
  not asserted to be total return.
- Point-in-time WIG20 plus mWIG40 membership and an official denominator of
  exactly 60 rows per evaluation session are mandatory. On 2019-12-23 the
  denominator remains 60 even when feature eligibility is lower.
- Decision session `t` is pre-open. A feature uses only the immediately prior
  official WIG session `s`; no same-`t` bar is an input. Daily bars are assumed
  conservatively available after their close and before the next decision;
  vendor latency is not independently verified.
- No synthetic or forward-filled prices. Every lookback and label endpoint is
  an exact official WIG-session endpoint. Missing, documented non-trading, and
  right-censored states remain distinct.
- Price usability follows `price_usable_for_features`. Relative volume also
  requires `volume_usable_for_relative_volume` for every volume observation in
  its exact window.
- Pairing is performed independently for every feature, label anchor, and
  horizon on the intersection of eligible `(security_id, session_date)` rows.
  Old and new ranks, buckets, ICs, and label comparisons use exactly those same
  identities and dates for that comparison.

## Frozen features

All stock formulas below are evaluated at prior session `s`.

- `momentum_12_1 = close[s-21] / close[s-252] - 1`; both exact endpoints are
  required, excluding the most recent 21 sessions.
- `return_5 = close[s] / close[s-5] - 1`; exact endpoints required.
- `realized_volatility_20`: sample standard deviation of the 20 consecutive
  close-to-close returns ending at `s`; all 21 closes required.
- `relative_volume_20 = volume[s] / mean(volume[s-19:s]) - 1`; all 20 volumes
  must be present and explicitly usable for relative volume.
- `wig_trend_200 = WIG close[s] / mean(WIG close[s-199:s]) - 1`; this is a
  descriptive regime variable and uses the accepted fixed WIG series.
- `proximity_to_max_high_252 = close[s] / max(high[s-251:s])`.
- `proximity_to_max_close_252 = close[s] / max(close[s-251:s])`.
- Both proximity variants require exactly 252 consecutive session observations.
  They are reported independently and never pooled or selected by strength.
- The max-close definition maps to the 2026-08-20 decision-oriented report and
  `RESEARCH/prototypes/decision_oriented_phase_a/analyze_decisions.py`. The
  max-high definition maps to the earlier accepted Phase A feature prose/report;
  exact code/report locations will be recorded in the semantic mapping table.

Ranks use average ranks within each eligible session and percentile
`rank / eligible_count`. Fixed quintiles are `ceil(percentile*5)` and fixed
terciles are `ceil(percentile*3)`, clipped to their declared ranges. The
momentum-by-proximity design is the fixed 3 by 3 cross of these terciles.

## Frozen labels

For horizons `h in {3,5,10,20}`:

- Legacy close-to-close: `close[t+h] / close[t] - 1`.
- Decision-aligned open-to-open: `open[t+h] / open[t] - 1`.

Both require prices at the exact official WIG sessions. Open-to-open is an
execution-timing proxy, not evidence of auction fillability. Results are never
selected between anchors.

## Hypotheses and expected direction

Primary:

1. Proximity to the trailing high is positively associated with forward return
   after controlling for 12-1 momentum; both proximity definitions are tested.
2. Medium-term momentum has a positive cross-sectional association.
3. The highest realized-volatility quintile has lower forward return than the
   lower-volatility selections and can serve as a negative filter.

Secondary controls:

4. Within each frozen strong-stock condition (`momentum > 0` and momentum
   percentile rank `> 0.5`), a deep five-session pullback (`<= -5%`) does not
   outperform nonnegative five-session continuation.
5. Relative volume is expected to be weak or only conditionally useful.

No feature family, cutoff, quantile, horizon, anchor, or period is added or
optimized after results are seen.

## Mandatory analyses and diagnostics

Three outputs remain separate: paired old/new common-period basis sensitivity,
full-new common-period coverage effect, and expanded-new results split into the
added interval, common interval, and aggregate.

For every feature/period/anchor/horizon report official rows and expected 60,
price-usable, feature-eligible, label-eligible, joint/ranking denominator;
session rank IC; mean, median, positive-session share; fixed quintile mean
returns and counts; Q2-Q1 through Q5-Q4 adjacent differences; quantile-profile
Spearman monotonicity; and calendar-year stability.

For both proximity variants also report partial rank IC controlling the
session momentum rank and the fixed momentum x proximity 3x3 cell means,
constituent/session counts, minimum cell counts, and warnings when a cell has
fewer than 5 names on any contributing session or fewer than 30 total
constituent observations.

Paired diagnostics additionally report session feature-rank agreement,
quintile reassignment, paired old-minus-new IC and label differences, eligibility
transitions, largest absolute-difference sessions and securities, the corrected
Dino window, and a conclusion-change label of strengthens, weakens, reverses,
or unchanged. Differences are attributed only descriptively among vendor
selection, split treatment, cash-dividend treatment, and coverage.

## Frozen inference and multiplicity

- Unit of time-series inference is the session statistic, equally weighted by
  session. Constituent counts remain descriptive.
- Newey-West/HAC standard errors use Bartlett weights and lag equal to horizon.
- Deterministic circular moving-block bootstrap uses seed 20260827, 1,000
  resamples, and block length `max(20,horizon)`; percentile 95% intervals.
- Two-sided normal HAC p-values are adjusted by Benjamini-Hochberg within two
  frozen families: (A) all primary standalone and partial-rank IC tests across
  both anchors and four horizons; (B) all secondary standalone IC and frozen
  pullback-contrast tests across both anchors and four horizons. Quantile shape,
  paired deltas, and sensitivities are supporting diagnostics, not extra tests.
- Non-overlapping sensitivity reports every offset `0..h-1` without selecting
  an offset.

## Frozen influence, sensitivity, and confirmation checks

- Leave each full calendar year 2021-2025 out in turn; preserve all partial
  years in each comparison.
- Report added interval alone and exclude it from the expanded result.
- Exclude Dino (`PLDINPL00011`) from 2024-04-11 through 2024-04-18 inclusive,
  and separately summarize that window's paired contribution.
- Security concentration: remove each security in turn for principal IC/spread
  results and report the maximum absolute shift and identity; also report the
  top five securities by absolute paired label-difference contribution.
- Session concentration: report the top ten absolute session-statistic
  contributions and results after removing the top 1% of absolute sessions.
- Large old/new differences: repeat paired conclusions after excluding the top
  1% of absolute paired label differences within each anchor/horizon.
- Source-switch and cash-dividend-gap concentration are checked only from
  existing fields/evidence or small bounded date summaries. They do not trigger
  new corporate-action research.
- Confirmation diagnostics that require substantial new infrastructure are
  marked `NOT RUN`, with the unproven claim and confidence effect stated.

## Bounded economic-plausibility screen

Only a primary hypothesis that passes the directional screen below receives an
implementability screen. Use its predefined Q5-Q1 selection or, for the
volatility filter, the predefined Q4-Q5 avoidance spread; proximity may also use
the frozen strongest-momentum/proximity 3x3 contrast only if the incremental
partial result passes independently. Use every non-overlapping offset.

Gross spread is the equal-weight decision-aligned open-to-open selection spread.
Name turnover per rebalance is one half of the sum of absolute equal-weight
changes on each leg; long and short/filter legs are added. Approximate net spread
is gross spread minus turnover times 25 bps per traded notional (10 bps
commission plus 15 bps slippage). Break-even cost is gross spread divided by
turnover, in bps. No cash ledger, fills, sizing optimization, or portfolio test
is constructed.

## Frozen decision rule

A primary hypothesis passes only if all apply:

1. Expected-sign new-panel common-period mean IC (partial IC for proximity) and
   expected-sign open-to-open predefined spread/filter contrast occur at at
   least three of four horizons, including 10 or 20 sessions.
2. At least one of those 10/20-session principal statistics has a 95% HAC or
   bootstrap interval excluding zero in the expected direction after the point
   estimate survives the frozen BH family at `q <= 0.10`; inference is
   supportive, not standalone proof.
3. The fixed quantile/conditional profile is directionally coherent: profile
   Spearman has the expected sign and the predefined tail contrast has the
   expected sign at the principal horizon. For volatility, Q5 must be worse than
   Q4 and the average of Q1-Q4.
4. Expected direction survives every leave-one-full-year-out result, removal of
   Dino's window, removal of the top 1% absolute sessions, and removal of the top
   1% old/new label differences; no single security changes the sign.
5. The conclusion exists in the common period, not only the added interval. A
   proximity conclusion must agree across both definitions; otherwise it is
   definition-sensitive and cannot pass. A conclusion confined to one anchor
   or only one horizon cannot pass.
6. The non-overlapping open-to-open gross effect is positive in a majority of
   offsets and its aggregate approximate break-even cost is at least 25 bps per
   traded notional.

Exactly one gate recommendation follows:

- `CONTINUE TO A BOUNDED STRATEGY TEST` if at least one primary hypothesis
  passes all six conditions; name the exact frozen signal, but do not test it.
- `RESEARCH INCONCLUSIVE — DEFER ENGINEERING` if none passes but a primary is
  directionally coherent and fails only for material basis, period, definition,
  anchor, horizon, uncertainty, or bounded plausibility sensitivity; state one
  smallest next research question.
- `STOP OR DESCOPE THIS RESEARCH LINE` otherwise, explicitly declining more
  infrastructure on current evidence.

Mandatory correctness failures (input/hash mismatch, non-60 official
denominator, timing leakage, invalid pairing, missing required core output, or
failed immutable reproduction) fail closed and prevent a positive gate.
