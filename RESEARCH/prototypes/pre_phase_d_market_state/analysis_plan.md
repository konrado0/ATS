# Pre-Phase-D market-state diagnostic: frozen analysis plan

## Freeze and scope

This plan is frozen on 2026-08-30 before any market-state value, drawdown
episode, state tercile, conditional return, or association result is calculated.
The run is descriptive research only. It does not implement Phase D, train a
model, alter Phase C, rerun the accepted v4 strategy, construct a regime-timing
strategy, select a market-state variable, or optimize a lookback, threshold,
combination, benchmark, portfolio, or ON/OFF rule.

After result inspection, this plan and `config.json` may change only in a new
version that identifies and demonstrates an implementation bug. Weak or strong
results do not authorize a change.

## Pinned inputs

All paths and physical SHA-256 values are listed in `config.json`. Controlling
inputs are the accepted Phase A WIG artifact, current local WIG source, pinned
split-normalized candidate panel, accepted Phase A v2 adapted panel, accepted
v4 composite NAV and their manifests. The three owner documents are pinned as
interpretive inputs. No `latest` pointer is permitted.

The controlling diagnostic period is the accepted v4 common-period start,
2020-11-27, through the final decision session having the exact accepted
`label__open_to_open__20`. The accepted v4 composite NAV is read, never rebuilt.

## Timing and WIG validation

Every state value attached to decision session `t` is calculated only through
the immediately preceding WIG information session `t-1`. The output records
both dates and requires `information_session < decision_session` without an
exception. The accepted next-open/20-session Phase A v2 timing is unchanged.

Parse the exact pinned Stooq WIG source as daily OHLCV. Require the documented
schema, one WIG record per date, strictly increasing unique dates, finite
positive OHLC, `high >= max(open, close, low)`, `low <= min(open, close, high)`,
and nonnegative volume. Require every accepted-artifact date and every candidate
panel official session to exist in WIG through 2026-08-18. Reconcile all OHLCV
values on the overlap to the accepted WIG artifact with exact date equality and
`rtol=1e-12, atol=1e-8`; any unexplained difference fails closed. Publish the
validated table only inside this research run.

## Frozen numerical market-state block

Let `C_t` be WIG close and `r_t = log(C_t/C_{t-1})`. All expressions below are
evaluated on information session `t`, then attached to decision session `t+1`.

1. `wig_log_return_20 = log(C_t/C_{t-20})` (21 exact WIG closes).
2. `wig_log_return_60 = log(C_t/C_{t-60})` (61 exact WIG closes).
3. `wig_trend_200 = C_t / mean(C_{t-199:t}) - 1`, preserving accepted Phase A.
4. `wig_trend_acceleration_20_60 = wig_log_return_20/20 - wig_log_return_60/60`.
5. `wig_drawdown_252 = C_t / max(C_{t-251:t}) - 1`.
6. `wig_downside_semivolatility_20 = sqrt(mean(min(r,0)^2))*sqrt(252)` over
   the exact 20 returns ending at `t`.
7. `wig_volatility_ratio_20_60 = std(r[-20:], ddof=1) / std(r[-60:], ddof=1)`;
   zero long volatility yields missing state `zero_long_volatility`.
8. `top60_breadth_positive_60` is positive exact 60-session split-adjusted
   member log returns divided by usable member count, never by treating missing
   members as nonpositive. Official denominator 60 and excluded states remain.
9. `top60_breadth_change_10` is item 8 at `t` minus the independently valid
   item 8 value at `t-10` using each date's PIT membership.
10. `top60_return_dispersion_20` is sample standard deviation (`ddof=1`) of
    usable exact 20-session split-adjusted member log returns.
11. `top60_average_pairwise_correlation_60` is the arithmetic mean of all
    off-diagonal Pearson correlations among usable members' exact vectors of 60
    daily split-adjusted log returns.
12. `top60_positive_leadership_share_20` is the sum of the largest 12 positive
    exact 20-session member log returns divided by the sum of all positive
    usable 20-session member log returns. If the positive sum is zero it is
    missing state `no_positive_leadership_denominator`.

TOP60 calculations use only the pinned candidate panel, split-adjusted prices,
and official PIT members on the information session. A member is usable for a
lookback only with finite positive closes at every required WIG session; no
forward fill or substitution is allowed. Each output records official
denominator 60, usable count, excluded count, and a deterministic pipe-separated
`isin:state` list. General cross-sectional validity requires at least 45/60
usable members. Correlation additionally requires 45 exact return vectors, all
pair variances positive, and all `n*(n-1)/2` correlations finite. Leadership
requires 45 exact 20-session returns and a positive denominator. Failure is
retained as NOT PROVEN for that value; it does not expand the task.

The optional supplement is `top60_share_within_5pct_high_252`: usable members
whose information-session close is at least 95% of their exact trailing
252-session maximum close, divided by usable count, with the same 45/60 gate.
It cannot select or modify the block.

## Frozen feature validity gate

A feature passes causality and coverage when it has zero timing violations,
zero denominator violations, zero unavailable-as-negative violations, and valid
values on at least 90% of controlling decision sessions after its maximum
lookback becomes available. Correlation and leadership may be NOT PROVEN under
their separate gates. A variable is removed only for demonstrated causality,
coverage, definition, or mechanical-duplication failure. Mechanical duplication
means bitwise-identical valid-value/missingness vectors or absolute Pearson
correlation 1 within `1e-12` plus an algebraically redundant definition.

## Accepted-Q5 episode attribution

Use the accepted v4 common composite NAV for Q5 and its eligible-universe
benchmark. A drawdown episode starts at the last running-maximum peak preceding
an underwater run, reaches its minimum at the first minimum NAV, and recovers at
the first later NAV at or above the peak. Unrecovered episodes end at the final
NAV date and retain a null recovery. Rank distinct episodes by peak-to-trough
loss, then peak date; take the four deepest Q5 episodes. Repeat independently on
relative wealth `Q5 NAV / benchmark NAV` and take the three deepest episodes.

For every selected episode report the first available state record at the exact
requested session positions: peak-20, peak, peak+5, peak+10, peak+20, trough,
trough+20 and recovery. Out-of-range or absent recovery remains explicit. Report
Q5, benchmark, and relative peak-to-trough loss for each episode.

For descriptive warning classification, transform every feature to an adverse
full-sample percentile. Adverse is low for WIG 20/60 return, trend, acceleration,
drawdown, breadth, breadth change, and the optional high share; adverse is high
for downside semivolatility, volatility ratio, dispersion, correlation, and
leadership concentration. `leading` means adverse percentile >=2/3 first at
peak-20; `early-contemporaneous` means the first crossing is peak through
peak+5; `late` means first crossing is peak+10 through trough; otherwise the
variable is `uninformative`. Recovery values are descriptive and do not alter
classification. Every uninformative episode-variable pair is retained.

## Frozen conditional proximity diagnostics

Use unchanged `proximity_to_max_high_252` and
`label__open_to_open__20` on `split_adjusted_price_return`. Recreate average tie
ranks and quintiles within each official decision-session cross-section exactly
as accepted; Q5 is the highest proximity quintile. Eligible-universe mean uses
the identical eligible rows. Missing labels/features are excluded but reported;
official denominator remains 60.

For each valid numerical market-state variable independently, assign full-sample
descriptive terciles by average rank across controlling decision sessions:
T1 <= 1/3, T2 <= 2/3, T3 > 2/3. These terciles are diagnostic labels, not PIT
features and are not carried to Phase D. Report all variables and all terciles;
no strongest variable or tercile is selected.

Per state-variable/tercile report session-level Spearman proximity rank IC; Q5
constituent mean forward return; Q5 minus same-session eligible-universe mean;
fixed label frequencies <=-5% and <=-10%; downside quantiles min/p01/p05/p10/p25
and conditional means below -5% and -10%; session, row, denominator, usable,
label-available, and excluded-state coverage. Report the same central metrics by
calendar year and by all 20 fixed non-overlapping offsets, where offset is the
zero-based ordinal of the controlling WIG decision session modulo 20.

Drawdown contribution is not a filtered backtest: for each selected absolute Q5
drawdown window, attribute accepted composite Q5 negative log-return magnitude
and total log return to the state tercile observed on each NAV date. Preserve
benchmark and relative contributions beside Q5.

Uncertainty uses a deterministic moving-block bootstrap over ordered session
aggregates, block length 20, 1,000 samples, seed 20260830. Blocks are sampled
with replacement from all non-circular contiguous 20-session starts and
concatenated/truncated to the original session count. Report percentile 95%
intervals for mean IC, Q5 mean return, and Q5-minus-eligible mean return.

## Interpretation and verdict gates

A state variable has a fixed conditional-heterogeneity flag if the T3-minus-T1
difference has a 95% block interval excluding zero and absolute magnitude at
least 0.02 IC or 0.50 percentage points Q5-minus-eligible return. This symmetric
diagnostic does not select a direction, variable, or trading rule.

`MARKET-STATE ASSOCIATION SUPPORTED` requires at least half of all valid block
variables to flag and at least half of selected episodes to contain a leading or
early-contemporaneous warning. `MIXED` requires at least one flag or one useful
episode warning but does not satisfy both support conditions, or has material
counterexamples. `NOT SUPPORTED` requires no flag and no useful episode warning.
`NOT PROVEN` applies if WIG validity, causality, or reproducibility fails.

Final separate gates are:

- WIG extension/input validity: PASS only if every frozen validation passes.
- Market-state feature causality and coverage: PASS only if every retained block
  variable passes; FAIL for causality/definition breach; otherwise NOT PROVEN.
- Q5 drawdown attribution: SUPPORTED under both support conditions above;
  MIXED for partial/inconsistent warnings; NOT SUPPORTED for none; NOT PROVEN if
  episode or state data are invalid.
- Frozen block: READY if all 12 predefined variables pass; READY WITH CAVEATS if
  only correlation/leadership is NOT PROVEN or documented input caveats remain;
  NOT READY for other failures.
- Safe to proceed to Phase D0/D1: YES only if WIG is PASS, causality/coverage is
  PASS, block is READY or READY WITH CAVEATS, and deterministic reproduction
  matches. Association strength is not a prerequisite.

The report must preserve counterexamples and interpretation limits: descriptive
association is not a causal mechanism, regime-timing rule, deployable alpha,
total return, or evidence from genuinely untouched history.

## Outputs and reproduction

Primary immutable run:
`D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1`.
Deterministic reproduction:
`D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v1-reproduction`.
Both retain exact commands, environment/Git state, code and input hashes,
machine-readable features, exclusions, episodes, conditional diagnostics,
uncertainty, validity gates, manifest and logical payload hash. The primary and
reproduction logical hashes must match before a YES verdict.
